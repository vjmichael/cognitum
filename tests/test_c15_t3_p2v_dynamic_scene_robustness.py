"""P2V camera, missing-object and stale-static safety regression tests."""
import hashlib
import math
import unittest

from cognitum.proto import spatial_dynamic_scene_robustness_pb2 as pb
from cognitum.proto import spatial_volume_pb2 as vp
from cognitum.spatial_dynamic_scene_robustness import analyze, verify, RobustnessRejected
from cognitum.spatial_dynamic_scene_mapping import map_scene
from cognitum.spatial_volume import classify
from tests.test_c15_t3_p2u_dynamic_scene_mapping import request as p2u_fixture, digest


def fixture():
    return pb.P2VRobustnessRequest(schema_version=1, dynamic_request=p2u_fixture(),
        max_camera_translation_step_m=.25, max_camera_rotation_step_deg=10,
        max_static_age_ticks=30, max_missing_object_ticks=30,
        reappearance_gap_ticks=200, missing_object_exclusion_radius_m=1,
        research_only=True)


def pose_translate(q, value, *, window=1):
    for c in q.dynamic_request.windows[window].temporal_request.captures:
        c.depth.camera.translation.x += value
        c.depth.camera_sha256 = digest(c.depth.camera)


def pose_rotate(q, degrees, *, window=1):
    angle=math.radians(degrees)/2
    for c in q.dynamic_request.windows[window].temporal_request.captures:
        c.depth.camera.qw=math.cos(angle)
        c.depth.camera.qz=math.sin(angle)
        c.depth.camera_sha256=digest(c.depth.camera)


