"""Host-only inline mathematical verification inside the MEL-04B executor.

The same incremental replay logic verifies retained receipts offline. The guarded
route rejects uncertain thresholds before conversion or successor dispatch.
No grant issuance, OS isolation or model-facing route is introduced.
"""
from dataclasses import dataclass
import hashlib
from . import uncertainty as u, uncertainty_pb2 as pb

METHOD = 'mel05b.real-composition.rational-interval.v1'
MAX_WITNESS = 2 * 1024 * 1024
MAX_TOTAL_COMPONENTS = 8 * 16 * 8


def _rational(q):
    return pb.Rational(numerator=str(q.numerator), denominator=str(q.denominator))


def _interval(v):
    return pb.Interval(lower=_rational(v.lo), upper=_rational(v.hi))


def _points(vals, rows, cols):
    u.require(len(vals)==rows*cols,'sample layout')
    return tuple(tuple(u.Interval.point(v) for v in vals[i:i+cols]) for i in range(0,len(vals),cols))


def _flat(rows):return tuple(v for row in rows for v in row)


def kan_certificate(scope, call, receipt, absolute_tolerance):
    """Independent KAN result check bound to existing admitted request/receipt.

    Returns local mathematical intervals; callers must not treat shape-only
    lineage as numerical verification. A non-within verdict is a refusal.
    """
    from . import engines as e, engines_pb2 as ep, exchange as x
    u.require(type(call) is e.Call and call.operation=='kan.evaluate','typed KAN call')
    raw,_,_=x._checked_receipt(scope,call,receipt)
    k=call.message.kan; res=ep.EngineResult.FromString(raw).kan
    u.require(type(absolute_tolerance) is tuple and len(absolute_tolerance)==res.columns and all(type(t) is float and 0<=t<=1e12 for t in absolute_tolerance),'explicit per-axis tolerance')
    bounds=u.kan_bounds(k.layers,_points(k.coordinates,k.rows,k.layers[0].inputs))
    statuses=tuple(u.error_verdict(b,y,absolute_tolerance[i%res.columns]) for i,(b,y) in enumerate(zip(_flat(bounds),res.values)))
    return bounds,statuses


def _tolerances(plan, tolerances):
    from . import cooperation as c
    u.require(type(plan) is c.Plan,'trusted plan')
    ordered,_=c._validate(plan)
    u.require(type(tolerances) is tuple and len(tolerances)<=c.MAX_NODES and all(type(a) is tuple and len(a)==2 and type(a[0]) is str and type(a[1]) is tuple for a in tolerances),'explicit tolerance mapping')
    ts=dict(tolerances)
    required={z.id:1 if type(z) is c.Vfa else z.approval.checkpoint.message().layers[-1].outputs for z in ordered if type(z) in (c.Vfa,c.Kan)}
    u.require(len(ts)==len(tolerances) and set(ts)==set(required),'exact numerical node tolerance mapping')
    for key,cols in required.items():
        u.require(len(ts[key])==cols and all(type(t) is float and 0<=t<=1e12 for t in ts[key]),'explicit per-axis tolerance')
    return ordered, ts


