"""Synthetic P3D validation smoke; forged mature candidates are shape probes only."""
from tests.test_c14_p3d_validation import graph_case,effects_case,encoded
from cognitum.causal_validation import (run_validation_frame,validation_receipt,
    run_conditional_comparison_frame,conditional_comparison_receipt)
from cognitum.proto import causal_validation_pb2 as v

def main():
    cases=0
    for label,req in [('synthetic declared graph',graph_case()),
                       ('candidate cross-backend skeleton',graph_case(external=True)),
                       ('unlabeled-truth abstention',graph_case(truth=False))]:
        raw=encoded(req); reply=run_validation_frame(raw,host_authorized=True,enabled=True)
        result=v.DiscoveryValidationResult.FromString(reply)
        assert result.status==v.CANDIDATE_COMPARISON_COMPUTED,label
        assert not result.real_world_causation_proven and not result.graph_orientations_identified
        assert validation_receipt(raw,reply).deterministic_arithmetic_replay
        if label=='unlabeled-truth abstention':assert not result.has_synthetic_scores
        print('PASS:',label);cases+=1
    req=effects_case();raw=encoded(req)
    reply=run_conditional_comparison_frame(raw,host_authorized=True,enabled=True)
    got=v.ConditionalComparisonResult.FromString(reply)
    assert got.status==v.CANDIDATE_COMPARISON_COMPUTED and got.mean_absolute_difference=='0.225'
    assert not got.same_estimand_proven and not got.causal_assumptions_proven
    assert conditional_comparison_receipt(raw,reply).deterministic_arithmetic_replay
    print('PASS: descriptive numeric comparison');cases+=1
    assert v.DiscoveryValidationResult.FromString(run_validation_frame(encoded(graph_case()))).status==v.CAUSAL_VALIDATION_REJECTED
    print('PASS: disabled host gate');cases+=1
    print(f'C14 P3D synthetic checks: {cases}/{cases}; no real mature library or LLM used')

if __name__=='__main__':main()
