"""C13 P1 finite discrete Bayesian-network inference, exact factors and seeded LW.

An OFFLINE reference for typed Protobuf inputs. No model-executable Python, no
user authority, no learned parameters, no Lu canonical-memory writes.
Exact factor elimination uses rational arithmetic; separate brute-force
joint factorization checks bounded instances, NOT the same elimination routine.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import product
from functools import reduce
import hashlib
import math
import random
import re
import time
from operator import mul

from cognitum.planning import _decode, _encode, NAME, TRACE
from cognitum.proto import probability_pb2 as p

PPM = 1_000_000
MAX_FRAME = 65536
MAX_NODES = 12
MAX_STATES = 8
MAX_CPT_ENTRIES = 8192
MAX_FACTOR_ENTRIES = 32768
MAX_VERIFY_ASSIGNMENTS = 32768
MAX_SAMPLES = 10000
MAX_TIMEOUT_MS = 5000
BACKEND_VERSION = 'C13-P1-v1'
BACKENDS = {p.EXACT_VARIABLE_ELIMINATION: 'reference-exact-variable-elimination',
            p.SEEDED_LIKELIHOOD_WEIGHTING: 'reference-seeded-likelihood-weighting'}
CANON = re.compile(r'(?:0|[1-9][0-9]*)(?:/[1-9][0-9]*)?\Z', re.ASCII)

@dataclass(frozen=True)
class Factor:
    scope: tuple[int, ...]
    rows: dict[tuple[int, ...], Fraction]

@dataclass(frozen=True)
class Model:
    dims: tuple[int, ...]
    parents: tuple[tuple[int, ...], ...]
    cpts: tuple[tuple[Fraction, ...], ...]
    topo: tuple[int, ...]
    targets: tuple[int, ...]
    hard: dict[int, int]
    soft: dict[int, tuple[Fraction, ...]]
    factor_cap: int
    verifier_cap: int

class BudgetExceeded(Exception):
    pass


def _product(values):
    return math.prod(values)


def _validate(req: p.InferenceRequest) -> Model:
    if req.schema_version != 1 or not TRACE.fullmatch(req.trace_id) or req.method not in BACKENDS:
        raise ValueError('INVALID_REQUEST')
    if not 1 <= req.timeout_ms <= MAX_TIMEOUT_MS:
        raise ValueError('INVALID_TIME_BUDGET')
    if req.method == p.EXACT_VARIABLE_ELIMINATION and req.samples:
        raise ValueError('EXACT_REJECTS_SAMPLING')
    if req.method == p.SEEDED_LIKELIHOOD_WEIGHTING and not 1 <= req.samples <= MAX_SAMPLES:
        raise ValueError('INVALID_SAMPLING_BUDGET')
    if req.max_factor_entries > MAX_FACTOR_ENTRIES or req.max_verifier_assignments > MAX_VERIFY_ASSIGNMENTS:
        raise ValueError('INVALID_RESOURCE_CEILING')
    nodes = req.model.nodes
    n = len(nodes)
    if not 1 <= n <= MAX_NODES or len(req.targets) == 0 or len(req.targets) > n:
        raise ValueError('INVALID_GRAPH_SHAPE')
    dims = tuple(len(node.states) for node in nodes)
    if any(not 2 <= d <= MAX_STATES for d in dims):
        raise ValueError('INVALID_CARDINALITY')
    if len(set(node.id for node in nodes)) != n or any(not NAME.fullmatch(node.id) for node in nodes):
        raise ValueError('INVALID_NODE_NAMES')
    for node in nodes:
        if len(set(node.states)) != len(node.states) or any(not NAME.fullmatch(s) for s in node.states):
            raise ValueError('INVALID_STATE_NAMES')
    parents, cpts = [], []
    for i, node in enumerate(nodes):
        pr = tuple(node.parents)
        if len(pr) != len(set(pr)) or any(x >= n or x == i for x in pr):
            raise ValueError('INVALID_PARENTS')
        length = dims[i] * _product(dims[x] for x in pr)
        if length > MAX_CPT_ENTRIES or len(node.cpt_ppm) != length:
            raise ValueError('INVALID_CPT_SIZE')
        for offset in range(0, length, dims[i]):
            if sum(node.cpt_ppm[offset:offset+dims[i]]) != PPM:
                raise ValueError('INVALID_CPT_NORMALIZATION')
        parents.append(pr)
        cpts.append(tuple(Fraction(v, PPM) for v in node.cpt_ppm))
    seen, active, topo = set(), set(), []
    def visit(i):
        if i in active: raise ValueError('CYCLIC_BAYESIAN_NETWORK')
        if i in seen: return
        active.add(i)
        for parent in parents[i]: visit(parent)
        active.remove(i)
        seen.add(i)
        topo.append(i)
    for i in range(n): visit(i)
    targets = tuple(req.targets)
    if _product(dims[i] for i in targets) > 512:
        raise ValueError('QUERY_OUTPUT_TOO_LARGE')
    if len(set(targets)) != len(targets) or any(x >= n for x in targets):
        raise ValueError('INVALID_QUERY_TARGETS')
    hard, soft = {}, {}
    for obs in req.hard_evidence:
        if obs.node >= n or obs.state >= dims[obs.node] or obs.node in hard:
            raise ValueError('INVALID_HARD_EVIDENCE')
        hard[obs.node] = obs.state
    for obs in req.soft_evidence:
        if (obs.node >= n or obs.node in soft or len(obs.likelihood_ppm) != dims[obs.node] or
                all(x == 0 for x in obs.likelihood_ppm) or any(x > PPM for x in obs.likelihood_ppm)):
            raise ValueError('INVALID_SOFT_EVIDENCE')
        soft[obs.node] = tuple(Fraction(x, PPM) for x in obs.likelihood_ppm)
    return Model(dims, tuple(parents), tuple(cpts), tuple(topo), targets, hard, soft,
                 req.max_factor_entries or 8192, req.max_verifier_assignments or 8192)


def _joint_node_probability(m: Model, node: int, assignment) -> Fraction:
    index = 0
    for parent in m.parents[node]:
        index = index * m.dims[parent] + assignment[parent]
    return m.cpts[node][index * m.dims[node] + assignment[node]]


def _base_factors(m: Model):
    factors = []
    for node in range(len(m.dims)):
        scope = m.parents[node] + (node,)
        if _product(m.dims[i] for i in scope) > m.factor_cap:
            raise BudgetExceeded('FACTOR_LIMIT')
        rows = {}
        for assign in product(*(range(m.dims[i]) for i in scope)):
            index = 0
            for parent_value, parent in zip(assign[:-1], m.parents[node]):
                index = index * m.dims[parent] + parent_value
            val = m.cpts[node][index * m.dims[node] + assign[-1]]
            if val: rows[assign] = val
        factors.append(Factor(scope, rows))
    for node, state in m.hard.items():
        factors.append(Factor((node,), {(state,): Fraction(1)}))
    for node, weights in m.soft.items():
        factors.append(Factor((node,), {(j,): v for j, v in enumerate(weights) if v}))
    return factors


def _multiply(a: Factor, b: Factor, m: Model) -> Factor:
    scope = a.scope + tuple(v for v in b.scope if v not in a.scope)
    if _product(m.dims[x] for x in scope) > m.factor_cap:
        raise BudgetExceeded('FACTOR_LIMIT')
    apos = [scope.index(v) for v in a.scope]
    bpos = [scope.index(v) for v in b.scope]
    rows = {}
    for assignment in product(*(range(m.dims[i]) for i in scope)):
        av = a.rows.get(tuple(assignment[i] for i in apos), Fraction(0))
        if not av: continue
        bv = b.rows.get(tuple(assignment[i] for i in bpos), Fraction(0))
        if bv: rows[assignment] = av * bv
    return Factor(scope, rows)


def _sum_out(factor: Factor, variable: int):
    place = factor.scope.index(variable)
    scope = tuple(x for x in factor.scope if x != variable)
    rows = {}
    for assignment, value in factor.rows.items():
        key = assignment[:place] + assignment[place+1:]
        rows[key] = rows.get(key, Fraction(0)) + value
    return Factor(scope, rows)


def _elimination_order(factors: list[Factor], targets: tuple[int, ...], m: Model):
    """Min-fill-style greedy estimate: eliminate variable with smallest product scope."""
    remaining = set(range(len(m.dims))) - set(targets)
    scopes = [set(f.scope) for f in factors]
    order = []
    while remaining:
        def cost(var):
            connected = set().union(*(s for s in scopes if var in s))
            return (_product(m.dims[x] for x in connected), len(connected), var)
        candidate = min(remaining, key=cost)
        connected = set().union(*(s for s in scopes if candidate in s))
        scopes = [s for s in scopes if candidate not in s]
        if connected: scopes.append(connected - {candidate})
        remaining.remove(candidate)
        order.append(candidate)
    return order


def _exact(m: Model):
    factors = _base_factors(m)
    for var in _elimination_order(factors, m.targets, m):
        matching = [f for f in factors if var in f.scope]
        factors = [f for f in factors if var not in f.scope]
        if not matching: continue
        joined = matching[0]
        for factor in matching[1:]: joined = _multiply(joined, factor, m)
        factors.append(_sum_out(joined, var))
    joined = Factor((), {(): Fraction(1)})
    for factor in factors: joined = _multiply(joined, factor, m)
    cells = {}
    positions = [joined.scope.index(var) for var in m.targets]
    for key, val in joined.rows.items():
        target = tuple(key[i] for i in positions)
        cells[target] = cells.get(target, Fraction(0)) + val
    denominator = sum(cells.values(), Fraction(0))
    if denominator == 0: return None, Fraction(0)
    return {states: cells.get(states, Fraction(0)) / denominator
            for states in product(*(range(m.dims[i]) for i in m.targets))}, denominator


def _oracle(m: Model):
    """Independent full-joint enumeration; doesn't use Factor or elimination."""
    count = _product(m.dims)
    if count > m.verifier_cap: raise BudgetExceeded('ENUMERATION_LIMIT')
    unnormalized = {}
    evidence_total = Fraction(0)
    for assignment in product(*(range(d) for d in m.dims)):
        if any(assignment[i] != state for i, state in m.hard.items()): continue
        likelihood = Fraction(1)
        for i in range(len(m.dims)):
            likelihood *= _joint_node_probability(m, i, assignment)
            if not likelihood: break
            if i in m.soft: likelihood *= m.soft[i][assignment[i]]
        if not likelihood: continue
        key = tuple(assignment[i] for i in m.targets)
        unnormalized[key] = unnormalized.get(key, Fraction(0)) + likelihood
        evidence_total += likelihood
    if not evidence_total: return None, Fraction(0), count
    return ({states: unnormalized.get(states, Fraction(0)) / evidence_total
             for states in product(*(range(m.dims[i]) for i in m.targets))},
            evidence_total, count)


