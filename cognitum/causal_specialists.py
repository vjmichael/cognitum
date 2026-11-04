"""C14 bounded causal specialists: maintained engines, strict epistemic status.

No dynamic model-authored code, network access, filesystem operations, grants,
Lu exposure, automatic causal assumption inference, or custom optimizer.

This module is a *trusted, in-process component* pending host isolation/approval
and actual backend-specific acceptance. Caller MUST enforce execution deadlines
outside this process: scientific libraries cannot be safely interrupted via Python.
"""
from __future__ import annotations

import hashlib
import importlib
import math
import re
from dataclasses import dataclass

from .proto import causal_pb2 as pb

MAX_INPUT_BYTES = 512 * 1024
MAX_OUTPUT_BYTES = 64 * 1024
MAX_ROWS = 2048
MAX_COLUMNS = 12
NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,31}\Z", re.ASCII)
OPERATIONS = {
    'ate_statsmodels': 'statsmodels',
    'ate_dowhy': 'dowhy',
    'conditional_effect_econml': 'econml',
    'discover_pc': 'causal-learn',
    'discover_pcmci': 'tigramite',
}
EFFECT_ASSUMPTIONS = frozenset({
    'consistency', 'no_interference', 'conditional_exchangeability', 'positivity',
})
PC_ASSUMPTIONS = frozenset({'causal_markov', 'faithfulness', 'causal_sufficiency', 'iid_sampling'})
PCMCI_ASSUMPTIONS = frozenset({'causal_markov', 'faithfulness', 'causal_sufficiency',
                                'causal_stationarity', 'no_contemporaneous_effects'})
ALL_ASSUMPTIONS = EFFECT_ASSUMPTIONS | PC_ASSUMPTIONS | PCMCI_ASSUMPTIONS
LIMITS_EFFECT = ('assumptions_declared_not_verified', 'observational_causal_identification_not_verified',
                 'confounding_and_model_misspecification_possible', 'no_global_optimality_claim')
LIMITS_DISCOVERY = ('assumptions_declared_not_verified', 'graph_discovery_not_causal_identification',
                    'link_statistics_not_treatment_effects', 'no_global_optimality_claim')


class CausalInputError(Exception):
    def __init__(self, code='invalid_request'):
        self.code = code


class CausalBackendError(Exception):
    def __init__(self, code='backend_failure'):
        self.code = code


@dataclass(frozen=True)
class Validated:
    req: object
    names: tuple[str, ...]
    assumptions: tuple[str, ...]
    matrix: object  # numpy.ndarray, native library imported only for valid data


def _finite(x):
    return math.isfinite(float(x))


def _check_wire(blob):
    if type(blob) is not bytes or not 0 < len(blob) <= MAX_INPUT_BYTES:
        raise CausalInputError('invalid_wire')
    req = pb.CausalRequest()
    try:
        req.ParseFromString(blob)
    except Exception as e:
        raise CausalInputError('invalid_wire') from e
    clean = pb.CausalRequest()
    clean.CopyFrom(req)
    clean.DiscardUnknownFields()
    if clean != req or req.SerializeToString(deterministic=True) != blob:
        raise CausalInputError('noncanonical_wire')
    return req


def _no_graph(req):
    return not req.graph_edges and not req.treatment and not req.outcome and not req.adjustment and not req.effect_modifiers and not req.modifier_profile


