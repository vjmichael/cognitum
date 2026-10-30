"""C14 P2A: offline bounded observational backdoor-adjustment reference.

Computes an empirical standardized binary risk difference from frequency rows.
A supplied DAG and passing backdoor check are NOT evidence that the graph is true,
that confounding has actually been controlled, or that the estimate is causal.
The future DoWhy adapter is intentionally unavailable until isolated and tested.
"""
from __future__ import annotations
from collections import defaultdict
from fractions import Fraction
import hashlib
import math
import time

from cognitum import causal
from cognitum.planning import TRACE, _encode
from cognitum.proto import causal_pb2 as p, causal_estimation_pb2 as q

MAX_FRAME = 131072
MAX_ROWS = 384
MAX_SAMPLES = 200000
MAX_STRATA = 128
MAX_TIME_MS = 5000
VERSION = 'C14-P2A-1'
BACKEND = 'c14-reference-observational-adjustment'
ASSURANCE = 'SUPPLIED_GRAPH_EMPIRICAL_ADJUSTMENT'
Z95 = 1.959963984540054


def _decode(raw, cls):
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_FRAME:
        raise ValueError('INVALID_FRAME')
    out = cls()
    try:
        out.ParseFromString(raw)
        canonical = cls(); canonical.CopyFrom(out); canonical.DiscardUnknownFields()
        if canonical.SerializeToString(deterministic=True) != raw:
            raise ValueError('NONCANONICAL_OR_UNKNOWN_FRAME')
    except Exception as exc:
        raise ValueError('INVALID_PROTOBUF') from exc
    return out


def _parse(raw):
    req = _decode(raw, q.EstimationRequest)
    if (req.schema_version != 1 or not TRACE.fullmatch(req.trace_id) or
        req.backend not in (q.REFERENCE_STRATIFIED_ADJUSTMENT, q.DOWHY_OPTIONAL_WORKER) or
        not 1 <= req.timeout_ms <= MAX_TIME_MS or
        not 2 <= req.min_arm_count <= 1000 or
        not 1 <= len(req.observations) <= MAX_ROWS):
        raise ValueError('INVALID_ESTIMATION_REQUEST')
    base = req.identification
    if base.operation != p.BACKDOOR_CHECK or base.trace_id != req.trace_id:
        raise ValueError('BACKDOOR_IDENTIFICATION_REQUIRED')
    model_frame = base.SerializeToString(deterministic=True)
    _, model, _, _ = causal._parse(model_frame)
    if model.endo_dims[base.treatment] != 2 or model.endo_dims[base.target] != 2:
        raise ValueError('BINARY_TREATMENT_AND_OUTCOME_REQUIRED')
    count = 0
    buckets = defaultdict(lambda: [[0, 0], [0, 0]])
    seen = set()
    for row in req.observations:
        states = tuple(row.states)
        if (not 1 <= row.count <= MAX_SAMPLES or len(states) != len(model.endo_dims) or
            any(state >= dim for state,dim in zip(states,model.endo_dims)) or states in seen):
            raise ValueError('INVALID_OBSERVATION_ROW')
        seen.add(states)
        count += row.count
        if count > MAX_SAMPLES: raise ValueError('SAMPLE_LIMIT')
        adj = tuple(states[index] for index in base.adjustment)
        bucket = buckets[adj][states[base.treatment]]
        bucket[0] += row.count
        bucket[1] += row.count * (states[base.target] == 1)
    if len(buckets) > MAX_STRATA: raise ValueError('STRATA_LIMIT')
    return req, model, count, buckets


def _fraction(n):
    return str(n)


def _effect(buckets, total, excluded=None):
    remaining = total - (sum(row[0] for row in buckets[excluded]) if excluded is not None else 0)
    if remaining == 0: raise ValueError('NO_REMAINING_STRATA')
    return sum((Fraction(row[0][0] + row[1][0], remaining) *
                (Fraction(row[1][1], row[1][0]) - Fraction(row[0][1], row[0][0]))
                for key,row in buckets.items() if key != excluded), start=Fraction(0))


def _independent_effect(buckets, total):
    """Alternative inverse-probability reweighting of each individual arm's count."""
    value = Fraction(0)
    for row in buckets.values():
        mass = Fraction(row[0][0] + row[1][0], total)
        for treatment in (0, 1):
            value += (1 if treatment == 1 else -1) * mass * Fraction(row[treatment][1], row[treatment][0])
    return value


