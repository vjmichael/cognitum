"""MEL-04B host-owned, fail-closed mathematical DAG adapter.

Every worker goes through the existing Admission; no grant issuance, registry
mutation, model graph parser, general function conversion or new runtime.
Wire material and deterministic work proxies are cumulative, not measured RAM
or FLOPs. Cancellation is cooperative and suppresses publication, not OS kill.
"""
from dataclasses import dataclass
import hashlib
import re
import struct
from threading import RLock
from time import monotonic_ns
from . import admission as a, exchange as x, native as n, engines as e
from . import model_engines as m, exchange_pb2 as p
from .engine_limits import HdcLimits, KanLimits, account, MAX_HDC_WORK, MAX_KAN_WORK
from .objects import number, token, need

MAX_NODES=8
MAX_EDGES=16
MAX_BYTES=1048576
MAX_WORK=8*(max(a.MAX_WORK,MAX_HDC_WORK,MAX_KAN_WORK)+65536)
MAX_PLAN_MS=30000
MAX_STEP_MS=10000
ID=re.compile(r'[A-Za-z0-9_.-]{1,40}\Z',re.ASCII)


def _id(v):return type(v) is str and ID.fullmatch(v) is not None

def _int(v,lo,hi):return type(v) is int and lo<=v<=hi


@dataclass(frozen=True,slots=True)
class Budget:
    work: int=MAX_WORK
    bytes: int=MAX_BYTES
    calls: int=MAX_NODES
    time_ms: int=MAX_PLAN_MS
    step_ms: int=MAX_STEP_MS
    def __post_init__(self):
        need(all(_int(v,1,h) for v,h in ((self.work,MAX_WORK),(self.bytes,MAX_BYTES),(self.calls,MAX_NODES),(self.time_ms,MAX_PLAN_MS),(self.step_ms,MAX_STEP_MS))),'graph budget')


@dataclass(frozen=True,slots=True)
class Seed:
    id:str
    points:n.NativeObject

@dataclass(frozen=True,slots=True)
class Bind:
    id:str
    call:e.Call

@dataclass(frozen=True,slots=True)
class Threshold:
    id:str
    parent:str
    at_least:float
    unit:str

@dataclass(frozen=True,slots=True)
class Lift:
    id:str
    parent:str
    rows:int
    columns:int

@dataclass(frozen=True,slots=True)
class Vfa:
    id:str
    parent:str
    function:n.NativeObject

@dataclass(frozen=True,slots=True)
class Kan:
    id:str
    parent:str
    approval:m.Approval
    input_axes:tuple
    output_axes:tuple

@dataclass(frozen=True,slots=True)
class Query:
    id:str
    probe:str
    candidates:tuple


NODES=(Seed,Bind,Threshold,Lift,Vfa,Kan,Query)
WORKERS=(Bind,Vfa,Kan,Query)


def _parents(v):
    if type(v) in (Seed,Bind):return ()
    if type(v) is Query:return (v.probe,)+v.candidates
    return (v.parent,)


def _kind(v):
    return 'bits' if type(v) in (Threshold,Bind) else 'terminal' if type(v) is Query else 'samples'


def _op(v):return {Bind:'hdc.bind',Vfa:'vfa.evaluate',Kan:'kan.evaluate',Query:'hdc.query'}.get(type(v))


def _request_id(plan,v):return plan.id+':'+v.id


def _part(v):
    # Length-delimited fixed-order semantic fields; no JSON, no grant tokens.
    if type(v) is str:v=v.encode('ascii')
    elif type(v) is int:v=struct.pack('<Q',v)
    need(type(v) is bytes,'plan identity field')
    return struct.pack('<I',len(v))+v