def _weighted(m: Model, samples: int, seed: int):
    rng = random.Random(seed)
    accum, sumw, sumw2 = {}, 0.0, 0.0
    for _ in range(samples):
        assignment = [0] * len(m.dims)
        weight = 1.0
        for node in m.topo:
            index = 0
            for parent in m.parents[node]:
                index = index * m.dims[parent] + assignment[parent]
            row = m.cpts[node][index*m.dims[node]:(index+1)*m.dims[node]]
            if node in m.hard:
                assignment[node] = m.hard[node]
                weight *= float(row[assignment[node]])
            else:
                draw = rng.randrange(PPM)
                for state, value in enumerate(row):
                    width = value.numerator * PPM // value.denominator
                    if draw < width:
                        assignment[node] = state
                        break
                    draw -= width
            if node in m.soft: weight *= float(m.soft[node][assignment[node]])
        if not weight: continue
        key = tuple(assignment[i] for i in m.targets)
        accum[key] = accum.get(key, 0.0) + weight
        sumw += weight
        sumw2 += weight * weight
    if not sumw or not sumw2: return None, 0
    probabilities = {states: format(accum.get(states, 0.0) / sumw, '.12f')
                     for states in product(*(range(m.dims[i]) for i in m.targets))}
    return probabilities, min(samples, int((sumw * sumw) / sumw2))


