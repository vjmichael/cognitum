"""C14 P3D offline comparison of *candidate* skeletons, never causal proof.

No external worker launch and no model-directed operation. The existing
reference replay is used to bind the observed candidate to exactly the data.
External results get only structural checks; unauthenticated callers cannot
turn this into evidence that causal-learn actually executed.
"""
from __future__ import annotations
from fractions import Fraction
import hashlib
import time
from cognitum.causal_discovery import _parse as parse_discovery, verify_discovery_result
from cognitum.causal_estimation import _decode
from cognitum.causal_mature_backend import verify_mature_receipt, _parse as parse_mature
from cognitum.proto import causal_validation_pb2 as v, causal_discovery_pb2 as d
from cognitum.proto import causal_mature_pb2 as m

MAX_FRAME = 196608
MAX_CAPTURE = 32768
LIMITS = ('DECLARED_SYNTHETIC_SKELETON_IS_NOT_ATTESTED_GROUND_TRUTH;'
          'REFERENCE_IS_REPLAY_CHECKED_NOT_INDEPENDENT_CAUSAL_PROOF;'
          'EXTERNAL_IS_SHAPE_CHECKED_NOT_PROVEN_LIBRARY_EXECUTION;'
          'UNDIRECTED_ONLY_NO_IDENTIFIABLE_ORIENTATIONS')


def _edges(edges, count):
    pairs = [(e.first, e.second) for e in edges]
    if any(not 0 <= a < b < count for a,b in pairs) or pairs != sorted(set(pairs)):
        raise ValueError('NONCANONICAL_OR_INVALID_EDGES')
    return set(pairs)


def _fraction_string(a: Fraction):
    return f'{float(a):.12g}'


def _scores(predicted, truth):
    tp=len(predicted & truth)
    fp=len(predicted - truth)
    fn=len(truth - predicted)
    precision=Fraction(tp,tp+fp) if tp+fp else Fraction(int(not truth),1)
    recall=Fraction(tp,tp+fn) if tp+fn else Fraction(1,1)
    f1=Fraction(2*tp,2*tp+fp+fn) if 2*tp+fp+fn else Fraction(1,1)
    return v.SkeletonScores(true_positive=tp,false_positive=fp,false_negative=fn,
        precision=_fraction_string(precision),recall=_fraction_string(recall),
        f1=_fraction_string(f1),skeleton_symmetric_difference=fp+fn)


def _parse(raw):
    if not isinstance(raw,bytes) or not raw or len(raw)>MAX_FRAME:
        raise ValueError('INVALID_VALIDATION_FRAME')
    req=_decode(raw,v.DiscoveryValidationRequest)
    if req.schema_version!=1 or not req.trace_id or len(req.trace_id)>64:
        raise ValueError('INVALID_VALIDATION_REQUEST')
    base=req.reference_request
    if not req.HasField('reference_request') or base.method!=d.REFERENCE_PC_STABLE_SKELETON:
        raise ValueError('REFERENCE_METHOD_REQUIRED')
    parse_discovery(base.SerializeToString(deterministic=True))
    if base.trace_id!=req.trace_id or not req.reference_result or len(req.reference_result)>MAX_CAPTURE:
        raise ValueError('INVALID_REFERENCE_CAPTURE')
    if req.declared_truth_skeleton and not req.has_declared_synthetic_truth:
        raise ValueError('UNLABELED_SYNTHETIC_GRAPH')
    truth=_edges(req.declared_truth_skeleton,len(base.variable_ids))
    has_ext=req.HasField('external_request')
    if bool(req.external_result)!=has_ext:
        raise ValueError('INCOMPLETE_EXTERNAL_PAIR')
    if has_ext:
        if len(req.external_result)>MAX_CAPTURE:
            raise ValueError('EXTERNAL_CAPTURE_TOO_LARGE')
        ext=req.external_request
        parse_mature(ext.SerializeToString(deterministic=True))
        if ext.backend!=m.CAUSAL_LEARN_PC_0148 or ext.trace_id!=base.trace_id:
            raise ValueError('EXTERNAL_DISCOVERY_MISMATCH')
        external_base=d.DiscoveryRequest();external_base.CopyFrom(ext.candidate_graph)
        external_base.method=d.REFERENCE_PC_STABLE_SKELETON
        if external_base.SerializeToString(deterministic=True)!=base.SerializeToString(deterministic=True):
            raise ValueError('DATASET_OR_SETTINGS_MISMATCH')
    return req, truth, has_ext