# Conservative serialized rational upper bound: each endpoint contains two
# signed integer fields, at most 2467 digits for MAX_BITS=8192, plus tags.
# A Sample has four endpoints. Reserve capacity before constructing them.
SAMPLE_BYTES=8*((u.MAX_BITS*30103+99999)//100000+16)+256
NODE_BYTES=2048


class _Verifier:
    def __init__(self,plan,tolerances):
        self.plan=plan; self.scope=plan.scope
        self.ordered,self.ts=_tolerances(plan,tolerances)
        self.witness=pb.GraphWitness(schema_version=1,plan_sha256=bytes.fromhex(plan.identity),method=METHOD,represented_inputs_only=True)
        self.objects={};self.propagated={}; self.total=0; self.index=0

    def _shape(self,node,parents):
        from . import cooperation as c
        if type(node) is c.Seed:return tuple(node.points.message().body.shape)
        if type(node) is c.Lift:return node.rows,node.columns
        if type(node) in (c.Vfa,c.Kan):
            return parents[0].message().body.samples.rows, (1 if type(node) is c.Vfa else node.approval.checkpoint.message().layers[-1].outputs)
        return 0,0

    def reserve(self,node,parents,meter):
        """Charge structural verification work, replay wire allowance, and witness capacity.

        These deterministic proxies are not measured FLOPs/RAM. The rational
        and graph size bounds also apply, and no unused reservation is refunded.
        """
        from . import cooperation as c
        rows,cols=self._shape(node,parents)
        count=rows*cols
        u.require(self.total+count<=MAX_TOTAL_COMPONENTS,'component budget')
        work=128+8*count+4*sum(len(o.wire) for o in parents)
        # Existing worker wire reservations cover the original and its replay
        # of the same bounded frames (logical material, not allocations).
        # Additional certificate and witness wire are charged separately.
        scratch=0
        if type(node) is c.Vfa:
            t,d=node.function.message().body.shape
            u.require(t<=u.MAX_TERMS and rows<=u.MAX_ROWS,'VFA verification size')
            work+=64*rows*(t+1)*(d+1) # two interval paths + independent Decimal certificate
            scratch=65536
        elif type(node) is c.Kan:
            for l in node.approval.checkpoint.message().layers:
                # Bound all spline span recurrences and masked edge sums;
                # covers local points and propagated interval path.
                work+=16*rows*(l.inputs*l.knots*l.knots*(l.degree+1)+l.outputs*l.inputs*l.knots+1)
        elif type(node) is c.Bind:
            work+=4*node.call.message.bind.left.dimension
        elif type(node) is c.Query:
            dim=parents[0].message().body.bits.dimension
            work+=4*dim*len(node.candidates)
        elif type(node) is c.Threshold:work+=16*len(parents[0].message().body.samples.values)
        meter.charge(work=work,bytes_=NODE_BYTES+SAMPLE_BYTES*count+scratch)

    def pre_threshold(self,node,parent):
        p=parent.message().body.samples; ideal=self.propagated[node.parent]
        u.require(len(_flat(ideal))==len(p.values),'threshold shape')
        for b,obs in zip(_flat(ideal),p.values):
            status,_=u.threshold_bit(b,node.at_least,obs)
            u.require(status=='verified','threshold '+status+': '+node.id)

    def pre_domain(self,node,call):
        """Only validate upstream domains before admission; no evaluation here.

        Independent numerical evaluation runs after the scoped worker receipt,
        within the original graph deadline and before any successor dispatch.
        """
        from . import cooperation as c
        rows=self.propagated[node.parent]
        if type(node) is c.Vfa:
            f=node.function.message().body
            domain=tuple((u.rational(d.lower),u.rational(d.upper)) for d in f.domain)
        else:
            l=call.message.kan.layers[0]
            domain=tuple((u.f32(l.grid[i*l.knots]),u.f32(l.grid[(i+1)*l.knots-1])) for i in range(l.inputs))
        u.require(all(len(row)==len(domain) and all(lo<=v.lo<=v.hi<=hi for v,(lo,hi) in zip(row,domain)) for row in rows),'uncertain input outside declared domain')

    def step(self,node,r,check=lambda:None):
        from . import cooperation as c, exchange as x, native as n, engines as e, engines_pb2 as ep, verification as v
        plan,scope,ts,witness,objects,propagated=self.plan,self.scope,self.ts,self.witness,self.objects,self.propagated
        u.require(self.index<len(self.ordered) and node==self.ordered[self.index],'verification node order')
        u.require(type(r) is c.NodeReceipt and r.node_id==node.id and r.status=='completed' and r.operation==c._op(node),'node receipt binding')
        parents=tuple(objects[i] for i in c._parents(node)); out=None; local=ideal=None; query=None
        if type(node) is c.Seed:
            out=x.from_vfa_points(scope,node.points); s=out.message().body.samples
            local=ideal=_points(s.values,s.rows,s.columns)
        elif type(node) is c.Bind:
            v.certify_hdc(scope,node.call,r.worker);out=x.from_result(scope,node.call,r.worker)
        elif type(node) is c.Threshold:
            self.pre_threshold(node,parents[0])
            out=x.threshold(scope,parents[0],node.at_least,node.unit)
            x.verify_derivation(scope,parents[0],out)
        elif type(node) is c.Lift:
            out=x.lift(scope,parents[0],node.rows,node.columns); x.verify_derivation(scope,parents[0],out)
            s=out.message().body.samples;local=ideal=_points(s.values,s.rows,s.columns)
        else:
            rid=c._request_id(plan,node); mapping={}
            if type(node) is c.Vfa:
                mapping={'function':node.function}; tr=x.prepare_vfa(scope,parents[0],node.function,'mel_vfa_evaluate',rid)
            elif type(node) is c.Kan:
                mapping={'approval':node.approval,'dimensionless_axes':node.input_axes};tr=x.prepare_kan(scope,parents[0],node.approval,node.input_axes,rid)
            else:tr=x.prepare_query(scope,parents[0],parents[1:],rid)
            u.require(type(r.transfer) is x.Transfer and tr.wire==r.transfer.wire,'transfer replay mismatch')
            raw=tr.message().request_frame
            call=n.decode_request(raw,'vfa.evaluate') if type(node) is c.Vfa else e.Call(c._op(node),raw)
            x.verify_transfer(scope,tr,parents,**mapping)
            if type(node) is c.Query:
                v.certify_hdc(scope,call,r.worker)
                query=ep.EngineResult.FromString(r.worker.result_frame).query
            else:
                out=x.from_transfer_result(scope,tr,parents,r.worker,**mapping,**({'output_axes':node.output_axes} if type(node) is c.Kan else {}))
                s=out.message().body.samples;tol=ts[node.id]
                u.require(len(tol)==s.columns and all(type(t) is float and 0<=t<=1e12 for t in tol),'explicit per-axis tolerance')
                self.pre_domain(node,call)
                check()
                if type(node) is c.Vfa:
                    cert=v.certify_vfa(scope,call,r.worker,tol)
                    u.require(cert.message().verdict==v.pb.WITHIN_TOLERANCE,'local VFA error not verified')
                    check()
                    f=node.function.message().body; p=call.points.message().body
                    local=u.vfa_bounds(f,_points(p.points.coordinates,*p.shape),check=check)
                    ideal=u.vfa_bounds(f,propagated[node.parent],check=check)
                else:
                    k=call.message.kan
                    local=u.kan_bounds(k.layers,_points(k.coordinates,k.rows,k.layers[0].inputs),check=check)
                    ideal=u.kan_bounds(k.layers,propagated[node.parent],check=check)
                # receipt and observed shape already checked by from_transfer_result.
                u.require(len(_flat(local))==len(_flat(ideal))==len(s.values),'numerical witness shape')
                u.require(all(u.error_verdict(b,y,tol[i%s.columns])=='within' for i,(b,y) in enumerate(zip(_flat(local),s.values))),'local numerical error not verified: '+node.id)
                u.require(all(u.error_verdict(b,y,tol[i%s.columns])=='within' for i,(b,y) in enumerate(zip(_flat(ideal),s.values))),'propagated error not verified: '+node.id)
        # Check all receipt metadata against the reconstructed trusted objects.
        if out is not None:
            u.require(type(r.output) is x.Object and out.wire==r.output.wire and out.identity==r.object_sha256,'output replay mismatch')
            objects[node.id]=out
        else:u.require(r.output is None and r.object_sha256 is None,'unexpected output')
        expected_loss=out.message().body.lossy_history if out else any(p.message().body.lossy_history for p in parents)
        u.require(r.lossy_history==expected_loss,'loss lineage')
        if type(node) in c.WORKERS:
            u.require(r.request_sha256==r.worker.request_sha256 and r.result_sha256==r.worker.result_sha256,'worker hashes')
        else:u.require(r.worker is None and r.request_sha256 is None and r.result_sha256 is None,'unexpected worker')
        if type(node) in (c.Vfa,c.Kan,c.Query):u.require(r.transfer_sha256==r.transfer.identity,'transfer hash')
        else:u.require(r.transfer is None and r.transfer_sha256 is None,'unexpected transfer')
        wr=witness.nodes.add(node_id=node.id,operation=type(node).__name__,lossy_history=expected_loss)
        for key in ('request_sha256','result_sha256','object_sha256','transfer_sha256'):
            if getattr(r,key):setattr(wr,key,bytes.fromhex(getattr(r,key)))
        if query is not None:
            wr.hamming_distance.extend(query.hamming_distance);wr.best_index.extend(query.best_index)
        if out is not None:
            b=out.message().body
            if b.HasField('bits'):wr.verified_packed_bits=b.bits.packed_bits;wr.bit_dimension=b.bits.dimension
            else:
                s=b.samples;wr.rows,wr.columns=s.rows,s.columns
                u.require(local is not None and ideal is not None and len(_flat(local))==len(_flat(ideal))==len(s.values),'propagated shape')
                propagated[node.id]=ideal;self.total+=len(s.values);u.require(self.total<=MAX_TOTAL_COMPONENTS,'component budget')
                for i,(l,g,y) in enumerate(zip(_flat(local),_flat(ideal),s.values)):
                    wr.samples.add(observed=y,local=_interval(l),propagated=_interval(g),absolute_tolerance=ts[node.id][i%s.columns] if node.id in ts else 0.,unit=s.axes[i%s.columns].unit)
        u.require(witness.ByteSize()<=MAX_WITNESS,'witness byte budget')
        self.index+=1

    def finish(self):
        u.require(self.index==len(self.ordered),'incomplete verification')
        wire=self.witness.SerializeToString(deterministic=True)
        u.require(len(wire)<=MAX_WITNESS,'witness byte budget')
        return wire


def verify_graph(plan,outcome,tolerances):
    """Independent bounded replay; not an admission or authority mechanism."""
    from . import cooperation as c
    u.require(type(plan) is c.Plan and type(outcome) is c.Outcome and outcome.status=='completed' and outcome.plan_sha256==plan.identity and outcome.scope==plan.scope,'trusted completed plan outcome')
    guard=_Verifier(plan,tolerances)
    u.require(type(outcome.nodes) is tuple and len(outcome.nodes)==len(guard.ordered),'graph receipt length')
    for node,r in zip(guard.ordered,outcome.nodes):guard.step(node,r)
    return guard.finish()


def replay(plan,outcome,tolerances,wire):
    u.require(type(wire) is bytes and len(wire)<=MAX_WITNESS,'bounded witness')
    u.require(verify_graph(plan,outcome,tolerances)==wire,'graph witness replay mismatch')
    return hashlib.sha256(b'cognitum.mel.uncertainty.v1.GraphWitness\0'+wire).hexdigest()


@dataclass(frozen=True,slots=True)
class Guarded:
    status:str
    outcome:object=None
    witness:bytes|None=None
    charged_work:int=0
    reserved_bytes:int=0
    reserved_calls:int=0


def execute_verified(host,plan,grants,tolerances,*,cancellation=None):
    from . import cooperation as c
    guard=_Verifier(plan,tolerances)
    raw,wire=c._execute(host,plan,grants,cancellation=cancellation,guard=guard)
    accounting=(raw.charged_work,raw.reserved_bytes,raw.reserved_calls)
    if raw.status!='completed':return Guarded(raw.status,None,None,*accounting)
    return Guarded('verified',raw,wire,*accounting)
