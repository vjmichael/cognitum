"""Scoped tensor and exact symbolic cooperation over the existing reference Runtime.
Trusted host API only; no installed Lu authority, model registration or OS sandbox.
No mutation of existing MEL admission/catalog/graph contracts.
"""
from dataclasses import dataclass
from fractions import Fraction as Q
from hashlib import sha256
from math import prod
from threading import RLock
from time import monotonic_ns
import json,re,secrets
from cognitum.contracts import Manifest,Operation,Shape,Request,HostContext,Response,CONTRACT_VERSION,digest
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from . import tensor_field as f,tensor_field_pb2 as pb

VERSION='1.0.0'; TENSOR='kan.tensor.field'; SYMBOLIC='scientific.tensor.residual'
TNAME='mel_tensor_field_reference'; SNAME='mel_tensor_residual_reference'
TIN=Shape((('checkpoint',4*((f.MAX_FRAME+2)//3)),('request',4*((f.MAX_REQUEST+2)//3))))
TOUT=Shape((('frame',4*((f.MAX_RESULT+2)//3)),))
S_MAX=32768; S_OUT=6144
SIN=Shape((('frame',S_MAX),)); SOUT=Shape((('frame',S_OUT),))
need=f.need
MAX_WORK=2_000_000; MAX_GRANTS=32; MAX_REQUESTS=256; MAX_ACTIVE=4


def rational(s):
    need(type(s) is str and 1<=len(s)<=2400 and re.fullmatch(r'-?(?:0|[1-9][0-9]*)(?:/[1-9][0-9]*)?',s),'bounded rational')
    v=Q(s);need(str(v)==s,'noncanonical rational');return v


def load(s,limit):
    need(type(s) is str and 0<len(s)<=limit and s.isascii(),'bounded JSON')
    try:d=json.loads(s)
    except (ValueError,RecursionError) as e:raise ValueError('invalid JSON') from e
    need(f.canonical(d).decode()==s,'noncanonical JSON');return d


def _stencil(mod,p):
    if mod is f.j:return ((0,0),(2,0),(0,2)),(Q(p.reaction),-Q(p.ax),-Q(p.ay))
    if mod is f.k:return ((0,0),(2,0),(0,1)),(Q(p.reaction),-Q(p.diffusion),Q(1))
    return ((0,0,0),(2,0,0),(0,2,0),(0,0,1)),(Q(p.reaction),-Q(p.ax),-Q(p.ay),Q(1))


def _symbol_input(s):
    d=load(s,S_MAX)
    need(type(d) is dict and set(d)=={'point','weights','values','forcing','inputs','request_id','turn','checkpoint'} and type(d['point']) is list and len(d['point']) in (2,3),'symbolic profile')
    need(all(type(d[k]) is str and f.ID.fullmatch(d[k]) for k in ('request_id','turn')) and type(d['checkpoint']) is str and re.fullmatch('[0-9a-f]{64}',d['checkpoint']),'symbolic request identity')
    point=tuple(map(rational,d['point']));need(all(0<=x<=1 for x in point),'point domain')
    need(all(type(d[k]) is list for k in ('weights','values','forcing','inputs')) and len(d['weights'])==len(d['values'])==len(d['inputs']) and len(d['weights']) in (3,4),'stencil size')
    need(all(type(x) is str and re.fullmatch('[0-9a-f]{64}',x) for x in d['inputs']) and len(set(d['inputs']))==len(d['inputs']),'receipt identities')
    w=tuple(map(rational,d['weights']));v=tuple(map(rational,d['values']));rows={};prev=None
    need(len(d['forcing'])<=125,'forcing budget')
    for row in d['forcing']:
        need(type(row) is list and len(row)==2 and type(row[0]) is list and len(row[0])==len(point),'forcing term')
        e=tuple(row[0]);need(all(type(z) is int and 0<=z<=4 for z in e) and (prev is None or prev<e),'canonical forcing');prev=e
        rows[e]=rational(row[1]);need(rows[e]!=0,'zero term')
    return point,w,v,rows


def _horner(rows,point):
    if not point:return rows.get((),Q(0))
    groups=[{} for _ in range(5)]
    for e,c in rows.items():groups[e[0]][e[1:]]=c
    z=Q(0)
    for g in reversed(groups):z=z*point[0]+_horner(g,point[1:]) if g else z*point[0]
    return z


def symbolic_compute(s):
    x,w,v,rows=_symbol_input(s)
    forcing=_horner(rows,x);lhs=sum((a*b for a,b in zip(w,v)),Q(0))
    out=f.canonical(dict(input_sha256=sha256(s.encode()).hexdigest(),forcing=str(forcing),lhs=str(lhs),residual=str(lhs-forcing))).decode()
    need(len(out)<=S_OUT,'symbolic result budget');return out


def symbolic_replay(s,out):
    x,w,v,rows=_symbol_input(s);d=load(out,S_OUT)
    # Distinct direct monomial evaluation; do not trust the worker's Horner result.
    forcing=sum((c*prod(z**e for z,e in zip(x,powers)) for powers,c in rows.items()),Q(0))
    lhs=Q(0)
    for i in range(len(v)-1,-1,-1):lhs+=w[i]*v[i]
    expected=dict(input_sha256=sha256(s.encode()).hexdigest(),forcing=str(forcing),lhs=str(lhs),residual=str(lhs-forcing))
    need(d==expected,'symbolic replay mismatch');return Q(expected['residual'])


class TensorPlugin:
    def manifest(self):return Manifest(TNAME,VERSION,(Operation(TENSOR,TENSOR,TIN,TOUT,assurance='exact_arithmetic'),),track='research')
    def health(self):return True
    def self_test(self):
        p=f.j.Problem(1,1,0,());m=f.j.Model((),(),(0,)*16);cp=f.export(p,m,f.j.assess(p,m))
        req=f.make_request(cp,pb.POINT,(.5,.5),derivative=(0,0));return pb.Result.FromString(f.execute(cp,req)).exact_value=='0'
    def handle(self,operation,payload):
        need(operation==TENSOR,'operation');TIN.validate(payload)
        return {'frame':f.carrier(f.execute(f.uncarrier(payload['checkpoint']),f.uncarrier(payload['request'])))}


class SymbolicPlugin:
    def manifest(self):return Manifest(SNAME,VERSION,(Operation(SYMBOLIC,SYMBOLIC,SIN,SOUT,assurance='exact_arithmetic'),),track='research')
    def health(self):return True
    def self_test(self):
        s=f.canonical(dict(point=['1/2','1/2'],weights=['1','2','3'],values=['1','2','3'],forcing=[[[1,1],'4']],inputs=['0'*64,'1'*64,'2'*64],request_id='self',turn='self',checkpoint='0'*64)).decode()
        return symbolic_replay(s,symbolic_compute(s))==13
    def handle(self,operation,payload):
        need(operation==SYMBOLIC,'operation');SIN.validate(payload);return {'frame':symbolic_compute(payload['frame'])}


FACTORIES={TENSOR:TensorPlugin,SYMBOLIC:SymbolicPlugin}

def descriptor(op):
    need(op in FACTORIES,'unknown route');m=FACTORIES[op]().manifest().describe()
    d=dict(schema='cognitum.mel.tensor_cooperation.v1',operation=op,manifest_sha256=digest(m),operation_sha256=digest(m['operations'][0]),wire_descriptor=f.DESCRIPTOR.hex(),effect='compute_only',track='research',model_advertised=False,lu_registered=False,execution_authorized=False)
    return digest(d),d


def selection():return tuple((op,descriptor(op)[0]) for op in (TENSOR,SYMBOLIC))


def _entry(reg,op):
    a=reg.resolve(op,allow_research=True);need(a is not None,'route unavailable');e,o=a;d=descriptor(op)[1]
    need(e.factory is FACTORIES[op] and digest(e.manifest.describe())==d['manifest_sha256'] and digest(o.describe())==d['operation_sha256'] and not o.effects and o.deterministic,'route not reviewed');return e


@dataclass(frozen=True,slots=True)
class Scope:
    session:str;workspace:str;subject:str;turn:str
    def __post_init__(self):need(all(type(x) is str and f.ID.fullmatch(x) for x in (self.session,self.workspace,self.subject,self.turn)),'scope identity')

@dataclass(frozen=True,slots=True)
class Limits:
    calls:int=8;work:int=8*MAX_WORK;timeout_ms:int=5000;request_bytes:int=f.MAX_REQUEST;result_bytes:int=f.MAX_RESULT
    def __post_init__(self):need(all(type(v) is int and 1<=v<=hi for v,hi in ((self.calls,16),(self.work,16*MAX_WORK),(self.timeout_ms,10000),(self.request_bytes,f.MAX_REQUEST),(self.result_bytes,f.MAX_RESULT))),'grant limits')

@dataclass(frozen=True,slots=True)
class Approval:
    checkpoint:bytes;review_id:str
    def __post_init__(self):
        need(type(self.review_id) is str and f.ID.fullmatch(self.review_id),'review identity');f.restore(self.checkpoint)
    @property
    def identity(self):return f.digest(self.checkpoint).hex()

@dataclass(slots=True)
class _Grant:
    scope:Scope;approval:Approval;entries:tuple;limits:Limits;expires:int;calls:int;work:int;cooperative:bool;revoked:bool=False

@dataclass(frozen=True,slots=True)
class Receipt:
    scope:Scope;operation:str;descriptor_sha256:str;checkpoint_sha256:str;request_id:str;request_sha256:str;result:bytes
    @property
    def result_sha256(self):return f.digest(self.result).hex()
    @property
    def identity(self):return f.digest(f.canonical(dict(scope=self.scope,operation=self.operation,descriptor=self.descriptor_sha256,checkpoint=self.checkpoint_sha256,request_id=self.request_id,request=self.request_sha256,result=self.result_sha256))).hex()

@dataclass(frozen=True,slots=True)
class Residual:
    scope:Scope;checkpoint_sha256:str;plan_id:str;point:tuple;requests:tuple;field_receipts:tuple;symbolic_request:str;symbolic_receipt:Receipt;exact_residual:str;certified_residual_upper:str


def _bound(cp):
    msg=f.parse(cp,pb.Checkpoint,f.MAX_FRAME);shape=tuple(a.basis_count for a in msg.axes);cells=prod(len(a.interior_knots)+1 for a in msg.axes)
    return min(MAX_WORK,1000+500*cells*prod(shape)) # administrative charge, not a FLOP bound


class Admission:
    """One bounded session; exact checkpoint+descriptor approvals; no ambient grant.
    All computation dispatch uses the existing Runtime. Revocation/cancel discards
    in-flight results; does not claim instantaneous worker kill or durable OS custody.
    """
    def __init__(self,runtime,session,*,enabled=False,reviewed=()):
        need(type(runtime) is Runtime and type(session) is str and f.ID.fullmatch(session) and type(enabled) is bool,'trusted session')
        need(reviewed==(selection() if enabled else ()),'explicit reviewed routes');self.runtime=runtime;self.session=session;self.enabled=enabled;self.lock=RLock();self.approvals={};self.grants={};self.seen=set();self.active={};self.closed=False
    def _scope(self,s):need(type(s) is Scope and s.session==self.session,'session scope')
    def approve(self,s,a):
        self._scope(s);need(self.enabled and type(a) is Approval,'approval disabled')
        with self.lock:
            key=(s,a.identity);need(not self.closed and len(self.approvals)<MAX_GRANTS and key not in self.approvals,'approval capacity or duplicate');self.approvals[key]=a;return a.identity
    def issue(self,s,checkpoint_sha256,limits=Limits(),*,ttl_ms=30000,cooperative=False):
        self._scope(s);need(self.enabled and type(limits) is Limits and type(cooperative) is bool and type(ttl_ms) is int and 1<=ttl_ms<=60000,'grant profile')
        with self.runtime.registry.lock:
            entries=tuple(_entry(self.runtime.registry,op) for op in (TENSOR,SYMBOLIC)[:2 if cooperative else 1])
            with self.lock:
                key=(s,checkpoint_sha256);need(not self.closed and self.approvals.get(key) is not None and len(self.grants)<MAX_GRANTS,'checkpoint not approved or capacity')
                token=secrets.token_bytes(32);need(token not in self.grants,'token collision');self.grants[token]=_Grant(s,self.approvals[key],entries,limits,monotonic_ns()+ttl_ms*1_000_000,limits.calls,limits.work,cooperative);return token
    def _get(self,s,token):
        self._scope(s);need(type(token) is bytes and len(token)==32 and token in self.grants,'unknown grant');g=self.grants[token];need(not self.closed and not g.revoked and g.scope==s and monotonic_ns()<g.expires and self.approvals.get((s,g.approval.identity)) is g.approval,'grant unavailable');return g
    def revoke(self,s,token):
        self._scope(s)
        with self.lock:
            g=self.grants.get(token);need(g is not None and g.scope==s,'grant scope');g.revoked=True
    def revoke_checkpoint(self,s,identity):
        self._scope(s)
        with self.lock:
            # Tombstone approvals remain counted; do not reopen a retired pin.
            need((s,identity) in self.approvals,'unknown checkpoint')
            for g in self.grants.values():
                if g.scope==s and g.approval.identity==identity:g.revoked=True
            self.approvals[(s,identity)]=None
    def cancel(self,s,request_id):
        self._scope(s)
        with self.lock:
            key=(s,request_id);need(key in self.active,'not active');self.active[key]=True
    def close(self):
        with self.lock:self.closed=True
    def _dispatch(self,s,token,op,request_id,raw,payload,charge,verify):
        need(type(request_id) is str and f.ID.fullmatch(request_id),'request identity');key=(s,request_id)
        with self.runtime.registry.lock:
            entry=_entry(self.runtime.registry,op)
            with self.lock:
                g=self._get(s,token);need(op==TENSOR or g.cooperative,'cooperation not granted');need(entry is g.entries[0 if op==TENSOR else 1],'grant route changed')
                need(key not in self.seen and len(self.seen)<MAX_REQUESTS and len(self.active)<MAX_ACTIVE and g.calls>=1 and g.work>=charge,'replay/call/work budget')
                g.calls-=1;g.work-=charge;self.seen.add(key);self.active[key]=False
                deadline=min(g.expires,monotonic_ns()+g.limits.timeout_ms*1_000_000)
            try:
                left=(deadline-monotonic_ns())//1_000_000;need(left>=1,'deadline')
                result=self.runtime.call(Request(request_id,s.turn,op,payload,s.workspace,s.subject,timeout_ms=int(left)),HostContext(s.workspace,s.subject,allow_research=True))
                need(type(result) is Response and result.contract_version==CONTRACT_VERSION and (result.request_id,result.correlation_id,result.operation)==(request_id,s.turn,op) and result.execution_status=='completed' and result.module=={'name':entry.manifest.name,'version':VERSION} and result.assurance=='exact_arithmetic','worker refusal or identity mismatch')
                verified=verify(result.result);need(type(verified) is bytes,'verified output')
                with self.lock:
                    self._get(s,token);need(not self.active[key] and monotonic_ns()<deadline,'cancelled or expired')
                    return Receipt(s,op,descriptor(op)[0],g.approval.identity,request_id,f.digest(raw).hex(),verified)
            finally:
                with self.lock:self.active.pop(key,None)
    def call(self,s,token,request):
        with self.lock:g=self._get(s,token);cp=g.approval.checkpoint;limits=g.limits
        q=f._validate_request(request,cp);need(q.correlation_id==s.turn and len(request)<=limits.request_bytes,'request scope or size')
        def verify(result):
            TOUT.validate(result);raw=f.uncarrier(result['frame']);need(len(raw)<=limits.result_bytes and f.replay(cp,request,raw),'result verification');return raw
        return self._dispatch(s,token,TENSOR,q.request_id,request,{'checkpoint':f.carrier(cp),'request':f.carrier(request)},_bound(cp),verify)
    def residual(self,s,token,point,*,request_id):
        with self.lock:g=self._get(s,token);need(g.cooperative,'cooperation not granted');cp=g.approval.checkpoint
        need(type(point) is tuple and type(request_id) is str and len(request_id)<=56 and f.ID.fullmatch(request_id),'plan identity');mod,p,m,cert=f.restore(cp);orders,weights=_stencil(mod,p);need(len(point)==len(orders[0]),'point rank')
        for x in point:f._coordinate(x)
        reqs=tuple(f.make_request(cp,pb.POINT,point,derivative=d,request_id=request_id+'-d'+str(i),correlation_id=s.turn) for i,d in enumerate(orders));
        with self.lock:
            g=self._get(s,token);need(g.calls>=len(reqs)+1 and g.work>=len(reqs)*_bound(cp)+1000+500*len(p.forcing),'plan resource budget')
            need(all((s,f._validate_request(q,cp).request_id) not in self.seen for q in reqs) and (s,request_id+'-sum') not in self.seen,'plan replay')
        receipts=tuple(self.call(s,token,q) for q in reqs)
        symbolic=_symbol_frame(p,point,weights,receipts,request_id+'-sum',s.turn,g.approval.identity)
        need(len(symbolic.encode())<=g.limits.request_bytes,'symbolic request budget')
        def verify(result):
            SOUT.validate(result);raw=result['frame'];need(len(raw.encode())<=g.limits.result_bytes,'result budget');symbolic_replay(symbolic,raw);return raw.encode()
        r=self._dispatch(s,token,SYMBOLIC,request_id+'-sum',symbolic.encode(),{'frame':symbolic},1000+500*len(p.forcing),verify)
        value=symbolic_replay(symbolic,r.result.decode());need(abs(value)<=cert.residual_upper,'residual outside full-domain certificate')
        out=Residual(s,g.approval.identity,request_id,point,reqs,receipts,symbolic,r,str(value),str(cert.residual_upper));replay_residual(cp,out,s)
        with self.lock:self._get(s,token)
        return out


def _symbol_frame(p,point,weights,receipts,request_id,turn,checkpoint):
    return f.canonical(dict(point=[str(Q(x)) for x in point],weights=list(map(str,weights)),values=[pb.Result.FromString(r.result).exact_value for r in receipts],forcing=[[list(row[:-1]),str(Q(row[-1]))] for row in p.forcing],inputs=[r.identity for r in receipts],request_id=request_id,turn=turn,checkpoint=checkpoint)).decode()


def replay_receipt(cp,request,r,scope):
    need(type(r) is Receipt and type(scope) is Scope and r.scope==scope and r.operation==TENSOR and r.descriptor_sha256==descriptor(TENSOR)[0] and r.checkpoint_sha256==f.digest(cp).hex() and r.request_sha256==f.digest(request).hex(),'receipt binding')
    q=f._validate_request(request,cp);need(q.request_id==r.request_id and q.correlation_id==scope.turn,'receipt scope');return f.replay(cp,request,r.result)


def replay_residual(cp,r,expected_scope):
    need(type(r) is Residual and type(expected_scope) is Scope and r.scope==expected_scope and type(r.plan_id) is str and len(r.plan_id)<=56 and f.ID.fullmatch(r.plan_id) and r.checkpoint_sha256==f.digest(cp).hex(),'plan binding')
    mod,p,_,cert=f.restore(cp);orders,weights=_stencil(mod,p);need(len(r.requests)==len(r.field_receipts)==len(orders),'plan count')
    for i,(d,q,a) in enumerate(zip(orders,r.requests,r.field_receipts)):
        m=f._validate_request(q,cp);need(m.request_id==r.plan_id+'-d'+str(i) and m.operation==pb.POINT and tuple(m.lower)==r.point and tuple(m.derivative)==d,'stencil binding');replay_receipt(cp,q,a,r.scope)
    need(len({a.request_id for a in r.field_receipts})==len(orders),'duplicate receipt')
    s=_symbol_frame(p,r.point,weights,r.field_receipts,r.plan_id+'-sum',r.scope.turn,r.checkpoint_sha256);a=r.symbolic_receipt
    need(s==r.symbolic_request and type(a) is Receipt and a.scope==r.scope and a.operation==SYMBOLIC and a.descriptor_sha256==descriptor(SYMBOLIC)[0] and a.checkpoint_sha256==r.checkpoint_sha256 and a.request_sha256==f.digest(s.encode()).hex() and a.request_id==r.plan_id+'-sum','symbolic handoff binding')
    v=symbolic_replay(s,a.result.decode());need(r.exact_residual==str(v) and r.certified_residual_upper==str(cert.residual_upper) and abs(v)<=cert.residual_upper,'cooperative certificate mismatch');return True
