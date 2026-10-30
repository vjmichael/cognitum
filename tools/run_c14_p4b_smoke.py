"""P4B exact temporal model smoke, assumption-bound only."""
from tests.test_c14_p4b_temporal_scm import model,feedback
from cognitum.proto import causal_temporal_scm_pb2 as t
from cognitum.causal_temporal_scm import run_time_scm_frame,time_scm_receipt

def main():
    cases=0
    for label,request in (
        ('observation',model()),
        ('time-indexed do',model(t.TIME_SCM_INTERVENTIONAL)),
        ('factual-world counterfactual',model(t.TIME_SCM_COUNTERFACTUAL)),
        ('lagged feedback do',feedback())):
        raw=request.SerializeToString(deterministic=True)
        reply=run_time_scm_frame(raw,host_authorized=True,enabled=True)
        out=t.TimeSCMResult.FromString(reply)
        assert out.status==t.TIME_SCM_COMPUTED and out.finite_model_verified
        assert not out.real_world_causation_proven
        assert time_scm_receipt(raw,reply).exact_model_replay
        print('PASS:',label);cases+=1
    denied=t.TimeSCMResult.FromString(run_time_scm_frame(model().SerializeToString(deterministic=True)))
    assert denied.status==t.TIME_SCM_REJECTED
    print('PASS: default-denied');cases+=1
    print(f'C14 P4B: {cases}/{cases} reference-smoke; no production host or external engine verified')

if __name__=='__main__':main()
