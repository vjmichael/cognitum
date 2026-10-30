"""P2C synthetic fixture and negative tests. No sensor provenance/real ML."""
import copy
import unittest
from cognitum import spatial_temporal_tracking as eng
from cognitum import spatial_identity_association as p2b
from cognitum.proto import spatial_temporal_pb2 as tp
from tests.test_c15_p2b_identity_association import seed, observed


def fixture(*,a=4,b=6,tick=2, descriptors=True):
    s=seed([observed('a',a,tick=tick),observed('b',b,tick=tick)])
    r=tp.TemporalRequest(schema_version=1,scene_id=s.scene_id,conversation_id=s.conversation_id,
        task_id='task_x',trace_id='trace_p2c',request_id='p2c_1',scene_sha256=p2b.digest(s),
        observation_sigma_m=.5,process_sigma_m_per_tick=.2,max_speed_m_per_tick=12,
        descriptor_weight=12,unmatched_cost=20,ambiguity_margin=.3,max_gap_ticks=6,top_k=6)
    for oid,prev,pos,feat in [('a',0,a,(1,0)),('b',10,b,(0,1))]:
        track=r.tracks.add(object_id=oid)
        t=track.samples.add(tick=1);t.position_world_m.x=prev
        t=track.samples.add(tick=tick);t.position_world_m.x=pos
        if descriptors:t.descriptor.extend(feat)
    for did,pos,feat in [('da',8,(1,0)),('db',2,(0,1))]:
        d=r.detections.add(detection_id=did,category='drone',source_id='sensor_a',tick=3)
        d.position_world_m.x=pos
        if descriptors:d.descriptor.extend(feat)
    return s,r

def pairs(result):
    return {p.detection_id:p.object_id for p in result.hypotheses[0].pairs}