def _validate(req):
    if req.schema_version != 1 or req.operation not in OPERATIONS:
        raise CausalInputError('unsupported_operation_or_schema')
    cols = tuple(req.columns)
    if not 2 <= len(cols) <= MAX_COLUMNS or len(set(cols)) != len(cols) or any(NAME.fullmatch(x) is None for x in cols):
        raise CausalInputError('invalid_columns')
    if not 40 <= len(req.rows) <= MAX_ROWS:
        raise CausalInputError('invalid_row_count')
    if any(len(r.values) != len(cols) or any(not _finite(x) for x in r.values) for r in req.rows):
        raise CausalInputError('nonfinite_or_ragged_data')
    if not 0.001 <= req.alpha <= 0.2 or not _finite(req.alpha):
        raise CausalInputError('invalid_alpha')
    assumptions = tuple(req.declared_assumptions)
    needed = (EFFECT_ASSUMPTIONS if req.operation.startswith(('ate_', 'conditional_'))
              else PC_ASSUMPTIONS if req.operation == 'discover_pc' else PCMCI_ASSUMPTIONS)
    if not set(needed).issubset(assumptions) or len(set(assumptions)) != len(assumptions) or set(assumptions) - ALL_ASSUMPTIONS:
        raise CausalInputError('assumptions_not_declared')
    # Only import numpy after bounded finite/shape inspection.
    try:
        np = importlib.import_module('numpy')
    except ImportError as e:
        raise CausalBackendError('optional_dependency_unavailable') from e
    a = np.asarray([list(r.values) for r in req.rows], dtype=float)
    if not np.isfinite(a).all():
        raise CausalInputError('nonfinite_data')
    if any(float(np.var(a[:, k])) < 1e-14 for k in range(len(cols))):
        raise CausalInputError('constant_or_degenerate_column')
    if req.operation in ('discover_pc', 'discover_pcmci'):
        if not _no_graph(req):
            raise CausalInputError('unexpected_estimation_fields')
        if req.operation == 'discover_pc' and req.max_lag != 0:
            raise CausalInputError('unexpected_lag')
        if req.operation == 'discover_pcmci' and not 1 <= req.max_lag <= 5:
            raise CausalInputError('invalid_lag')
        if req.operation == 'discover_pcmci' and len(req.rows) < 15 * req.max_lag + 40:
            raise CausalInputError('insufficient_time_samples')
        return Validated(req, cols, assumptions, a)

    if req.treatment not in cols or req.outcome not in cols or req.treatment == req.outcome:
        raise CausalInputError('invalid_treatment_or_outcome')
    adj,mods=tuple(req.adjustment),tuple(req.effect_modifiers)
    if (len(set(adj)) != len(adj) or len(set(mods)) != len(mods) or
        any(x not in cols or x in (req.treatment,req.outcome) for x in adj+mods) or
        len(set(adj) & set(mods)) != 0):
        raise CausalInputError('invalid_covariates')
    if req.operation != 'conditional_effect_econml' and (mods or req.modifier_profile):
        raise CausalInputError('unexpected_modifiers')
    if req.operation == 'conditional_effect_econml':
        if not mods or len(req.modifier_profile) != len(mods) or any(not _finite(x) for x in req.modifier_profile):
            raise CausalInputError('invalid_modifier_profile')
    if req.max_lag:
        raise CausalInputError('unexpected_lag')
    t = a[:, cols.index(req.treatment)]
    if not np.isin(t, [0.,1.]).all() or min((t == 0).sum(), (t == 1).sum()) < 12:
        raise CausalInputError('positivity_not_supported_by_observed_groups')
    if len(req.rows) < max(50, 12 * (len(adj)+len(mods)+2)):
        raise CausalInputError('insufficient_samples')
    if req.operation == 'ate_dowhy':
        _check_dag(req, cols)
    elif req.graph_edges:
        raise CausalInputError('unexpected_graph')
    return Validated(req, cols, assumptions, a)


def _check_dag(req, cols):
    if not 1 <= len(req.graph_edges) <= 50:
        raise CausalInputError('explicit_graph_required')
    edges=set(); graph={c:[] for c in cols}
    for e in req.graph_edges:
        if (e.source not in graph or e.target not in graph or e.source == e.target or
            e.lag or e.orientation or e.statistic or e.p_value or (e.source,e.target) in edges):
            raise CausalInputError('invalid_graph_edge')
        graph[e.source].append(e.target)
        edges.add((e.source,e.target))
    colors={c:0 for c in cols}
    def visit(x):
        if colors[x]==1:raise CausalInputError('cyclic_graph')
        if colors[x]==2:return
        colors[x]=1
        for v in graph[x]:visit(v)
        colors[x]=2
    for c in cols:visit(c)
    if (req.treatment,req.outcome) not in edges and req.outcome not in _descendants(req.treatment,graph):
        raise CausalInputError('no_treatment_to_outcome_path')
    # The externally declared adjustment set must be explicitly present in the DAG.
    for c in req.adjustment:
        if (c,req.treatment) not in edges and (c,req.outcome) not in edges:
            raise CausalInputError('adjustment_not_in_graph')


