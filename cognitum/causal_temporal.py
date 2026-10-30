"""C14 P4A: bounded conditional Granger-style lagged predictive screening.

Nested linear models compare held-constant past histories. It is not a causal
intervention, causal discovery, neural causal model, or temporal SCM. It assumes
ordered equally spaced observations and independent model residuals for its
classical nested-model F p-values; these assumptions are not verified here.
"""
from __future__ import annotations
import hashlib
import math
import re
import time
from cognitum.causal_estimation import _decode
from cognitum.proto import causal_temporal_pb2 as t
from cognitum.planning import TRACE

MAX_FRAME=180000
IDENTIFIER=re.compile(r'[A-Za-z][A-Za-z0-9_]{0,31}\Z')
LIMITS=('CONDITIONAL_LAGGED_LINEAR_PREDICTIVE_SCREEN_ONLY;NO_CAUSAL_IDENTIFICATION;'
        'STATIONARITY_RESIDUAL_INDEPENDENCE_GAUSSIAN_NO_UNOBSERVED_CONFOUNDING_UNTESTED;'
        'BONFERRONI_FAMILYWISE_ADJUSTMENT;NO_CONTEMPORANEOUS_EFFECTS;'
        'FIXED_INTERVAL_ASSUMED_NOT_EXTERNALLY_VERIFIED')


def _parse(raw):
    if not isinstance(raw,bytes) or not raw or len(raw)>MAX_FRAME:
        raise ValueError('INVALID_TEMPORAL_FRAME')
    req=_decode(raw,t.TemporalScreenRequest)
    n=len(req.variable_ids)
    if (req.schema_version!=1 or not TRACE.fullmatch(req.trace_id) or
        not 2<=n<=4 or any(not IDENTIFIER.fullmatch(x) for x in req.variable_ids) or
        len(set(req.variable_ids))!=n or
        not 100<=len(req.observations)<=400 or
        not 1<=req.interval_ms<=86400000 or
        not 1<=req.max_lag<=3 or
        not .0001<=req.familywise_alpha<=.2 or
        not 1<=req.timeout_ms<=10000):
        raise ValueError('INVALID_TEMPORAL_REQUEST')
    if any(len(row.values)!=n or any(not math.isfinite(x) for x in row.values)
           for row in req.observations):
        raise ValueError('INVALID_TEMPORAL_OBSERVATIONS')
    if len(req.observations)-req.max_lag <= n*req.max_lag+10:
        raise ValueError('INSUFFICIENT_EFFECTIVE_SAMPLES')
    return req


def _fmt(x):
    return format(float(x),'.12g')


def _compute(req,raw,*,clock=time.monotonic):
    import numpy as np
    from scipy.stats import f as f_dist
    start=clock()
    rows=np.asarray([row.values for row in req.observations],dtype=np.float64)
    n=rows.shape[1]
    lags=req.max_lag
    nobs=rows.shape[0]-lags
    design=np.column_stack([np.ones(nobs)]+[
        rows[lags-k:rows.shape[0]-k,j] for k in range(1,lags+1) for j in range(n)])
    rank=np.linalg.matrix_rank(design)
    full_cols=design.shape[1]
    if rank!=full_cols or np.linalg.cond(design)>1e9:
        raise ValueError('COLLINEAR_OR_ILL_CONDITIONED_HISTORY')
    out=t.TemporalScreenResult(schema_version=1,trace_id=req.trace_id,
        request_sha256=hashlib.sha256(raw).digest(),status=t.TEMPORAL_INCONCLUSIVE,
        reason_code='NOT_COMPUTED',assumptions_and_limits=LIMITS)
    out.effective_samples=nobs
    count=n*(n-1)*lags
    df2=nobs-full_cols
    if df2<=10: raise ValueError('INSUFFICIENT_RESIDUAL_DOF')
    for target in range(n):
        if (clock()-start)*1000>=req.timeout_ms:
            out.status=t.TEMPORAL_RESOURCE_LIMIT
            out.reason_code='TOTAL_TIME_BUDGET_EXHAUSTED'
            return out
        dependent=rows[lags:,target]
        coef=np.linalg.lstsq(design,dependent,rcond=None)[0]
        residual=dependent-design@coef
        rss_full=float(residual@residual)
        if rss_full<=1e-14 or not math.isfinite(rss_full):
            raise ValueError('DEGENERATE_REGRESSION_RESIDUAL')
        for source in range(n):
            if source==target:continue
            for lag in range(1,lags+1):
                if (clock()-start)*1000>=req.timeout_ms:
                    out.status=t.TEMPORAL_RESOURCE_LIMIT
                    out.reason_code='TOTAL_TIME_BUDGET_EXHAUSTED'
                    return out
                index=1+(lag-1)*n+source
                reduced=np.delete(design,index,axis=1)
                beta=np.linalg.lstsq(reduced,dependent,rcond=None)[0]
                errors=dependent-reduced@beta
                rss_reduced=float(errors@errors)
                # floating arithmetic may produce tiny negative differences
                difference=max(0.0,rss_reduced-rss_full)
                statistic=difference/(rss_full/df2)
                p=float(f_dist.sf(statistic,1,df2))
                if not math.isfinite(p):raise ValueError('INVALID_P_VALUE')
                adjusted=min(1.0,p*count)
                out.screens.add(source=source,target=target,lag=lag,
                    coefficient=_fmt(coef[index]),f_statistic=_fmt(statistic),
                    unadjusted_p=_fmt(p),bonferroni_adjusted_p=_fmt(adjusted),
                    passes_familywise_threshold=adjusted<=req.familywise_alpha)
    out.tests_executed=count
    out.status=t.TEMPORAL_SCREEN_COMPUTED
    out.reason_code='LAGGED_PREDICTIVE_ASSOCIATIONS_ONLY'
    return out


