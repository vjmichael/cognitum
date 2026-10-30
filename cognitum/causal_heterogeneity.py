"""C14 P3A: bounded conditional effect heterogeneity, NOT causal discovery.

Every reported conditional effect assumes the supplied graph and backdoor criterion.
The modifier must be a member of the pre-treatment adjustment set, avoiding
unjustified conditioning on arbitrary post-treatment variables. This is a
stratified empirical reference, NOT EconML or a causal truth certificate.
"""
from __future__ import annotations
from collections import defaultdict
from fractions import Fraction
import hashlib
import math
import time

from cognitum.causal_estimation import (_parse, _compute, _effect, _independent_effect,
    _decode, BACKEND as P2_BACKEND, Z95)
from cognitum.planning import _encode
from cognitum.proto import causal_heterogeneity_pb2 as h, causal_estimation_pb2 as q

VERSION='C14-P3A-1'
BACKEND='c14-conditional-stratified-reference'
ASSURANCE='ASSUMED_GRAPH_CONDITIONAL_EMPIRICAL_EFFECTS'
MAX_FRAME=131072


def _parse_request(raw):
    req=_decode(raw,h.HeterogeneityRequest)
    if (req.schema_version!=1 or not 1<=req.timeout_ms<=5000 or not 1<=req.max_subgroups<=64 or
        req.method not in (h.REFERENCE_CONDITIONAL_STANDARDIZATION,h.ECONML_CATE_OPTIONAL)):
        raise ValueError('INVALID_HETEROGENEITY_REQUEST')
    if req.estimation.backend!=q.REFERENCE_STRATIFIED_ADJUSTMENT:
        raise ValueError('REFERENCE_BACKEND_REQUIRED')
    data=req.estimation.SerializeToString(deterministic=True)
    base,model,total,buckets=_parse(data)
    mods=tuple(req.modifier_indices)
    allowed=set(base.identification.adjustment)
    if (not 1<=len(mods)<=2 or len(set(mods))!=len(mods) or
        not set(mods)<=allowed or any(x>=len(model.endo_dims) for x in mods)):
        raise ValueError('MODIFIERS_MUST_BE_PRETREATMENT_ADJUSTMENT_SUBSET')
    positions=tuple(tuple(base.identification.adjustment).index(x) for x in mods)
    return req,base,model,total,buckets,positions


def _calculate(raw):
    req,base,model,total,buckets,positions=_parse_request(raw)
    start=time.monotonic()
    result=h.HeterogeneityResult(schema_version=1, request_sha256=hashlib.sha256(raw).digest(),
        trace_id=base.trace_id, status=h.HETEROGENEITY_INCONCLUSIVE,
        reason_code='NOT_COMPUTED',backend_id=BACKEND,backend_version=VERSION)
    if req.method==h.ECONML_CATE_OPTIONAL:
        result.status=h.HETEROGENEITY_BACKEND_UNAVAILABLE
        result.reason_code='ECONML_RUNTIME_NOT_ATTESTED'
        return result
    prior=_compute(base,model,total,buckets,time.monotonic_ns(),start+req.timeout_ms/1000)
    if prior.status!=q.ADJUSTED_EFFECT_COMPUTED:
        result.status=(h.HETEROGENEITY_OVERLAP_FAILED if prior.status==q.POSITIVITY_NOT_MET else
            h.HETEROGENEITY_NOT_IDENTIFIED if prior.status==q.ADJUSTMENT_NOT_CERTIFIED else
            h.HETEROGENEITY_INCONCLUSIVE)
        result.reason_code='P2A_'+prior.reason_code
        return result
    by_group=defaultdict(dict)
    for adj,arms in sorted(buckets.items()):
        key=tuple(adj[x] for x in positions)
        by_group[key][adj]=arms
    if len(by_group)>req.max_subgroups:
        result.reason_code='SUBGROUP_LIMIT'
        return result
    group_weighted=Fraction()
    for key,part in sorted(by_group.items()):
        if time.monotonic()>start+req.timeout_ms/1000:
            result.reason_code='DEADLINE'
            return result
        mass=sum(a[0][0]+a[1][0] for a in part.values())
        effect=_effect(part,mass)
        independent=_independent_effect(part,mass)
        if effect!=independent:
            result.reason_code='INDEPENDENT_GROUP_CHECK_FAILED'
            return result
        variance=0.0
        for arms in part.values():
            n0,y0=arms[0]; n1,y1=arms[1]
            weight=(n0+n1)/mass
            p0=y0/n0; p1=y1/n1
            variance+=weight*weight*(p0*(1-p0)/n0+p1*(1-p1)/n1)
        se=math.sqrt(variance)
        result.subgroups.add(modifier_states=key,observations=mass,
            observed_weight=str(Fraction(mass,total)),estimated_effect=str(effect),
            approximate_se=format(se,'.12g'),ci95_lower=format(float(effect)-Z95*se,'.12g'),
            ci95_upper=format(float(effect)+Z95*se,'.12g'),adjustment_cells=len(part))
        group_weighted+=Fraction(mass,total)*effect
    if group_weighted!=_independent_effect(buckets,total) or str(group_weighted)!=prior.estimate:
        result.reason_code='WEIGHTED_OVERALL_EFFECT_DISAGREEMENT'
        result.subgroups.clear()
        return result
    result.overall_effect=prior.estimate
    result.subgroup_weighted_effect=str(group_weighted)
    result.assurance=ASSURANCE
    result.uncertainty_method='NORMAL_PLUGIN_WALD_APPROX_NOT_COVERAGE_VALIDATED'
    result.independently_checked=True
    result.status=h.CONDITIONAL_EFFECTS_COMPUTED
    result.reason_code='ASSUMED_GRAPH_SUBGROUP_EFFECTS_NOT_CAUSAL_PROOF'
    return result


