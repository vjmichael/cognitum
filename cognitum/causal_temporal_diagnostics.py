"""C14 P4C bounded temporal *diagnostics*, not causal discovery.

Checks actually provided observation timestamps. Reports missing expected grid slots
and off-grid intervals without imputing observations. For *exactly regular* data,
fits a bounded linear lag model and performs approximate Ljung-Box residual tests.
Diagnostics may flag violated assumptions but cannot prove stationarity, no
confounding, correct lag order, independent innovations, or real causation.
"""
from __future__ import annotations
import hashlib
import math
import re
import time
from cognitum.causal_estimation import _decode
from cognitum.proto import causal_temporal_diagnostics_pb2 as d
from cognitum.proto import causal_temporal_pb2 as a
from cognitum.planning import TRACE

MAX_FRAME = 250000
ID = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,31}\Z')
LIMITS = ('TIMESTAMP_CADENCE_VERIFIED_FROM_SUPPLIED_DATA_ONLY;NO_IMPUTATION;'
          'REGULAR_CADENCE_NOT_PROOF_OF_STATIONARITY_OR_EXOGENEITY;'
          'APPROXIMATE_LJUNG_BOX_RESIDUAL_TEST;MULTIPLE_TARGET_BONFERRONI;'
          'LINEAR_VAR_ASSUMED;NO_CAUSAL_IDENTIFICATION;NO_CI_PROOF;'
          'NO_TIGRAMITE_EXECUTION;NO_REAL_WORLD_CAUSAL_CLAIMS')


def _parse(raw):
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_FRAME:
        raise ValueError('INVALID_TEMP_DIAG_FRAME')
    req = _decode(raw, d.TemporalDiagnosticRequest)
    n = len(req.variable_ids)
    if (req.schema_version != 1 or not TRACE.fullmatch(req.trace_id) or
        not 2 <= n <= 4 or len(set(req.variable_ids)) != n or
        any(not ID.fullmatch(x) for x in req.variable_ids) or
        not 100 <= len(req.observations) <= 500 or
        not 1 <= req.declared_interval_ms <= 86400000 or
        not 1 <= req.max_lag <= 3 or
        not .0001 <= req.familywise_alpha <= .2 or
        not 1 <= req.timeout_ms <= 10000):
        raise ValueError('INVALID_TEMP_DIAG_REQUEST')
    old = None
    for row in req.observations:
        if len(row.values) != n or any(not math.isfinite(v) for v in row.values):
            raise ValueError('INVALID_TEMP_DIAG_OBSERVATIONS')
        if old is not None and row.timestamp_ms <= old:
            raise ValueError('NONMONOTONIC_OR_DUPLICATE_TIMESTAMPS')
        old = row.timestamp_ms
    return req


