"""Offline C14 G10 fail-closed assurance smoke; no Lu authority."""
from cognitum import causal_interval_comparison as g9
from cognitum import causal_assurance_policy as policy
from cognitum.proto import causal_interval_comparison_pb2 as gp
from cognitum.proto import causal_assurance_policy_pb2 as pb


def make_case(scenario, n, method='G8_POPULATION_MIX_WALD', resamples=199):
    e=gp.IntervalComparisonRequest(schema_version=1,trace_id='g10-smoke-g9',scenario=scenario,
                                    seed=1001,sample_size=n,bootstrap_resamples=resamples,confidence=.95)
    r,t=g9.calculate(e)
    return pb.CausalAssuranceRequest(schema_version=1,trace_id='g10-smoke',experiment=e,
          candidate=r,calculation_receipt=t,selected_method=method)


def main():
    clean=make_case('null_effect',900)
    hetero=make_case('observed_heterogeneous',300)
    confounded=make_case('hidden_confounder',300)
    overlap=make_case('no_overlap',300)
    cases=[(clean,pb.CAUSAL_ASSURANCE_DESCRIBE_SYNTHETIC_ONLY),
           (hetero,pb.CAUSAL_ASSURANCE_ABSTAIN_CALIBRATION),
           (confounded,pb.CAUSAL_ASSURANCE_ABSTAIN_CONFOUNDING),
           (overlap,pb.CAUSAL_ASSURANCE_ABSTAIN_POSITIVITY)]
    checks=[]
    for request,disp in cases:
        decision,receipt=policy.calculate(request)
        checks.append(decision.disposition==disp and policy.verify(request,decision,receipt))
        checks.append(not decision.may_issue_causal_claim and not decision.may_recommend_intervention
                      and not decision.may_trigger_external_action and not decision.authenticated_lu_host)
    decision,receipt=policy.calculate(clean)
    decision.may_recommend_intervention=True
    checks.append(not policy.verify(clean,decision,receipt))
    clean.candidate.methods[0].lower=100
    decision,_=policy.calculate(clean)
    checks.append(decision.disposition==pb.CAUSAL_ASSURANCE_REJECT_UNVERIFIED)
    if not all(checks):raise RuntimeError('G10_SMOKE_FAILED '+repr(checks))
    print('PASS: %d/%d G10 offline research-only smoke checks' % (sum(checks),len(checks)))

if __name__=='__main__':main()