def _descendants(start, graph):
    seen=set();todo=list(graph[start]);
    while todo:
        x=todo.pop()
        if x not in seen:
            seen.add(x);todo.extend(graph[x])
    return seen


def _clean_effect(value, lo, hi):
    import numpy as np
    try:
        if any(np.asarray(z).size != 1 for z in (value,lo,hi)):
            raise CausalBackendError('malformed_backend_interval')
        x=float(np.asarray(value).reshape(-1)[0]); l=float(np.asarray(lo).reshape(-1)[0]); h=float(np.asarray(hi).reshape(-1)[0])
    except (TypeError,ValueError,IndexError) as e:
        raise CausalBackendError('malformed_backend_interval') from e
    if not all(map(math.isfinite,(x,l,h))) or not l <= x <= h:
        raise CausalBackendError('malformed_backend_interval')
    return x,l,h


def _estimate_statsmodels(v, out):
    import numpy as np
    sm=importlib.import_module('statsmodels.api')
    q=v.req;a=v.matrix; idx={n:i for i,n in enumerate(v.names)}
    matrix=np.column_stack([np.ones(len(a)),a[:,idx[q.treatment]],*[a[:,idx[c]] for c in q.adjustment]])
    if np.linalg.matrix_rank(matrix) != matrix.shape[1] or np.linalg.cond(matrix)>1e8:
        raise CausalInputError('rank_deficient_design')
    fit=sm.OLS(a[:,idx[q.outcome]],matrix).fit(cov_type='HC3')
    p=np.asarray(fit.params); bounds=np.asarray(fit.conf_int(alpha=q.alpha))
    x,l,h=_clean_effect(p[1],bounds[1,0],bounds[1,1])
    out.estimand='backdoor_ate_linear_additive_model'
    out.effect=x;out.interval_lower=l;out.interval_upper=h
    out.has_effect=True;out.has_interval=True;out.confidence_level=1-q.alpha
    out.uncertainty_kind='HC3_asymptotic_confidence_interval'


def _estimate_dowhy(v,out):
    # No arbitrary method string, graph text, or user-authored Python goes to DoWhy.
    import pandas as pd
    m=importlib.import_module('dowhy')
    q=v.req
    frame=pd.DataFrame(v.matrix,columns=v.names)
    edges=' '.join(f'{e.source} -> {e.target};' for e in q.graph_edges)
    graph='digraph {'+edges+'}'
    model=m.CausalModel(data=frame,treatment=q.treatment,outcome=q.outcome,graph=graph,
                        proceed_when_unidentifiable=False)
    estimand=model.identify_effect(proceed_when_unidentifiable=False)
    if estimand is None or not getattr(estimand,'estimands',{}).get('backdoor'):
        raise CausalBackendError('effect_not_identified')
    # Require matching declared covariate set: do not quietly switch estimands.
    identified=set(estimand.get_backdoor_variables())
    if identified != set(q.adjustment):
        raise CausalBackendError('adjustment_set_disagrees_with_identification')
    # DoWhy establishes an identified *graphical* backdoor estimand.
    # Independently compute an HC3 interval using a maintained regression
    # engine: DoWhy estimators do not all expose intervals consistently.
    estimate=model.estimate_effect(estimand,method_name='backdoor.linear_regression',
                                   confidence_intervals=False,control_value=0,treatment_value=1)
    _estimate_statsmodels(v,out)
    try:
        from numpy import asarray
        if asarray(estimate.value).size != 1:
            raise CausalBackendError('malformed_backend_result')
        dowhy_value=float(asarray(estimate.value).reshape(-1)[0])
    except (TypeError,ValueError,AttributeError,IndexError) as e:
        raise CausalBackendError('malformed_backend_result') from e
    if (not math.isfinite(dowhy_value) or
        abs(dowhy_value-out.effect)>max(1e-6,1e-3*max(abs(dowhy_value),abs(out.effect)))):
        raise CausalBackendError('backdoor_estimator_disagreement')
    out.estimand='dag_identified_backdoor_ate_linear_model'
    out.uncertainty_kind='HC3_asymptotic_interval_after_DAG_identification'



