"""Bounded G11 typed assurance smoke, no network or real side effects."""
from unittest.mock import patch
from pathlib import Path
from tests.test_c14_p4e_g11_holdout import sample
from cognitum import causal_holdout_assurance as g11

CASES=[
 ('bca_small_sample',sample(), 'DESCRIBE_INDEPENDENT_SYNTHETIC_ONLY'),
 ('g10_refusal_preserved',sample(method='G8_POPULATION_MIX_WALD'), 'ABSTAIN_UPSTREAM_G10'),
 ('aipw_900_downgrade',sample(method='AIPW_CROSSFIT_IF_WALD',n=900),'ABSTAIN_HOLDOUT_CALIBRATION'),
 ('shift_refused',sample(domain='SHIFTED_SYNTHETIC'),'ABSTAIN_DISTRIBUTION_UNKNOWN_OR_SHIFTED'),
 ('unknown_domain_refused',sample(domain='UNKNOWN'),'ABSTAIN_DISTRIBUTION_UNKNOWN_OR_SHIFTED'),
 ('hidden_confounder_refused',sample(scenario='hidden_confounder'),'ABSTAIN_UPSTREAM_G10'),
 ('positivity_refused',sample(scenario='no_overlap'),'ABSTAIN_UPSTREAM_G10'),
]

def main():
    for name,q,expected in CASES:
        result,proof=g11.calculate(q)
        assert result.disposition==expected,name
        assert g11.verify(q,result,proof),name
        assert not any((result.may_issue_real_world_causal_claim,result.may_recommend_intervention,
                        result.may_trigger_external_action,result.authenticated_lu_host)),name
        print('PASS',name)
    with patch.object(g11,'REPORT_PATH',Path('/nonexistent-g11-evidence.json')):
        q=CASES[0][1];result,proof=g11.calculate(q)
        assert result.disposition=='REJECT_UNVERIFIED' and g11.verify(q,result,proof)
        print('PASS evidence_missing_fails_closed')
    with patch.object(g11,'PINNED_G11_SHA256','0'*64):
        q=CASES[0][1];result,proof=g11.calculate(q)
        assert result.disposition=='REJECT_UNVERIFIED' and g11.verify(q,result,proof)
        print('PASS wrong_source_digest_fails_closed')
    print('PASS 9/9 G11 assurance smoke')

if __name__=='__main__':main()
