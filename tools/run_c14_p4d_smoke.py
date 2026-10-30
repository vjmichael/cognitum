"""C14 P4D bounded real-statsmodels and denial smoke cases."""
from cognitum.causal_temporal_advanced import run_temporal_advanced_frame,temporal_advanced_receipt
from cognitum.proto import causal_temporal_advanced_pb2 as d
from tests.test_c14_p4d_temporal_advanced import request

def scenario(req,**flags):
    raw=req.SerializeToString(deterministic=True)
    reply=run_temporal_advanced_frame(raw,**flags)
    return raw,d.TemporalAdvancedResult.FromString(reply),reply


def main():
    raw,got,reply=scenario(request(),host_authorized=True,enabled=True)
    assert got.status==d.ADV_COMPUTED and len(got.diagnostics)==2
    assert temporal_advanced_receipt(raw,reply).same_backend_replay_checked
    print('PASS 1/5: genuine statsmodels ADF+KPSS+CUSUM and request replay')
    _,denied,_=scenario(request())
    assert denied.status==d.ADV_REJECTED and denied.reason_code=='HOST_AUTHORIZATION_REQUIRED'
    print('PASS 2/5: host gate default deny')
    _,disabled,_=scenario(request(),host_authorized=True)
    assert disabled.status==d.ADV_REJECTED and disabled.reason_code=='ADV_TEMP_DISABLED'
    print('PASS 3/5: independently disabled by default')
    irregular=request();del irregular.samples.observations[10]
    _,blocked,_=scenario(irregular,host_authorized=True,enabled=True)
    assert blocked.status==d.ADV_INCONCLUSIVE and not blocked.regular_cadence_checked
    print('PASS 4/5: irregular sample cannot enter standard hypothesis test')
    got.causal_directions_verified=True
    assert not temporal_advanced_receipt(raw,got.SerializeToString(deterministic=True)).same_backend_replay_checked
    print('PASS 5/5: forged causal proof rejected')

if __name__=='__main__':main()
