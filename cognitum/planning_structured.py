"""C12 P3 resource-free temporal precedence and bounded ordered HTN references.

No effects or actions are performed. HTN returns action indices replayed against
C12 P1 STRIPS; temporal results are integer schedules checked independently.
Not unrestricted HDDL, PDDL2.1 temporal planning, or resource scheduling.
"""
from __future__ import annotations

from collections import deque
from hashlib import sha256
import re
import time

from cognitum.planning import _decode, _encode, _task, replay_plan, NAME, TRACE
from cognitum.proto import planning_pb2 as classical
from cognitum.proto import planning_structured_pb2 as p

MAX_HTN_FRAME = 131072
MAX_METHODS = 48
MAX_ROOTS = 12
MAX_EXPANSIONS = 4096
MAX_PRIMITIVES = 48
MAX_TIMED = 128
MAX_TIMESTAMP = 1_000_000_000


def _frame(req):
    return req.SerializeToString(deterministic=True)


def _hash(data):
    return sha256(data).digest()


def _htn(req):
    if req.schema_version != 1 or not TRACE.fullmatch(req.trace_id):
        raise ValueError('INVALID_HTN_REQUEST')
    if not (1 <= len(req.root_tasks) <= MAX_ROOTS and 1 <= len(req.methods) <= MAX_METHODS and
            1 <= req.max_expansions <= MAX_EXPANSIONS):
        raise ValueError('INVALID_HTN_BOUNDS')
    c = _decode(req.classical_request, classical.PlanningRequest)
    task = _task(c)
    primitives = {a.id:i for i,a in enumerate(c.task.actions)}
    methods = {}
    identifiers = set()
    for method in req.methods:
        if (not NAME.fullmatch(method.method_id) or method.method_id in identifiers or
                not NAME.fullmatch(method.abstract_task_id) or len(method.subtasks) > 8 or
                any(not NAME.fullmatch(t) for t in method.subtasks)):
            raise ValueError('INVALID_METHOD')
        identifiers.add(method.method_id)
        methods.setdefault(method.abstract_task_id, []).append(tuple(method.subtasks))
    if set(primitives).intersection(methods):
        raise ValueError('ABSTRACT_PRIMITIVE_COLLISION')
    for tasks in [req.root_tasks, *(m.subtasks for m in req.methods)]:
        if any(x not in primitives and x not in methods for x in tasks):
            raise ValueError('UNDECLARED_SUBTASK')
    # Reject recursion to ensure that a completed exhaustive search is meaningful.
    edges = {task_id:{s for seq in paths for s in seq if s in methods}
             for task_id, paths in methods.items()}
    visited, active = set(), set()
    def visit(node):
        if node in active: raise ValueError('CYCLIC_HTN_METHODS')
        if node in visited: return
        active.add(node)
        for child in edges[node]: visit(child)
        active.remove(node)
        visited.add(node)
    for node in methods:visit(node)
    return task, primitives, methods


def _enumerate_htn(req, *, independent=False):
    task, primitives, methods = _htn(req)
    pending = deque([tuple(req.root_tasks)])
    count = 0
    best = None
    complete = True
    while pending:
        if count >= req.max_expansions:
            complete = False
            break
        current = pending.popleft() if independent else pending.pop()
        count += 1
        if len(current) > MAX_PRIMITIVES:
            complete = False
            continue
        spot = next((i for i,t in enumerate(current) if t in methods), None)
        if spot is not None:
            options = methods[current[spot]]
            for sub in options:
                nxt = current[:spot] + sub + current[spot+1:]
                pending.append(nxt)
            continue
        indices = [primitives[name] for name in current]
        try:
            cost = replay_plan(task, indices)
        except ValueError:
            continue
        if best is None or (cost, tuple(indices)) < (best[0], tuple(best[1])):
            best = cost, indices
    return best, complete, count


