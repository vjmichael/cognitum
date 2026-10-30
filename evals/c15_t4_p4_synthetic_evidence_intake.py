"""P4 negative-control demo built on P3's fixed 80 synthetic examples.

Does not inspect real engineering data, authenticate an external source, or
establish the actual preregistration date of a claimed plan.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path

from cognitum.proto import spatial_functional_material_p3_pb2 as p3
from cognitum.proto import spatial_functional_material_p4_pb2 as p4
from cognitum.spatial_functional_material import T4Rejected
from cognitum.spatial_functional_material_p4 import evaluate

ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/'evals'/'c15_t4_p3_synthetic_heldout.py'
spec=importlib.util.spec_from_file_location('p3_study',MODULE)
assert spec and spec.loader
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def dumps(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def construct():
    result=p4.T4P4EvidenceRequest(schema_version=1,research_only=True)
    result.p3_audit.CopyFrom(mod.study())
    plan={'plan_version':1,'study_id':result.p3_audit.study_id,
          'conversation_id':result.p3_audit.conversation_id,
          'model_id':'C15_T4_P2','reference_format':'C15_T4_P4_OBSERVATION_V1',
          'case_partitions':{}}
    labels={p3.T4P3_OBSERVED_SATISFIES:'satisfies',
            p3.T4P3_OBSERVED_VIOLATES:'violates',
            p3.T4P3_OBSERVED_UNDETERMINED:'undetermined'}
    for case in result.p3_audit.cases:
        partition='calibration' if case.partition==p3.T4P3_CALIBRATION else 'holdout'
        plan['case_partitions'][case.case_id]=partition
        observation={'schema_version':1,'case_id':case.case_id,
            'specimen_group_id':case.specimen_group_id,'partition':partition,
            'observed_class':labels[case.observed_class],
            'unit':'m' if case.HasField('observed_clearance_m') else 'not_applicable'}
        if case.HasField('observed_clearance_m'):
            observation['observed_clearance_m']=case.observed_clearance_m
        payload=dumps(observation)
        case.reference_sha256=hashlib.sha256(payload).digest()
        result.references.add(case_id=case.case_id,reference_payload=payload,
            source_uri=case.reference_source_ref,
            license_id='TEST_SYNTHETIC_ONLY')
    result.frozen_plan_json=dumps(plan)
    result.p3_audit.prespecified_plan_sha256=hashlib.sha256(result.frozen_plan_json).digest()
    return result


def run():
    request=construct()
    output=evaluate(request)
    tampered=p4.T4P4EvidenceRequest()
    tampered.CopyFrom(request)
    tampered.references[0].reference_payload+=b' '
    failure='NOT_REJECTED'
    try:
        evaluate(tampered)
    except T4Rejected as err:
        failure=str(err)
    swapped=p4.T4P4EvidenceRequest()
    swapped.CopyFrom(request)
    fixture=json.loads(swapped.frozen_plan_json)
    fixture['case_partitions']['item_000']='holdout'
    swapped.frozen_plan_json=dumps(fixture)
    swapped.p3_audit.prespecified_plan_sha256=hashlib.sha256(swapped.frozen_plan_json).digest()
    split_failure='NOT_REJECTED'
    try:
        evaluate(swapped)
    except T4Rejected as err:
        split_failure=str(err)
    return {
      'milestone':'C15 T4 P4 research-only evidence content integrity',
      'dataset_kind':'SYNTHETIC_ONLY',
      'cases':len(request.references),
      'content_hashes_verified':output.payload_integrity_verified,
      'plan_content_matches_sha256':True,
      'source_authenticity_verified':output.source_authenticity_verified,
      'preregistration_verified':output.preregistration_verified,
      'independent_measurement_verified':output.independent_measurement_verified,
      'calibration_decisions':output.p3_result.calibration.decided,
      'calibration_errors':output.p3_result.calibration.false_positive+output.p3_result.calibration.false_negative,
      'holdout_decisions':output.p3_result.holdout.decided,
      'holdout_errors':output.p3_result.holdout.false_positive+output.p3_result.holdout.false_negative,
      'tampered_payload_negative_control':failure,
      'tampered_split_negative_control':split_failure,
      'plan_digest':output.plan_sha256.hex(),
      'physical_authority_granted':output.grants_authority,
    }

if __name__=='__main__':
    print(json.dumps(run(),indent=2,sort_keys=True))