def _compute(req, model, total, buckets, start, deadline):
    result = q.EstimationResult(schema_version=1,
                                trace_id=req.trace_id, backend_id=BACKEND,
                                backend_version=VERSION, status=q.ESTIMATION_INCONCLUSIVE,
                                reason_code='NOT_COMPUTED')
    if req.backend == q.DOWHY_OPTIONAL_WORKER:
        result.status = q.ESTIMATION_BACKEND_UNAVAILABLE
        result.reason_code = 'DOWHY_WORKER_NOT_INTEGRATED'
        return result
    base = req.identification
    graph_ok = causal._backdoor(model,base.treatment,base.target,tuple(base.adjustment))
    graph_independent = causal._backdoor_independent(model,base.treatment,base.target,tuple(base.adjustment))
    if graph_ok != graph_independent:
        result.reason_code = 'GRAPH_CHECK_DISAGREEMENT'
        return result
    if not graph_ok:
        result.status = q.ADJUSTMENT_NOT_CERTIFIED
        result.reason_code = 'BACKDOOR_SUFFICIENCY_NOT_ESTABLISHED'
        return result
    result.graph_criterion_checked = True
    for key, arms in sorted(buckets.items()):
        if time.monotonic() > deadline:
            result.reason_code = 'DEADLINE'
            result.graph_criterion_checked = False
            return result
        n0,n1 = arms[0][0],arms[1][0]
        if min(n0,n1) < req.min_arm_count:
            result.status = q.POSITIVITY_NOT_MET
            result.reason_code = 'INSUFFICIENT_ARM_OVERLAP'
            result.graph_criterion_checked = False
            return result
    estimate = _effect(buckets, total)
    if estimate != _independent_effect(buckets,total):
        result.reason_code = 'INDEPENDENT_EFFECT_CHECK_FAILED'
        result.graph_criterion_checked = False
        return result
    variance = 0.0
    for key, arms in sorted(buckets.items()):
        n0,y0=arms[0]; n1,y1=arms[1]
        weight=Fraction(n0+n1,total)
        result.strata.add(covariate_states=key,control_count=n0,treated_count=n1,
                          observed_weight=_fraction(weight))
        p0,p1=y0/n0,y1/n1
        variance += float(weight)**2 * (p0*(1-p0)/n0 + p1*(1-p1)/n1)
    se=math.sqrt(variance)
    result.estimate = _fraction(estimate)
    result.standard_error = format(se, '.12g')
    result.ci95_lower = format(float(estimate)-Z95*se,'.12g')
    result.ci95_upper = format(float(estimate)+Z95*se,'.12g')
    result.uncertainty_method = 'NORMAL_PLUGIN_95_APPROX_NOT_VALIDATED_COVERAGE'
    if len(buckets) > 1:
        variants = [_effect(buckets,total,excluded=k) for k in buckets]
        result.leave_one_stratum_out_min = _fraction(min(variants))
        result.leave_one_stratum_out_max = _fraction(max(variants))
    result.status = q.ADJUSTED_EFFECT_COMPUTED
    result.reason_code = 'GRAPH_ASSUMPTIONS_NOT_EMPIRICALLY_VERIFIED'
    result.assurance = ASSURANCE
    result.independently_checked = True
    result.total_observations = total
    return result


def run_estimation_frame(raw, *, host_authorized=False, enabled=False):
    """Host-gated reference function; flags are NOT authenticated Lu identity."""
    start = time.monotonic_ns()
    result = q.EstimationResult(schema_version=1, request_sha256=hashlib.sha256(raw if isinstance(raw,bytes) else b'').digest(),
                                status=q.ESTIMATION_REJECTED, backend_id=BACKEND, backend_version=VERSION,
                                reason_code='INVALID_FRAME')
    try:
        req,model,total,buckets = _parse(raw)
        result.trace_id = req.trace_id
        if not host_authorized: raise ValueError('HOST_AUTHORIZATION_REQUIRED')
        if not enabled: raise ValueError('CAUSAL_ESTIMATION_DISABLED')
        deadline = time.monotonic() + req.timeout_ms / 1000.0
        result = _compute(req,model,total,buckets,start,deadline)
        result.request_sha256 = hashlib.sha256(raw).digest()
    except ValueError as exc:
        code = str(exc)
        result.reason_code = code if len(code) < 90 and code.isupper() else 'INVALID_OR_FAILED'
    except Exception:
        result.status = q.ESTIMATION_INCONCLUSIVE
        result.reason_code = 'ESTIMATION_RUNTIME_FAILURE'
    result.wall_ns = time.monotonic_ns() - start
    return _encode(result)


def verify_estimation_result(raw, reply):
    """Independent mathematical check; does not authenticate causal assumptions."""
    try:
        req,model,total,buckets = _parse(raw)
        result = _decode(reply,q.EstimationResult)
        if (result.schema_version != 1 or result.request_sha256 != hashlib.sha256(raw).digest() or
            result.trace_id != req.trace_id or result.backend_id != BACKEND or result.backend_version != VERSION):
            return False
        if result.status != q.ADJUSTED_EFFECT_COMPUTED:
            return False # Do not certify failed, missing or unavailable outcomes.
        expected = _compute(req,model,total,buckets,time.monotonic_ns(),time.monotonic()+5)
        if not expected.independently_checked or result.wall_ns < 0: return False
        result.wall_ns=0; expected.wall_ns=0
        expected.request_sha256=result.request_sha256
        return result.SerializeToString(deterministic=True) == expected.SerializeToString(deterministic=True)
    except Exception:
        return False


def estimation_receipt(raw, reply):
    ok=verify_estimation_result(raw,reply)
    return q.EstimationReceipt(request_sha256=hashlib.sha256(raw).digest(),
          result_sha256=hashlib.sha256(reply).digest(),computation_verified=ok,
          assurance=ASSURANCE if ok else 'NONE',reason_code='REFERENCE_CALCULATION_VERIFIED' if ok else 'UNVERIFIED_OR_NONRESULT')


def estimation_audit(raw, reply):
    result=_decode(reply,q.EstimationResult)
    return q.EstimationAudit(request_sha256=hashlib.sha256(raw).digest(),
          result_sha256=hashlib.sha256(reply).digest(),trace_id=result.trace_id,
          status=result.status,backend_id=result.backend_id,backend_version=result.backend_version,
          reason_code=result.reason_code,wall_ns=result.wall_ns)
