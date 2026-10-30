"""Generate a compact, deterministic C14 G10 *synthetic-only* policy evidence file."""
import hashlib
import json
from pathlib import Path
from cognitum import causal_interval_comparison as g9
from cognitum import causal_assurance_policy as policy
from cognitum.proto import causal_interval_comparison_pb2 as gp
from cognitum.proto import causal_assurance_policy_pb2 as pb

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/components/causal/P4E-G10-assurance-policy-evidence.json'
CASES=(
    ('null_effect',900,'G8_POPULATION_MIX_WALD',199),
    ('observed_heterogeneous',300,'G8_POPULATION_MIX_WALD',199),
    ('observed_heterogeneous',300,'PAIRS_BOOT_BCA',399),
    ('observed_heterogeneous',300,'PAIRS_BOOT_BCA',199),
    ('observed_heterogeneous',900,'PAIRS_BOOT_BCA',399),
    ('hidden_confounder',300,'G8_POPULATION_MIX_WALD',199),
    ('no_overlap',300,'G8_POPULATION_MIX_WALD',199),
)


def run():
    cases=[]
    for scenario,n,method,resamples in CASES:
        exp=gp.IntervalComparisonRequest(schema_version=1,trace_id='g10-research-evidence',scenario=scenario,
             seed=1001,sample_size=n,bootstrap_resamples=resamples,confidence=.95)
        result,receipt=g9.calculate(exp)
        req=pb.CausalAssuranceRequest(schema_version=1,trace_id='g10-research-evidence',experiment=exp,
             candidate=result,calculation_receipt=receipt,selected_method=method,
             requests_intervention_recommendation=True)
        decision,proof=policy.calculate(req)
        if not policy.verify(req,decision,proof):raise RuntimeError('POLICY_REPLAY_FAILURE')
        cases.append({
            'scenario':scenario,'sample_size':n,'method':method,'bootstrap_resamples':resamples,
            'disposition':pb.CausalAssuranceDisposition.Name(decision.disposition),
            'reason_codes':list(decision.reason_codes),
            'source_report_sha256':decision.calibration.source_report_sha256.hex(),
            'coverage_from_separate_seeded_simulations':(
                decision.calibration.observed_coverage if decision.calibration.recorded_calibration else None),
            'coverage_wilson_95':(
                [decision.calibration.wilson_lower,decision.calibration.wilson_upper]
                if decision.calibration.recorded_calibration else None),
            'completed_calibration_cases':decision.calibration.completed,
            'identified_plugin_lower':decision.partial_bounds.plug_in_identified_lower,
            'identified_plugin_upper':decision.partial_bounds.plug_in_identified_upper,
            'population_sampling_envelope_lower':decision.partial_bounds.population_envelope_lower,
            'population_sampling_envelope_upper':decision.partial_bounds.population_envelope_upper,
            'policy_receipt_sha256':hashlib.sha256(proof.SerializeToString(deterministic=True)).hexdigest(),
            'calculation_replay_checked':decision.calculation_replay_checked,
            'intervention_authorized':decision.may_recommend_intervention,
            'causal_conclusion_verified':decision.causal_assumptions_verified,
            'host_authenticated':decision.authenticated_lu_host,
        })
    content={
        'phase':'C14 P4E G10', 'policy_version':policy.POLICY_VERSION,
        'research_only':True,'host_authority_granted':False,
        'causal_identification_ascertained':False,'synthetic_source':'G7/G8/G9 fixed-seed research fixtures',
        'g9_calibration_report_sha256':policy.G9_EVIDENCE_SHA256,
        'minimum_completed_trials':policy.MIN_COMPLETED,
        'minimum_completion_rate':policy.MIN_COMPLETION_FRACTION,
        'minimum_coverage_for_descriptive_advisory':.95-policy.CALIBRATION_TOLERANCE,
        'limitations':[
            'Descriptive eligibility is never a real-world calibration or intervention certificate',
            'G9 empirical coverage is 200-case synthetic reference only, and Wilson intervals remain uncertain',
            'Selected-method comparison uses prior fixtures; avoid choosing a winner on this same grid',
            'Partial identified sets are distinct from sampling confidence envelopes',
            'This source and replay receipt are not signatures, external attestation, Lu admission or Windows confinement',
        ],
        'cases':cases,
    }
    OUT.write_text(json.dumps(content,sort_keys=True,indent=2)+'\n')
    print('PASS:',len(cases),'policy traces replay verified; wrote',OUT)

if __name__=='__main__':run()
