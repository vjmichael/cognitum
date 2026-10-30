"""C12 P1: bounded grounded STRIPS planning, independent replay and exact finite checks.

Uses established NetworkX shortest paths when selected; includes conventional A*
with admissible h_max delete-relaxation and optional weighted satisficing search.
No PDDL parser, model-controlled code, tool execution or Lu authorization.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import hashlib
import heapq
import itertools
import re
import time

from cognitum.proto import planning_pb2 as p

MAX_FRAME = 65536
MAX_RESPONSE = 65536
MAX_TIME_MS = 3000
MAX_FACTS = 24
MAX_ACTIONS = 96
MAX_STATES = 1024
MAX_PLAN_LENGTH = 512
NAME = re.compile(r'[A-Za-z][A-Za-z0-9_.:-]{0,63}\Z', re.ASCII)
TRACE = re.compile(r'[A-Za-z0-9_.:-]{0,64}\Z', re.ASCII)
ENGINES = {p.NETWORKX_DIJKSTRA, p.ASTAR_HMAX, p.WEIGHTED_ASTAR_HMAX, p.NETWORKX_BFS}


def _encode(msg, cap=MAX_RESPONSE):
    frame = msg.SerializeToString(deterministic=True)
    if len(frame) > cap:
        raise ValueError('FRAME_TOO_LARGE')
    return frame


def _decode(frame, cls):
    if not isinstance(frame, bytes) or len(frame) > MAX_FRAME:
        raise ValueError('INVALID_FRAME')
    obj = cls()
    try:
        obj.ParseFromString(frame)
        # Refuse unknown fields, including unsanctioned host fields.
        clean = cls()
        clean.CopyFrom(obj)
        clean.DiscardUnknownFields()
        if _encode(clean, MAX_FRAME) != frame:
            raise ValueError('NONCANONICAL_OR_UNKNOWN_FRAME')
    except Exception as exc:
        raise ValueError('INVALID_PROTOBUF') from exc
    return obj


def _mask(indices, size, tag):
    values = list(indices)
    if len(values) != len(set(values)) or any(v >= size for v in values):
        raise ValueError('INVALID_' + tag)
    return sum(1 << v for v in values)


@dataclass(frozen=True)
class Action:
    req_true: int
    req_false: int
    add: int
    remove: int
    cost: int


@dataclass(frozen=True)
class Task:
    actions: tuple[Action, ...]
    start: int
    goal_true: int
    goal_false: int
    facts: int
    max_states: int
    max_expansions: int


def _task(req):
    if req.schema_version != 1 or not TRACE.fullmatch(req.trace_id):
        raise ValueError('INVALID_REQUEST')
    if req.engine not in ENGINES or req.timeout_ms > MAX_TIME_MS:
        raise ValueError('INVALID_ENGINE_OR_LIMIT')
    t = req.task
    if not (1 <= len(t.facts) <= MAX_FACTS and 1 <= len(t.actions) <= MAX_ACTIONS):
        raise ValueError('INVALID_DOMAIN_SIZE')
    if len(set(t.facts)) != len(t.facts) or any(not NAME.fullmatch(f) for f in t.facts):
        raise ValueError('INVALID_FACTS')
    if (t.max_states > MAX_STATES or t.max_expansions > MAX_STATES or
            (t.max_states and t.max_states < 2) or
            (t.max_expansions and t.max_expansions < 1)):
        raise ValueError('INVALID_SEARCH_BUDGET')
    n = len(t.facts)
    start = _mask(t.initial_true, n, 'INITIAL')
    gtrue, gfalse = _mask(t.goal_true, n, 'GOAL_TRUE'), _mask(t.goal_false, n, 'GOAL_FALSE')
    if gtrue & gfalse:
        raise ValueError('CONTRADICTORY_GOAL')
    actions = []
    ids = set()
    for a in t.actions:
        if not NAME.fullmatch(a.id) or a.id in ids or not (1 <= a.cost <= 1_000_000):
            raise ValueError('INVALID_ACTION')
        ids.add(a.id)
        tr = _mask(a.require_true, n, 'PRECONDITION')
        fl = _mask(a.require_false, n, 'PRECONDITION')
        add = _mask(a.add, n, 'EFFECT')
        remove = _mask(a.remove, n, 'EFFECT')
        if tr & fl or add & remove or not (add | remove):
            raise ValueError('CONFLICTING_ACTION')
        actions.append(Action(tr, fl, add, remove, a.cost))
    if req.engine == p.NETWORKX_BFS and any(a.cost != 1 for a in actions):
        raise ValueError('BFS_REQUIRES_UNIT_COSTS')
    return Task(tuple(actions), start, gtrue, gfalse, n, t.max_states or 256, t.max_expansions or 256)


def _goal(t, state):
    return state & t.goal_true == t.goal_true and not state & t.goal_false


def _move(action, state):
    if (state & action.req_true != action.req_true) or (state & action.req_false):
        return None
    nxt = (state | action.add) & ~action.remove
    return nxt if nxt != state else None


def replay_plan(t, indices):
    """Check a plan without importing the search solver or trusting backend output."""
    if len(indices) > MAX_PLAN_LENGTH:
        raise ValueError('PLAN_TOO_LONG')
    state, cost = t.start, 0
    for i in indices:
        if i >= len(t.actions):
            raise ValueError('UNKNOWN_ACTION')
        next_state = _move(t.actions[i], state)
        if next_state is None:
            raise ValueError('INAPPLICABLE_ACTION')
        state = next_state
        cost += t.actions[i].cost
    if not _goal(t, state):
        raise ValueError('GOAL_NOT_REACHED')
    return cost


def _hmax(t, state):
    """Admissible positive-goal h_max delete-relaxation; false goals ignored."""
    dist = [0 if state & (1 << i) else float('inf') for i in range(t.facts)]
    for _ in range(t.facts):
        change = False
        for action in t.actions:
            needed = [dist[j] for j in range(t.facts) if action.req_true & (1 << j)]
            candidate = action.cost + (max(needed) if needed else 0)
            for j in range(t.facts):
                if action.add & (1 << j) and candidate < dist[j]:
                    dist[j] = candidate
                    change = True
        if not change:
            break
    goals = [dist[i] for i in range(t.facts) if t.goal_true & (1 << i)]
    return max(goals, default=0)


def _astar(t, engine, cutoff):
    weight = 2 if engine == p.WEIGHTED_ASTAR_HMAX else 1
    pq = [(weight * _hmax(t, t.start), 0, 0, t.start)]
    best = {t.start: 0}
    parents = {}
    expanded = 0
    serial = itertools.count(1)
    while pq and expanded < t.max_expansions and time.monotonic() < cutoff:
        _, cost, _, state = heapq.heappop(pq)
        if best[state] != cost:
            continue
        if _goal(t, state):
            path = []
            while state != t.start:
                state, action = parents[state]
                path.append(action)
            path.reverse()
            return path, expanded, len(best), 'FOUND'
        expanded += 1
        for i, action in enumerate(t.actions):
            nxt = _move(action, state)
            if nxt is None:
                continue
            new_cost = cost + action.cost
            if new_cost >= best.get(nxt, float('inf')):
                continue
            if nxt not in best and len(best) >= t.max_states:
                return None, expanded, len(best), 'RESOURCE_EXHAUSTED'
            h = _hmax(t, nxt)
            if h == float('inf'):
                continue
            best[nxt] = new_cost
            parents[nxt] = (state, i)
            heapq.heappush(pq, (new_cost + weight * h, new_cost, next(serial), nxt))
    if pq:
        return None, expanded, len(best), 'RESOURCE_EXHAUSTED'
    return None, expanded, len(best), 'FRONTIER_EXHAUSTED'


def _graph(t, cutoff):
    """Independent reachable-state graph enumeration with an explicit completion bit."""
    import networkx as nx
    graph = nx.DiGraph()
    graph.add_node(t.start)
    pending = deque([t.start])
    expanded = 0
    while pending:
        if expanded >= t.max_expansions or time.monotonic() >= cutoff:
            return graph, False, expanded
        state = pending.popleft()
        expanded += 1
        for i, action in enumerate(t.actions):
            nxt = _move(action, state)
            if nxt is None:
                continue
            if nxt not in graph:
                if len(graph) >= t.max_states:
                    return graph, False, expanded
                graph.add_node(nxt)
                pending.append(nxt)
            prior = graph.get_edge_data(state, nxt)
            if prior is None or action.cost < prior['weight']:
                graph.add_edge(state, nxt, weight=action.cost, action=i)
    return graph, True, expanded


def _shortest(t, graph, engine):
    import networkx as nx
    goals = [n for n in graph if _goal(t, n)]
    if not goals:
        return None
    try:
        if engine == p.NETWORKX_BFS:
            paths = nx.single_source_shortest_path(graph, t.start)
            end = min(goals, key=lambda g: len(paths.get(g, [None] * (len(graph)+1))))
            route = paths.get(end)
        else:
            lengths, paths = nx.single_source_dijkstra(graph, t.start, weight='weight')
            end = min((g for g in goals if g in lengths), key=lambda g: lengths[g], default=None)
            route = paths.get(end) if end is not None else None
    except (nx.NetworkXNoPath, ValueError):
        return None
    if route is None:
        return None
    return [graph[a][b]['action'] for a, b in zip(route, route[1:])]


def _certify(t, indices, status, cutoff):
    """Independent complete bounded reachable-state check, separate from A*."""
    graph, complete, explored = _graph(t, cutoff)
    if not complete:
        return False, explored
    opt = _shortest(t, graph, p.NETWORKX_DIJKSTRA)
    if status == p.VERIFIED_UNREACHABLE:
        return opt is None, explored
    if opt is None or indices is None:
        return False, explored
    return replay_plan(t, opt) == replay_plan(t, indices), explored


def _rejected(frame, reason, request=None):
    result = p.PlanningResult(schema_version=1, request_sha256=hashlib.sha256(frame).digest(),
                              status=p.REJECTED, reason_code=reason)
    if request is not None:
        result.trace_id = request.trace_id
        result.engine = request.engine
    return _encode(result)


class PlanningRegistry:
    def __init__(self, *, enabled=False):
        self.enabled = enabled

    def disable(self):
        self.enabled = False

    def solve_frame(self, frame: bytes, *, host_authorized=False):
        start = time.monotonic_ns()
        if not host_authorized:
            return _rejected(frame, 'HOST_AUTHORIZATION_REQUIRED')
        if not self.enabled:
            return _rejected(frame, 'PLANNING_DISABLED')
        try:
            req = _decode(frame, p.PlanningRequest)
            task = _task(req)
        except ValueError as exc:
            return _rejected(frame, str(exc))
        deadline = time.monotonic() + (req.timeout_ms or MAX_TIME_MS) / 1000
        result = p.PlanningResult(schema_version=1, request_sha256=hashlib.sha256(frame).digest(),
                                  trace_id=req.trace_id, engine=req.engine,
                                  backend_id='networkx' if req.engine in (p.NETWORKX_DIJKSTRA,p.NETWORKX_BFS) else 'cognitum-astar-hmax',
                                  backend_version='P1')
        if req.engine in (p.NETWORKX_DIJKSTRA, p.NETWORKX_BFS):
            graph, complete, expanded = _graph(task, deadline)
            path = _shortest(task, graph, req.engine)
            result.expanded, result.discovered = expanded, len(graph)
            reason = 'FOUND' if path is not None else 'FRONTIER_EXHAUSTED' if complete else 'RESOURCE_EXHAUSTED'
        else:
            path, expanded, found, reason = _astar(task, req.engine, deadline)
            result.expanded, result.discovered = expanded, found
        if path is not None and len(path) <= MAX_PLAN_LENGTH:
            try:
                result.total_cost = replay_plan(task, path)
                result.actions.extend(path)
                result.plan_verified = True
                result.status = p.VERIFIED_PLAN
            except ValueError:
                result.status = p.UNKNOWN
                reason = 'INVALID_BACKEND_WITNESS'
        else:
            result.status = p.UNKNOWN
            if path is not None:
                reason = 'PLAN_TOO_LONG'
        # Complete independent finite enumeration required for any optimality or
        # impossibility claim; engine assertion alone is not sufficient.
        if result.status == p.VERIFIED_PLAN:
            if req.engine != p.WEIGHTED_ASTAR_HMAX:
                verified, _ = _certify(task, list(result.actions), result.status, deadline)
                if verified:
                    result.status, result.optimality_verified = p.VERIFIED_OPTIMAL, True
        elif result.status == p.UNKNOWN and reason == 'FRONTIER_EXHAUSTED':
            proved, _ = _certify(task, None, p.VERIFIED_UNREACHABLE, deadline)
            if proved:
                result.status, result.optimality_verified = p.VERIFIED_UNREACHABLE, True
        result.reason_code = (('PLAN_CERTIFIED' if result.status == p.VERIFIED_OPTIMAL else
                               'UNREACHABILITY_CERTIFIED') if result.optimality_verified else reason)
        result.wall_ns = time.monotonic_ns() - start
        return _encode(result)


def verify_plan_frame(request_frame: bytes, result_frame: bytes):
    """Independent check; receipt is not signed or an authorization credential."""
    req = _decode(request_frame, p.PlanningRequest)
    result = _decode(result_frame, p.PlanningResult)
    t = _task(req)
    digest = hashlib.sha256(request_frame).digest()
    receipt = p.PlanReceipt(request_sha256=digest, result_sha256=hashlib.sha256(result_frame).digest())
    try:
        if (result.schema_version != 1 or result.request_sha256 != digest or
                result.trace_id != req.trace_id or result.engine != req.engine or result.host_approved):
            raise ValueError('RESULT_BINDING_MISMATCH')
        expected_backend = ('networkx' if req.engine in (p.NETWORKX_DIJKSTRA, p.NETWORKX_BFS)
                            else 'cognitum-astar-hmax')
        if result.status != p.REJECTED and (result.backend_id != expected_backend or result.backend_version != 'P1'):
            raise ValueError('BACKEND_METADATA_MISMATCH')
        if result.expanded > t.max_expansions or result.discovered > t.max_states:
            raise ValueError('INVALID_SEARCH_COUNTS')
        if result.status == p.VERIFIED_OPTIMAL and result.reason_code != 'PLAN_CERTIFIED':
            raise ValueError('FORGED_PROOF_REASON')
        if result.status == p.VERIFIED_UNREACHABLE and result.reason_code != 'UNREACHABILITY_CERTIFIED':
            raise ValueError('FORGED_PROOF_REASON')
        if result.status in (p.VERIFIED_PLAN, p.VERIFIED_OPTIMAL):
            if not result.plan_verified or replay_plan(t, result.actions) != result.total_cost:
                raise ValueError('INVALID_PLAN_WITNESS')
            if result.status == p.VERIFIED_PLAN and result.optimality_verified:
                raise ValueError('FORGED_OPTIMALITY_FLAG')
        elif result.actions or result.total_cost or result.plan_verified:
            raise ValueError('UNEXPECTED_PLAN')
        if result.optimality_verified != (result.status in (p.VERIFIED_OPTIMAL, p.VERIFIED_UNREACHABLE)):
            raise ValueError('INCONSISTENT_ASSURANCE')
        if result.status in (p.VERIFIED_OPTIMAL, p.VERIFIED_UNREACHABLE):
            certified, checked = _certify(t, list(result.actions) if result.plan_verified else None,
                                         result.status, time.monotonic() + MAX_TIME_MS / 1000)
            receipt.reachable_states_checked = checked
            if not certified:
                raise ValueError('INVALID_COMPLETENESS_CLAIM')
            receipt.optimality_verified = True
        elif result.status not in (p.VERIFIED_PLAN, p.UNKNOWN, p.REJECTED):
            raise ValueError('INVALID_RESULT_STATUS')
        receipt.evidence_valid = True
        receipt.reason_code = 'VERIFIED'
    except ValueError as exc:
        receipt.reason_code = str(exc)
    return _encode(receipt)


def make_planning_audit(request_frame: bytes, result_frame: bytes):
    req = _decode(request_frame, p.PlanningRequest)
    result = _decode(result_frame, p.PlanningResult)
    receipt = p.PlanReceipt.FromString(verify_plan_frame(request_frame, result_frame))
    return _encode(p.PlanningAudit(schema_version=1, request_sha256=hashlib.sha256(request_frame).digest(),
              result_sha256=hashlib.sha256(result_frame).digest(), trace_id=req.trace_id,
              engine=req.engine, status=result.status, backend_id=result.backend_id,
              backend_version=result.backend_version, reason_code=receipt.reason_code,
              wall_ns=result.wall_ns, evidence_valid=receipt.evidence_valid,
              optimality_verified=receipt.optimality_verified))


def capability_manifest():
    """Maturity inventory: optional research/external backends are NOT runnable."""
    records = (
        ('networkx-dijkstra', 'NetworkX', 'established', 'Python exact graph search', True, True, False),
        ('networkx-bfs', 'NetworkX', 'established', 'Python unit-cost search', True, True, False),
        ('astar-hmax', 'Cognitum reference', 'reference', 'bounded typed STRIPS', True, True, False),
        ('weighted-astar-hmax', 'Cognitum reference', 'satisficing', 'bounded typed STRIPS', True, True, False),
        ('fast-downward', 'Fast Downward', 'established', 'P2 host-pinned subprocess adapter; real runtime untested', False, False, False),
        ('unified-planning', 'Unified Planning', 'established', 'P2 host-pinned UP Fast Downward adapter; real runtime untested', False, False, False),
        ('learned-transition-heuristic', 'ECAI 2025 / 2026 publication', 'research', 'future sandboxed transition scoring only', False, False, True),
        ('learned-relational-search', 'ICML 2026', 'research', 'future sandboxed heuristic only', False, False, True),
        ('llm-generated-heuristic', 'NeurIPS 2025', 'research', 'future pinned, isolated candidate heuristic only', False, False, True),
    )
    msg = p.PlanningManifest(schema_version=1)
    for ident, library, maturity, interface, tested, avail, experimental in records:
        msg.backends.add(backend_id=ident,library_or_system=library,maturity=maturity,
                         interface=interface,runtime_tested=tested,available=avail,experimental=experimental)
    msg.manifest_sha256 = hashlib.sha256(_encode(msg)).digest()
    return _encode(msg)


def verify_manifest(data):
    try:
        record = _decode(data, p.PlanningManifest)
        return data == capability_manifest()
    except ValueError:
        return False


def export_pddl_frame(request_frame: bytes, *, host_authorized=False):
    """Safe PDDL 2.2 STRIPS+cost export; no parser, no subprocess, no arbitrary PDDL."""
    if not host_authorized:
        raise PermissionError('HOST_AUTHORIZATION_REQUIRED')
    request = _decode(request_frame, p.PlanningRequest)
    t = _task(request)
    facts = [f'f{i}' for i in range(t.facts)]
    def atoms(mask, negative=False):
        return [('(not ('+f+'))' if negative else '('+f+')') for i,f in enumerate(facts) if mask & (1 << i)]
    def conj(lines): return '(and ' + ' '.join(lines) + ')'
    actions=[]
    for i,a in enumerate(t.actions):
        pre=conj(atoms(a.req_true)+atoms(a.req_false,True))
        eff=conj(atoms(a.add)+atoms(a.remove,True)+[f'(increase (total-cost) {a.cost})'])
        actions.append(f' (:action act{i} :parameters () :precondition {pre} :effect {eff})')
    domain='\n'.join(['(define (domain cognitum_grounded)',
                     ' (:requirements :strips :negative-preconditions :action-costs)',
                     ' (:predicates ' + ' '.join('('+f+')' for f in facts) + ')',
                     ' (:functions (total-cost))']+actions+[')'])+'\n'
    initial=atoms(t.start)+['(= (total-cost) 0)']
    goal=conj(atoms(t.goal_true)+atoms(t.goal_false,True))
    problem='\n'.join(['(define (problem cognitum_problem)', ' (:domain cognitum_grounded)',
                       ' (:init '+' '.join(initial)+')', ' (:goal '+goal+')',
                       ' (:metric minimize (total-cost))', ')'])+'\n'
    result=p.PddlExport(schema_version=1,request_sha256=hashlib.sha256(request_frame).digest(),
                         domain_pddl=domain,problem_pddl=problem,dialect='PDDL-2.2-STRIPS-NEGATIVE-PRECONDITIONS-ACTION-COSTS')
    return _encode(result, 128*1024)
