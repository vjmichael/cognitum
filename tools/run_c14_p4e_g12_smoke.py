"""G12 standalone Protobuf assurance negative and positive research smoke."""
from tests.test_c14_p4e_g12_adversarial import request
from cognitum import causal_adversarial_assurance as gate
from cognitum.proto import causal_adversarial_assurance_pb2 as pb


def main():
    cases=[('CLEAN_INTERACTION','ABSTAIN_NEW_UNCALIBRATED_GENERATOR'),
        ('HIDDEN_COMMON_CAUSE','ABSTAIN_ADVERSARIAL_CAUSAL_GENERALIZATION'),
        ('MISMEASURED_CONFOUNDER','ABSTAIN_ADVERSARIAL_CAUSAL_GENERALIZATION'),
        ('SELECTION_COLLIDER','ABSTAIN_ADVERSARIAL_CAUSAL_GENERALIZATION'),
        ('TRANSPORT_SHIFT','ABSTAIN_ADVERSARIAL_CAUSAL_GENERALIZATION'),
        ('NEGATIVE_CONTROL','ABSTAIN_NEW_UNCALIBRATED_GENERATOR'),
        ('UNKNOWN','REJECT_UNVERIFIED')]
    for scenario,expected in cases:
        q=request(scenario);d,r=gate.calculate(q)
        assert d.disposition==expected and gate.verify(q,d,r)
        assert not(d.may_issue_real_world_causal_claim or d.may_recommend_intervention or d.may_trigger_external_action)
        assert pb.AdversarialAssuranceDecision.FromString(d.SerializeToString())==d
    q=request('CLEAN_INTERACTION',upstream_method='G8_POPULATION_MIX_WALD')
    d,r=gate.calculate(q)
    assert d.disposition=='ABSTAIN_UPSTREAM' and gate.verify(q,d,r)
    print('PASS 8 G12 research assurance smoke checks; no authority granted')

if __name__=='__main__':main()