def _material(plan):
    parts=[b'cognitum.mel.cooperation.v1',hashlib.sha256(p.DESCRIPTOR.serialized_pb).digest(),plan.id,plan.scope.session,plan.scope.workspace,plan.scope.subject,plan.scope.turn,
           plan.budget.work,plan.budget.bytes,plan.budget.calls,plan.budget.time_ms,plan.budget.step_ms,len(plan.nodes)]
    for v in plan.nodes:
        parents=_parents(v);parts.extend((type(v).__name__,v.id,len(parents),*parents))
        if type(v) in WORKERS:
            op=_op(v);route=next(r for r in a.routes(include_engines=True) if r.operation==op)
            parts.extend((op,route.descriptor_sha256,route.operation_version))
        if type(v) is Seed:parts.append(v.points.wire)
        elif type(v) is Bind:parts.append(v.call.wire)
        elif type(v) is Threshold:parts.extend((struct.pack('<d',number(v.at_least,1e12)),v.unit))
        elif type(v) is Lift:parts.extend((v.rows,v.columns))
        elif type(v) is Vfa:parts.append(v.function.wire)
        elif type(v) is Kan:parts.extend((v.approval.checkpoint.wire,v.approval.review_id,len(v.input_axes),*v.input_axes,len(v.output_axes),*v.output_axes))
    return b''.join(_part(v) for v in parts)


def _validate(plan):
    need(type(plan.scope) is a.Scope and type(plan.budget) is Budget and _id(plan.id),'host plan scope or ID')
    need(type(plan.nodes) is tuple and 1<=len(plan.nodes)<=MAX_NODES,'graph node budget')
    nodes={}
    for v in plan.nodes:
        need(type(v) in NODES and _id(v.id) and v.id not in nodes,'node identity');nodes[v.id]=v
        if type(v) is Seed:
            need(type(v.points) is n.NativeObject and v.points.message().body.WhichOneof('representation')=='points','native point seed')
        elif type(v) is Bind:
            need(type(v.call) is e.Call and v.call.operation=='hdc.bind','typed HDC bind seed')
            c=v.call.message;need((c.request_id,c.correlation_id)==(_request_id(plan,v),plan.scope.turn),'bind scope or request')
        elif type(v) is Threshold:number(v.at_least,1e12);need(token(v.unit),'threshold unit')
        elif type(v) is Lift:need(_int(v.rows,1,x.MAX_ROWS) and _int(v.columns,1,x.MAX_COLS),'lift shape')
        elif type(v) is Vfa:need(type(v.function) is n.NativeObject and v.function.message().body.WhichOneof('representation')=='function','VFA function')
        elif type(v) is Kan:
            need(type(v.approval) is m.Approval,'trusted checkpoint selection');ck=v.approval.checkpoint.message()
            for axes,d in ((v.input_axes,ck.layers[0].inputs),(v.output_axes,ck.layers[-1].outputs)):
                need(type(axes) is tuple and len(axes)==d and all(token(z) for z in axes) and len(set(axes))==d,'KAN axis mapping')
        else:need(type(v.candidates) is tuple and 1<=len(v.candidates)<=e.MAX_CANDIDATES,'query candidate budget')
    edge_count=0
    for v in plan.nodes:
        parents=_parents(v);edge_count+=len(parents)
        required='bits' if type(v) in (Lift,Query) else 'samples'
        need(all(_id(i) and i in nodes and _kind(nodes[i])==required for i in parents),'missing or incompatible dependency')
    need(edge_count<=MAX_EDGES and 1<=sum(type(v) in WORKERS for v in plan.nodes)<=plan.budget.calls,'edge or worker count budget')
    ordered=[];seen=set()
    while len(ordered)<len(nodes):
        for v in plan.nodes:
            if v.id not in seen and all(i in seen for i in _parents(v)):
                ordered.append(v);seen.add(v.id);break
        else:raise ValueError('cyclic graph')
    raw=_material(plan);need(len(raw)<=plan.budget.bytes,'plan material budget')
    return tuple(ordered),raw


@dataclass(frozen=True,slots=True)
class Plan:
    id:str
    scope:a.Scope
    nodes:tuple
    budget:Budget=Budget()
    def __post_init__(self):_validate(self)
    @property
    def identity(self):return hashlib.sha256(_validate(self)[1]).hexdigest()


@dataclass(frozen=True,slots=True)
class NodeReceipt:
    node_id:str
    status:str
    operation:str|None=None
    request_sha256:str|None=None
    result_sha256:str|None=None
    transfer_sha256:str|None=None
    object_sha256:str|None=None
    lossy_history:bool=False
    worker:a.Receipt|None=None
    transfer:x.Transfer|None=None
    output:x.Object|None=None


@dataclass(frozen=True,slots=True)
class Outcome:
    plan_sha256:str
    scope:a.Scope
    status:str
    nodes:tuple
    charged_work:int
    reserved_bytes:int
    reserved_calls:int


