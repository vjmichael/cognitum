"""MEL-06A offline reference turn. No Lu registration or model-granted authority.

Caller owns the scope, allowed routes, checkpoint, tolerance and worker grants.
Model supplies one closed JSON request only. Independent verification precedes
feedback; refusals carry no numeric payload. This is deliberately a one-call
reference, not a production agent or a general-purpose authorization system.
"""
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import math
from . import admission as a, discovery as d, native as n, engines as e, engines_pb2 as ep
from . import model_engines as m, verification as v, verified_graph as vg, uncertainty as u, exchange as x
from .engine_limits import HdcLimits, KanLimits
from . import polynomial_kan as pk, polynomial_model as pm
from cognitum.registry import Registry
from cognitum.runtime import Runtime

OPS = tuple(sorted((*n.OP,*e.OPERATIONS)))
NAMES = {op:next((name for name, value in n.PUBLIC.items() if value==op), 'mel_'+op.replace('.','_')) for op in OPS}
ALL_OPS=(*OPS,pk.OP)

def name_for(op):return pm.PUBLIC if op==pk.OP else NAMES[op]

MAX_REPLY = 8192
MAX_FEEDBACK = 65536


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def parse_request(raw):
    n.need(type(raw) is str and 0<len(raw)<=MAX_REPLY,'model reply limit')
    value=d.strict_json(raw); d.fields(value, ('tool','arguments'))
    n.need(type(value['tool']) is str and type(value['arguments']) is dict,'closed model request')
    return value['tool'],canonical(value['arguments'])


def interval_wire(bounds):
    # Exact rational audit retained separately. Decimal display is outward
    # rounded binary64, never narrower than the independent rational bound.
    lo,hi=float(bounds.lo),float(bounds.hi)
    n.need(math.isfinite(lo) and math.isfinite(hi),'display range')
    if Fraction(lo)>bounds.lo:lo=math.nextafter(lo,-math.inf)
    if Fraction(hi)<bounds.hi:hi=math.nextafter(hi,math.inf)
    return {'lower':lo,'upper':hi}


def refusal(code):return {'ok':False,'error':code,'result':None}


def verified_feedback(scope,call,receipt,tolerances,approval=None):
    """Trusted retained receipt only; caller never accepts receipt from model JSON."""
    if call.operation==pk.OP:
        n.need(type(tolerances) is tuple and len(tolerances)==1,'polynomial host tolerance')
        return pm.feedback(scope,call,receipt,approval,tolerances[0])
    if receipt.status!='completed':return refusal(receipt.status),None
    checked,_,_=x._checked_receipt(scope,call,receipt)
    audit={'scope':{'session':scope.session,'workspace':scope.workspace,'subject':scope.subject,'turn':scope.turn},
           'operation':call.operation,'request_sha256':receipt.request_sha256,'result_sha256':receipt.result_sha256,
           'descriptor_sha256':receipt.descriptor_sha256,'request_hex':(call.wire() if type(call) is n.NativeCall else call.wire).hex(),
           'result_hex':receipt.result_frame.hex(),'tolerance':tolerances}
    if call.operation in n.OP:
        cert=v.certify_vfa(scope,call,receipt,tolerances)
        verdict=v.replay(scope,call,receipt,cert,absolute_tolerance=tolerances)
        audit['certificate_hex']=cert.wire.hex();audit['verdict']=str(verdict)
        if verdict!=v.pb.WITHIN_TOLERANCE:return refusal('verification_refused'),audit
        msg=cert.message();values=[z.observed for z in msg.components]
        bounds=[u.Interval(Fraction(z.lower),Fraction(z.upper)) for z in msg.components]
        # Fraction accepts decimal/scientific string representations exactly.
        shape=list(msg.shape);units=[{'numerator':z.numerator,'denominator':z.denominator} for z in msg.units]
        result={'values':values,'shape':shape,'units':units,'intervals':[interval_wire(b) for b in bounds]}
        assurance='represented_input_enclosure';audit['bounds']=[(str(b.lo),str(b.hi)) for b in bounds]
    elif call.operation=='kan.evaluate':
        n.need(type(approval) is m.Approval and m.matches(call,approval),'pinned checkpoint mismatch')
        rows,status=vg.kan_certificate(scope,call,receipt,tolerances)
        again,status2=vg.kan_certificate(scope,call,receipt,tolerances)
        n.need(rows==again and status==status2,'KAN replay mismatch')
        bounds=[b for row in rows for b in row];audit['bounds']=[(str(b.lo),str(b.hi)) for b in bounds];audit['verdict']=list(status)
        if any(z!='within' for z in status):return refusal('verification_refused'),audit
        r=ep.EngineResult.FromString(checked).kan
        result={'values':list(r.values),'shape':[r.rows,r.columns],'intervals':[interval_wire(b) for b in bounds],'checkpoint_sha256':approval.checkpoint.identity}
        assurance='represented_input_enclosure'
    else:
        cert=v.certify_hdc(scope,call,receipt);v.replay(scope,call,receipt,cert)
        audit['certificate_hex']=cert.wire.hex();audit['verdict']='exact_submitted_bits'
        result=m.feedback(call,None,receipt)['result'];assurance='exact_submitted_bits'
        result={k:val for k,val in result.items() if k in ('bits','hamming_distance','best_index')}
    result['assurance']=assurance
    result['limitations']=['submitted_objects_only','no_learned_target_or_semantic_probability','bounds_are_not_worker_rounding_model'] if assurance!='exact_submitted_bits' else ['submitted_bits_only','not_semantic_probability']
    # Record exact input/result hashes so the model cannot substitute a receipt.
    result['request_sha256']=receipt.request_sha256;result['result_sha256']=receipt.result_sha256
    out={'ok':True,'tool':NAMES[call.operation],'result':result}
    n.need(len(canonical(out))<=MAX_FEEDBACK,'feedback limit')
    return out,audit


