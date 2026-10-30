"""C14 P4D: bounded regular-cadence *statistical* stationarity/stability checks.

Real statsmodels ADF (unit-root null), KPSS (level-stationarity null), and
intercept-only OLS CUSUM (mean stability null). No automatic differencing,
interpolation, causal identification, future prediction, or tool authorization.
"""
from __future__ import annotations
import hashlib
import importlib.metadata
import math
import time
import warnings
from cognitum.causal_estimation import _decode
from cognitum.causal_temporal_diagnostics import _parse as parse_p4c
from cognitum.proto import causal_temporal_advanced_pb2 as d

MAX_FRAME=260000
LIMITS=('ADF_NULL_UNIT_ROOT;KPSS_NULL_LEVEL_STATIONARITY;'
        'CUSUM_NULL_MEAN_STABILITY_INTERCEPT_ONLY;'
        'BONFERRONI_ACROSS_VARIABLES_AND_THREE_TEST_FAMILIES;'
        'KPSS_TABLE_PVALUES_MAY_BE_BOUNDARY_CENSORED;'
        'NON_REJECTION_NEVER_PROVES_A_NULL;FINITE_SAMPLE_ASSUMPTIONS_UNCHECKED;'
        'NO_INTERPOLATION_OR_AUTO_DIFFERENCING;NO_CAUSAL_DISCOVERY_OR_PROOF;'
        'NO_TIGRAMITE_PCMCI_RUNTIME_OR_WINDOWS_LU_SECURITY_ATTESTATION')


def _parse(raw):
    if not isinstance(raw,bytes) or not raw or len(raw)>MAX_FRAME:
        raise ValueError('INVALID_ADV_TEMP_FRAME')
    req=_decode(raw,d.TemporalAdvancedRequest)
    samples=req.samples
    if req.schema_version!=1 or req.timeout_ms<1 or req.timeout_ms>10000 or req.adf_maxlag>3:
        raise ValueError('INVALID_ADV_TEMP_REQUEST')
    # Existing strict field, number, trace, sample count, size, monotonicity
    # and budget validation; no schema changes to the P4C contract.
    parse_p4c(samples.SerializeToString(deterministic=True))
    return req


def _fmt(x):
    if not math.isfinite(float(x)):
        raise ValueError('NONFINITE_STATISTIC')
    return format(float(x),'.12g')


def _compute(req,raw,*,clock=time.monotonic):
    started=clock()
    samples=req.samples
    out=d.TemporalAdvancedResult(schema_version=1,trace_id=samples.trace_id,
        request_sha256=hashlib.sha256(raw).digest(),
        status=d.ADV_INCONCLUSIVE,reason_code='NOT_EVALUATED',
        backend_id='statsmodels-adf-kpss-cusum',assumptions_and_limits=LIMITS)
    intervals=[b.timestamp_ms-a.timestamp_ms for a,b in
               zip(samples.observations,samples.observations[1:])]
    if any(delta != samples.declared_interval_ms for delta in intervals):
        out.reason_code='NONREGULAR_TIMESTAMPS_NO_INTERPOLATION'
        return out
    out.regular_cadence_checked=True
    # Explicit optional mature-library baseline; do not fallback to homemade
    # hypothesis tests if the dependency is missing.
    import numpy as np
    from statsmodels.tsa.stattools import adfuller,kpss
    from statsmodels.stats.diagnostic import breaks_cusumolsresid
    from statsmodels.tools.sm_exceptions import InterpolationWarning
    out.backend_version=importlib.metadata.version('statsmodels')
    data=np.asarray([row.values for row in samples.observations],dtype=float)
    size,cols=data.shape
    # Whole-family Bonferroni across 3 tests * each observed variable, rather
    # than uncorrected significance over multiple targets and nulls.
    family_count=3*cols
    cutoff=samples.familywise_alpha/family_count
    for col in range(cols):
        if (clock()-started)*1000>=req.timeout_ms:
            out.status=d.ADV_RESOURCE_LIMIT
            out.reason_code='TOTAL_TIME_BUDGET_EXHAUSTED'
            del out.diagnostics[:]
            return out
        series=data[:,col]
        if np.std(series)<1e-10:
            out.reason_code='CONSTANT_OR_DEGENERATE_SERIES'
            del out.diagnostics[:]
            return out
        try:
            # Fixed, declared lag count prevents silent algorithm selection.
            adf=adfuller(series,maxlag=req.adf_maxlag,regression='c',autolag=None)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always',InterpolationWarning)
                kp=kpss(series,regression='c',nlags='auto')
            bound=any(issubclass(w.category,InterpolationWarning) for w in caught)
            # Mean-stability test only. No regression slope stability claim.
            cusum=breaks_cusumolsresid(series-series.mean(),ddof=1)
            a_stat,a_p,a_lags=adf[0],adf[1],adf[2]
            k_stat,k_p,k_lags=kp[0],kp[1],kp[2]
            c_stat,c_p=cusum[0],cusum[1]
            if not all(math.isfinite(float(z)) and 0 <= float(z) <= 1
                       for z in (a_p,k_p,c_p)):
                raise ValueError('INVALID_REFERENCE_P_VALUE')
            adf_reject=a_p<cutoff
            kpss_reject=k_p<cutoff
            if adf_reject and not kpss_reject:
                signal='PATTERN_COMPATIBLE_WITH_LEVEL_STATIONARITY_NOT_PROOF'
            elif not adf_reject and kpss_reject:
                signal='PATTERN_OPPOSES_LEVEL_STATIONARITY_NOT_PROOF'
            elif adf_reject and kpss_reject:
                signal='CONFLICTING_NULL_REJECTIONS'
            else:
                signal='BOTH_NULLS_UNREJECTED_INCONCLUSIVE'
            out.diagnostics.add(
                variable=col,adf_statistic=_fmt(a_stat),adf_raw_p=_fmt(a_p),
                adf_adjusted_p=_fmt(min(1.,family_count*a_p)),
                kpss_statistic=_fmt(k_stat),kpss_raw_p=_fmt(k_p),
                kpss_adjusted_p=_fmt(min(1.,family_count*k_p)),
                cusum_statistic=_fmt(c_stat),cusum_raw_p=_fmt(c_p),
                cusum_adjusted_p=_fmt(min(1.,family_count*c_p)),
                stationarity_signal=signal,possible_mean_instability=(c_p<cutoff),
                adf_lag=a_lags,kpss_lags=k_lags,kpss_table_boundary=bound)
        except (ValueError,ZeroDivisionError,ArithmeticError):
            out.reason_code='STATISTICAL_TEST_UNDEFINED_OR_NUMERICAL_FAILURE'
            del out.diagnostics[:]
            return out
    out.status=d.ADV_COMPUTED
    out.reason_code='STATISTICAL_DIAGNOSTICS_ONLY_NOT_CAUSAL'
    return out


