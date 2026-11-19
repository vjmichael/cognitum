"""MEL-06A-R1: typed host intent and receipt-bound answer publication.

Reference only: a trusted caller supplies the intent independently of the model.
No natural-language intent extraction, no authority from digests, no Lu changes.
"""
from dataclasses import dataclass
import hashlib
import math
import json
from fractions import Fraction
from threading import RLock
from . import model_reference as r, admission as a, native as n, model_engines as m, discovery as d


def _equal(a,b):
    # Compare represented JSON numbers, not Python's bool/int equivalence.
    if type(a) in (int,float) and type(b) in (int,float):
        return math.isfinite(a) and math.isfinite(b) and Fraction(a)==Fraction(b)
    if type(a) is not type(b):return False
    if type(a) is dict:return a.keys()==b.keys() and all(_equal(a[k],b[k]) for k in a)
    if type(a) is list:return len(a)==len(b) and all(_equal(x,y) for x,y in zip(a,b))
    return a==b


def digest(value):return hashlib.sha256(r.canonical(value).encode('ascii')).hexdigest()


@dataclass(frozen=True,slots=True)
class Intent:
    scope: a.Scope
    operation: str
    arguments: str
    threshold: float | None = None
    checkpoint: str | None = None
    component: int = 0
    def __post_init__(self):
        n.need(type(self.scope) is a.Scope and self.operation in r.OPS,'typed scope and operation')
        n.need(type(self.arguments) is str and len(self.arguments)<=r.MAX_REPLY,'intent argument budget')
        args=d.strict_json(self.arguments)
        n.need(type(args) is dict and self.arguments==r.canonical(args),'canonical intent arguments')
        numeric=self.operation in ('kan.evaluate',*n.OP)
        n.need(type(self.component) is int and 0<=self.component<128,'component budget')
        n.need((type(self.threshold) is float and math.isfinite(self.threshold)) if numeric else self.threshold is None and self.component==0,'threshold contract')
        n.need((type(self.checkpoint) is str and len(self.checkpoint)==64 and all(c in '0123456789abcdef' for c in self.checkpoint)) if self.operation=='kan.evaluate' else self.checkpoint is None,'checkpoint identity')
    @property
    def identity(self):
        return digest({'scope':[self.scope.session,self.scope.workspace,self.scope.subject,self.scope.turn], 'op':self.operation,'arguments':self.arguments,'threshold':self.threshold,'checkpoint':self.checkpoint,'component':self.component})
    def matches(self,raw):
        try:
            name,args=r.parse_request(raw)
            return name==r.NAMES[self.operation] and _equal(d.strict_json(args),d.strict_json(self.arguments))
        except (ValueError,TypeError,OverflowError,KeyError):return False


def _projection(intent,feedback):
    n.need(feedback.get('ok') is True and feedback.get('tool')==r.NAMES[intent.operation],'verified feedback required')
    result=feedback['result']
    if intent.operation in ('hdc.query','hdc.bind'):
        ans=r.expected_answer(feedback,intent.operation)
        data={k:result[k] for k in ('bits','hamming_distance','best_index') if k in result}
        data['assurance']=result['assurance'];return ans,data
    n.need(result['assurance']=='represented_input_enclosure' and intent.component<len(result['intervals']),'verified component')
    if intent.checkpoint is not None:n.need(result.get('checkpoint_sha256')==intent.checkpoint,'checkpoint drift')
    z=result['intervals'][intent.component];t=intent.threshold
    # The published binary64 display encloses the exact rational interval.
    # Only these comparisons are used, never the rounded worker observation.
    decision=r.bound_decision(z,t)
    return decision,{'interval':z,'threshold':t,'component':intent.component,
                     'lower_ge_threshold':z['lower']>=t,'upper_lt_threshold':z['upper']<t,
                     'assurance':result['assurance'],'limitations':result['limitations']}


