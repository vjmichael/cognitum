"""C15 P2T calibrated synthetic motion, provenance, isolation and replay tests."""
import hashlib
import math
import random
import unittest

from cognitum.proto import spatial_object_aware_volume_pb2 as p
from cognitum.proto import spatial_temporal_consistency_pb2 as s
from cognitum.proto import spatial_correlated_fusion_pb2 as r
from cognitum.proto import spatial_scene_pb2 as scene
from cognitum.proto import spatial_volume_pb2 as volume
from cognitum.spatial_object_aware_volume import analyze, verify, ObjectAwareVolumeRejected
from cognitum.spatial_temporal_consistency import reconcile
from cognitum.spatial_volume import classify
from tests.test_c15_t3_p2q_calibrated_depth import sample

OLD=(4,4,6)
NEW=(6,4,6)

def coordinates(voxel):
    return tuple((x+.5)*.5 for x in voxel)


def fixture():
    timeline = s.P2STemporalRequest(schema_version=1, conversation_id='chat',
        volume_id='vox', half_life_ticks=1000, historical_retention=.05,
        min_stable_observations=2,max_age_ticks=50,research_only=True,evaluation_tick=50)
    for i in range(5):
        tick=10*(i+1)
        depth=sample(u=3,depth=2 if i<2 else 5,hit=i<2,tick=tick)
        depth.evaluation_tick=tick
        depth.capture_id=f'capture{tick}'
        depth.pixels[0].depth_frame_sha256=hashlib.sha256(f'frame:{tick}'.encode()).digest()
        second=depth.pixels.add()
        second.CopyFrom(depth.pixels[0])
        second.u=5
        second.endpoint_hit=i>=2
        second.axial_depth_m=2 if i>=2 else 5
        timeline.captures.add().CopyFrom(r.P2RFusionRequest(schema_version=1,
            depth=depth, assumed_within_capture_rho=.3, research_only=True))
    world=scene.SceneSnapshot(schema_version=1,scene_id='scene',conversation_id='chat',
                              research_only=True,revision=1)
    a=world.objects.add(object_id='moving1',category='box',display_name='moving box',
                frame_id='world',visibility=scene.VISIBILITY_VISIBLE,
                observation_source_id='depthframe',last_observed_tick=40,version=1,confidence=.6)
    a.position_m.x,a.position_m.y,a.position_m.z=coordinates(NEW)
    a.rotation_xyzw.w=1
    req=p.P2TObjectAwareRequest(schema_version=1,conversation_id='chat',volume_id='vox',
        temporal_request=timeline,scene=world,research_only=True,
        min_displacement_m=.6,spatial_tolerance_m=.51,max_link_gap_ticks=30)
    req.scene_sha256=hashlib.sha256(world.SerializeToString(deterministic=True)).digest()
    tr=req.tracks.add(object_id='moving1')
    for tick,where in ((20,OLD),(40,NEW)):
        frame=next(c.depth.pixels[0] for c in timeline.captures if c.depth.pixels[0].tick==tick)
        xyz=coordinates(where)
        sm=tr.samples.add(capture_id=f'capture{tick}',tick=tick,source_ref=frame.source_ref,
                depth_frame_sha256=frame.depth_frame_sha256)
        sm.center_world_m.x,sm.center_world_m.y,sm.center_world_m.z=xyz
    return req


def getcell(result,coord):
    return next(c for c in result.cells if (c.x,c.y,c.z)==coord)

