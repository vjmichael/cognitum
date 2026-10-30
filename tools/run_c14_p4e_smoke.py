"""P4E smoke: genuine *unavailability* plus bounded contract checks, not PCMCI execution."""
from cognitum import causal_tigramite_backend as t
from cognitum.proto import causal_temporal_discovery_pb2 as pb
from tests.test_c14_p4e_tigramite import request,raw_result


def main():
    raw=request().SerializeToString(deterministic=True)
    out=pb.TemporalDiscoveryResult.FromString(t.run_temporal_discovery_frame(raw))
    assert out.status==pb.TD_REJECTED and out.reason_code=='HOST_AUTHORIZATION_REQUIRED'
    print('PASS 1/6: host default deny')
    out=pb.TemporalDiscoveryResult.FromString(t.run_temporal_discovery_frame(raw,host_authorized=True))
    assert out.status==pb.TD_REJECTED and out.reason_code=='TEMPORAL_DISCOVERY_DISABLED'
    print('PASS 2/6: worker default OFF')
    out=pb.TemporalDiscoveryResult.FromString(t.run_temporal_discovery_frame(raw,host_authorized=True,enabled=True))
    assert out.status==pb.TD_UNAVAILABLE and out.reason_code=='WORKER_POLICY_UNAVAILABLE'
    print('PASS 3/6: no host-approved worker policy')
    out=pb.TemporalDiscoveryResult.FromString(t._compute_worker(raw))
    assert out.status==pb.TD_UNAVAILABLE and out.reason_code=='TIGRAMITE_NOT_INSTALLED'
    print('PASS 4/6: actual unavailable Tigramite dependency, no fabricated graph')
    req=request();del req.samples.observations[34]
    try:t._parse(req.SerializeToString(deterministic=True))
    except ValueError as err:assert str(err)=='NONREGULAR_TIMESTAMPS_NO_INTERPOLATION'
    else:raise AssertionError('gap accepted')
    print('PASS 5/6: no silent timestamp interpolation')
    raw,out=raw_result(request());out.causal_directions_proven=True
    assert not t.verify_temporal_discovery_receipt(raw,out.SerializeToString()).request_bound_structure_checked
    print('PASS 6/6: forged proof rejected')

if __name__=='__main__':main()
