"""MEL-07A-R3 bounded CPU batch proposals, never authority or dispatch.

Use measured sizes only and split one already typed homogeneous request.
A trusted caller must separately approve every proposed exact child request
and use the existing Admission/Runtime and independent verification. Observed
CPU/peak/timing estimates are advisory, NOT enforced OS resource ceilings.
"""
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from . import admission as a, native as n, engines as e, polynomial_kan as p
from . import model_engines as m, cpu_routing as routing
from .engine_limits import HdcLimits, KanLimits, account

OPS = ('vfa.evaluate','vfa.gradient','kan.evaluate',p.OP,'hdc.query')
CAP = {'vfa.evaluate':16,'vfa.gradient':16,'kan.evaluate':16,p.OP:4,'hdc.query':8}
SIZES = {op: ((1,2,4) if op==p.OP else (1,2,8) if op=='hdc.query'
              else (1,2,8,16)) for op in OPS}


def digest(raw):return sha256(raw).hexdigest()
def wire(call):return call.wire() if type(call) is n.NativeCall else call.wire
def _positive(x,maximum):return type(x) is int and 0<x<=maximum
def _estimate(x):return type(x) in (int,float) and isfinite(x) and 0<=x<=1e12
def _digest(x):return type(x) is str and len(x)==64 and all(c in '0123456789abcdef' for c in x)


@dataclass(frozen=True,slots=True)
class Estimate:
    count:int
    elapsed_ms:float
    cpu_s:float
    peak_bytes:int
    def __post_init__(self):
        n.need(_positive(self.count,16) and _estimate(self.elapsed_ms)
               and self.elapsed_ms>0 and _estimate(self.cpu_s)
               and _positive(self.peak_bytes,1<<50),'invalid measurement estimate')


@dataclass(frozen=True,slots=True)
class Calibration:
    operation:str
    workload_key:str
    evidence_sha256:str
    source_sha:str
    target:str
    estimates:tuple
    def __post_init__(self):
        n.need(self.operation in OPS and _digest(self.workload_key)
               and _digest(self.evidence_sha256) and type(self.source_sha) is str
               and len(self.source_sha)==40 and all(c in '0123456789abcdef' for c in self.source_sha)
               and type(self.target) is str and 0<len(self.target)<=512
               and type(self.estimates) is tuple and all(type(x) is Estimate for x in self.estimates)
               and tuple(x.count for x in self.estimates)==SIZES[self.operation],
               'invalid or incomplete trusted calibration')


@dataclass(frozen=True,slots=True)
class Budget:
    total_request_bytes:int
    total_result_reserve_bytes:int
    estimated_elapsed_ms:float
    estimated_cpu_s:float
    estimated_peak_bytes:int
    max_items_per_call:int=16
    def __post_init__(self):
        n.need(_positive(self.total_request_bytes,16*n.MAX_REQUEST)
               and _positive(self.total_result_reserve_bytes,16*p.MAX_RESULT)
               and _estimate(self.estimated_elapsed_ms) and self.estimated_elapsed_ms>0
               and _estimate(self.estimated_cpu_s)
               and _positive(self.estimated_peak_bytes,1<<50)
               and _positive(self.max_items_per_call,16),'invalid planner budget')


@dataclass(frozen=True,slots=True)
class Part:
    start:int
    stop:int
    request:object
    request_sha256:str
    work:int
    request_bytes:int
    result_reserve_bytes:int
    estimate:Estimate


@dataclass(frozen=True,slots=True)
class Plan:
    scope:a.Scope
    route:a.Route
    parent_sha256:str
    workload_key:str
    evidence_sha256:str
    parts:tuple
    total_work:int
    total_request_bytes:int
    total_result_reserve_bytes:int
    estimated_elapsed_ms:float
    estimated_cpu_s:float
    estimated_peak_bytes:int
    execution_authorized:bool=False


def describe(call):
    """Return immutable-profile fingerprint, count and exact parent identity.

    Fingerprint includes the actual function, checkpoint or query probe; row
    values can differ, so observed resource behavior is not a universal bound.
    Derivative order/tolerance and exact engine descriptor are bound.
    """
    if type(call) is n.NativeCall:
        f,q=n.pair(call.function,call.points)
        count=q.body.shape[0]
        material=call.function.wire
        return digest(b'cpu-v1\0'+call.descriptor_sha256.encode()+material),count,call.request_id,call.correlation_id,call.descriptor_sha256
    n.need(type(call) in (e.Call,p.Call) and call.operation in OPS,'unsupported typed batch')
    msg=call.message
    if call.operation=='kan.evaluate':
        count=msg.kan.rows;material=m.checkpoint_wire(msg.kan.layers)
    elif call.operation=='hdc.query':
        count=len(msg.query.candidates);material=n.serialize(msg.query.probe)
    else:
        count=msg.rows
        material=n.serialize(msg.checkpoint)+bytes([msg.order])+msg.absolute_tolerance.hex().encode()
    return digest(b'cpu-v1\0'+msg.descriptor_sha256+material),count,msg.request_id,msg.correlation_id,msg.descriptor_sha256.hex()