def _evaluate(req,truth,has_ext):
    base=req.reference_request
    baseraw=base.SerializeToString(deterministic=True)
    if not verify_discovery_result(baseraw,req.reference_result):
        raise ValueError('REFERENCE_REPLAY_FAILURE')
    reference=_decode(req.reference_result,d.DiscoveryResult)
    reference_edges=_edges(reference.undirected_edges,len(base.variable_ids))
    out=v.DiscoveryValidationResult(schema_version=1,trace_id=req.trace_id,
        status=v.CANDIDATE_COMPARISON_COMPUTED,
        reason_code='OBSERVATIONAL_SKELETON_COMPARISON_ONLY',
        reference_replay_checked=True,evidence_limitations=LIMITS)
    if req.has_declared_synthetic_truth:
        out.has_synthetic_scores=True
        out.reference_scores.CopyFrom(_scores(reference_edges,truth))
    if has_ext:
        external_request=req.external_request.SerializeToString(deterministic=True)
        external_reply=req.external_result
        if not verify_mature_receipt(external_request,external_reply).request_bound_structure_checked:
            raise ValueError('UNVERIFIED_EXTERNAL_SHAPE')
        external=_decode(external_reply,m.MatureCausalResult)
        external_edges=_edges(external.skeleton_edges,len(base.variable_ids))
        out.external_shape_checked=True
        intersection=len(reference_edges & external_edges)
        union=len(reference_edges | external_edges)
        out.reference_external_jaccard=_fraction_string(Fraction(intersection,union) if union else Fraction(1))
        if req.has_declared_synthetic_truth:
            out.external_scores.CopyFrom(_scores(external_edges,truth))
    return out


def run_validation_frame(raw,*,host_authorized=False,enabled=False):
    """Offline evaluation gate. No external execution and no authenticated host assumed."""
    start=time.monotonic_ns()
    out=v.DiscoveryValidationResult(schema_version=1,
        request_sha256=hashlib.sha256(raw if isinstance(raw,bytes) else b'').digest(),
        status=v.CAUSAL_VALIDATION_REJECTED,reason_code='INVALID_VALIDATION_FRAME',
        evidence_limitations=LIMITS)
    try:
        req,truth,has_ext=_parse(raw)
        out.trace_id=req.trace_id
        if not host_authorized:raise ValueError('HOST_AUTHORIZATION_REQUIRED')
        if not enabled:raise ValueError('VALIDATION_DISABLED')
        out=_evaluate(req,truth,has_ext)
        out.request_sha256=hashlib.sha256(raw).digest()
    except (ValueError,TypeError) as exc:
        reason=str(exc)
        out.reason_code=reason if reason.isupper() and len(reason)<100 else 'INVALID_VALIDATION_REQUEST'
        if reason in ('REFERENCE_REPLAY_FAILURE','UNVERIFIED_EXTERNAL_SHAPE'):
            out.status=v.CAUSAL_VALIDATION_INCONCLUSIVE
    except Exception:
        out.reason_code='EVALUATION_FAILURE'
        out.status=v.CAUSAL_VALIDATION_INCONCLUSIVE
    out.wall_ns=time.monotonic_ns()-start
    return out.SerializeToString(deterministic=True)


def validation_receipt(raw,reply):
    receipt=v.DiscoveryValidationReceipt(
        request_sha256=hashlib.sha256(raw if isinstance(raw,bytes) else b'').digest(),
        result_sha256=hashlib.sha256(reply if isinstance(reply,bytes) else b'').digest(),
        reason_code='NOT_VERIFIED')
    try:
        req,truth,has_ext=_parse(raw)
        observed=_decode(reply,v.DiscoveryValidationResult)
        if observed.status!=v.CANDIDATE_COMPARISON_COMPUTED or observed.request_sha256!=receipt.request_sha256:
            return receipt
        expected=_evaluate(req,truth,has_ext)
        expected.request_sha256=receipt.request_sha256
        expected.wall_ns=observed.wall_ns
        if observed.SerializeToString(deterministic=True)==expected.SerializeToString(deterministic=True):
            receipt.deterministic_arithmetic_replay=True
            receipt.reason_code='EVALUATION_REPLAY_ONLY_NO_CAUSAL_PROOF'
    except Exception:
        pass
    return receipt

# Parallel P3D comparison for P3A empirical subgroup effects vs P3C EconML
# candidate. Neither a statistically identified shared estimand nor a claim
# that an actual EconML process ran can be inferred from shape-checking alone.
def _parse_conditional(raw):
    from cognitum import causal_heterogeneity as het
    from cognitum.proto import causal_heterogeneity_pb2 as h
    if not isinstance(raw,bytes) or not raw or len(raw)>MAX_FRAME:
        raise ValueError('INVALID_COMPARISON_FRAME')
    req=_decode(raw,v.ConditionalComparisonRequest)
    if (req.schema_version!=1 or not req.trace_id or len(req.trace_id)>64 or
        not req.HasField('reference_request') or not req.HasField('external_request') or
        not req.reference_result or not req.external_result or
        len(req.reference_result)>MAX_CAPTURE or len(req.external_result)>MAX_CAPTURE):
        raise ValueError('INVALID_CONDITIONAL_PAIR')
    if (req.reference_request.method!=h.REFERENCE_CONDITIONAL_STANDARDIZATION or
        req.reference_request.estimation.trace_id!=req.trace_id):
        raise ValueError('INVALID_REFERENCE_EFFECT_METHOD')
    het._parse_request(req.reference_request.SerializeToString(deterministic=True))
    ext=req.external_request
    parse_mature(ext.SerializeToString(deterministic=True))
    if ext.backend!=m.ECONML_LINEAR_DML_0170 or ext.trace_id!=req.trace_id:
        raise ValueError('INVALID_EXTERNAL_EFFECT_BACKEND')
    external_base=h.HeterogeneityRequest();external_base.CopyFrom(ext.conditional_effects)
    external_base.method=h.REFERENCE_CONDITIONAL_STANDARDIZATION
    if external_base.SerializeToString(deterministic=True)!=req.reference_request.SerializeToString(deterministic=True):
        raise ValueError('EFFECT_DATASET_OR_SETTINGS_MISMATCH')
    return req