def run_htn(frame, *, enabled=False, host_authorized=False):
    start_ns=time.monotonic_ns()
    raw=frame if isinstance(frame,bytes) and len(frame)<=MAX_HTN_FRAME else b''
    result=p.HtnResult(schema_version=1,request_sha256=_hash(raw),status=p.HTN_REJECTED,
                       reason_code='INVALID_FRAME', backend_id='reference-grounded-ordered-htn')
    try:
        if not raw: raise ValueError('INVALID_FRAME')
        req=_decode(raw,p.HtnRequest)
        _htn(req)
        result.trace_id=req.trace_id
        if not host_authorized:raise ValueError('HOST_AUTHORIZATION_REQUIRED')
        if not enabled:raise ValueError('HTN_DISABLED')
        best,complete,count=_enumerate_htn(req)
        result.explored_decompositions=count
        if best is None:
            result.status=p.VERIFIED_HTN_NO_PLAN if complete else p.HTN_UNKNOWN
            result.complete_search_verified=complete
            result.reason_code='EXHAUSTED_FINITE_HTN_DECOMPOSITIONS' if complete else 'HTN_BUDGET_EXHAUSTED'
        else:
            cost, indices=best
            result.action_indices.extend(indices)
            result.total_cost=cost
            result.plan_verified=True
            result.complete_search_verified=complete
            result.status=p.VERIFIED_HTN_OPTIMAL if complete else p.VERIFIED_HTN_PLAN
            result.reason_code='FINITE_HTN_OPTIMUM' if complete else 'VALID_PARTIAL_HTN_SEARCH'
    except (ValueError,TypeError,RecursionError) as exc:
        result.status=p.HTN_REJECTED
        result.reason_code=str(exc)[:100] or 'INVALID_HTN_REQUEST'
    result.wall_ns=time.monotonic_ns()-start_ns
    return _frame(result)


def verify_htn(frame, result_frame):
    rec=p.StructuredReceipt(request_sha256=_hash(frame),result_sha256=_hash(result_frame),
                            reason_code='INVALID_EVIDENCE')
    try:
        req=_decode(frame,p.HtnRequest)
        result=_decode(result_frame,p.HtnResult)
        task, primitives, methods=_htn(req)
        if (result.schema_version != 1 or result.request_sha256!=rec.request_sha256 or
                result.trace_id!=req.trace_id or result.backend_id!='reference-grounded-ordered-htn' or
                not (1 <= result.explored_decompositions <= req.max_expansions) or
                result.status not in (p.VERIFIED_HTN_OPTIMAL,p.VERIFIED_HTN_PLAN,p.VERIFIED_HTN_NO_PLAN)):
            return rec
        # Only a certified exhaustive claim requires complete independent search.
        # A partial witness may be verified by grammar derivation + STRIPS replay
        # even if a different enumeration order has not reached that witness.
        best = complete = None
        if result.status != p.VERIFIED_HTN_PLAN:
            best,complete,_explored=_enumerate_htn(req,independent=True)
            if complete and result.explored_decompositions != _explored:
                return rec
        if result.status==p.VERIFIED_HTN_NO_PLAN:
            if not (complete and result.complete_search_verified and not result.plan_verified and not result.action_indices and not result.total_cost and best is None and result.reason_code=='EXHAUSTED_FINITE_HTN_DECOMPOSITIONS'):
                return rec
            rec.optimality_verified=True
        else:
            if not result.plan_verified or (result.status==p.VERIFIED_HTN_OPTIMAL and best is None):
                return rec
            cost=replay_plan(task,result.action_indices)
            if cost != result.total_cost:
                return rec
            # Independent grammar derivation: require this exact primitive sequence.
            if not _derived(req, tuple(result.action_indices), primitives, methods):
                return rec
            if result.status==p.VERIFIED_HTN_OPTIMAL:
                if not complete or not result.complete_search_verified or cost!=best[0] or result.reason_code!='FINITE_HTN_OPTIMUM':
                    return rec
                rec.optimality_verified=True
            elif result.complete_search_verified or result.reason_code!='VALID_PARTIAL_HTN_SEARCH':
                return rec
        rec.evidence_valid=True
        rec.reason_code='REPLAYED_GROUNDED_HTN_AND_CHECKED_DECOMPOSITION'
    except (ValueError,TypeError,RecursionError,KeyError):
        return rec
    return rec


