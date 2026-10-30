"""80-case adversarial SIGNED SYNTHETIC evaluation. Runtime test-only keys.

This uses dynamically generated keys and a fabricated host policy. This does
NOT show any real external publisher, registry, review or timed preregistration.
"""
from __future__ import annotations
import json
from evals.c15_t4_p4_synthetic_evidence_intake import construct
from tests.test_c15_t4_p5_p7_assurance import create, rewrite, P7_DOMAIN
from cognitum.spatial_functional_material import T4Rejected
from cognitum.spatial_functional_material_p5_p7 import evaluate_p5,evaluate_p6,evaluate_p7


def fails(call):
    try:
        call()
    except T4Rejected as err:
        return str(err)
    return 'NOT_REJECTED'


def run():
    q, policy, keys=create(p4_request=construct())
    p5=evaluate_p5(q.p6.p5,policy)
    p6=evaluate_p6(q.p6,policy)
    p7=evaluate_p7(q,policy)
    baseline=p5.p4_result.p3_result
    sig=q.p6.p5.source_statements[0]
    sig.ed25519_signature=b'\x00'*64
    forgery=fails(lambda:evaluate_p5(q.p6.p5,policy))
    sig.ed25519_signature=keys[sig.key_id].sign(
        b'C15-T4-P5-SOURCE-V1\x00'+sig.statement_json)
    ref=q.reviewer_statements[0]
    rewrite(ref,keys,P7_DOMAIN,observed_class=(
        'violates' if json.loads(ref.statement_json)['observed_class']!='violates' else 'satisfies'))
    disagreement=fails(lambda:evaluate_p7(q,policy))
    return {
        'milestone':'C15 T4 P5/P6/P7 portable signed assurance',
        'environment':'OFFLINE_SYNTHETIC_GENERATED_KEYS_NOT_REAL_TRUST',
        'cases':len(q.p6.p5.p4.references),
        'signed_sources_verified':p5.source_signatures_verified,
        'signed_timeline_consistent':p6.signed_timeline_consistent,
        'two_reviewer_consensus_verified':p7.two_reviewer_consensus,
        'signed_reviews_verified':p7.verified_signatures,
        'calibration_decided':baseline.calibration.decided,
        'calibration_errors':baseline.calibration.false_positive+baseline.calibration.false_negative,
        'holdout_decided':baseline.holdout.decided,
        'holdout_errors':baseline.holdout.false_positive+baseline.holdout.false_negative,
        'forged_signature_control':forgery,
        'reviewer_disagreement_control':disagreement,
        'external_identity_verified':p5.external_publisher_identity_verified,
        'independent_preregistration_verified':p6.independent_preregistration_verified,
        'blind_expert_qualification_verified':p7.qualified_expert_status_verified,
        'real_data_verified':p7.licensed_real_world_data_verified,
        'physical_safety_verified':p7.physical_safety_verified,
        'Lu_modified':False,
        'grants_authority':p7.grants_authority,
    }

if __name__=='__main__':
    print(json.dumps(run(),sort_keys=True,indent=2))