def run_temporal_advanced_frame(raw,*,host_authorized=False,enabled=False):
    started=time.monotonic_ns()
    out=d.TemporalAdvancedResult(schema_version=1,
        request_sha256=hashlib.sha256(raw if isinstance(raw,bytes) else b'').digest(),
        status=d.ADV_REJECTED,reason_code='INVALID_ADV_TEMP_FRAME',
        assumptions_and_limits=LIMITS)
    try:
        req=_parse(raw)
        out.trace_id=req.samples.trace_id
        if not host_authorized:raise ValueError('HOST_AUTHORIZATION_REQUIRED')
        if not enabled:raise ValueError('ADV_TEMP_DISABLED')
        out=_compute(req,raw)
    except (ValueError,TypeError) as err:
        code=str(err)
        out.reason_code=code if code.isupper() and len(code)<110 else 'INVALID_ADV_TEMP_REQUEST'
    except (ImportError,ModuleNotFoundError):
        out.status=d.ADV_BACKEND_UNAVAILABLE
        out.reason_code='STATSMODELS_NUMERICAL_BACKEND_UNAVAILABLE'
    except Exception:
        out.status=d.ADV_INCONCLUSIVE
        out.reason_code='ADV_TEMP_RUNTIME_FAILURE'
    out.wall_ns=time.monotonic_ns()-started
    return out.SerializeToString(deterministic=True)


def temporal_advanced_receipt(raw,reply):
    result=d.TemporalAdvancedReceipt(
        request_sha256=hashlib.sha256(raw if isinstance(raw,bytes) else b'').digest(),
        result_sha256=hashlib.sha256(reply if isinstance(reply,bytes) else b'').digest(),
        reason_code='NOT_VERIFIED')
    try:
        req=_parse(raw)
        got=_decode(reply,d.TemporalAdvancedResult)
        if got.request_sha256 !=result.request_sha256 or got.status!=d.ADV_COMPUTED:
            return result
        expected=_compute(req,raw)
        expected.wall_ns=got.wall_ns
        if (expected.status==d.ADV_COMPUTED and
            got.SerializeToString(deterministic=True)==expected.SerializeToString(deterministic=True)):
            result.same_backend_replay_checked=True
            result.reason_code='STATS_MODELS_SAME_BACKEND_REPLAY_NOT_INDEPENDENT_PROOF'
    except Exception:
        pass
    return result
