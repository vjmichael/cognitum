"""C12 P3 finite-horizon MDP planning (exact Bellman DP and bounded UCT MCTS).

Protobuf-native, offline, host-gated Python reference. DP has independently checked
Bellman optimality for a *supplied* finite model. MCTS is an estimate, never a proof.
Neither backend performs effects, learns a world model, or has Lu host authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import math
import random
import re
import time

from cognitum.planning import _decode, _encode, TRACE, NAME
from cognitum.proto import planning_stochastic_pb2 as p

PARTS = 1_000_000
MAX_FRAME = 65536
MAX_STATES = 24
MAX_DECISIONS = 128
MAX_OUTCOMES = 8
MAX_HORIZON = 12
MAX_SIMULATIONS = 2000
MAX_TIMEOUT_MS = 3000
MAX_REWARD = 1_000_000_000
VALUE = re.compile(r'(?:0|-?[1-9][0-9]*)(?:/[1-9][0-9]*)?\Z', re.ASCII)
BACKENDS = {p.FINITE_HORIZON_BELLMAN: 'reference-bellman-exact',
            p.UCT_MCTS: 'reference-uct-stochastic'}


@dataclass(frozen=True)
class Outcome:
    to: int
    prob: Fraction
    reward: int


@dataclass(frozen=True)
class Model:
    actions: tuple[tuple[tuple[str, tuple[Outcome, ...]], ...], ...]
    terminal: tuple[int, ...]
    start: int
    horizon: int
    discount: Fraction


def _model(req: p.StochasticRequest) -> Model:
    if req.schema_version != 1 or not TRACE.fullmatch(req.trace_id) or req.method not in BACKENDS:
        raise ValueError('INVALID_REQUEST')
    if not (1 <= req.timeout_ms <= MAX_TIMEOUT_MS):
        raise ValueError('INVALID_TIMEOUT')
    if req.method == p.UCT_MCTS and not (1 <= req.simulations <= MAX_SIMULATIONS):
        raise ValueError('INVALID_SIMULATION_BUDGET')
    if req.method == p.FINITE_HORIZON_BELLMAN and req.simulations != 0:
        raise ValueError('DP_REJECTS_SIMULATIONS')
    task = req.model
    size = len(task.state_names)
    if not (1 <= size <= MAX_STATES and 1 <= task.horizon <= MAX_HORIZON and
            task.initial_state < size and 1 <= task.discount_ppm <= PARTS and
            len(task.terminal_reward_milli) == size and
            1 <= len(task.decisions) <= MAX_DECISIONS):
        raise ValueError('INVALID_MDP_SHAPE')
    if len(set(task.state_names)) != size or any(not NAME.fullmatch(s) for s in task.state_names):
        raise ValueError('INVALID_STATE_NAME')
    if any(abs(v) > MAX_REWARD for v in task.terminal_reward_milli):
        raise ValueError('INVALID_TERMINAL_REWARD')
    actions = [[] for _ in range(size)]
    ids = [set() for _ in range(size)]
    for d in task.decisions:
        if d.state >= size or not NAME.fullmatch(d.action_id) or d.action_id in ids[d.state] or not (1 <= len(d.outcomes) <= MAX_OUTCOMES):
            raise ValueError('INVALID_ACTION')
        ids[d.state].add(d.action_id)
        total = 0
        outcomes = []
        for o in d.outcomes:
            if o.next_state >= size or not 1 <= o.probability_ppm <= PARTS or abs(o.reward_milli) > MAX_REWARD:
                raise ValueError('INVALID_OUTCOME')
            total += o.probability_ppm
            outcomes.append(Outcome(o.next_state, Fraction(o.probability_ppm, PARTS), o.reward_milli))
        if total != PARTS:
            raise ValueError('PROBABILITIES_NOT_NORMALIZED')
        actions[d.state].append((d.action_id, tuple(outcomes)))
    if any(not a for a in actions):
        raise ValueError('STATE_WITHOUT_ACTION')
    return Model(tuple(tuple(a) for a in actions), tuple(task.terminal_reward_milli),
                 task.initial_state, task.horizon, Fraction(task.discount_ppm, PARTS))


def _action_value(m: Model, outcomes, nxt) -> Fraction:
    return sum((o.prob * (o.reward + m.discount * nxt[o.to]) for o in outcomes), Fraction(0))


def _bellman(m: Model):
    """Backward induction produces exact fractions for all stages and all states."""
    future = tuple(map(Fraction, m.terminal))
    entries = []
    for stage in range(m.horizon - 1, -1, -1):
        now = []
        rows = []
        for state, actions in enumerate(m.actions):
            choices = [(_action_value(m, outcomes, future), name) for name, outcomes in actions]
            best = max(value for value, _ in choices)
            winner = next(name for value, name in choices if value == best)
            rows.append((stage, state, winner, best))
            now.append(best)
        entries.extend(rows)
        future = tuple(now)
    entries.sort()
    return entries


def _fraction(s):
    if not VALUE.fullmatch(s) or len(s) > 1200:
        raise ValueError('INVALID_RATIONAL')
    val = Fraction(s)
    if str(val) != s:
        raise ValueError('NONCANONICAL_RATIONAL')
    return val


def _verify_policy(m: Model, entries) -> bool:
    """Independent policy evaluation + improvement: no call to Bellman planner."""
    if len(entries) != m.horizon * len(m.actions):
        return False
    by_key = {}
    for row in entries:
        key = (row.stage, row.state)
        if row.stage >= m.horizon or row.state >= len(m.actions) or key in by_key:
            return False
        names = dict(m.actions[row.state])
        if row.action_id not in names:
            return False
        by_key[key] = (row.action_id, _fraction(row.expected_value_fraction))
    if len(by_key) != m.horizon * len(m.actions):
        return False
    # Evaluate the given policy directly and enforce Bellman inequalities.
    from functools import lru_cache
    @lru_cache(None)
    def eval_policy(stage, state):
        if stage == m.horizon:
            return Fraction(m.terminal[state])
        action = by_key[(stage, state)][0]
        return sum((out.prob * (out.reward + m.discount * eval_policy(stage + 1, out.to))
                    for out in dict(m.actions[state])[action]), Fraction(0))
    for stage in range(m.horizon):
        for state, actions in enumerate(m.actions):
            chosen = eval_policy(stage, state)
            if chosen != by_key[(stage, state)][1]:
                return False
            for _name, outcomes in actions:
                alternate = sum((out.prob * (out.reward + m.discount * eval_policy(stage + 1, out.to))
                                 for out in outcomes), Fraction(0))
                if alternate > chosen:
                    return False
    return True


def _rollout(m: Model, stage, state, rng):
    if stage == m.horizon:
        return float(m.terminal[state])
    action = rng.choice(m.actions[state])
    outcome = _sample(action[1], rng)
    return outcome.reward + float(m.discount) * _rollout(m, stage + 1, outcome.to, rng)


def _sample(outcomes, rng):
    draw = rng.randrange(PARTS)
    for out in outcomes:
        width = out.prob.numerator * PARTS // out.prob.denominator
        if draw < width:
            return out
        draw -= width
    raise AssertionError('normalized probability invariant')


def _uct(m: Model, simulations, seed):
    rng = random.Random(seed)
    stats = {}  # (stage, state, action id) => [visits, sum of rollout rewards]
    node_visits = {}  # (stage, state) => visits

    def visit(stage, state):
        if stage == m.horizon:
            return float(m.terminal[state])
        node = (stage, state)
        actions = m.actions[state]
        untried = [a for a in actions if (stage, state, a[0]) not in stats]
        if untried:
            action = untried[0]
            first = True
        else:
            parent_visits = node_visits[node]
            def score(a):
                visits, reward_sum = stats[(stage, state, a[0])]
                return reward_sum / visits + math.sqrt(2.0 * math.log(parent_visits) / visits) * MAX_REWARD
            action = max(actions, key=score)
            first = False
        outcome = _sample(action[1], rng)
        downstream = (_rollout(m, stage + 1, outcome.to, rng) if first else
                      visit(stage + 1, outcome.to))
        reward = outcome.reward + float(m.discount) * downstream
        key = stage, state, action[0]
        current = stats.get(key)
        if current is None: stats[key] = [1, reward]
        else: current[0] += 1; current[1] += reward
        node_visits[node] = node_visits.get(node, 0) + 1
        return reward

    for _ in range(simulations):
        visit(0, m.start)
    roots = [(name, *stats.get((0, m.start, name), (0, 0.0)))
             for name, _ in m.actions[m.start]]
    selected = max(roots, key=lambda x: (x[1], x[2] / x[1] if x[1] else float('-inf')))
    return selected[0], format(selected[2] / selected[1], '.6f'), [(a, v) for a, v, _ in roots]


def _digest(message):
    return hashlib.sha256(_encode(message)).digest()


def _result(raw, start):
    return p.StochasticResult(schema_version=1, request_sha256=hashlib.sha256(raw).digest(),
                              status=p.REJECTED_STOCHASTIC, reason_code='INVALID_REQUEST',
                              wall_ns=time.monotonic_ns() - start)


def run(frame: bytes, *, enabled=False, host_authorized=False) -> bytes:
    start = time.monotonic_ns()
    raw = frame if isinstance(frame, bytes) and len(frame) <= MAX_FRAME else b''
    result = _result(raw, start)
    try:
        if not raw: raise ValueError('INVALID_FRAME')
        req = _decode(raw, p.StochasticRequest)
        m = _model(req)
        result.trace_id, result.method = req.trace_id, req.method
        result.backend_id, result.backend_version = BACKENDS[req.method], 'c12-p3-v1'
        if not host_authorized: raise ValueError('HOST_AUTHORIZATION_REQUIRED')
        if not enabled: raise ValueError('PLANNING_DISABLED')
        if req.method == p.FINITE_HORIZON_BELLMAN:
            rows = _bellman(m)
            for stage, state, action, value in rows:
                result.policy.add(stage=stage, state=state, action_id=action,
                                  expected_value_fraction=str(value))
            if not _verify_policy(m, result.policy):
                raise ValueError('POLICY_VERIFICATION_FAILED')
            result.root_action_id = next(e.action_id for e in result.policy if e.stage == 0 and e.state == m.start)
            result.root_estimated_value = next(e.expected_value_fraction for e in result.policy if e.stage == 0 and e.state == m.start)
            result.status = p.VERIFIED_POLICY
            result.policy_verified = True
            result.optimality_verified = True
            result.reason_code = 'EXACT_BELLMAN_POLICY_CHECKED'
        else:
            root, value, visits = _uct(m, req.simulations, req.random_seed)
            result.root_action_id, result.root_estimated_value = root, value
            for name, count in visits: result.root_visits.add(action_id=name, visits=count)
            result.status = p.ESTIMATED_ACTION
            result.reason_code = 'UCT_ESTIMATE_NOT_PROOF'
        # Cooperative wall timeout: no claim on overrun.
        if time.monotonic_ns() - start > req.timeout_ms * 1_000_000:
            result.ClearField('policy')
            result.ClearField('root_visits')
            result.root_action_id = result.root_estimated_value = ''
            result.policy_verified = result.optimality_verified = False
            result.status = p.UNKNOWN_STOCHASTIC
            result.reason_code = 'TIME_BUDGET_EXCEEDED'
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        result.status = p.REJECTED_STOCHASTIC
        result.reason_code = str(exc)[:100] or 'INVALID_REQUEST'
        result.policy_verified = result.optimality_verified = False
    result.wall_ns = time.monotonic_ns() - start
    return _encode(result)


def verify(frame: bytes, result_frame: bytes) -> p.StochasticReceipt:
    receipt = p.StochasticReceipt(request_sha256=hashlib.sha256(frame).digest(),
                                   result_sha256=hashlib.sha256(result_frame).digest(),
                                   reason_code='INVALID_EVIDENCE')
    try:
        req = _decode(frame, p.StochasticRequest)
        result = _decode(result_frame, p.StochasticResult)
        m = _model(req)
        if (result.schema_version != 1 or result.request_sha256 != receipt.request_sha256 or
                result.trace_id != req.trace_id or result.method != req.method or
                result.backend_id != BACKENDS[req.method] or result.backend_version != 'c12-p3-v1'):
            return receipt
        if result.status == p.VERIFIED_POLICY and req.method == p.FINITE_HORIZON_BELLMAN:
            if (not result.policy_verified or not result.optimality_verified or result.root_visits or
                    result.reason_code != 'EXACT_BELLMAN_POLICY_CHECKED' or not _verify_policy(m, result.policy)):
                return receipt
            root = next(x for x in result.policy if x.stage == 0 and x.state == m.start)
            if result.root_action_id != root.action_id or result.root_estimated_value != root.expected_value_fraction:
                return receipt
            receipt.evidence_valid = receipt.optimality_verified = True
            receipt.reason_code = 'INDEPENDENT_POLICY_EVALUATION_AND_IMPROVEMENT'
        elif result.status == p.ESTIMATED_ACTION and req.method == p.UCT_MCTS:
            if (result.optimality_verified or result.policy_verified or result.policy or
                    result.reason_code != 'UCT_ESTIMATE_NOT_PROOF'):
                return receipt
            # Deterministic trace reproduction checks integrity, NOT statistical optimality.
            root, value, counts = _uct(m, req.simulations, req.random_seed)
            if (result.root_action_id != root or result.root_estimated_value != value or
                    [(a.action_id, a.visits) for a in result.root_visits] != counts):
                return receipt
            receipt.evidence_valid = True
            receipt.reason_code = 'REPRODUCED_SEEDED_ESTIMATE_NOT_OPTIMALITY'
        else:
            return receipt
    except (ValueError, TypeError, StopIteration, RecursionError, OverflowError):
        return receipt
    return receipt


def audit(frame: bytes, result_frame: bytes) -> bytes:
    req = _decode(frame, p.StochasticRequest)
    result = _decode(result_frame, p.StochasticResult)
    r = verify(frame, result_frame)
    obj = p.StochasticAudit(schema_version=1, request_sha256=r.request_sha256,
                            result_sha256=r.result_sha256, trace_id=req.trace_id,
                            method=req.method, status=result.status, backend_id=result.backend_id,
                            wall_ns=result.wall_ns, evidence_valid=r.evidence_valid,
                            optimality_verified=r.optimality_verified, reason_code=r.reason_code)
    return _encode(obj)


def manifest():
    return ({'id':'reference-bellman-exact', 'maturity':'reference', 'available':True,
             'assurance':'independent finite-horizon policy evaluation/improvement'},
            {'id':'reference-uct-stochastic', 'maturity':'reference', 'available':True,
             'assurance':'reproducible statistical estimate, no optimality proof'},
            {'id':'pymdptoolbox', 'maturity':'established-optional', 'available':False,
             'assurance':'not installed or runtime-tested'},
            {'id':'unified-planning-temporal-htn', 'maturity':'established-optional', 'available':False,
             'assurance':'separate C12 extension'},
            {'id':'learned-uct-guidance', 'maturity':'research', 'available':False,
             'assurance':'unimplemented; opt-in only'})