def _compute(req, raw, *, clock=time.monotonic):
    started = clock()
    result = d.TemporalDiagnosticResult(
        schema_version=1, request_sha256=hashlib.sha256(raw).digest(),
        trace_id=req.trace_id, status=d.TEMP_DIAG_COMPUTED,
        reason_code='NO_DIAGNOSTIC_FAILURE', assumptions_and_limits=LIMITS,
        observed_samples=len(req.observations))
    stamps = [r.timestamp_ms for r in req.observations]
    differences = [b-a for a,b in zip(stamps,stamps[1:])]
    expected = req.declared_interval_ms
    result.min_interval_ms = min(differences)
    result.max_interval_ms = max(differences)
    result.regular_cadence_checked = True
    nonmultiple = sum(dt % expected != 0 for dt in differences)
    result.irregular_intervals = sum(dt != expected for dt in differences)
    if nonmultiple:
        result.cadence = d.TEMP_CADENCE_IRREGULAR
        result.reason_code = 'OFF_GRID_IRREGULAR_SAMPLING_BLOCKED'
        return result
    gaps = sum(dt // expected-1 for dt in differences)
    result.missing_grid_slots = gaps
    if gaps:
        result.cadence = d.TEMP_CADENCE_GAPPED
        result.reason_code = 'MISSING_GRID_SLOTS_NO_IMPUTATION'
        return result
    result.cadence = d.TEMP_CADENCE_REGULAR
    # The bounded predictive regression design is identical to C14 P4A, but
    # here only residual autocorrelation is tested and the timestamp spacing
    # is actually checked against caller-declared cadence.
    import numpy as np
    from scipy.stats import chi2
    arr = np.asarray([row.values for row in req.observations], dtype=np.float64)
    lag = req.max_lag
    size, n = arr.shape
    effective = size-lag
    if (effective <= n*lag+20 or (time.monotonic()-started)*1000 >= req.timeout_ms):
        result.status = d.TEMP_DIAG_RESOURCE_LIMIT
        result.reason_code = 'INSUFFICIENT_SAMPLES_OR_TIME_BUDGET'
        return result
    design = np.column_stack([np.ones(effective)] +
        [arr[lag-k:size-k,j] for k in range(1,lag+1) for j in range(n)])
    if (np.linalg.matrix_rank(design) != design.shape[1] or
        np.linalg.cond(design) > 1e9):
        result.status = d.TEMP_DIAG_INCONCLUSIVE
        result.reason_code = 'COLLINEAR_OR_ILL_CONDITIONED_HISTORY'
        return result
    horizon = min(10, max(5, 2*lag), (effective-1)//5)
    if horizon <= lag:
        result.status = d.TEMP_DIAG_INCONCLUSIVE
        result.reason_code = 'INSUFFICIENT_LJUNG_BOX_DOF'
        return result
    for target in range(n):
        if (clock()-started)*1000 >= req.timeout_ms:
            result.status = d.TEMP_DIAG_RESOURCE_LIMIT
            result.reason_code = 'TOTAL_TIME_BUDGET_EXHAUSTED'
            del result.residual_tests[:]
            return result
        residual = arr[lag:,target]-design@np.linalg.lstsq(design,arr[lag:,target],rcond=None)[0]
        residual -= residual.mean()
        denom = float(residual @ residual)
        if denom < 1e-12 or not math.isfinite(denom):
            result.status = d.TEMP_DIAG_INCONCLUSIVE
            result.reason_code = 'DEGENERATE_REGRESSION_RESIDUAL'
            del result.residual_tests[:]
            return result
        corrs = [float(residual[k:]@residual[:-k])/denom for k in range(1,horizon+1)]
        statistic = effective*(effective+2)*sum(c*c/(effective-k) for k,c in enumerate(corrs,1))
        # Approximate fitted-AR correction; this test does NOT certify white noise.
        raw_p = float(chi2.sf(statistic,horizon-lag))
        if not math.isfinite(raw_p):
            result.status = d.TEMP_DIAG_INCONCLUSIVE
            result.reason_code = 'INVALID_LJUNG_BOX_P'
            del result.residual_tests[:]
            return result
        adjusted = min(1.0,n*raw_p)
        result.residual_tests.add(
            variable=target,tested_lags=horizon,ljung_box_q=format(statistic,'.12g'),
            raw_p=format(raw_p,'.12g'),bonferroni_p=format(adjusted,'.12g'),
            reject_white_noise=(adjusted < req.familywise_alpha))
    result.eligible_for_fixed_lag_screen = not any(x.reject_white_noise for x in result.residual_tests)
    result.reason_code = ('RESIDUAL_AUTOCORRELATION_FLAGGED' if not result.eligible_for_fixed_lag_screen
                          else 'CADENCE_CHECKED_NO_AUTOCORRELATION_REJECTION')
    return result


def run_temporal_diagnostics_frame(raw, *, host_authorized=False, enabled=False):
    start = time.monotonic_ns()
    out = d.TemporalDiagnosticResult(
        schema_version=1,
        request_sha256=hashlib.sha256(raw if isinstance(raw,bytes) else b'').digest(),
        status=d.TEMP_DIAG_REJECTED,
        reason_code='INVALID_TEMP_DIAG_FRAME',assumptions_and_limits=LIMITS)
    try:
        req = _parse(raw)
        out.trace_id=req.trace_id
        if not host_authorized:
            raise ValueError('HOST_AUTHORIZATION_REQUIRED')
        if not enabled:
            raise ValueError('TEMP_DIAGNOSTICS_DISABLED')
        out = _compute(req,raw)
    except (TypeError, ValueError) as err:
        code = str(err)
        out.reason_code = code if code.isupper() and len(code)<110 else 'INVALID_TEMP_DIAG_REQUEST'
    except (ImportError, ModuleNotFoundError):
        out.status = d.TEMP_DIAG_BACKEND_UNAVAILABLE
        out.reason_code = 'NUMERICAL_RUNTIME_UNAVAILABLE'
    except Exception:
        out.status = d.TEMP_DIAG_INCONCLUSIVE
        out.reason_code = 'TEMP_DIAG_RUNTIME_FAILURE'
    out.wall_ns = time.monotonic_ns()-start
    return out.SerializeToString(deterministic=True)


def temporal_diagnostics_receipt(raw, reply):
    receipt = d.TemporalDiagnosticReceipt(
        request_sha256=hashlib.sha256(raw if isinstance(raw,bytes) else b'').digest(),
        result_sha256=hashlib.sha256(reply if isinstance(reply,bytes) else b'').digest(),
        reason_code='NOT_VERIFIED')
    try:
        req = _parse(raw)
        got = _decode(reply,d.TemporalDiagnosticResult)
        if got.status!=d.TEMP_DIAG_COMPUTED or got.request_sha256!=receipt.request_sha256:
            return receipt
        expected = _compute(req,raw)
        expected.wall_ns = got.wall_ns
        if (expected.status==d.TEMP_DIAG_COMPUTED and
            got.SerializeToString(deterministic=True)==expected.SerializeToString(deterministic=True)):
            receipt.numerical_replay_checked = True
            receipt.reason_code='REPLAY_OF_TIMESTAMP_AND_LINEAR_DIAGNOSTICS_ONLY'
    except Exception:
        pass
    return receipt


def make_screen_from_regular_timestamps(raw, diagnostics_reply):
    """Return serialized P4A candidate only after replayable cadence/diagnostic checks.

    Does not authorize executing P4A, validate the causal assumptions, or
    guarantee correct stationarity/lag order. The *trusted host* must approve
    executing the returned request under P4A's own independent gate.
    """
    req = _parse(raw)
    diag = _decode(diagnostics_reply,d.TemporalDiagnosticResult)
    check = temporal_diagnostics_receipt(raw, diagnostics_reply)
    if not (check.numerical_replay_checked and
            diag.cadence == d.TEMP_CADENCE_REGULAR and
            diag.eligible_for_fixed_lag_screen):
        raise ValueError('TEMPORAL_SCREEN_PREFLIGHT_NOT_SATISFIED')
    target = a.TemporalScreenRequest(
        schema_version=1, trace_id=req.trace_id, variable_ids=req.variable_ids,
        interval_ms=req.declared_interval_ms,max_lag=req.max_lag,
        familywise_alpha=req.familywise_alpha,timeout_ms=req.timeout_ms)
    for row in req.observations:
        target.observations.add(values=row.values)
    return target.SerializeToString(deterministic=True)