class BoundTurn:
    """One host-owned turn. Neither claimed feedback nor matched-intent flag enters publish()."""
    def __init__(self,intent,allowed):
        n.need(type(intent) is Intent and type(allowed) is r.Allowed,'trusted intent and allowlist')
        n.need(intent.operation in allowed.operations,'intent not allowed')
        if intent.checkpoint is not None:n.need(allowed.approval.checkpoint.identity==intent.checkpoint,'intent checkpoint drift')
        self.intent=intent;self.allowed=allowed;self.turn=r.ReferenceTurn(intent.scope,allowed)
        self._attempt=False;self._published=False;self._closed=False;self._evidence=None;self.audit=None
        self._state_lock=RLock()
        try:
            op=intent.operation;call=self._bind(intent.arguments)
            if op in n.OP:
                rows,cols=call.points.message().body.shape
                count=rows*(cols if op=='vfa.gradient' else 1)
                self._expected_wire=call.wire()
            else:
                self._expected_wire=call.wire
                count=call.message.kan.rows*call.message.kan.layers[-1].outputs if op=='kan.evaluate' else 1
            n.need(intent.component<count,'component absent from approved intent')
        except BaseException:
            self.close();raise
    def _bind(self,args):
        op=self.intent.operation;name=r.NAMES[op];rid='mel06-call';scope=self.intent.scope
        if op in n.OP:
            return n.bind_model(self.turn.registry,((name,n.descriptor(name)[0]),),name,args,request_id=rid,correlation_id=scope.turn)
        return m.bind(op,self.allowed.approval if op=='kan.evaluate' else None,args,rid,scope.turn)
    @staticmethod
    def _wire(call):return call.wire() if call.operation in n.OP else call.wire
    def schemas(self):return self.turn.schemas()
    def __enter__(self):return self
    def __exit__(self,*_):self.close()
    def close(self):
        # Close the actual host first so in-flight execution can be suppressed.
        self.turn.close()
        with self._state_lock:self._closed=True
    @property
    def worker_calls(self):return len(self.turn.host._seen)
    def dispatch(self,raw):
        with self._state_lock:
            if self._closed or self._attempt or self._published:return r.refusal('turn_attempt_limit')
            self._attempt=True
        if not self.intent.matches(raw):return r.refusal('intent_mismatch')
        try:
            _,args=r.parse_request(raw)
            n.need(self._wire(self._bind(args))==self._expected_wire,'typed input mismatch')
        except (ValueError,TypeError,ArithmeticError,KeyError,RuntimeError):return r.refusal('intent_mismatch')
        out=self.turn.dispatch(raw)
        if not out['ok']:return out
        try:
            checked,audit=self._replay()
            n.need(r.canonical(checked)==r.canonical(out),'feedback drift')
            ans,projection=_projection(self.intent,checked)
            with self._state_lock:
                n.need(not self._closed and not self._published,'turn no longer open')
                self._evidence=r.canonical({'intent_sha256':self.intent.identity,'request_sha256':audit['request_sha256'],'result_sha256':audit['result_sha256'],'projection':projection,'answer':ans})
                self.audit=json.loads(r.canonical(audit))
            return {'ok':True,'tool':out['tool'],'projection':json.loads(r.canonical(projection)),'intent_sha256':self.intent.identity,'evidence_sha256':hashlib.sha256(self._evidence.encode('ascii')).hexdigest()}
        except (ValueError,TypeError,ArithmeticError,KeyError,RuntimeError):return r.refusal('verification_refused')
    def _replay(self):
        call=self.turn.last_call;receipt=self.turn.last_receipt
        n.need(call is not None and receipt is not None and call.operation==self.intent.operation,'missing retained call')
        op=call.operation
        wire=self._wire(call)
        n.need(wire==self._expected_wire,'typed request does not match approved intent')
        cols=call.points.message().body.shape[1] if op=='vfa.gradient' else (call.message.kan.layers[-1].outputs if op=='kan.evaluate' else (1 if op in n.OP else 0))
        return r.verified_feedback(self.intent.scope,call,receipt,(self.allowed.tolerance,)*cols,self.allowed.approval if op=='kan.evaluate' else None)
    def publish(self,raw,*,host_fallback=False):
        n.need(type(host_fallback) is bool,'trusted fallback policy')
        with self._state_lock:
            if self._closed or self._published:return r.refusal('publication_attempt_limit')
            self._published=True
            if self._evidence is None:return r.refusal('no_verified_result')
        try:
            # Prevent publication after revocation, expiry or session closure.
            host=self.turn.host;token=self.turn.grants[r.NAMES[self.intent.operation]]
            with host._lock:
                n.need(host._live(host._grant(self.intent.scope,token),self.intent.scope),'grant no longer live')
            checked,audit=self._replay();ans,projection=_projection(self.intent,checked)
            expected=r.canonical({'intent_sha256':self.intent.identity,'request_sha256':audit['request_sha256'],'result_sha256':audit['result_sha256'],'projection':projection,'answer':ans})
            n.need(expected==self._evidence,'retained evidence drift')
            try:
                n.need(type(raw) is str and len(raw)<=r.MAX_REPLY,'answer budget')
                obj=d.strict_json(raw);d.fields(obj,('answer',));correct=r.canonical(obj['answer'])==r.canonical(ans)
            except (ValueError,TypeError,KeyError):correct=False
            if not correct and not host_fallback:return r.refusal('interpretation_mismatch')
            # Explicit deterministic fallback is separately measured, never scored as model success.
            with host._lock:
                n.need(host._live(host._grant(self.intent.scope,token),self.intent.scope),'grant no longer live')
                return {'ok':True,'answer':ans,'source':'model_verified' if correct else 'host_verified_fallback','intent_sha256':self.intent.identity,'request_sha256':audit['request_sha256'],'result_sha256':audit['result_sha256'],'evidence_sha256':hashlib.sha256(expected.encode('ascii')).hexdigest()}
        except (ValueError,TypeError,KeyError,ArithmeticError,RuntimeError):return r.refusal('unverified_answer')
