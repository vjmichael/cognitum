"""C15 T4 P4: synthetic-only, no authenticated measurement claims."""
import hashlib
import json
import math
import unittest

from cognitum.proto import spatial_functional_material_pb2 as b
from cognitum.proto import spatial_functional_material_p2_pb2 as p2
from cognitum.proto import spatial_functional_material_p3_pb2 as p3
from cognitum.proto import spatial_functional_material_p4_pb2 as p4
from cognitum.spatial_functional_material import T4Rejected
from cognitum.spatial_functional_material_p4 import evaluate


def raw(o):
    return json.dumps(o,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def scenario(case, conversation):
    x=case.scenario
    x.schema_version=1; x.research_only=True
    x.baseline.schema_version=1; x.baseline.research_only=True
    x.baseline.graph_id='graph_'+case.case_id
    x.baseline.conversation_id=conversation
    for name in ('bore','shaft'):
        x.baseline.parts.add(id=name,kind='part',evidence=b.T4_MEASUREMENT_ASSERTED,
                             source_ref='model_input')
    fit=x.fits.add(id='fit',bore_part_id='bore',shaft_part_id='shaft')
    for field,v in (('bore_diameter',10.2),('shaft_diameter',10),
                    ('allowed_min_clearance',.1),('allowed_max_clearance',.3)):
        interval=getattr(fit,field)
        interval.center.CopyFrom(b.T4Quantity(value=v,unit=b.T4_MILLIMETER,
                    evidence=b.T4_MEASUREMENT_ASSERTED,source_ref='model_input'))
        interval.radius.CopyFrom(b.T4Quantity(value=.005 if field in ('bore_diameter','shaft_diameter') else 0,
                    unit=b.T4_MILLIMETER,evidence=b.T4_MEASUREMENT_ASSERTED,source_ref='model_input'))


def build(n=2):
    x=p4.T4P4EvidenceRequest(schema_version=1,research_only=True)
    x.p3_audit.schema_version=1
    x.p3_audit.research_only=True
    x.p3_audit.study_id='synthetic_p4'
    x.p3_audit.conversation_id='research_chat'
    plan={'plan_version':1,'study_id':'synthetic_p4','conversation_id':'research_chat',
          'model_id':'C15_T4_P2', 'reference_format':'C15_T4_P4_OBSERVATION_V1',
          'case_partitions':{}}
    for i in range(n):
        id='sample_%d'%i
        part='calibration' if i%2==0 else 'holdout'
        group='specimen_%d'%i
        plan['case_partitions'][id]=part
        data={'schema_version':1,'case_id':id,'specimen_group_id':group,
              'partition':part,'observed_class':'satisfies',
              'observed_clearance_m':.0002,'unit':'m'}
        blob=raw(data)
        c=x.p3_audit.cases.add(case_id=id,specimen_group_id=group,
              reference_source_ref='ref_%d'%i,reference_sha256=hashlib.sha256(blob).digest(),
              partition=p3.T4P3_CALIBRATION if i%2==0 else p3.T4P3_HOLDOUT,
              reference_kind=p3.T4P3_SYNTHETIC_ORACLE,
              observed_class=p3.T4P3_OBSERVED_SATISFIES,observed_clearance_m=.0002,
              finding_id='fit')
        scenario(c,x.p3_audit.conversation_id)
        x.references.add(case_id=id,source_uri='ref_%d'%i,license_id='TEST_ONLY',
                         reference_payload=blob)
    x.frozen_plan_json=raw(plan)
    x.p3_audit.prespecified_plan_sha256=hashlib.sha256(x.frozen_plan_json).digest()
    return x

class P4EvidenceTests(unittest.TestCase):
    def rejected(self,x,code):
        with self.assertRaisesRegex(T4Rejected,code): evaluate(x)

    def test_valid_synthetic_two_partitions(self):
        x=build(2)
        out=evaluate(x)
        self.assertTrue(out.payload_integrity_verified)
        self.assertEqual(len(out.verified),2)
        self.assertEqual(out.p3_result.holdout.decided,1)
        self.assertEqual(out.p3_result.calibration.decided,1)
        self.assertFalse(out.source_authenticity_verified)
        self.assertFalse(out.preregistration_verified)
        self.assertFalse(out.independent_measurement_verified)
        self.assertFalse(out.grants_authority)

    def test_independently_compiled_roundtrip(self):
        x=build()
        y=p4.T4P4EvidenceRequest.FromString(x.SerializeToString())
        self.assertEqual(evaluate(x),evaluate(y))

    def test_order_independent_results(self):
        x=build(4)
        first=evaluate(x)
        x.references.reverse()
        self.assertEqual([i.case_id for i in first.verified],
                         [i.case_id for i in evaluate(x).verified])

    def test_tampered_reference_bytes(self):
        x=build()
        x.references[0].reference_payload+=b' '
        self.rejected(x,'REFERENCE_CONTENT_HASH_MISMATCH')

    def test_claimed_label_inconsistent_with_reference_bytes(self):
        x=build()
        x.p3_audit.cases[0].observed_class=p3.T4P3_OBSERVED_VIOLATES
        self.rejected(x,'OBSERVED_LABEL_MISMATCH')

    def test_claimed_clearance_inconsistent(self):
        x=build()
        x.p3_audit.cases[0].observed_clearance_m=.00024
        self.rejected(x,'OBSERVATION_NUMERIC_MISMATCH')

    def test_wrong_reference_group_even_with_updated_digest(self):
        x=build()
        data=json.loads(x.references[0].reference_payload)
        data['specimen_group_id']='another_specimen'
        x.references[0].reference_payload=raw(data)
        x.p3_audit.cases[0].reference_sha256=hashlib.sha256(x.references[0].reference_payload).digest()
        self.rejected(x,'OBSERVATION_IDENTITY_MISMATCH')

    def test_wrong_reference_partition_even_with_updated_digest(self):
        x=build()
        data=json.loads(x.references[0].reference_payload)
        data['partition']='holdout'
        x.references[0].reference_payload=raw(data)
        x.p3_audit.cases[0].reference_sha256=hashlib.sha256(x.references[0].reference_payload).digest()
        self.rejected(x,'OBSERVATION_IDENTITY_MISMATCH')

    def test_frozen_plan_split_swap_rejected(self):
        x=build()
        p=json.loads(x.frozen_plan_json)
        p['case_partitions']['sample_0']='holdout'
        x.frozen_plan_json=raw(p)
        x.p3_audit.prespecified_plan_sha256=hashlib.sha256(x.frozen_plan_json).digest()
        self.rejected(x,'PLAN_PARTITION_MISMATCH')

    def test_plan_change_without_digest_rejected(self):
        x=build()
        x.frozen_plan_json+=b' '
        self.rejected(x,'FROZEN_PLAN_SHA256_MISMATCH')

    def test_plan_has_no_externally_attested_timestamp(self):
        x=build()
        p=json.loads(x.frozen_plan_json); p['external_preregistration_verified']=True
        x.frozen_plan_json=raw(p)
        x.p3_audit.prespecified_plan_sha256=hashlib.sha256(x.frozen_plan_json).digest()
        self.rejected(x,'UNEXPECTED_OR_MISSING_JSON_FIELD')

    def test_unknown_plan_case(self):
        x=build()
        p=json.loads(x.frozen_plan_json); p['case_partitions']['other']='holdout'
        x.frozen_plan_json=raw(p)
        x.p3_audit.prespecified_plan_sha256=hashlib.sha256(x.frozen_plan_json).digest()
        self.rejected(x,'FROZEN_PLAN_MISMATCH')

    def test_duplicate_json_key_fail_closed(self):
        x=build()
        x.frozen_plan_json=x.frozen_plan_json[:-1]+b',"plan_version":1}'
        self.rejected(x,'DUPLICATE_JSON_KEY')

    def test_malformed_reference_json_even_with_hash(self):
        x=build()
        x.references[0].reference_payload=b'{' 
        x.p3_audit.cases[0].reference_sha256=hashlib.sha256(b'{').digest()
        self.rejected(x,'INVALID_REFERENCE_PAYLOAD')

    def test_nonfinite_json_observation(self):
        x=build()
        x.references[0].reference_payload=x.references[0].reference_payload.replace(b'0.0002',b'NaN')
        x.p3_audit.cases[0].reference_sha256=hashlib.sha256(x.references[0].reference_payload).digest()
        self.rejected(x,'NONFINITE_JSON_VALUE')

    def test_wrong_units_even_with_updated_digest(self):
        x=build()
        data=json.loads(x.references[0].reference_payload); data['unit']='mm'
        x.references[0].reference_payload=raw(data)
        x.p3_audit.cases[0].reference_sha256=hashlib.sha256(x.references[0].reference_payload).digest()
        self.rejected(x,'REFERENCE_UNIT_MISMATCH')

    def test_extra_untrusted_field_rejected(self):
        x=build()
        data=json.loads(x.references[0].reference_payload); data['safety_certified']=True
        x.references[0].reference_payload=raw(data)
        x.p3_audit.cases[0].reference_sha256=hashlib.sha256(x.references[0].reference_payload).digest()
        self.rejected(x,'UNEXPECTED_OR_MISSING_JSON_FIELD')

    def test_duplicate_reference_rejected(self):
        x=build()
        x.references[1].CopyFrom(x.references[0])
        self.rejected(x,'DUPLICATE_REFERENCE_CASE')

    def test_missing_reference_rejected(self):
        x=build()
        del x.references[-1]
        self.rejected(x,'P4_RESOURCE_LIMIT')

    def test_reference_uri_mismatch_rejected(self):
        x=build()
        x.references[0].source_uri='another_ref'
        self.rejected(x,'REFERENCE_URI_MISMATCH')

    def test_cross_partition_shared_source_denied(self):
        x=build()
        x.references[1].source_uri='ref_0'
        x.p3_audit.cases[1].reference_source_ref='ref_0'
        self.rejected(x,'REFERENCE_REUSED_ACROSS_PARTITIONS')

    def test_missing_license_assertion_denied(self):
        x=build()
        x.references[0].license_id='UNSPECIFIED'
        self.rejected(x,'MISSING_CLAIMED_SOURCE_OR_LICENSE')

    def test_lab_claim_requires_calibration_ref(self):
        x=build()
        x.p3_audit.cases[0].reference_kind=p3.T4P3_LAB_OBSERVATION_CLAIM
        self.rejected(x,'MISSING_CALIBRATION_CLAIM')

    def test_caller_calibration_ref_does_not_authenticate(self):
        x=build()
        x.p3_audit.cases[0].reference_kind=p3.T4P3_LAB_OBSERVATION_CLAIM
        x.references[0].calibration_record_ref='calibration_claim_only'
        out=evaluate(x)
        self.assertFalse(out.independent_measurement_verified)
        self.assertFalse(out.source_authenticity_verified)

    def test_reject_authority(self):
        x=build(); x.grants_authority=True
        self.rejected(x,'INVALID_P4_CONTRACT')

    def test_reject_p3_authority(self):
        x=build(); x.p3_audit.grants_authority=True
        self.rejected(x,'INVALID_P3_CONTRACT')

    def test_reject_schema_drift(self):
        x=build(); x.schema_version=2
        self.rejected(x,'INVALID_P4_CONTRACT')

    def test_request_bounds(self):
        x=build(); x.references[0].reference_payload=b'a'*8193
        self.rejected(x,'REFERENCE_PAYLOAD_TOO_LARGE')

    def test_model_prediction_and_reference_are_independent(self):
        x=build()
        x.p3_audit.cases[0].reference_source_ref='model_input'
        x.references[0].source_uri='model_input'
        self.rejected(x,'REFERENCE_REUSED_AS_MODEL_INPUT')

    def test_duplicate_specimen_rejected_by_p3(self):
        x=build()
        x.p3_audit.cases[1].specimen_group_id=x.p3_audit.cases[0].specimen_group_id
        data=json.loads(x.references[1].reference_payload)
        data['specimen_group_id']=x.p3_audit.cases[1].specimen_group_id
        x.references[1].reference_payload=raw(data)
        x.p3_audit.cases[1].reference_sha256=hashlib.sha256(x.references[1].reference_payload).digest()
        self.rejected(x,'DEPENDENT_OR_DUPLICATE_SPECIMEN')

    def test_unknown_proto_field_rejected(self):
        x=build()
        # Wire-format varint field #99 value 1.
        raw_unknown=x.SerializeToString()+b'\x98\x06\x01'
        corrupted=p4.T4P4EvidenceRequest.FromString(raw_unknown)
        self.rejected(corrupted,'UNKNOWN_PROTO_FIELDS')

if __name__=='__main__': unittest.main()