def _estimate_econml(v,out):
    import numpy as np
    dml=importlib.import_module('econml.dml')
    q=v.req;idx={n:i for i,n in enumerate(v.names)};a=v.matrix
    x=a[:,[idx[z] for z in q.effect_modifiers]]
    w=a[:,[idx[z] for z in q.adjustment]] if q.adjustment else None
    model=dml.LinearDML(discrete_treatment=True,cv=3,random_state=0)
    model.fit(Y=a[:,idx[q.outcome]],T=a[:,idx[q.treatment]].astype(int),X=x,W=w,inference='auto')
    profile=np.asarray([list(q.modifier_profile)],dtype=float)
    effect=model.effect(profile,T0=0,T1=1)
    interval=model.effect_interval(profile,T0=0,T1=1,alpha=q.alpha)
    if not isinstance(interval,(tuple,list)) or len(interval)!=2:
        raise CausalBackendError('interval_not_available')
    x0,l,h=_clean_effect(effect,interval[0],interval[1])
    out.estimand='conditional_binary_treatment_effect_at_explicit_profile'
    out.effect=x0;out.interval_lower=l;out.interval_upper=h
    out.has_effect=True;out.has_interval=True;out.confidence_level=1-q.alpha
    out.uncertainty_kind='backend_conditional_confidence_interval'


def _discover_pc(v,out):
    import numpy as np
    mod=importlib.import_module('causallearn.search.ConstraintBased.PC')
    graph=mod.pc(v.matrix,alpha=v.req.alpha,indep_test='fisherz',stable=True,
                 verbose=False,show_progress=False)
    matrix=np.asarray(graph.G.graph)
    n=len(v.names)
    if matrix.shape!=(n,n) or not np.isin(matrix,[-1,0,1,2]).all():
        raise CausalBackendError('malformed_graph')
    for i in range(n):
        for j in range(i+1,n):
            u=int(matrix[i,j]);w=int(matrix[j,i])
            if u==0 and w==0:continue
            if u==-1 and w==1:src,tgt,kind=v.names[i],v.names[j],'directed'
            elif u==1 and w==-1:src,tgt,kind=v.names[j],v.names[i],'directed'
            elif u==-1 and w==-1:src,tgt,kind=v.names[i],v.names[j],'undirected'
            else:src,tgt,kind=v.names[i],v.names[j],'uncertain_endpoints'
            out.discovered_edges.add(source=src,target=tgt,orientation=kind)
    out.estimand='constraint_based_graph_discovery_not_effect'
    out.uncertainty_kind='not_calibrated_no_effect_interval'