def _populate(result, posterior):
    for assignment, probability in posterior.items():
        cell = result.posterior.add()
        cell.states.extend(assignment)
        cell.probability = str(probability)


def infer_frame(frame: bytes, *, host_authorized=False, enabled=False) -> bytes:
    start = time.monotonic_ns()
    raw = frame if isinstance(frame, bytes) and len(frame) <= MAX_FRAME else b''
    result = p.InferenceResult(schema_version=1, request_sha256=hashlib.sha256(raw).digest(),
                               status=p.REJECTED_INFERENCE, reason_code='INVALID_FRAME')
    try:
        if not raw: raise ValueError('INVALID_FRAME')
        req = _decode(raw, p.InferenceRequest)
        model = _validate(req)
        result.trace_id, result.method = req.trace_id, req.method
        result.backend_id, result.backend_version = BACKENDS[req.method], BACKEND_VERSION
        if not host_authorized: raise ValueError('HOST_AUTHORIZATION_REQUIRED')
        if not enabled: raise ValueError('PROBABILITY_DISABLED')
        if req.method == p.EXACT_VARIABLE_ELIMINATION:
            posterior, evidence = _exact(model)
            if posterior is None:
                result.status = p.IMPOSSIBLE_EVIDENCE
                result.reason_code = 'ZERO_EVIDENCE_PROBABILITY_EXACT'
            else:
                _populate(result, posterior)
                result.evidence_probability = str(evidence)
                result.status = p.EXACT_POSTERIOR
                result.reason_code = 'EXACT_FACTOR_ELIMINATION'
                try:
                    independent, mass, _ = _oracle(model)
                    result.independent_posterior_verified = independent == posterior and mass == evidence
                    if not result.independent_posterior_verified: raise ValueError('INDEPENDENT_CHECK_FAILED')
                except BudgetExceeded:
                    result.reason_code = 'EXACT_UNCERTIFIED_VERIFIER_LIMIT'
        else:
            posterior, ess = _weighted(model, req.samples, req.random_seed)
            if posterior is None:
                result.status = p.UNKNOWN_INFERENCE
                result.reason_code = 'NO_NONZERO_SAMPLING_WEIGHTS'
            else:
                _populate(result, posterior)
                result.samples_drawn = req.samples
                result.effective_samples = ess
                result.status = p.APPROXIMATE_POSTERIOR
                result.reason_code = 'SEEDED_LW_ESTIMATE_NOT_PROOF'
        if time.monotonic_ns() - start > req.timeout_ms * 1_000_000:
            result.ClearField('posterior')
            result.evidence_probability = ''
            result.independent_posterior_verified = False
            result.status = p.UNKNOWN_INFERENCE
            result.reason_code = 'TIME_LIMIT_EXCEEDED'
    except BudgetExceeded as exc:
        result.status = p.UNKNOWN_INFERENCE
        result.reason_code = str(exc)
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        result.status = p.REJECTED_INFERENCE
        result.reason_code = str(exc)[:120]
    result.wall_ns = time.monotonic_ns() - start
    return _encode(result)