class P2VTests(unittest.TestCase):
    def rejected(self, q, reason):
        with self.assertRaises(RobustnessRejected) as exc:
            analyze(q)
        self.assertIn(reason,str(exc.exception))

    def test_baseline_p2u_is_unchanged_and_p2v_is_subset(self):
        q=fixture()
        old=map_scene(q.dynamic_request).SerializeToString(deterministic=True)
        result=analyze(q)
        self.assertEqual(old,map_scene(q.dynamic_request).SerializeToString(deterministic=True))
        self.assertFalse(result.pose_discontinuity_found)
        self.assertEqual(len(result.cameras),10)
        before={(e.x,e.y,e.z) for e in map_scene(q.dynamic_request).stationary_hypothetical_volume.evidence}
        after={(e.x,e.y,e.z) for e in result.conservative_static_hypothetical_volume.evidence}
        self.assertEqual(before,after)
        self.assertEqual(len(result.request_sha256),32)
        self.assertTrue(verify(q,result))

    def test_real_sized_pose_change_within_threshold_is_recorded(self):
        q=fixture();pose_translate(q,.05)
        out=analyze(q)
        self.assertFalse(out.pose_discontinuity_found)
        self.assertAlmostEqual(max(c.translation_step_m for c in out.cameras),.05,places=6)
        self.assertTrue(out.conservative_static_hypothetical_volume.evidence)

    def test_translation_jump_quarantines_all_static_cells(self):
        q=fixture();pose_translate(q,.05);q.max_camera_translation_step_m=.01
        out=analyze(q)
        self.assertTrue(out.pose_discontinuity_found)
        self.assertTrue(any(c.state==pb.P2V_CAMERA_DISCONTINUITY for c in out.cameras))
        self.assertEqual(len(out.conservative_static_hypothetical_volume.evidence),0)
        self.assertTrue(any(c.state==pb.P2V_STATIC_POSE_DISPUTED for c in out.cells))

    def test_rotation_step_quarantines(self):
        q=fixture();pose_rotate(q,1);q.max_camera_rotation_step_deg=.1
        out=analyze(q)
        self.assertTrue(out.pose_discontinuity_found)
        self.assertGreater(max(c.rotation_step_deg for c in out.cameras),.8)

    def test_quaternion_sign_equivalence(self):
        q=fixture()
        for c in q.dynamic_request.windows[1].temporal_request.captures:
            camera=c.depth.camera
            camera.qw*=-1;camera.qx*=-1;camera.qy*=-1;camera.qz*=-1
            c.depth.camera_sha256=digest(camera)
        out=analyze(q)
        self.assertFalse(out.pose_discontinuity_found)
        self.assertAlmostEqual(max(x.rotation_step_deg for x in out.cameras),0.,places=5)

    def test_camera_frame_namespace_mismatch_rejected(self):
        q=fixture()
        for c in q.dynamic_request.windows[1].temporal_request.captures:
            c.depth.camera.frame_id='unregistered_camera_frame'
            c.depth.camera_sha256=digest(c.depth.camera)
        self.rejected(q,'CAMERA_FRAME_DISCONTINUITY_REQUIRES_REGISTRATION')

    def test_calibration_source_change_is_not_silent(self):
        q=fixture()
        for c in q.dynamic_request.windows[1].temporal_request.captures:
            c.depth.camera.calibration_source_ref='different_source'
            c.depth.camera_sha256=digest(c.depth.camera)
        self.rejected(q,'CALIBRATION_SOURCE_CHANGED_REQUIRES_REVIEW')

    def test_t2_still_classifies_predictions_as_unknown(self):
        from tests.test_c15_t2_composition import fixture as structural_fixture
        from cognitum.proto import spatial_structural_audit_pb2 as ap
        from cognitum.spatial_structural_audit import audit
        q=fixture()
        out=analyze(q)
        graph=structural_fixture()
        graph.conversation_id=q.dynamic_request.conversation_id
        target=next(c for c in out.cells if c.retained)
        rq=ap.StructuralAuditRequest(schema_version=1,conversation_id=q.dynamic_request.conversation_id,
            graph_id=graph.graph_id,volume_id=q.dynamic_request.volume_id,research_only=True)
        claim=rq.claims.add(claim_id='maybe_wall',node_id='wall',source_ref='synthetic',expected=ap.SPATIAL_EXPECT_OCCUPIED)
        claim.box.min_x=claim.box.max_x=target.x
        claim.box.min_y=claim.box.max_y=target.y
        claim.box.min_z=claim.box.max_z=target.z
        check=audit(graph,out.conservative_static_hypothetical_volume,rq)
        self.assertEqual(check.audits[0].state,ap.SPATIAL_AUDIT_INDETERMINATE)

    def test_camera_digest_tampering_fails_closed(self):
        q=fixture();q.dynamic_request.windows[1].temporal_request.captures[-1].depth.camera_sha256=b'x'*32
        self.rejected(q,'INVALID_P2U_INPUT')

    def test_stale_static_evidence_not_returned(self):
        q=fixture();q.max_static_age_ticks=1
        q.dynamic_request.windows[1].temporal_request.evaluation_tick+=3
        out=analyze(q)
        self.assertTrue(any(c.state==pb.P2V_STATIC_STALE for c in out.cells))
        self.assertEqual(len(out.conservative_static_hypothetical_volume.evidence),0)

    def test_missing_not_equated_to_confirmed_occlusion(self):
        q=fixture();q.max_missing_object_ticks=5
        result=analyze(q)
        self.assertEqual(result.identities[0].state,pb.P2V_MISSING_UNEXPLAINED)
        self.assertFalse(result.identities[0].authenticated_identity)
        self.assertFalse(result.grants_authority)
        self.assertIn('MISSING_OBJECT_MAY_BE_OCCLUDED_OUT_OF_VIEW_OR_UNDETECTED',result.warnings)

    def test_reappearance_is_unverified(self):
        q=fixture();q.reappearance_gap_ticks=30
        out=analyze(q)
        self.assertEqual(out.identities[0].state,pb.P2V_REAPPEARANCE_UNVERIFIED)
        self.assertEqual(out.identities[0].gap_to_previous_observation_ticks,80)
        self.assertEqual(len(out.identities[0].distinct_support_capture_ids),4)

    def test_reappearance_uncertainty_filters_nearby_voxels(self):
        q=fixture();q.reappearance_gap_ticks=30;q.missing_object_exclusion_radius_m=3.0
        out=analyze(q)
        base=map_scene(q.dynamic_request)
        self.assertLess(len(out.conservative_static_hypothetical_volume.evidence),
                        len(base.stationary_hypothetical_volume.evidence))
        self.assertTrue(any(c.state==pb.P2V_STATIC_OBJECT_UNCERTAIN for c in out.cells))

    def test_reappearance_outside_missing_radius_not_all_quarantined(self):
        q=fixture();q.reappearance_gap_ticks=30;q.missing_object_exclusion_radius_m=.1
        out=analyze(q)
        self.assertTrue(out.conservative_static_hypothetical_volume.evidence)

    def test_static_map_cannot_promote_predictions_to_measurements(self):
        q=fixture();out=analyze(q)
        v=out.conservative_static_hypothetical_volume
        self.assertTrue(v.research_only)
        self.assertFalse(v.grants_authority)
        self.assertTrue(all(e.kind in (vp.VOLUME_PREDICTED_FREE,vp.VOLUME_PREDICTED_OCCUPIED) for e in v.evidence))
        self.assertTrue(all(x.state==vp.CELL_UNKNOWN for x in classify(v).cells))

    def test_determinism_and_tampered_replay_rejection(self):
        q=fixture();a=analyze(q);b=analyze(q)
        self.assertEqual(a.SerializeToString(deterministic=True),b.SerializeToString(deterministic=True))
        a.cells[0].retained=not a.cells[0].retained
        with self.assertRaisesRegex(RobustnessRejected,'P2V_REPLAY_MISMATCH'):
            verify(q,a)

    def test_unknown_fields_and_authority_rejected(self):
        q=fixture();q.grants_authority=True;self.rejected(q,'INVALID_P2V_CONTRACT')
        q=fixture();q.schema_version=3;self.rejected(q,'INVALID_P2V_CONTRACT')
        q=fixture();q2=pb.P2VRobustnessRequest.FromString(q.SerializeToString()+b'\x98\x06\x01')
        self.rejected(q2,'INVALID_P2V_CONTRACT')

    def test_policy_bounds_fail_closed(self):
        q=fixture();q.max_static_age_ticks=0;self.rejected(q,'INVALID_P2V_POLICY')
        q=fixture();q.max_camera_translation_step_m=float('nan');self.rejected(q,'INVALID_P2V_POLICY')
        q=fixture();q.max_camera_rotation_step_deg=0;self.rejected(q,'INVALID_P2V_POLICY')
        q=fixture();q.missing_object_exclusion_radius_m=30;self.rejected(q,'INVALID_P2V_POLICY')

    def test_cross_scope_rejected_by_p2u(self):
        q=fixture();q.dynamic_request.windows[1].volume_id='forged'
        self.rejected(q,'INVALID_P2U_INPUT')

    def test_repeated_windows_do_not_duplicate_capture_provenance(self):
        q=fixture();out=analyze(q)
        self.assertEqual(len(out.cameras),map_scene(q.dynamic_request).unique_capture_count)
        self.assertEqual(len({x.capture_id for x in out.cameras}),len(out.cameras))

    def test_unchanged_r1_r2_and_t2_contracts(self):
        from cognitum.proto import spatial_dynamic_scene_mapping_pb2 as upstream
        q=fixture();out=analyze(q)
        self.assertIsInstance(q.dynamic_request,upstream.P2UDynamicSceneRequest)
        self.assertFalse(out.conservative_static_hypothetical_volume.grants_authority)

if __name__=='__main__':unittest.main()