class TemporalTrackingTests(unittest.TestCase):
    def test_01_motion_resolves_crossing_ranking(self):
        s,r=fixture(descriptors=False);o=eng.propose(s,r)
        self.assertEqual(pairs(o),{'da':'a','db':'b'})
        self.assertEqual(o.decision,tp.TEMPORAL_AMBIGUOUS)
    def test_02_descriptor_temporal_research_candidate(self):
        s,r=fixture();o=eng.propose(s,r)
        self.assertEqual(pairs(o),{'da':'a','db':'b'})
        self.assertEqual(o.decision,tp.TEMPORAL_CANDIDATE_ONLY)
        self.assertFalse(o.grants_authority)
    def test_03_does_not_modify_scene_or_request(self):
        s,r=fixture();old=(s.SerializeToString(),r.SerializeToString());eng.propose(s,r)
        self.assertEqual(old,(s.SerializeToString(),r.SerializeToString()))
    def test_04_replays_deterministically(self):
        s,r=fixture();self.assertTrue(eng.verify_proposal(s,r,eng.propose(s,r)))
    def test_05_forged_pair_rejected(self):
        s,r=fixture();o=eng.propose(s,r);o.hypotheses[0].pairs[0].object_id='evil'
        self.assertFalse(eng.verify_proposal(s,r,o))
    def test_06_forged_authority_rejected(self):
        s,r=fixture();o=eng.propose(s,r);o.grants_authority=True
        self.assertFalse(eng.verify_proposal(s,r,o))
    def test_07_other_conversation_rejected(self):
        s,r=fixture();r.conversation_id='conv_other'
        with self.assertRaisesRegex(eng.TemporalRejected,'SCOPE_MISMATCH'):eng.propose(s,r)
    def test_08_hash_rejected(self):
        s,r=fixture();r.scene_sha256=b'x'*32
        with self.assertRaisesRegex(eng.TemporalRejected,'HASH_MISMATCH'):eng.propose(s,r)
    def test_09_last_history_must_match_snapshot(self):
        s,r=fixture();r.tracks[0].samples[-1].position_world_m.x+=1
        with self.assertRaisesRegex(eng.TemporalRejected,'LAST_POSE_MISMATCH'):eng.propose(s,r)
    def test_10_old_observation_rejected(self):
        s,r=fixture();r.detections[0].tick=2;r.detections[1].tick=2
        with self.assertRaisesRegex(eng.TemporalRejected,'STALE_OBSERVATION_TICK'):eng.propose(s,r)
    def test_11_mixed_ticks_rejected(self):
        s,r=fixture();r.detections[0].tick=4
        with self.assertRaisesRegex(eng.TemporalRejected,'MIXED_OR_INVALID_TICKS'):eng.propose(s,r)
    def test_12_nonmonotonic_history_rejected(self):
        s,r=fixture();r.tracks[0].samples[0].tick=2
        with self.assertRaisesRegex(eng.TemporalRejected,'NONMONOTONIC_HISTORY'):eng.propose(s,r)
    def test_13_nan_descriptor_rejected(self):
        s,r=fixture();r.detections[0].descriptor[0]=float('nan')
        with self.assertRaisesRegex(eng.TemporalRejected,'INVALID_DESCRIPTOR'):eng.propose(s,r)
    def test_14_zero_descriptor_rejected(self):
        s,r=fixture();r.detections[0].descriptor[:]=[0,0]
        with self.assertRaisesRegex(eng.TemporalRejected,'ZERO_DESCRIPTOR'):eng.propose(s,r)
    def test_15_long_occlusion_outside_horizon_unmatched(self):
        s,r=fixture();r.max_gap_ticks=1
        for d in r.detections:d.tick=8
        o=eng.propose(s,r)
        self.assertEqual(o.decision,tp.TEMPORAL_NO_MATCH)
    def test_16_no_category_crossing(self):
        s,r=fixture()
        for d in r.detections:d.category='person'
        self.assertEqual(eng.propose(s,r).decision,tp.TEMPORAL_NO_MATCH)
    def test_17_no_source_crossing(self):
        s,r=fixture()
        for d in r.detections:d.source_id='untrusted'
        self.assertEqual(eng.propose(s,r).decision,tp.TEMPORAL_NO_MATCH)
    def test_18_duplicate_detection_rejected(self):
        s,r=fixture();r.detections[1].detection_id='da'
        with self.assertRaisesRegex(eng.TemporalRejected,'DUPLICATE_IDS'):eng.propose(s,r)
    def test_19_max_gap_validated(self):
        s,r=fixture();r.max_gap_ticks=101
        with self.assertRaisesRegex(eng.TemporalRejected,'INVALID_HORIZON'):eng.propose(s,r)
    def test_20_absent_descriptor_conservative(self):
        s,r=fixture(descriptors=False)
        self.assertIn('INSUFFICIENT_INDEPENDENT_IDENTITY_EVIDENCE',eng.propose(s,r).warnings)
    def test_21_no_unsafe_actions_in_wire(self):
        self.assertFalse({'action','execute','grant_permission'} & set(tp.TemporalProposal.DESCRIPTOR.fields_by_name))
    def test_22_swap_false_data_cannot_be_authenticated(self):
        s,r=fixture();r.tracks[0].samples[-1].descriptor[:]=[0,1]
        o=eng.propose(s,r)
        self.assertIn('CALLER_SUPPLIED_HISTORY_AND_DESCRIPTOR_UNAUTHENTICATED',o.warnings)
    def test_23_unmatched_nonmatch_not_new_id(self):
        s,r=fixture();r.detections[0].position_world_m.x=1000
        o=eng.propose(s,r)
        self.assertEqual(pairs(o)['da'],'')
    def test_24_output_order_independent(self):
        s,r=fixture();r2=copy.deepcopy(r)
        r2.detections.reverse();r2.tracks.reverse()
        self.assertEqual(pairs(eng.propose(s,r)),pairs(eng.propose(s,r2)))
    def test_25_unapproved_scene_request_replay(self):
        s,r=fixture();r.request_id=s.processed_request_ids[0]
        with self.assertRaisesRegex(eng.TemporalRejected,'REPLAYED_SCENE_REQUEST'):eng.propose(s,r)

if __name__=='__main__': unittest.main()