@dataclass(frozen=True,slots=True)
class Allowed:
    operations: tuple
    approval: m.Approval | None = None
    tolerance: float = 1e-5
    polynomial_approval: pk.Approval | None = None
    def __post_init__(self):
        n.need(type(self.operations) is tuple and len(self.operations)<=len(ALL_OPS) and len(set(self.operations))==len(self.operations) and all(op in ALL_OPS for op in self.operations),'explicit allowlist')
        n.need((type(self.approval) is m.Approval)==('kan.evaluate' in self.operations),'explicit approved KAN checkpoint')
        n.need(type(self.polynomial_approval) is pk.Approval if pk.OP in self.operations else self.polynomial_approval is None,'explicit approved polynomial checkpoint')
        n.need(type(self.tolerance) is float and math.isfinite(self.tolerance) and 0<=self.tolerance<=(1e-6 if pk.OP in self.operations else 1e-3),'host tolerance')


class ReferenceTurn:
    def __init__(self,scope,allowed):
        n.need(type(scope) is a.Scope and type(allowed) is Allowed,'trusted scope and policy')
        self.scope=scope;self.allowed=allowed;self.attempted=False;self.audit=None;self.last_call=None;self.last_receipt=None
        self.registry=Registry();self.registry.install(n.NativeVFAPlugin,enabled=True);self.registry.install(e.EnginePlugin,enabled=True)
        poly=pk.OP in allowed.operations
        if poly:self.registry.install(pk.PolynomialPlugin,enabled=True)
        for op in allowed.operations:self.registry.nominate(op,n.NAME if op in n.OP else pk.NAME if op==pk.OP else e.NAME)
        self.host=a.Admission(Runtime(self.registry),scope.session,enable_engines=True,enable_model_codecs=True,enable_polynomial_kan=poly,enable_polynomial_model_codecs=poly)
        self.grants={};self.offers={}
        try:
            if allowed.approval:
                cp=allowed.approval.checkpoint;self.host.approve_checkpoint(scope,cp.wire,expected_sha256=cp.identity,review_id=allowed.approval.review_id)
            if poly:
                cp=allowed.polynomial_approval.checkpoint;self.host.approve_polynomial_checkpoint(scope,cp.wire,expected_sha256=cp.identity,review_id=allowed.polynomial_approval.review_id)
            for op in allowed.operations:
                route=next(r for r in a.routes(include_engines=True,include_polynomial_kan=poly) if r.operation==op)
                limits=a.Limits(timeout_ms=10000) if op in n.OP else (KanLimits if op=='kan.evaluate' else HdcLimits)(timeout_ms=10000)
                kw={} if op in n.OP else {'model_codec':True,'checkpoint_sha256':allowed.approval.checkpoint.identity if op=='kan.evaluate' else None}
                if op==pk.OP:
                    limits=pk.Limits(timeout_ms=10000);kw=dict(model_codec=True,checkpoint_sha256=allowed.polynomial_approval.checkpoint.identity,model_tolerance=allowed.tolerance)
                token=self.host.issue(scope,route,limits,ttl_ms=60000,**kw);self.grants[route.public_name]=token
                offer=self.host.discover(scope,token) if op in n.OP else self.host.discover_model(scope,token)['tool_schema']
                self.offers[route.public_name]=offer
        except BaseException:
            self.host.close();raise

    def schemas(self):return json.loads(canonical(list(self.offers.values())))
    def close(self):self.host.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()

    def dispatch(self,raw):
        if self.attempted:return refusal('turn_attempt_limit')
        self.attempted=True
        try:
            name,args=parse_request(raw)
            if name not in self.grants:return refusal('not_authorized')
            token=self.grants[name];op=next(op for op in ALL_OPS if name_for(op)==name)
            rid='mel06-call';s=self.scope;approval=self.allowed.approval if op=='kan.evaluate' else self.allowed.polynomial_approval if op==pk.OP else None
            if op in n.OP:
                current=self.host.discover(s,token);n.need(current==self.offers[name],'descriptor changed')
                call=n.bind_model(self.registry,((name,n.descriptor(name)[0]),),name,args,request_id=rid,correlation_id=s.turn)
                wire=call.wire();cols=call.points.message().body.shape[1] if op=='vfa.gradient' else 1
            elif op==pk.OP:
                current=self.host.discover_model(s,token);n.need(current==pm.offer(approval,self.allowed.tolerance) and current['tool_schema']==self.offers[name],'polynomial descriptor changed')
                call=pm.bind(approval,self.allowed.tolerance,args,rid,s.turn);wire=call.wire;cols=1
            else:
                current=self.host.discover_model(s,token);n.need(current['tool_schema']==self.offers[name] and current['codec_sha256']==m.descriptor(op)[0],'descriptor changed')
                call=m.bind(op,approval,args,rid,s.turn);wire=call.wire;cols=call.message.kan.layers[-1].outputs if op=='kan.evaluate' else 0
            self.last_call=call
            receipt=self.host.execute(s,token,rid,wire,timeout_ms=10000);self.last_receipt=receipt
            out,self.audit=verified_feedback(s,call,receipt,(self.allowed.tolerance,)*cols,approval)
            return out
        except (ValueError, ArithmeticError, OverflowError, RuntimeError, TypeError):
            self.audit=None;return refusal('invalid_or_unverified')