def run_heterogeneity_frame(raw,*,host_authorized=False,enabled=False):
    start=time.monotonic_ns()
    result=h.HeterogeneityResult(schema_version=1,status=h.HETEROGENEITY_REJECTED,
        request_sha256=hashlib.sha256(raw if isinstance(raw,bytes) else b'').digest(),
        backend_id=BACKEND,backend_version=VERSION,reason_code='INVALID_FRAME')
    try:
        if not isinstance(raw,bytes) or not raw or len(raw)>MAX_FRAME:
            raise ValueError('INVALID_FRAME')
        req,base,*_=_parse_request(raw)
        result.trace_id=base.trace_id
        if not host_authorized: raise ValueError('HOST_AUTHORIZATION_REQUIRED')
        if not enabled: raise ValueError('HETEROGENEITY_DISABLED')
        result=_calculate(raw)
    except ValueError as e:
        result.reason_code=str(e) if str(e).isupper() and len(str(e))<95 else 'INVALID_OR_FAILED'
    except Exception:
        result.status=h.HETEROGENEITY_INCONCLUSIVE
        result.reason_code='HETEROGENEITY_RUNTIME_FAILURE'
    result.wall_ns=time.monotonic_ns()-start
    return _encode(result)


def verify_heterogeneity_result(raw,reply):
    try:
        result=_decode(reply,h.HeterogeneityResult)
        if result.status!=h.CONDITIONAL_EFFECTS_COMPUTED or not result.independently_checked:
            return False
        expected=_calculate(raw)
        if expected.status!=h.CONDITIONAL_EFFECTS_COMPUTED: return False
        expected.wall_ns=0; result.wall_ns=0
        return expected.SerializeToString(deterministic=True)==result.SerializeToString(deterministic=True)
    except Exception:
        return False


def heterogeneity_receipt(raw,reply):
    verified=verify_heterogeneity_result(raw,reply)
    return h.HeterogeneityReceipt(request_sha256=hashlib.sha256(raw).digest(),
        result_sha256=hashlib.sha256(reply).digest(),arithmetic_verified=verified,
        causal_assumptions_proven=False,
        reason_code='EMPIRICAL_ARITHMETIC_VERIFIED' if verified else 'UNVERIFIED_OR_NONRESULT')


def heterogeneity_audit(raw,reply):
    result=_decode(reply,h.HeterogeneityResult)
    return h.HeterogeneityAudit(request_sha256=hashlib.sha256(raw).digest(),
        result_sha256=hashlib.sha256(reply).digest(),trace_id=result.trace_id,
        status=result.status,backend_id=result.backend_id,
        reason_code=result.reason_code,wall_ns=result.wall_ns)