def _evaluate_conditional(req):
    from cognitum.causal_heterogeneity import verify_heterogeneity_result
    from cognitum.proto import causal_heterogeneity_pb2 as h
    rraw=req.reference_request.SerializeToString(deterministic=True)
    eraw=req.external_request.SerializeToString(deterministic=True)
    if not verify_heterogeneity_result(rraw,req.reference_result):
        raise ValueError('REFERENCE_EFFECT_REPLAY_FAILED')
    if not verify_mature_receipt(eraw,req.external_result).request_bound_structure_checked:
        raise ValueError('EXTERNAL_EFFECT_SHAPE_NOT_VERIFIED')
    ref=_decode(req.reference_result,h.HeterogeneityResult)
    ext=_decode(req.external_result,m.MatureCausalResult)
    out=v.ConditionalComparisonResult(schema_version=1,trace_id=req.trace_id,
        status=v.CANDIDATE_COMPARISON_COMPUTED,
        reason_code='EMPIRICAL_VS_MODEL_EFFECT_DIFFERENCE_ONLY',
        empirical_reference_replay_checked=True,external_shape_checked=True,
        evidence_limitations='EMPIRICAL_AND_DML_ESTIMANDS_MAY_DIFFER;'+LIMITS)
    distances=[]
    for a,b in zip(ref.subgroups,ext.effects):
        magnitude=abs(Fraction(a.estimated_effect)-Fraction(b.estimated_effect))
        distances.append(magnitude)
        out.differences.add(modifier_states=a.modifier_states,observations=a.observations,
            empirical_reference_effect=a.estimated_effect,model_candidate_effect=b.estimated_effect,
            absolute_difference=_fraction_string(magnitude))
    if not distances:
        raise ValueError('MISSING_SUBGROUP_CONTRASTS')
    out.mean_absolute_difference=_fraction_string(sum(distances,Fraction())/len(distances))
    out.max_absolute_difference=_fraction_string(max(distances))
    return out


def run_conditional_comparison_frame(raw,*,host_authorized=False,enabled=False):
    start=time.monotonic_ns()
    out=v.ConditionalComparisonResult(schema_version=1,
        request_sha256=hashlib.sha256(raw if isinstance(raw,bytes) else b'').digest(),
        status=v.CAUSAL_VALIDATION_REJECTED,reason_code='INVALID_COMPARISON_FRAME',
        evidence_limitations=LIMITS)
    try:
        req=_parse_conditional(raw)
        out.trace_id=req.trace_id
        if not host_authorized:raise ValueError('HOST_AUTHORIZATION_REQUIRED')
        if not enabled:raise ValueError('VALIDATION_DISABLED')
        out=_evaluate_conditional(req)
        out.request_sha256=hashlib.sha256(raw).digest()
    except (ValueError,TypeError) as exc:
        reason=str(exc)
        out.reason_code=reason if reason.isupper() and len(reason)<100 else 'INVALID_COMPARISON_REQUEST'
        if reason in ('REFERENCE_EFFECT_REPLAY_FAILED','EXTERNAL_EFFECT_SHAPE_NOT_VERIFIED'):
            out.status=v.CAUSAL_VALIDATION_INCONCLUSIVE
    except Exception:
        out.status=v.CAUSAL_VALIDATION_INCONCLUSIVE
        out.reason_code='COMPARISON_RUNTIME_FAILURE'
    out.wall_ns=time.monotonic_ns()-start
    return out.SerializeToString(deterministic=True)


def conditional_comparison_receipt(raw,reply):
    receipt=v.DiscoveryValidationReceipt(
        request_sha256=hashlib.sha256(raw if isinstance(raw,bytes) else b'').digest(),
        result_sha256=hashlib.sha256(reply if isinstance(reply,bytes) else b'').digest(),
        reason_code='NOT_VERIFIED')
    try:
        req=_parse_conditional(raw)
        got=_decode(reply,v.ConditionalComparisonResult)
        if got.status!=v.CANDIDATE_COMPARISON_COMPUTED or got.request_sha256!=receipt.request_sha256:
            return receipt
        expected=_evaluate_conditional(req)
        expected.request_sha256=receipt.request_sha256
        expected.wall_ns=got.wall_ns
        if got.SerializeToString(deterministic=True)==expected.SerializeToString(deterministic=True):
            receipt.deterministic_arithmetic_replay=True
            receipt.reason_code='DESCRIPTIVE_EFFECT_COMPARISON_NOT_CAUSAL_PROOF'
    except Exception:
        pass
    return receipt