class ObjectAwareTests(unittest.TestCase):
    def bad(self,req,reason=None):
        with self.assertRaises(ObjectAwareVolumeRejected) as err:
            analyze(req)
        if reason: self.assertIn(reason,str(err.exception))

    def test_paired_vacated_arrived_motion(self):
        req=fixture();out=analyze(req)
        self.assertEqual(len(out.motion_candidates),1)
        self.assertEqual(out.motion_candidates[0].object_id,'moving1')
        self.assertEqual((out.motion_candidates[0].origin_x,out.motion_candidates[0].origin_y,out.motion_candidates[0].origin_z), OLD)
        self.assertEqual((out.motion_candidates[0].destination_x,out.motion_candidates[0].destination_y,out.motion_candidates[0].destination_z), NEW)
        for coord in (OLD,NEW):
            c=getcell(out,coord)
            self.assertEqual(c.explanation,p.P2T_MOTION_CANDIDATE)
            self.assertEqual(list(c.candidate_object_ids),['moving1'])
            self.assertFalse(c.static_handoff_allowed)
        self.assertTrue(verify(req,out))
        self.assertFalse(out.grants_authority)
        self.assertTrue(out.research_only)

    def test_separate_static_map_never_promotes_t2(self):
        req=fixture();result=analyze(req)
        temporal=reconcile(req.temporal_request)
        orig={(e.x,e.y,e.z) for e in temporal.hypothetical_volume.evidence}
        static={(e.x,e.y,e.z) for e in result.stationary_hypothetical_volume.evidence}
        self.assertTrue(static <= orig)
        self.assertTrue(orig-static)
        self.assertNotIn(OLD,static);self.assertNotIn(NEW,static)
        self.assertTrue(all(c.state==volume.CELL_UNKNOWN for c in classify(result.stationary_hypothetical_volume).cells))
        self.assertTrue(all(e.kind in (volume.VOLUME_PREDICTED_FREE,volume.VOLUME_PREDICTED_OCCUPIED)
                             for e in result.stationary_hypothetical_volume.evidence))
        self.assertFalse(result.stationary_hypothetical_volume.grants_authority)

    def test_t2_structural_audit_never_promotes_static_predictions(self):
        from tests.test_c15_t2_composition import fixture as graph_fixture
        from cognitum.proto import spatial_structural_audit_pb2 as audit_pb
        from cognitum.spatial_structural_audit import audit
        q=fixture();result=analyze(q)
        structure=graph_fixture();structure.conversation_id='chat'
        check=audit_pb.StructuralAuditRequest(schema_version=1,conversation_id='chat',
            graph_id=structure.graph_id,volume_id='vox',research_only=True)
        claim=check.claims.add(claim_id='old_cell_wall',node_id='wall',
            source_ref='caller',expected=audit_pb.SPATIAL_EXPECT_OCCUPIED)
        claim.box.min_x=claim.box.max_x=OLD[0]
        claim.box.min_y=claim.box.max_y=OLD[1]
        claim.box.min_z=claim.box.max_z=OLD[2]
        answer=audit(structure,result.stationary_hypothetical_volume,check)
        self.assertEqual(answer.audits[0].state,audit_pb.SPATIAL_AUDIT_INDETERMINATE)
        self.assertEqual(answer.audits[0].claimed_support_cells,0)

    def test_no_arrival_transition_no_motion(self):
        req=fixture()
        for c in req.temporal_request.captures:
            second=c.depth.pixels[1]
            second.endpoint_hit=False;second.axial_depth_m=5
        out=analyze(req)
        self.assertEqual(len(out.motion_candidates),0)
        self.assertEqual(getcell(out,OLD).explanation,p.P2T_UNATTRIBUTED_CHANGE)

    def test_no_vacating_no_motion(self):
        req=fixture()
        for c in req.temporal_request.captures:
            old=c.depth.pixels[0]
            old.endpoint_hit=True;old.axial_depth_m=2
        self.assertEqual(len(analyze(req).motion_candidates),0)

    def test_stationary_object_no_motion(self):
        req=fixture();req.min_displacement_m=2
        self.assertEqual(len(analyze(req).motion_candidates),0)

    def test_mismatched_t1_scene_ref(self):
        req=fixture();req.scene_sha256=b'0'*32
        self.bad(req,'INVALID_OR_UNBOUND_T1_SCENE')

    def test_mismatched_t1_latest_pose(self):
        req=fixture();req.scene.objects[0].position_m.x+=.2
        req.scene_sha256=hashlib.sha256(req.scene.SerializeToString(deterministic=True)).digest()
        self.bad(req,'T1_LATEST_POSE_MISMATCH')

    def test_latest_t1_source_must_match_frame(self):
        req=fixture();req.scene.objects[0].observation_source_id='other'
        req.scene_sha256=hashlib.sha256(req.scene.SerializeToString(deterministic=True)).digest()
        self.bad(req,'T1_LATEST_SOURCE_MISMATCH')

    def test_invalid_t1_orientation_rejected(self):
        req=fixture();req.scene.objects[0].rotation_xyzw.w=.3
        req.scene_sha256=hashlib.sha256(req.scene.SerializeToString(deterministic=True)).digest()
        self.bad(req,'INVALID_T1_COORDINATE_FRAME')

    def test_scene_and_capture_cross_scope_rejected(self):
        req=fixture();req.temporal_request.conversation_id='other'
        self.bad(req,'CROSS_SCOPE_TEMPORAL_INPUT')
        req=fixture();req.scene.conversation_id='other'
        req.scene_sha256=hashlib.sha256(req.scene.SerializeToString(deterministic=True)).digest()
        self.bad(req,'INVALID_OR_UNBOUND_T1_SCENE')

    def test_frame_source_or_digest_mismatch(self):
        for attr, value in [('source_ref','other'),('depth_frame_sha256',b'z'*32)]:
            req=fixture();setattr(req.tracks[0].samples[0],attr,value)
            self.bad(req,'UNBOUND_OBJECT_SAMPLE_FRAME')

    def test_missing_depth_and_invalid_calibration_fail_closed(self):
        req=fixture();req.temporal_request.captures[0].depth.pixels[0].axial_depth_m=0
        self.bad(req,'INVALID_P2S_EVIDENCE')

    def test_unordered_and_replayed_samples(self):
        req=fixture();req.tracks[0].samples.reverse()
        self.bad(req,'INVALID_OBJECT_SAMPLE')
        req=fixture();req.tracks[0].samples.add().CopyFrom(req.tracks[0].samples[-1])
        self.bad(req,'INVALID_OBJECT_SAMPLE')

    def test_duplicate_ids_unknown_ids(self):
        req=fixture();req.tracks.add().CopyFrom(req.tracks[0]);self.bad(req,'INVALID_OBJECT_TRACK')
        req=fixture();req.tracks[0].object_id='forged';self.bad(req,'INVALID_OBJECT_TRACK')

    def test_resource_and_policy_limits(self):
        req=fixture();req.spatial_tolerance_m=10;self.bad(req,'SPATIAL_TOLERANCE_EXCEEDS_FOUR_VOXELS')
        req=fixture();req.min_displacement_m=float('nan');self.bad(req,'INVALID_OBJECT_AWARE_POLICY')
        req=fixture();req.max_link_gap_ticks=0;self.bad(req,'INVALID_OBJECT_AWARE_POLICY')

    def test_unknown_fields_rejected(self):
        req=fixture();corrupt=p.P2TObjectAwareRequest.FromString(req.SerializeToString()+b'\x98\x06\x01')
        self.bad(corrupt,'INVALID_P2T_CONTRACT')

    def test_result_tamper_and_exact_replay(self):
        req=fixture();result=analyze(req)
        result.motion_candidates[0].displacement_m+=.5
        self.bad_verify(req,result)
        result=analyze(req);result.cells[0].static_handoff_allowed=not result.cells[0].static_handoff_allowed
        self.bad_verify(req,result)

    def bad_verify(self,req,result):
        with self.assertRaisesRegex(ObjectAwareVolumeRejected,'P2T_REPLAY_MISMATCH'):
            verify(req,result)

    def test_frame_swap_cannot_give_motion_credit(self):
        req=fixture();req.tracks[0].samples[0].depth_frame_sha256 = (
            req.tracks[0].samples[1].depth_frame_sha256)
        self.bad(req,'UNBOUND_OBJECT_SAMPLE_FRAME')

    def test_multiobject_candidate_not_promoted(self):
        req=fixture();obj=req.scene.objects.add();obj.CopyFrom(req.scene.objects[0]);obj.object_id='moving2'
        req.scene_sha256=hashlib.sha256(req.scene.SerializeToString(deterministic=True)).digest()
        tr=req.tracks.add();tr.CopyFrom(req.tracks[0]);tr.object_id='moving2'
        result=analyze(req)
        self.assertEqual(len(result.motion_candidates),2)
        self.assertEqual(getcell(result,OLD).explanation,p.P2T_MULTIPLE_OBJECTS)
        self.assertFalse(getcell(result,OLD).static_handoff_allowed)

    def test_deterministic_with_object_track_reordering(self):
        req=fixture();obj=req.scene.objects.add();obj.CopyFrom(req.scene.objects[0]);obj.object_id='moving2'
        req.scene_sha256=hashlib.sha256(req.scene.SerializeToString(deterministic=True)).digest()
        tr=req.tracks.add();tr.CopyFrom(req.tracks[0]);tr.object_id='moving2'
        a=analyze(req);req.tracks.reverse();b=analyze(req)
        # Request hash differs, actual semantic result remains identical.
        self.assertEqual([(x.object_id,x.origin_x,x.destination_x) for x in a.motion_candidates],
                         [(x.object_id,x.origin_x,x.destination_x) for x in b.motion_candidates])

if __name__=='__main__':unittest.main()