def _slice(call,start,stop,rid):
    if type(call) is n.NativeCall:
        q=call.points.message().body
        _,d=q.shape;v=list(q.points.coordinates)
        rows=[v[i*d:(i+1)*d] for i in range(start,stop)]
        return n.make_call(call.public_name,call.function,n.points(call.function,rows),
                           rid,call.correlation_id)
    msg=call.message;msg.request_id=rid
    if call.operation=='hdc.query':
        del msg.query.candidates[stop:];del msg.query.candidates[:start]
    elif call.operation=='kan.evaluate':
        d=msg.kan.layers[0].inputs
        v=list(msg.kan.coordinates)[start*d:stop*d]
        msg.kan.rows=stop-start;del msg.kan.coordinates[:];msg.kan.coordinates.extend(v)
    else:
        d=msg.checkpoint.layers[0].inputs
        v=list(msg.coordinates)[start*d:stop*d]
        msg.rows=stop-start;del msg.coordinates[:];msg.coordinates.extend(v)
    return type(call)(call.operation,n.serialize(msg))


def _work(call,limits):
    if type(call) is n.NativeCall:
        f,q=n.pair(call.function,call.points);t,d=f.body.shape;count=q.body.shape[0]
        # Respect both runtime and independently certifiable envelopes.
        if t>min(32,limits.terms) or d>limits.dimensions or count>min(16,limits.points):
            return None
        return (t+1)*d*count
    if type(call) is p.Call:return p.account(call,limits)
    return account(call,limits)


def plan_cpu(registry,scope,route,parent,limits,budget,calibration,*,
             allow_research=False,allow_polynomial=False,preference='auto'):
    """Return an exact contiguous partition or reject; never creates grants.

    Aggregate calls/work are charged against the supplied existing limit
    envelope, including repeated checkpoint cost. Per-call raw frame bytes
    and total reservation are checked exactly. Timing/CPU/memory constraints
    apply to estimates only. Host must enforce actual policy independently.
    """
    n.need(type(scope) is a.Scope and type(budget) is Budget and
           type(calibration) is Calibration and type(parent) in (n.NativeCall,e.Call,p.Call),
           'trusted batch policy')
    op=parent.operation
    n.need(type(route) is a.Route and op==route.operation and op in OPS
           and calibration.operation==op,'batch operation mismatch')
    routing.select_cpu(registry,route,preference=preference,
                       allow_research=allow_research,allow_polynomial=allow_polynomial)
    key,count,rid,turn,descriptor=describe(parent)
    n.need(key==calibration.workload_key and turn==scope.turn and
           descriptor==route.descriptor_sha256 and 1<=count<=CAP[op],
           'stale profile, scope, descriptor or workload bound')
    expected=a.Limits if op in n.OP else p.Limits if op==p.OP else KanLimits if op=='kan.evaluate' else HdcLimits
    n.need(type(limits) is expected,'wrong limit profile')
    # Cache exact child construction; the search has at most 16 items, and
    # only previously measured sizes are candidates. No unbounded optimizer.
    edges={}
    for start in range(count):
        for est in calibration.estimates:
            stop=start+est.count
            if stop>count or est.count>budget.max_items_per_call or est.peak_bytes>budget.estimated_peak_bytes or est.elapsed_ms>limits.timeout_ms:
                continue
            child_id=rid+':b'+str(start)+'-'+str(stop)
            if not n.ID.fullmatch(child_id):continue
            child=_slice(parent,start,stop,child_id);raw=wire(child)
            child_key,child_count,_,child_turn,child_desc=describe(child)
            n.need((child_key,child_count,child_turn,child_desc)==(key,stop-start,turn,descriptor),'child typed identity drift')
            work=_work(child,limits)
            if work is None or work>limits.work or len(raw)>limits.request_bytes:continue
            edges[start,stop]=Part(start,stop,child,digest(raw),work,len(raw),limits.result_bytes,est)
    best=None
    def search(start,parts,work,req,res,elapsed,cpu,peak):
        nonlocal best
        if len(parts)>limits.calls or work>limits.work or req>budget.total_request_bytes or res>budget.total_result_reserve_bytes or elapsed>budget.estimated_elapsed_ms or cpu>budget.estimated_cpu_s:
            return
        if best is not None and elapsed>best[0][0]:return
        if start==count:
            score=(elapsed,cpu,len(parts),tuple(-(q.stop-q.start) for q in parts))
            if best is None or score<best[0]:
                best=score,Plan(scope,route,digest(wire(parent)),key,calibration.evidence_sha256,
                    parts,work,req,res,elapsed,cpu,peak)
            return
        for est in reversed(calibration.estimates):
            q=edges.get((start,start+est.count))
            if q is not None:
                search(q.stop,parts+(q,),work+q.work,req+q.request_bytes,
                    res+q.result_reserve_bytes,elapsed+est.elapsed_ms,cpu+est.cpu_s,max(peak,est.peak_bytes))
    search(0,(),0,0,0,0.,0.,0)
    n.need(best is not None,'no feasible measured CPU partition')
    return best[1]