class Cancellation:
    """Trusted one-shot execution handle. Cancellation never issues authority.

    Race before Admission reservation can still let an inert worker run;
    the graph will discard it. Completion/cancellation publication is locked.
    """
    def __init__(self):
        self._lock=RLock();self._used=False;self._done=False;self._cancelled=False;self._active=None
    def cancel(self):
        with self._lock:
            if self._done or self._cancelled:return False
            self._cancelled=True
            if self._active is not None:
                host,s,rid=self._active;host.cancel(s,rid)
            return True
    def _begin(self):
        with self._lock:
            need(not self._used,'one-shot cancellation handle');self._used=True
    def _check(self):
        with self._lock:return self._cancelled
    def _dispatch(self,host,s,rid,token,raw,timeout):
        with self._lock:
            if self._cancelled:raise _Stop('cancelled')
            self._active=(host,s,rid)
        try:return host.execute(s,token,rid,raw,timeout_ms=timeout)
        finally:
            with self._lock:self._active=None
    def _finish(self):
        with self._lock:self._done=True;return self._cancelled


class _Stop(Exception):pass


class _Meter:
    def __init__(self,b,material):self.b=b;self.work=0;self.bytes=material;self.calls=0
    def charge(self,work=0,bytes_=0,calls=0):
        if self.work+work>self.b.work or self.bytes+bytes_>self.b.bytes or self.calls+calls>self.b.calls:raise _Stop('resource_denied')
        self.work+=work;self.bytes+=bytes_;self.calls+=calls


def _work(call):
    if type(call) is n.NativeCall:
        f,q=n.pair(call.function,call.points);t,d=f.body.shape;return (t+1)*d*q.body.shape[0]
    return account(call,HdcLimits() if call.operation.startswith('hdc.') else KanLimits())


def _metadata(v,status,*,worker=None,transfer=None,output=None,loss=False):
    return NodeReceipt(v.id,status,_op(v),worker.request_sha256 if worker else None,worker.result_sha256 if worker else None,
                       transfer.identity if transfer else None,output.identity if output else None,loss,worker,transfer,output)


