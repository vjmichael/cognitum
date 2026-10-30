"""Protobuf-native, offline-only C14 G8 causal uncertainty reference.

Never grants authority or verifies assumptions; not available to Lu by default.
A replay receipt checks deterministic calculation and request linkage, NOT
causal identification, runtime attestation, proof of correct formalization, or
independent statistical verification.
"""
import hashlib
from cognitum.proto import causal_uncertainty_pb2 as pb
from tools import run_c14_p4e_g8_uncertainty as study

MAX_OBSERVATIONS=3000


def calculate(req):
    if not isinstance(req,pb.CausalUncertaintyRequest):
        raise TypeError('TYPED_REQUEST_REQUIRED')
    if req.schema_version!=1 or not req.fixture_id or len(req.fixture_id)>128 or not req.trace_id or len(req.trace_id)>128:
        raise ValueError('INVALID_REQUEST_IDENTITY')
    if req.synthetic_oracle_available and (not -1<=req.synthetic_oracle_ate<=1):
        raise ValueError('INVALID_SYNTHETIC_ORACLE')
    if not (.5<=req.confidence<1.0) or req.minimum_cell_count<5 or req.minimum_cell_count>1000:
        raise ValueError('INVALID_STATISTICAL_PARAMETERS')
    if not 2<=len(req.observations)<=MAX_OBSERVATIONS:
        raise ValueError('RESOURCE_LIMIT')
    rows=[(int(o.covariate),int(o.treatment),int(o.outcome)) for o in req.observations]
    bound=study.manski_binary_bounds(rows,req.confidence)
    point=study.stratified_wald_interval(rows,req.confidence,req.minimum_cell_count,include_covariate_mix_variation=True)
    request_hash=hashlib.sha256(req.SerializeToString(deterministic=True)).digest()
    result=pb.CausalUncertaintyResult(schema_version=1,
          request_sha256=request_hash,fixture_id=req.fixture_id,trace_id=req.trace_id,
          hidden_confounder_declared=req.known_hidden_confounder,
          causal_identification_proven=False,research_only=True)
    b=result.partial_identification
    b.identified_lower_plugin=bound['identified_set_plugin_lower']
    b.identified_upper_plugin=bound['identified_set_plugin_upper']
    b.population_envelope_lower=bound['population_coverage_envelope_lower']
    b.population_envelope_upper=bound['population_coverage_envelope_upper']
    b.conservative_envelope_confidence=bound['envelope_nominal_confidence']
    b.causal_point_identified=False
    b.identification_assumptions='BINARY_TREATMENT_OUTCOME_CONSISTENCY_WITH_NO_UNCONFOUNDEDNESS'
    b.sampling_assumptions='IID_ROWS_HOEFFDING_CONSERVATIVE_ENVELOPE'
    p=result.point_interval
    p.nominal_confidence=req.confidence
    p.causal_assumptions_verified=False
    p.method='STRATIFIED_PLUGIN_WALD_POPULATION_Z_MIX_ADJUSTED'
    if req.known_hidden_confounder:
        p.point_interval_available=False
        p.reason_code='KNOWN_HIDDEN_CONFOUNDER_POINT_IDENTIFICATION_BLOCKED'
        result.warning='BOUNDS_ONLY_IDENTIFICATION_ASSUMPTIONS_VIOLATED'
    elif point['status']!='APPROXIMATE_INTERVAL_COMPUTED':
        p.point_interval_available=False
        p.reason_code='INSUFFICIENT_OVERLAP'
        result.warning='BOUNDS_ONLY_NO_POINT_INTERVAL'
    else:
        p.point_interval_available=True
        p.estimate=point['ate']
        p.lower=point['lower'];p.upper=point['upper']
        p.standard_error=point['standard_error']
        p.reason_code='COMPUTED_UNDER_UNVERIFIED_ASSUMPTIONS'
        result.warning='APPROXIMATE_INTERVAL_NOT_CAUSAL_PROOF'
    result_hash=hashlib.sha256(result.SerializeToString(deterministic=True)).digest()
    receipt=pb.CausalUncertaintyReceipt(request_sha256=request_hash,result_sha256=result_hash,
        deterministic_replay_checked=True,causal_conclusion_verified=False,
        authenticated_host_checked=False)
    return result,receipt


def verify(req,result,receipt):
    if (not isinstance(req,pb.CausalUncertaintyRequest) or
        not isinstance(result,pb.CausalUncertaintyResult) or
        not isinstance(receipt,pb.CausalUncertaintyReceipt)):
        return False
    if receipt.causal_conclusion_verified or receipt.authenticated_host_checked or result.causal_identification_proven or not result.research_only:
        return False
    try:
        expected,expected_receipt=calculate(req)
        return (result.SerializeToString(deterministic=True)==expected.SerializeToString(deterministic=True)
                and receipt.SerializeToString(deterministic=True)==expected_receipt.SerializeToString(deterministic=True))
    except (ValueError,TypeError):return False
