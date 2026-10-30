"""Focused offline C14 P3E/P3F/P4A synthetic smoke; no real causal proof."""
from tests.test_c14_p3e_stability import case as stability_case
from tests.test_c14_p3f_ambiguity import case as ambiguity_case
from tests.test_c14_p4a_temporal import case as temporal_case
from cognitum.proto import causal_stability_pb2 as s, causal_ambiguity_pb2 as a, causal_temporal_pb2 as t
from cognitum.causal_stability import run_stability_frame, stability_receipt
from cognitum.causal_ambiguity import run_ambiguity_frame, ambiguity_receipt
from cognitum.causal_temporal import run_temporal_frame, temporal_receipt


def raw(req):return req.SerializeToString(deterministic=True)


def main():
    cases=0
    for label,req in [('subsample',stability_case()),('permuted-null',stability_case(s.SUBSAMPLE_PERMUTED_NULL))]:
        source=raw(req)
        reply=run_stability_frame(source,host_authorized=True,enabled=True)
        result=s.StabilityResult.FromString(reply)
        assert result.status==s.STABILITY_COMPUTED and not result.causal_orientation_established
        assert stability_receipt(source,reply).exact_resampling_replay
        print('PASS: P3E',label)
        cases+=1
    source=raw(ambiguity_case());reply=run_ambiguity_frame(source,host_authorized=True,enabled=True)
    result=a.AmbiguityResult.FromString(reply)
    assert result.status==a.AMBIGUITY_COMPUTED and [g.dag_count for g in result.classes]==[3,1]
    assert ambiguity_receipt(source,reply).enumeration_replay and not result.causal_direction_established
    print('PASS: P3F Markov-equivalence enumeration');cases+=1
    source=raw(temporal_case());reply=run_temporal_frame(source,host_authorized=True,enabled=True)
    result=t.TemporalScreenResult.FromString(reply)
    assert result.status==t.TEMPORAL_SCREEN_COMPUTED and temporal_receipt(source,reply).numerical_replay_checked
    assert not result.time_lagged_causality_verified
    print('PASS: P4A lagged predictive screen');cases+=1
    denied=s.StabilityResult.FromString(run_stability_frame(raw(stability_case())))
    assert denied.status==s.STABILITY_REJECTED
    print('PASS: default-denied synthetic host gate');cases+=1
    altered=t.TemporalScreenResult.FromString(reply)
    altered.time_lagged_causality_verified=True
    assert not temporal_receipt(source,raw(altered)).numerical_replay_checked
    print('PASS: forged causal claim rejected');cases+=1
    print(f'C14 P3E/P3F/P4A smoke: {cases}/{cases}; third-party engines, Lu and Windows remain unverified')

if __name__=='__main__':main()