def execute(host,plan,grants,*,cancellation=None):
    """Execute a trusted immutable graph with independently issued grants.

    Fail fast; all node output payloads are suppressed on any graph failure.
    Previously executed compute is not undone and its quotas stay charged.
    No arbitrary exchange objects or external result receipts can enter a graph.
    """
    need(type(host) is a.Admission and type(plan) is Plan,'trusted host and plan')
    start=monotonic_ns();ordered,material=_validate(plan);host._scope(plan.scope)
    ids={v.id for v in ordered if type(v) in WORKERS}
    need(type(grants) is tuple and len(grants)==len(ids),'exact worker grants')
    tokens={}
    for entry in grants:
        need(type(entry) is tuple and len(entry)==2,'grant binding');i,t=entry
        need(_id(i) and i in ids and i not in tokens and type(t) is bytes and len(t)==32 and t not in tokens.values(),'distinct per-node grants');tokens[i]=t
    ctrl=Cancellation() if cancellation is None else cancellation;need(type(ctrl) is Cancellation,'trusted cancellation handle');ctrl._begin()
    meter=_Meter(plan.budget,len(material));s=plan.scope;deadline=start+plan.budget.time_ms*1000000;node_deadline=deadline
    records={};objects={};failure=None
    def check():
        if ctrl._check():raise _Stop('cancelled')
        remaining=(min(deadline,node_deadline)-monotonic_ns())//1000000
        if remaining<1:raise _Stop('timed_out')
        return remaining
    def pinned_offer(tok):
        # The existing discovery API uses the registry RLock. Bound waiting
        # for that same lock before calling it reentrantly; independently
        # admitted dispatch still rechecks the grant and installed entry.
        lock=host._runtime.registry.lock
        while not lock.acquire(timeout=min(.02,check()/1000)):
            check()
        try:
            check()
            try:return host.discover_model(s,tok)
            except ValueError:raise _Stop('denied') from None
        finally:lock.release()
    for v in ordered:
        if failure is not None:
            records[v.id]=_metadata(v,'blocked_dependency' if any(records[i].status!='completed' for i in _parents(v)) else 'not_run');continue
        worker=transfer=out=None;loss=False
        node_deadline=min(deadline,monotonic_ns()+plan.budget.step_ms*1000000)
        try:
            check();parents=tuple(objects[i] for i in _parents(v));loss=any(o.message().body.lossy_history for o in parents)
            # Charge logical link validation/derivation proxy before transforming.
            meter.charge(work=1+sum(len(o.wire) for o in parents))
            if type(v) is Seed:
                meter.charge(work=len(v.points.wire),bytes_=x.MAX_OBJECT);out=x.from_vfa_points(s,v.points)
            elif type(v) in (Threshold,Lift):
                meter.charge(bytes_=x.MAX_OBJECT)
                out=x.threshold(s,parents[0],v.at_least,v.unit) if type(v) is Threshold else x.lift(s,parents[0],v.rows,v.columns)
                x.verify_derivation(s,parents[0],out)
            else:
                rid=_request_id(plan,v);mapping={};op=_op(v)
                # Reserve bounded wire allocations before materializing a link.
                # This is deliberately conservative, with no reuse/refund.
                reserve=(n.MAX_REQUEST if type(v) is Vfa else e.MAX_REQUEST)+(n.MAX_RESULT if type(v) is Vfa else e.MAX_RESULT)+(0 if type(v) is Query else x.MAX_OBJECT)+(0 if type(v) is Bind else x.MAX_TRANSFER)
                meter.charge(bytes_=reserve)
                if type(v) is Bind:call=v.call
                else:
                    if type(v) is Vfa:
                        mapping={'function':v.function};transfer=x.prepare_vfa(s,parents[0],v.function,'mel_vfa_evaluate',rid)
                    elif type(v) is Kan:
                        mapping={'approval':v.approval,'dimensionless_axes':v.input_axes};transfer=x.prepare_kan(s,parents[0],v.approval,v.input_axes,rid)
                        # Verify that the existing grant actually has the host-approved checkpoint pin.
                        offer=pinned_offer(tokens[v.id])
                        if offer['checkpoint_sha256']!=v.approval.checkpoint.identity or offer['descriptor_sha256']!=e.descriptor(op)[0]:raise _Stop('denied')
                    else:transfer=x.prepare_query(s,parents[0],parents[1:],rid)
                    x.verify_transfer(s,transfer,parents,**mapping);raw=transfer.message().request_frame
                    call=n.decode_request(raw,op) if type(v) is Vfa else e.Call(op,raw)
                raw=call.wire() if type(call) is n.NativeCall else call.wire
                work=_work(call);need(work is not None,'work accounting unavailable')
                # Charge validated logical engine work before attempting admission.
                meter.charge(work=work+len(raw),calls=1)
                remaining=check()
                try:worker=ctrl._dispatch(host,s,rid,tokens[v.id],raw,remaining)
                except ValueError:raise _Stop('denied') from None
                check()
                if worker.status!='completed':raise _Stop(worker.status)
                if type(v) is Bind:out=x.from_result(s,call,worker)
                elif type(v) is Query:x._checked_receipt(s,call,worker) # exact independent Hamming witness
                else:out=x.from_transfer_result(s,transfer,parents,worker,**mapping,**({'output_axes':v.output_axes} if type(v) is Kan else {}))
            check()
            if out is not None:objects[v.id]=out;loss=out.message().body.lossy_history
            records[v.id]=_metadata(v,'completed',worker=worker,transfer=transfer,output=out,loss=loss)
        except _Stop as exc:failure=str(exc);records[v.id]=_metadata(v,failure,worker=worker,transfer=transfer,loss=loss)
        except (ValueError,TypeError):failure='invalid_exchange';records[v.id]=_metadata(v,failure,worker=worker,transfer=transfer,loss=loss)
        except Exception:failure='error';records[v.id]=_metadata(v,failure,worker=worker,transfer=transfer,loss=loss)
    if ctrl._finish():failure='cancelled'
    if failure is None and monotonic_ns()>=deadline:failure='timed_out'
    if failure is not None:
        # Retain audit hashes/status only; no partial result frame or object published.
        from dataclasses import replace
        records={i:replace(r,worker=None,transfer=None,output=None) for i,r in records.items()}
    return Outcome(hashlib.sha256(material).hexdigest(),s,failure or 'completed',tuple(records[v.id] for v in ordered),meter.work,meter.bytes,meter.calls)
