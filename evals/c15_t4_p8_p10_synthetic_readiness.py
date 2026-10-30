"""Portable synthetic P8-P10 demo, never proof of real data or identity."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile

from cognitum.spatial_functional_material import T4Rejected
from cognitum.spatial_functional_material_p5_p7 import canonical,sha
from cognitum.spatial_functional_material_p8_p10 import (
    P9_DOMAIN,HostHighwater,advance_policy_highwater,evaluate_p9,evaluate_p10,
)
from cognitum.proto import spatial_functional_material_p8_p10_pb2 as w
from evals.c15_t4_p4_synthetic_evidence_intake import construct
from tests.test_c15_t4_p5_p7_assurance import create,signed
from tests.test_c15_t4_p8_p10_external_readiness import make_policy,make_dataset


def rejection(operation):
    try: operation()
    except T4Rejected as exc: return str(exc)
    return 'NOT_REJECTED'


def run():
    req,_,keys=create(p4_request=construct())
    envelope,pinned,root,all_keys=make_policy(keys=keys)
    with tempfile.TemporaryDirectory() as directory:
        snap,p8=advance_policy_highwater(envelope,pinned,Path(directory)/'highwater.sqlite')
        _,p8_checked=advance_policy_highwater(envelope,pinned,
             Path(directory)/'highwater.sqlite',HostHighwater(snap.generation,snap.policy_sha256))
    p9_req=w.T4P9TimeAnchorRequest(schema_version=1,research_only=True)
    p9_req.p7.CopyFrom(req)
    p9_req.notary_statement.key_id='notary'
    signed(p9_req.notary_statement,all_keys['notary'],P9_DOMAIN,
           {'schema_version':1,'study_id':req.p6.p5.p4.p3_audit.study_id,
            'p6_sha256':sha(req.p6.SerializeToString(deterministic=True)),
            'issued_at_ms':1790000000500,'notary_sequence':1})
    p9=evaluate_p9(p9_req,snap)
    baseline=p9.p7_result.p6_result.p5_result.p4_result.p3_result
    notary_record=p9_req.notary_statement
    original=notary_record.ed25519_signature
    notary_record.ed25519_signature=b'\x00'*64
    bad_notary=rejection(lambda:evaluate_p9(p9_req,snap))
    notary_record.ed25519_signature=original
    data_req,_=make_dataset()
    p10=evaluate_p10(data_req,{'synthetic_fixture'})
    data_req.raw_csv+=b' '
    bad_dataset=rejection(lambda:evaluate_p10(data_req,{'synthetic_fixture'}))
    return {
      'milestone':'C15 T4 P8/P9/P10 portable synthetic readiness',
      'environment':'SYNTHETIC_KEYS_AND_CSV_OFFLINE_NO_REAL_WORLD_ATTESTATION',
      'policy_generation':p8.generation,
      'signed_root_policy_verified':p8.host_root_signature_verified,
      'host_provided_checkpoint_checked':p8_checked.persistent_highwater_verified,
      'signed_notary_anchor_verified':p9.signed_notary_anchor_verified,
      'notary_timestamp_authority_independently_verified':p9.externally_issued_timestamp_verified,
      'signed_reviewer_statements':p9.p7_result.verified_signatures,
      'signed_source_cases':p9.p7_result.p6_result.p5_result.source_signatures_verified,
      'calibration_decisions':baseline.calibration.decided,
      'calibration_errors':baseline.calibration.false_positive+baseline.calibration.false_negative,
      'holdout_decisions':baseline.holdout.decided,
      'holdout_errors':baseline.holdout.false_positive+baseline.holdout.false_negative,
      'synthetic_staged_csv_rows':p10.rows_validated,
      'synthetic_calibration_content_hashes':p10.calibrations_bound,
      'independent_license_authority_verified':p10.licensed_real_world_data_verified,
      'genuine_instrument_calibration_verified':p10.calibration_independently_verified,
      'bad_notary_signature_control':bad_notary,
      'csv_tamper_negative_control':bad_dataset,
      'external_publisher_identity_verified':p9.p7_result.p6_result.p5_result.external_publisher_identity_verified,
      'physical_safety_verified':p10.physical_safety_verified,
      'grants_authority':p9.grants_authority or p10.grants_authority,
      'Lu_modified':False,
    }

if __name__=='__main__': print(json.dumps(run(),indent=2,sort_keys=True))