def bound_decision(interval,threshold):
    """Decision on the conservative displayed enclosure, not a rounded sample."""
    n.need(type(interval) is dict and set(interval)=={'lower','upper'},'interval shape')
    lo,hi=interval['lower'],interval['upper']
    n.need(all(type(x) in (float,int) and math.isfinite(x) for x in (lo,hi,threshold)) and lo<=hi,'finite ordered threshold interval')
    return 'above' if lo>=threshold else 'below' if hi<threshold else 'uncertain'


def intent_matches(raw,operation,arguments):
    """Only for an independently supplied, trusted *typed* reference intent.

    No general natural-language intent classifier; no argument repair. Existing
    codecs still validate every allowed request, including numeric types.
    """
    try:
        name,encoded=parse_request(raw)
        return name==name_for(operation) and json.loads(encoded)==arguments
    except (KeyError,ValueError,TypeError):return False


def expected_answer(feedback,operation,threshold=None):
    n.need(type(feedback) is dict and feedback.get('ok') is True and feedback.get('tool')==name_for(operation),'verified result required')
    result=feedback['result']
    if operation=='hdc.query':
        n.need(threshold is None and result['assurance']=='exact_submitted_bits','exact HDC query required')
        return result['best_index']
    if operation=='hdc.bind':
        n.need(threshold is None and result['assurance']=='exact_submitted_bits','exact HDC binding required')
        return result['bits']
    n.need(threshold is not None and result['assurance']=='represented_input_enclosure' and len(result['intervals'])==1,'scalar verified threshold required')
    return bound_decision(result['intervals'][0],threshold)


def publish_checked(raw_final,feedback,*,matched_intent,operation,threshold=None):
    """Narrow reference answer gate, not a natural-language fact checker.

    Feedback is trusted host output retained by the caller. Never invoke with
    feedback, expected intent, or threshold provided by the model itself.
    """
    if matched_intent is not True:return refusal('intent_mismatch')
    try:
        predicted=d.strict_json(raw_final);d.fields(predicted,('answer',))
        expected=expected_answer(feedback,operation,threshold)
        if canonical(predicted['answer'])!=canonical(expected):return refusal('interpretation_mismatch')
        return {'ok':True,'answer':predicted['answer']}
    except (ValueError,TypeError,KeyError):return refusal('unverified_answer')