def run_temporal_frame(raw,*,host_authorized=False,enabled=False):
    start=time.monotonic_ns()
    out=t.TemporalScreenResult(schema_version=1,
        request_sha256=hashlib.sha256(raw if isinstance(raw,bytes) else b'').digest(),
        status=t.TEMPORAL_REJECTED,reason_code='INVALID_TEMPORAL_FRAME',assumptions_and_limits=LIMITS)
    try:
        req=_parse(raw)
        out.trace_id=req.trace_id
        if not host_authorized:raise ValueError('HOST_AUTHORIZATION_REQUIRED')
        if not enabled:raise ValueError('TEMPORAL_SCREEN_DISABLED')
        out=_compute(req,raw)
    except (ValueError,TypeError) as exc:
        reason=str(exc)
        if reason in ('COLLINEAR_OR_ILL_CONDITIONED_HISTORY',
                      'DEGENERATE_REGRESSION_RESIDUAL','INVALID_P_VALUE'):
            out.status=t.TEMPORAL_INCONCLUSIVE
        out.reason_code=reason if reason.isupper() and len(reason)<100 else 'INVALID_TEMPORAL_REQUEST'
    except (ImportError,ModuleNotFoundError):
        out.status=t.TEMPORAL_BACKEND_UNAVAILABLE
        out.reason_code='NUMERICAL_RUNTIME_UNAVAILABLE'
    except Exception:
        out.status=t.TEMPORAL_INCONCLUSIVE
        out.reason_code='TEMPORAL_RUNTIME_FAILURE'
    if out.status!=t.TEMPORAL_SCREEN_COMPUTED:
        del out.screens[:]
        out.tests_executed=0
        out.effective_samples=0
    out.wall_ns=time.monotonic_ns()-start
    return out.SerializeToString(deterministic=True)


def temporal_receipt(raw,reply):
    out=t.TemporalScreenReceipt(
        request_sha256=hashlib.sha256(raw if isinstance(raw,bytes) else b'').digest(),
        result_sha256=hashlib.sha256(reply if isinstance(reply,bytes) else b'').digest(),
        reason_code='NOT_VERIFIED')
    try:
        req=_parse(raw)
        got=_decode(reply,t.TemporalScreenResult)
        if got.status!=t.TEMPORAL_SCREEN_COMPUTED or got.request_sha256!=out.request_sha256:
            return out
        expected=_compute(req,raw)
        expected.wall_ns=got.wall_ns
        if expected.status==t.TEMPORAL_SCREEN_COMPUTED and got.SerializeToString(deterministic=True)==expected.SerializeToString(deterministic=True):
            out.numerical_replay_checked=True
            out.reason_code='NESTED_MODEL_NUMERICAL_REPLAY_ONLY'
    except Exception:
        pass
    return out