def _derived(req, target, primitives, methods):
    """Separately verify a claimed primitive sequence belongs to the HTN grammar."""
    from functools import lru_cache
    primitive_by_idx={i:name for name,i in primitives.items()}
    try: names=tuple(primitive_by_idx[i] for i in target)
    except KeyError:return False
    @lru_cache(None)
    def derive(terms, start, end):
        if not terms:return start==end
        if len(terms)>MAX_PRIMITIVES:return False
        head,*tail=terms
        if head in primitives:
            return start<end and names[start]==head and derive(tuple(tail),start+1,end)
        for method in methods[head]:
            if derive(tuple(method)+tuple(tail),start,end):
                return True
        return False
    return derive(tuple(req.root_tasks),0,len(names))


def _temporal(req):
    if req.schema_version!=1 or not TRACE.fullmatch(req.trace_id) or not (1<=len(req.actions)<=MAX_TIMED):
        raise ValueError('INVALID_TEMPORAL_REQUEST')
    nodes={}
    for a in req.actions:
        if (not NAME.fullmatch(a.id) or a.id in nodes or not (1<=a.duration<=MAX_TIMESTAMP) or
                a.earliest_start>MAX_TIMESTAMP or a.latest_finish>MAX_TIMESTAMP or
                len(a.predecessors)!=len(set(a.predecessors))):
            raise ValueError('INVALID_TEMPORAL_ACTION')
        nodes[a.id]=a
    if any(pre not in nodes or pre==a.id for a in req.actions for pre in a.predecessors):
        raise ValueError('INVALID_PRECEDENCE')
    return nodes


def run_temporal(frame, *, enabled=False, host_authorized=False):
    start_ns=time.monotonic_ns()
    raw=frame if isinstance(frame,bytes) and len(frame)<=MAX_HTN_FRAME else b''
    result=p.TemporalResult(schema_version=1,request_sha256=_hash(raw),status=p.TEMPORAL_REJECTED,
                            reason_code='INVALID_FRAME', backend_id='networkx-precedence-dag')
    try:
        if not raw:raise ValueError('INVALID_FRAME')
        req=_decode(raw,p.TemporalRequest)
        nodes=_temporal(req)
        result.trace_id=req.trace_id
        if not host_authorized:raise ValueError('HOST_AUTHORIZATION_REQUIRED')
        if not enabled:raise ValueError('TEMPORAL_DISABLED')
        import networkx as nx
        g=nx.DiGraph()
        for a in req.actions:
            g.add_node(a.id)
            for pre in a.predecessors:g.add_edge(pre,a.id)
        try:
            order=list(nx.topological_sort(g))
        except nx.NetworkXUnfeasible:
            result.status=p.VERIFIED_TEMPORAL_INFEASIBLE
            result.independently_verified=True
            result.reason_code='POSITIVE_DURATION_PRECEDENCE_CYCLE'
            result.wall_ns=time.monotonic_ns()-start_ns
            return _frame(result)
        starts={}
        for name in order:
            a=nodes[name]
            starts[name]=max([a.earliest_start]+[starts[pre]+nodes[pre].duration for pre in a.predecessors])
        if any(a.latest_finish and starts[a.id]+a.duration>a.latest_finish for a in req.actions):
            result.status=p.VERIFIED_TEMPORAL_INFEASIBLE
            result.independently_verified=True
            result.reason_code='EARLIEST_SCHEDULE_VIOLATES_DEADLINE'
        else:
            result.status=p.VERIFIED_TEMPORAL_EARLIEST
            result.independently_verified=True
            result.reason_code='EARLIEST_PRECEDENCE_SCHEDULE'
            result.makespan=max(starts[a.id]+a.duration for a in req.actions)
            for a in req.actions:result.starts.add(id=a.id,start=starts[a.id])
    except (ValueError,TypeError) as exc:
        result.status=p.TEMPORAL_REJECTED
        result.reason_code=str(exc)[:100] or 'INVALID_TEMPORAL_REQUEST'
    result.wall_ns=time.monotonic_ns()-start_ns
    return _frame(result)


