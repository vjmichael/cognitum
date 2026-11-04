"""Canonical C12 Protobuf boundary; planning never executes host effects."""
from hashlib import sha256
from google.protobuf.message import DecodeError
from .proto import planning_pb2 as pb
from .planning_graph import Action,PlanProblem,PlanResult,validate,plan,check_plan

MAX_FRAME=16384
MAX_RESULT=8192
STATUSES=frozenset(("OPTIMAL","FEASIBLE","UNREACHABLE_EXHAUSTIVE",
                    "UNKNOWN_LIMIT","INVALID_SOLUTION","UNSUPPORTED"))


def _parse(frame,cls,limit):
    if type(frame) is not bytes or not 0<len(frame)<=limit:
        raise ValueError("invalid planning frame size")
    obj=cls()
    try:
        obj.ParseFromString(frame)
    except DecodeError as exc:
        raise ValueError("invalid planning wire") from exc
    clean=cls()
    clean.CopyFrom(obj)
    clean.DiscardUnknownFields()
    if obj!=clean or obj.SerializeToString(deterministic=True)!=frame:
        raise ValueError("noncanonical planning wire")
    return obj


def _problem(req):
    if req.schema_version!=1 or req.algorithm not in ("dijkstra","astar","bfs","dag_dp"):
        raise ValueError("unsupported planning schema/algorithm")
    return validate(PlanProblem(
        facts=tuple(req.facts),initial=tuple(req.initial),
        goal=tuple(req.goal),goal_forbids=tuple(req.goal_forbids),
        actions=tuple(Action(a.name,tuple(a.requires),tuple(a.forbids),
                             tuple(a.add),tuple(a.delete),a.cost,a.risk)
                      for a in req.actions),
        horizon=req.horizon,risk_budget=req.risk_budget,
    ))


def execute(request:bytes)->bytes:
    req=_parse(request,pb.PlanRequest,MAX_FRAME)
    p=_problem(req)
    result=plan(p,algorithm=req.algorithm)
    if result.status not in STATUSES:
        raise ValueError("unknown planning status")
    wire=pb.PlanResult(schema_version=1,status=result.status,
                       expanded_states=result.expanded_states,
                       backend=result.backend,limitations=result.limitations,
                       request_sha256=sha256(request).hexdigest())
    if result.status in ("OPTIMAL","FEASIBLE"):
        checked=check_plan(p,result.actions)
        if checked is None or checked!=(result.final_state,result.total_cost,result.total_risk):
            raise ValueError("planner solution fails independent replay")
        wire.has_result=True
        wire.actions.extend(result.actions)
        wire.final_state.extend(result.final_state)
        wire.total_cost=result.total_cost
        wire.total_risk=result.total_risk
    data=wire.SerializeToString(deterministic=True)
    if not 0<len(data)<=MAX_RESULT:
        raise ValueError("planning response too large")
    return data


def decode_result(request:bytes,response:bytes):
    req=_parse(request,pb.PlanRequest,MAX_FRAME)
    p=_problem(req)
    result=_parse(response,pb.PlanResult,MAX_RESULT)
    if (result.schema_version!=1 or result.status not in STATUSES
            or result.request_sha256!=sha256(request).hexdigest()
            or result.backend!="networkx_"+req.algorithm
                and result.status!="UNSUPPORTED"
            or result.expanded_states>4096):
        raise ValueError("planning response contract mismatch")
    if result.status in ("OPTIMAL","FEASIBLE"):
        if not result.has_result:
            raise ValueError("missing plan witness")
        checked=check_plan(p,tuple(result.actions))
        if (checked is None or checked!=(tuple(result.final_state),
                 result.total_cost,result.total_risk)):
            raise ValueError("plan witness failed independent simulator")
    elif (result.has_result or result.actions or result.final_state
          or result.total_cost or result.total_risk):
        raise ValueError("no-plan result fabricated witness")
    # The search-optimality or exhaustive-unreachability label is *not*
    # itself independently proved by this decoder. We validate witnesses.
    return result