def _discover_pcmci(v,out):
    import numpy as np
    df=importlib.import_module('tigramite.data_processing')
    cond=importlib.import_module('tigramite.independence_tests.parcorr')
    pcm=importlib.import_module('tigramite.pcmci')
    dataframe=df.DataFrame(v.matrix,var_names=list(v.names))
    algo=pcm.PCMCI(dataframe=dataframe,cond_ind_test=cond.ParCorr(significance='analytic'),verbosity=0)
    q=v.req
    results=algo.run_pcmci(tau_min=1,tau_max=q.max_lag,pc_alpha=q.alpha,
                           alpha_level=q.alpha,fdr_method='fdr_bh')
    p=np.asarray(results['p_matrix']);strength=np.asarray(results['val_matrix'])
    orientations=np.asarray(results['graph'])
    n=len(v.names)
    if p.shape!=(n,n,q.max_lag+1) or strength.shape!=p.shape or orientations.shape!=p.shape:
        raise CausalBackendError('malformed_graph')
    for i in range(n):
        for j in range(n):
            for lag in range(1,q.max_lag+1):
                if str(orientations[i,j,lag])=='-->':
                    score=float(strength[i,j,lag]);pv=float(p[i,j,lag])
                    if not _finite(score) or not 0<=pv<=1:
                        raise CausalBackendError('malformed_backend_uncertainty')
                    if pv <= q.alpha:
                        out.discovered_edges.add(source=v.names[i],target=v.names[j],lag=lag,
                                                orientation='directed_lagged',statistic=score,p_value=pv)
    out.estimand='time_lagged_graph_discovery_not_effect'
    out.uncertainty_kind='fdr_adjusted_link_p_values_not_confidence_intervals'


def _clear_computed(out):
    for field in ('effect','interval_lower','interval_upper','confidence_level','estimand','uncertainty_kind'):
        out.ClearField(field)
    out.ClearField('discovered_edges')
    out.has_effect=False
    out.has_interval=False


def run_causal_wire(blob: bytes, *, enable_gpl_tigramite: bool=False) -> bytes:
    """Execute bounded specialist behind a host-owned resource/authorization gate.

    The flag is a trusted *caller* policy, intentionally NOT present in protobuf.
    Libraries execute in-process; the host MUST isolate/time-limit the process.
    """
    if type(enable_gpl_tigramite) is not bool:
        raise TypeError('invalid host policy')
    req=_check_wire(blob)
    out=pb.CausalReply(schema_version=1,input_sha256=hashlib.sha256(blob).hexdigest(),
                       backend=OPERATIONS.get(req.operation,'unknown'))
    try:
        v=_validate(req)
        out.declared_assumptions.extend(v.assumptions)
        if req.operation=='discover_pcmci' and not enable_gpl_tigramite:
            raise CausalBackendError('license_review_required')
        fn={
            'ate_statsmodels':_estimate_statsmodels,
            'ate_dowhy':_estimate_dowhy,
            'conditional_effect_econml':_estimate_econml,
            'discover_pc':_discover_pc,
            'discover_pcmci':_discover_pcmci,
        }[req.operation]
        fn(v,out)
        # Validate that we did not accidentally publish nonfinite/invalid output.
        if out.has_effect and (not out.has_interval or not all(map(_finite,(out.effect,out.interval_lower,out.interval_upper)))
                               or not out.interval_lower <= out.effect <= out.interval_upper):
            raise CausalBackendError('malformed_backend_interval')
        if not out.estimand or not out.uncertainty_kind:
            raise CausalBackendError('malformed_backend_result')
        out.limitations.extend(LIMITS_EFFECT if out.has_effect else LIMITS_DISCOVERY)
        out.status='completed';out.code='ok'
    except CausalInputError as e:
        _clear_computed(out)
        out.ClearField('declared_assumptions')
        out.status='invalid_input';out.code=e.code;out.limitations.append('no_computed_answer')
    except (ImportError,ModuleNotFoundError):
        _clear_computed(out)
        out.status='unavailable';out.code='optional_dependency_unavailable';out.limitations.append('no_computed_answer')
    except CausalBackendError as e:
        _clear_computed(out)
        out.status='unavailable' if e.code in ('license_review_required','optional_dependency_unavailable') else 'error'
        out.code=e.code;out.limitations.append('no_computed_answer')
    except Exception:
        # No arbitrary library exception strings or dataset values in the reply.
        _clear_computed(out)
        out.status='error';out.code='backend_failure';out.limitations.append('no_computed_answer')
    raw=out.SerializeToString(deterministic=True)
    if len(raw)>MAX_OUTPUT_BYTES:
        raise CausalBackendError('output_size_limit')
    return raw