def verify_temporal(frame,result_frame):
    rec=p.StructuredReceipt(request_sha256=_hash(frame),result_sha256=_hash(result_frame),
                            reason_code='INVALID_EVIDENCE')
    try:
        req=_decode(frame,p.TemporalRequest)
        result=_decode(result_frame,p.TemporalResult)
        nodes=_temporal(req)
        if (result.schema_version!=1 or result.request_sha256!=rec.request_sha256 or
                result.trace_id!=req.trace_id or result.backend_id!='networkx-precedence-dag' or
                not result.independently_verified):
            return rec
        # Separate, dependency-driven topological check (without NetworkX).
        indeg={name:len(a.predecessors) for name,a in nodes.items()}
        successors={name:[] for name in nodes}
        for name,a in nodes.items():
            for pre in a.predecessors:successors[pre].append(name)
        queue=deque(name for name,n in indeg.items() if n==0)
        starts={}
        while queue:
            name=queue.popleft()
            a=nodes[name]
            starts[name]=max([a.earliest_start]+[starts[pre]+nodes[pre].duration for pre in a.predecessors])
            for child in successors[name]:
                indeg[child]-=1
                if indeg[child]==0:queue.append(child)
        cycle=len(starts)!=len(nodes)
        deadline=not cycle and any(a.latest_finish and starts[a.id]+a.duration>a.latest_finish for a in req.actions)
        if result.status==p.VERIFIED_TEMPORAL_INFEASIBLE:
            if result.starts or result.makespan or not (cycle or deadline):return rec
            if (cycle and result.reason_code!='POSITIVE_DURATION_PRECEDENCE_CYCLE') or (not cycle and result.reason_code!='EARLIEST_SCHEDULE_VIOLATES_DEADLINE'):
                return rec
        elif result.status==p.VERIFIED_TEMPORAL_EARLIEST:
            if cycle or deadline or result.reason_code!='EARLIEST_PRECEDENCE_SCHEDULE':return rec
            supplied={x.id:x.start for x in result.starts}
            if (len(supplied)!=len(result.starts) or supplied!=starts or
                    result.makespan!=max(starts[a.id]+a.duration for a in req.actions)):
                return rec
        else:return rec
        rec.evidence_valid=True
        rec.optimality_verified=True  # Earliest schedule / infeasibility within precedence-only model.
        rec.reason_code='INDEPENDENT_PRECEDENCE_CONSTRAINT_CHECK'
    except (ValueError,TypeError,KeyError):
        return rec
    return rec


def audit(frame,result_frame,kind):
    if kind=='htn':
        req=_decode(frame,p.HtnRequest);out=_decode(result_frame,p.HtnResult)
        r=verify_htn(frame,result_frame);status=p.HtnStatus.Name(out.status)
    elif kind=='temporal':
        req=_decode(frame,p.TemporalRequest);out=_decode(result_frame,p.TemporalResult)
        r=verify_temporal(frame,result_frame);status=p.TemporalStatus.Name(out.status)
    else:raise ValueError('INVALID_CAPABILITY')
    return _frame(p.StructuredAudit(schema_version=1,request_sha256=r.request_sha256,
               result_sha256=r.result_sha256,trace_id=req.trace_id,capability_id='c12-'+kind,
               status=status,evidence_valid=r.evidence_valid,optimality_verified=r.optimality_verified,
               reason_code=r.reason_code, wall_ns=out.wall_ns, backend_id=out.backend_id))
