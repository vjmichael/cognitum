"""Offline-only Protobuf-native C14 G9 seeded *research* comparison.

This cannot grant Lu authority; no uploaded/private datasets; causal assumptions
are never claimed verified. Receipt means deterministic replay, nothing more.
"""
import hashlib
from cognitum.proto import causal_interval_comparison_pb2 as pb
from tools import run_c14_p4e_g9_interval_comparison as g9


def calculate(request):
    if not isinstance(request,pb.IntervalComparisonRequest):raise TypeError('TYPED_REQUEST_REQUIRED')
    if (request.schema_version!=1 or not request.trace_id or len(request.trace_id)>128 or
            request.scenario not in g9.SCENARIOS or not 50<=request.sample_size<=3000 or
            not 99<=request.bootstrap_resamples<=g9.MAX_RESAMPLES or
            not .5<=request.confidence<1):
        raise ValueError('INVALID_G9_REQUEST')
    record=g9.one_case(request.scenario,request.seed,request.sample_size,
                       resamples=request.bootstrap_resamples,confidence=request.confidence)
    request_hash=hashlib.sha256(request.SerializeToString(deterministic=True)).digest()
    output=pb.IntervalComparisonResult(schema_version=1,trace_id=request.trace_id,
                  request_sha256=request_hash,research_only=True,
                  host_authorized=False,causal_conclusion_verified=False,
                  warning='ASSUMPTION_DEPENDENT_SYNTHETIC_EVALUATION_NOT_CAUSAL_PROOF')
    for name,value in record['methods'].items():
        v=output.methods.add(method=name,status=value['status'],
             causal_identification_verified=False,
             warning=('SYNTHETIC_ASSUMPTION_VIOLATION_NO_POINT_CAUSAL_CLAIM'
                       if not record['identification_assumptions_supported_by_generator'] else
                       'SIMULATION_ONLY_NO_CAUSAL_PROOF'))
        if value['status']=='COMPUTED' and record['identification_assumptions_supported_by_generator']:
            v.point_interval_available=True
            v.estimate=value['estimate'];v.lower=value['lower'];v.upper=value['upper']
    receipt=pb.IntervalComparisonReceipt(request_sha256=request_hash,
       result_sha256=hashlib.sha256(output.SerializeToString(deterministic=True)).digest(),
       deterministic_replay_checked=True,host_authenticated=False,
       causal_conclusion_verified=False)
    return output,receipt


def verify(request,result,receipt):
    if not (isinstance(request,pb.IntervalComparisonRequest) and
            isinstance(result,pb.IntervalComparisonResult) and
            isinstance(receipt,pb.IntervalComparisonReceipt)):
        return False
    if not result.research_only or result.host_authorized or result.causal_conclusion_verified or receipt.host_authenticated or receipt.causal_conclusion_verified or any(m.causal_identification_verified for m in result.methods):return False
    try:
        expected,expected_receipt=calculate(request)
        return (result.SerializeToString(deterministic=True)==expected.SerializeToString(deterministic=True) and
                receipt.SerializeToString(deterministic=True)==expected_receipt.SerializeToString(deterministic=True))
    except (ValueError,TypeError):return False
