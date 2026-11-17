"""Reviewed, inert CPU specialist adapters for the existing Runtime/Registry.

The host must install, nominate and enable this adapter explicitly. A route
descriptor or a serialized request NEVER authorizes dispatch. No research,
external command, file, network or durable-state capability is admitted here.
"""
from __future__ import annotations

from base64 import b64decode, b64encode
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
from itertools import permutations
from math import isfinite
from google.protobuf.descriptor import FieldDescriptor
from types import MappingProxyType
from google.protobuf.message import DecodeError
from .contracts import Manifest, Operation, Shape, digest
from .proto import (specialists_pb2 as math, formal_pb2 as formal,
                    formal_backend_pb2 as backend, formal_advanced_pb2 as advanced,
                    optimization_pb2 as opt, planning_pb2 as plan,
                    probability_pb2 as prob, physics_ode_pb2 as physics,
                    temporal_practical_pb2 as temporal)

MAX_FRAME=8192
MAX_B64=4*((MAX_FRAME+2)//3)
PLUGIN_NAME="cooperative_cpu_reference"
VERSION="0.1.0"

def type_url(cls):
    return "type.googleapis.com/"+cls.DESCRIPTOR.full_name

def sha(data):
    return sha256(data).hexdigest()

def wire(msg):
    raw=msg.SerializeToString(deterministic=True)
    if not 0<len(raw)<=MAX_FRAME:
        raise ValueError("cooperative frame bound")
    return raw

def parse(raw, cls):
    if type(raw) is not bytes or not 0<len(raw)<=MAX_FRAME:
        raise ValueError("cooperative frame bound")
    try: obj=cls.FromString(raw)
    except DecodeError as exc: raise ValueError("invalid cooperative protobuf") from exc
    known=cls();known.CopyFrom(obj);known.DiscardUnknownFields()
    if known!=obj or wire(obj)!=raw:
        raise ValueError("unknown or noncanonical cooperative protobuf")
    return obj

def encode(raw):
    if type(raw) is not bytes or not 0<len(raw)<=MAX_FRAME:
        raise ValueError("cooperative frame bound")
    return b64encode(raw).decode("ascii")

def decode(s):
    if type(s) is not str or not 0<len(s)<=MAX_B64:
        raise ValueError("cooperative transport bound")
    try: raw=b64decode(s,validate=True)
    except (ValueError,UnicodeError) as exc: raise ValueError("invalid base64") from exc
    if encode(raw)!=s:
        raise ValueError("noncanonical base64")
    return raw

@dataclass(frozen=True)
class Route:
    operation: str
    input_class: type
    output_class: type
    assurances: tuple[str,...]
    @property
    def identity(self):
        return digest({"operation":self.operation,"version":VERSION,
                       "input":type_url(self.input_class),"output":type_url(self.output_class),
                       "input_descriptor":sha(self.input_class.DESCRIPTOR.file.serialized_pb),
                       "output_descriptor":sha(self.output_class.DESCRIPTOR.file.serialized_pb),
                       "assurances":self.assurances})
    def worker_operation(self,phase):
        if phase not in ("compute","verify"):raise ValueError("unknown phase")
        return "cooperative."+self.operation+"."+phase

def _route(name,ic,oc,*assurances):
    return Route(name,ic,oc,assurances)

ROUTES=MappingProxyType({r.operation:r for r in (
    _route("math.linear",math.LinearRequest,math.LinearResult,"exact_linear_checked"),
    _route("formal.integer",formal.VerifyRequest,formal.VerifyResult,"witness_rechecked","independent_exhaustion"),
    _route("formal.finite",backend.BackendRun,advanced.FiniteCertificate,"finite_unsat_exhaustion"),
    _route("optimization.schedule",opt.ScheduleRequest,opt.ScheduleResult,"feasibility_checked"),
    _route("optimization.allocation",opt.AllocationRequest,opt.AllocationResult,"feasibility_checked"),
    _route("planning.graph",plan.PlanRequest,plan.PlanResult,"plan_witness_checked"),
    _route("probability.bayes",prob.BayesRequest,prob.BayesResult,"numerical_replay"),
    _route("probability.beta",prob.BetaRequest,prob.BetaResult,"numerical_replay"),
    _route("physics.ode",physics.PhysicalRequest,physics.PhysicalResult,"numerical_replay"),
    _route("temporal.kalman",temporal.FilterRequest,temporal.FilterResult,"numerical_replay"),
    _route("temporal.hmm",temporal.HMMRequest,temporal.HMMResult,"numerical_replay"),
)})

def catalog():
    """Discovery metadata, explicitly not activation or host approval."""
    return tuple({"operation":r.operation,"input_type_url":type_url(r.input_class),
                  "output_type_url":type_url(r.output_class),"route_sha256":r.identity,
                  "assurances":r.assurances,"default_enabled":False,
                  "execution_authorized":False} for r in ROUTES.values())

def _matrix(rows):
    if not 1<=len(rows)<=4 or not 1<=len(rows[0].entries)<=4:
        raise ValueError("matrix bound")
    n=len(rows[0].entries)
    result=[]
    for row in rows:
        if len(row.entries)!=n:raise ValueError("ragged matrix")
        values=[]
        for x in row.entries:
            if not 1<=len(x)<=320:raise ValueError("rational bound")
            q=Fraction(x)
            if max(q.numerator.bit_length(),q.denominator.bit_length())>1024:
                raise ValueError("rational magnitude")
            values.append(q)
        result.append(values)
    return result

def _multiply(a,b):
    if len(a[0])!=len(b):raise ValueError("matrix dimension")
    return [[sum(x*y for x,y in zip(row,col)) for col in zip(*b)] for row in a]

def _det(a):
    n=len(a)
    if len(a[0])!=n:raise ValueError("not square")
    total=Fraction(0)
    for p in permutations(range(n)):
        term=Fraction((-1)**sum(p[i]>p[j] for i in range(n) for j in range(i+1,n)))
        for i,j in enumerate(p):term*=a[i][j]
        total+=term
    return total

def _verify_linear(req,out):
    a=_matrix(req.a)
    if list(out.limitations)!=["exact_rational_arithmetic","intent_not_verified","units_unspecified"]:
        raise ValueError("linear assurance metadata")
    if req.action=="determinant":
        if req.b or out.rows or not 1<=len(out.scalar)<=320 or Fraction(out.scalar)!=_det(a):
            raise ValueError("determinant mismatch")
    elif req.action=="multiply":
        if out.scalar or _matrix(out.rows)!=_multiply(a,_matrix(req.b)):
            raise ValueError("matrix product mismatch")
    elif req.action=="solve":
        b=_matrix(req.b);x=_matrix(out.rows)
        if (out.scalar or len(x)!=len(a) or any(len(row)!=1 for row in x)
                or any(len(row)!=1 for row in b) or not _det(a) or _multiply(a,x)!=b):
            raise ValueError("linear witness invalid or nonunique")
    else:raise ValueError("unsupported linear action")
    return "exact_linear_checked"

def compute(name,raw):
    route=ROUTES[name];parse(raw,route.input_class)
    if name=="math.linear":
        from .scientific_math import run_inert_specialist
        result=run_inert_specialist("linear",raw)
    elif name=="formal.integer":
        from .formal_wire import execute
        result=execute(raw)
    elif name=="formal.finite":
        from .formal_finite import prove_finite_frame
        result=prove_finite_frame(raw)
    elif name.startswith("optimization."):
        from .optimization_wire import execute
        result=execute(name.split(".")[1],raw)
    elif name=="planning.graph":
        from .planning_wire import execute
        result=execute(raw)
    elif name.startswith("probability."):
        from .probability_wire import execute
        result=execute(name.split(".")[1],raw)
    elif name=="physics.ode":
        from .physics_ode_wire import execute
        result=execute(raw)
    elif name.startswith("temporal."):
        from .temporal_practical_wire import execute
        result=execute(name.split(".")[1],raw)
    else:raise ValueError("unreviewed route")
    parse(result,route.output_class)
    return result

def _finite_fields(obj):
    # Reject NaN/Inf even in ancillary result fields not used by a verifier.
    for field,value in obj.ListFields():
        items=value if field.is_repeated else (value,)
        if field.type in (FieldDescriptor.TYPE_DOUBLE,FieldDescriptor.TYPE_FLOAT):
            if not all(isfinite(x) for x in items):raise ValueError("nonfinite result")
        elif field.type==FieldDescriptor.TYPE_MESSAGE:
            for x in items:_finite_fields(x)

def verify(name,raw,result):
    route=ROUTES[name];req=parse(raw,route.input_class);out=parse(result,route.output_class)
    _finite_fields(out)
    if name=="math.linear":
        return _verify_linear(req,out)
    if name=="formal.integer":
        from .formal_wire import decode_result
        checked=decode_result(result,raw)
        if checked.status=="SAT":return "witness_rechecked"
        if checked.status=="UNSAT_EXHAUSTIVE":return "independent_exhaustion"
    elif name=="formal.finite":
        from .formal_finite import verify_finite_frame
        if verify_finite_frame(raw,result):return "finite_unsat_exhaustion"
    elif name.startswith("optimization."):
        from .optimization_wire import decode_result
        if decode_result(name.split(".")[1],raw,result).status in ("OPTIMAL","FEASIBLE"):
            return "feasibility_checked"
    elif name=="planning.graph":
        from .planning_wire import decode_result
        if decode_result(raw,result).status in ("OPTIMAL","FEASIBLE"):
            return "plan_witness_checked"
    elif name.startswith("probability."):
        from .probability_wire import decode_result
        if decode_result(name.split(".")[1],raw,result).status=="OK":return "numerical_replay"
    elif name=="physics.ode":
        from .physics_ode_wire import verify as check
        if check(raw,result).status in ("OK","EVENT_STOP"):return "numerical_replay"
    elif name.startswith("temporal."):
        from .temporal_practical_wire import verify as check
        if check(name.split(".")[1],raw,result).status=="OK":return "numerical_replay"
    raise ValueError("no independently admissible result")

def verification_binding(route,raw,result,assurance):
    return digest({"route":route.identity,"input":sha(raw),"result":sha(result),
                   "assurance":assurance})

class CooperativeCpu:
    """Existing trusted worker plugin interface; no default installation."""
    def manifest(self):
        ops=[]
        for route in ROUTES.values():
            for phase in ("compute","verify"):
                name=route.worker_operation(phase)
                inp=Shape((("frame",MAX_B64),) if phase=="compute" else
                          (("frame",MAX_B64),("result",MAX_B64)))
                out=Shape((("frame",MAX_B64),) if phase=="compute" else
                          (("receipt",64),("assurance",64)))
                # Runtime's generic label must never promise semantic proof.
                ops.append(Operation(name,name,inp,out,assurance="unverified"))
        return Manifest(PLUGIN_NAME,VERSION,tuple(ops))
    def health(self):return True
    def self_test(self):
        q=math.LinearRequest(action="determinant")
        q.a.add(entries=["2"])
        raw=wire(q)
        return verify("math.linear",raw,compute("math.linear",raw))=="exact_linear_checked"
    def handle(self,operation,payload):
        for route in ROUTES.values():
            if operation==route.worker_operation("compute"):
                return {"frame":encode(compute(route.operation,decode(payload["frame"])))}
            if operation==route.worker_operation("verify"):
                raw=decode(payload["frame"]);result=decode(payload["result"])
                assurance=verify(route.operation,raw,result)
                if assurance not in route.assurances:raise ValueError("invalid assurance")
                return {"receipt":verification_binding(route,raw,result,assurance),
                        "assurance":assurance}
        raise ValueError("unreviewed cooperative operation")