def verify_receipt(request_frame: bytes, result_frame: bytes) -> p.InferenceReceipt:
    """Recheck exact claims by independent full-joint enumeration, including impossible evidence.

    No optimistic verification outside the oracle's cap; approximate remains a proposal.
    """
    receipt = p.InferenceReceipt(request_sha256=hashlib.sha256(request_frame).digest(),
                                 result_sha256=hashlib.sha256(result_frame).digest(),
                                 reason_code='NOT_VERIFIED')
    try:
        req = _decode(request_frame, p.InferenceRequest)
        out = _decode(result_frame, p.InferenceResult)
        model = _validate(req)
        if (out.schema_version != 1 or out.request_sha256 != receipt.request_sha256 or
                out.trace_id != req.trace_id or out.method != req.method or
                out.backend_id != BACKENDS[req.method] or out.backend_version != BACKEND_VERSION):
            return receipt
        if out.status not in (p.EXACT_POSTERIOR, p.IMPOSSIBLE_EVIDENCE):
            return receipt  # approximate is not independently certified
        if req.method != p.EXACT_VARIABLE_ELIMINATION:
            return receipt
        expected, evidence, count = _oracle(model)
        receipt.enumerated_assignments = count
        if expected is None:
            if (out.status != p.IMPOSSIBLE_EVIDENCE or out.posterior or
                    out.independent_posterior_verified or out.evidence_probability or
                    out.reason_code != 'ZERO_EVIDENCE_PROBABILITY_EXACT'):
                return receipt
        else:
            if (out.status != p.EXACT_POSTERIOR or len(out.posterior) != len(expected) or
                    out.evidence_probability != str(evidence) or
                    out.independent_posterior_verified is not True or
                    out.reason_code != 'EXACT_FACTOR_ELIMINATION'):
                return receipt
            received = {}
            for cell in out.posterior:
                states = tuple(cell.states)
                if states not in expected or states in received or not CANON.fullmatch(cell.probability):
                    return receipt
                fraction = Fraction(cell.probability)
                if str(fraction) != cell.probability: return receipt
                received[states] = fraction
            if received != expected: return receipt
        receipt.evidence_valid = True
        receipt.exact_posterior_verified = True
        receipt.reason_code = 'INDEPENDENT_FULL_JOINT_ENUMERATION'
    except (ValueError, TypeError, BudgetExceeded, OverflowError, RecursionError):
        pass
    return receipt


def make_audit(request_frame: bytes, result_frame: bytes, receipt: p.InferenceReceipt | None = None):
    out = _decode(result_frame, p.InferenceResult)
    if receipt is not None and (receipt.request_sha256 != hashlib.sha256(request_frame).digest() or
                                receipt.result_sha256 != hashlib.sha256(result_frame).digest()):
        raise ValueError('UNBOUND_RECEIPT')
    checked = verify_receipt(request_frame, result_frame)
    if receipt is not None and receipt != checked:
        raise ValueError('FORGED_RECEIPT')
    return p.InferenceAudit(schema_version=1, request_sha256=hashlib.sha256(request_frame).digest(),
                            result_sha256=hashlib.sha256(result_frame).digest(), trace_id=out.trace_id,
                            backend_id=out.backend_id, backend_version=out.backend_version,
                            status=out.status, wall_ns=out.wall_ns,
                            independent_posterior_verified=checked.exact_posterior_verified,
                            reason_code=out.reason_code)
