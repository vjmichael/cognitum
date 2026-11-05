"""C11 strict typed Protobuf facade; no host launch or execution authority.

Dispatch strictly by registered component domain, never dynamic Python code.
Canonical frames prevent unknown fields and alternate encodings. Result claims
are rechecked independently for feasibility, not solver optimality.
"""
from hashlib import sha256
from google.protobuf.message import DecodeError

from .proto import optimization_pb2 as pb
from .optimization_schedule import (
    Job, ScheduleProblem, ScheduledJob, validate as validate_schedule,
    verify_schedule, optimize_schedule,
)
from .optimization_allocation import (
    Quantity, ResourceConstraint, AllocationProblem,
    validate as validate_allocation, verify_allocation, minimize_allocation,
)

MAX_FRAME=16384
MAX_RESULT=8192
KINDS={
    "schedule":(pb.ScheduleRequest,pb.ScheduleResult),
    "allocation":(pb.AllocationRequest,pb.AllocationResult),
}
STATUSES=frozenset({"OPTIMAL","FEASIBLE","INFEASIBLE","UNKNOWN","UNSUPPORTED","INVALID_SOLUTION"})


def _read(frame,cls,limit):
    if type(frame) is not bytes or not 0<len(frame)<=limit:
        raise ValueError("invalid optimization Protobuf frame")
    obj=cls()
    try:
        obj.ParseFromString(frame)
    except DecodeError as exc:
        raise ValueError("invalid optimization Protobuf") from exc
    clone=cls()
    clone.CopyFrom(obj)
    clone.DiscardUnknownFields()
    if clone!=obj or obj.SerializeToString(deterministic=True)!=frame:
        raise ValueError("unknown/duplicate/noncanonical optimization Protobuf")
    return obj


def _write(obj,limit):
    frame=obj.SerializeToString(deterministic=True)
    if not 0<len(frame)<=limit:
        raise ValueError("optimization Protobuf response oversized")
    return frame


def _as_schedule(req):
    if req.schema_version!=1:
        raise ValueError("unsupported schedule schema")
    problem=ScheduleProblem(
        req.horizon,tuple(req.resources),
        tuple(Job(j.name,j.duration,j.release,j.deadline,
                  tuple(j.eligible_resources),tuple(j.after))
              for j in req.jobs),
        req.unit,
    )
    return validate_schedule(problem)


def _as_allocation(req):
    if req.schema_version!=1:
        raise ValueError("unsupported allocation schema")
    problem=AllocationProblem(
        tuple(Quantity(q.name,q.lower,q.upper,q.cost) for q in req.quantities),
        tuple(ResourceConstraint(tuple(c.coefficients),c.relation,c.rhs)
              for c in req.constraints),
        req.unit,
    )
    return validate_allocation(problem)


def execute(kind:str, frame:bytes) -> bytes:
    if kind not in KINDS:
        raise ValueError("unknown optimization domain")
    request=_read(frame,KINDS[kind][0],MAX_FRAME)
    if not 10<=request.timeout_ms<=10000:
        raise ValueError("bounded optimization time required")
    digest=sha256(frame).hexdigest()
    if kind=="schedule":
        problem=_as_schedule(request)
        outcome=optimize_schedule(problem,time_limit_ms=request.timeout_ms)
        if outcome.status not in STATUSES:
            raise ValueError("unknown schedule solver status")
        reply=pb.ScheduleResult(schema_version=1,status=outcome.status,
                                limitations=outcome.limitations,request_sha256=digest)
        if outcome.status in ("OPTIMAL","FEASIBLE"):
            if not verify_schedule(problem,outcome.assignments):
                raise ValueError("schedule invalid before encoding")
            reply.has_objective=True
            reply.makespan=max(a.end for a in outcome.assignments)
            for a in outcome.assignments:
                reply.assignments.add(name=a.name,resource=a.resource,start=a.start,end=a.end)
            if outcome.solver_bound is not None:
                reply.solver_bound=str(outcome.solver_bound)
        return _write(reply,MAX_RESULT)
    problem=_as_allocation(request)
    outcome=minimize_allocation(problem,time_limit_ms=request.timeout_ms)
    if outcome.status not in STATUSES:
        raise ValueError("unknown allocation solver status")
    reply=pb.AllocationResult(schema_version=1,status=outcome.status,
                              limitations=outcome.limitations,request_sha256=digest)
    if outcome.status in ("OPTIMAL","FEASIBLE"):
        if not verify_allocation(problem,outcome.values):
            raise ValueError("allocation invalid before encoding")
        reply.values.extend(outcome.values)
        reply.has_objective=True
        reply.objective=sum(q.cost*v for q,v in zip(problem.quantities,outcome.values))
        if outcome.solver_bound is not None:
            reply.solver_bound=str(outcome.solver_bound)
        if outcome.gap is not None:
            reply.gap=str(outcome.gap)
    return _write(reply,MAX_RESULT)


def decode_result(kind:str, request_frame:bytes, response_frame:bytes):
    if kind not in KINDS:
        raise ValueError("unknown optimization domain")
    request=_read(request_frame,KINDS[kind][0],MAX_FRAME)
    response=_read(response_frame,KINDS[kind][1],MAX_RESULT)
    if (response.schema_version!=1 or response.request_sha256!=sha256(request_frame).hexdigest()
            or response.status not in STATUSES):
        raise ValueError("optimization result mismatch")
    if kind=="schedule":
        problem=_as_schedule(request)
        if response.status in ("OPTIMAL","FEASIBLE"):
            items=tuple(ScheduledJob(a.name,a.resource,a.start,a.end) for a in response.assignments)
            if (not response.has_objective or not verify_schedule(problem,items)
                    or max(a.end for a in items)!=response.makespan):
                raise ValueError("invalid schedule result witness")
        elif response.has_objective or response.assignments or response.makespan or response.solver_bound:
            raise ValueError("nonfeasible schedule with fabricated witness")
    else:
        problem=_as_allocation(request)
        if response.status in ("OPTIMAL","FEASIBLE"):
            vals=tuple(response.values)
            if (not response.has_objective or not verify_allocation(problem,vals)
                    or sum(q.cost*v for q,v in zip(problem.quantities,vals))!=response.objective):
                raise ValueError("invalid allocation result witness")
        elif (response.has_objective or response.values or response.objective
              or response.solver_bound or response.gap):
            raise ValueError("nonfeasible allocation with fabricated witness")
    # No claim that a remote status labeled OPTIMAL was independently proved:
    # only exact feasibility and objective consistency are independently checked.
    return response
