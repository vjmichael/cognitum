"""P2Q adversarial, reference, and bounded end-to-end integration tests."""
import hashlib
import math
import random
import unittest

from cognitum.proto import spatial_calibrated_depth_pb2 as p
from cognitum.proto import spatial_volume_pb2 as volume
from cognitum import spatial_calibrated_depth as gate
from cognitum.spatial_volume import classify as classify_volume


def sample(*, u=3, v=3, depth=2.0, hit=True, tick=10, source='depthframe'):
    q = p.P2QDepthRequest(schema_version=1,conversation_id='chat',volume_id='vox',capture_id='capture',
                           voxel_size_m=.5,max_axis=32,evaluation_tick=10,half_life_ticks=5,
                           hit_probability=.8,free_probability=.3,research_only=True)
    c=q.camera
    c.frame_id='camera1';c.calibration_source_ref='factory-data'
    c.width=8;c.height=8;c.fx=4;c.fy=4;c.cx=3.5;c.cy=3.5
    c.rectified_pinhole=True;c.qw=1;c.translation.x=2;c.translation.y=2;c.translation.z=1
    c.max_axial_depth_m=5
    q.camera_sha256=gate._digest(c)
    q.pixels.add(u=u,v=v,axial_depth_m=depth,tick=tick,source_ref=source,
                 depth_frame_sha256=hashlib.sha256(b'unverified-depth-frame').digest(),
                 endpoint_hit=hit)
    return q


class CalibratedDepthTests(unittest.TestCase):
    def assertBad(self,request):
        with self.assertRaises(gate.CalibratedDepthRejected): gate.project(request)

    def test_center_depth_to_world_endpoint(self):
        req=sample(); result=gate.project(req)
        self.assertEqual(tuple(gate._coords(result.projections[0].camera_endpoint_m)),(0.,0.,2.))
        self.assertEqual(tuple(gate._coords(result.projections[0].world_endpoint_m)),(2.,2.,3.))
        self.assertEqual((result.projections[0].voxel_x,result.projections[0].voxel_y,result.projections[0].voxel_z),(4,4,6))
        self.assertTrue(gate.verify(req,result));self.assertTrue(result.research_only)
        self.assertFalse(result.grants_authority)

    def test_center_occupied_free_and_unknown_classification(self):
        out=gate.project(sample());cells={(c.x,c.y,c.z):c for c in out.temporal_result.cells}
        self.assertGreater(cells[4,4,6].hit_count,0)
        self.assertGreater(cells[4,4,2].free_count,0)
        v=classify_volume(out.hypothetical_volume)
        self.assertTrue(v.cells)
        self.assertTrue(all(c.state == volume.CELL_UNKNOWN for c in v.cells))
        self.assertTrue(all(e.kind in (volume.VOLUME_PREDICTED_FREE,volume.VOLUME_PREDICTED_OCCUPIED) for e in out.hypothetical_volume.evidence))
        self.assertTrue(all(e.tick==10 for e in out.hypothetical_volume.evidence))
        self.assertTrue(gate.verify(sample(),out))

    def test_two_pixel_rays_same_source_and_tick(self):
        req=sample()
        req.pixels.add().CopyFrom(req.pixels[0]);req.pixels[-1].u=4
        out=gate.project(req)
        self.assertEqual(len(out.projections),2)
        self.assertNotEqual(out.projections[0].derived_ray_source_ref,out.projections[1].derived_ray_source_ref)
        self.assertEqual({r.source_ref for r in out.temporal_request.rays},
                         {m.derived_ray_source_ref for m in out.projections})
        self.assertIn('SAME_FRAME_RAYS_ARE_CORRELATED_DESPITE_DISTINCT_DERIVED_EVENT_REFS',out.warnings)

    def test_repeated_sample_rejected(self):
        req=sample();req.pixels.add().CopyFrom(req.pixels[0]);self.assertBad(req)

    def test_same_source_tick_requires_same_frame_hash(self):
        req=sample()
        req.pixels.add().CopyFrom(req.pixels[0]);req.pixels[-1].u=4
        req.pixels[-1].depth_frame_sha256=hashlib.sha256(b'another-frame').digest()
        with self.assertRaisesRegex(gate.CalibratedDepthRejected,
                                    'INCONSISTENT_SOURCE_TICK_DEPTH_FRAME_HASH'):
            gate.project(req)

    def test_unrectified_rejected(self):
        req=sample();req.camera.rectified_pinhole=False;req.camera_sha256=gate._digest(req.camera);self.assertBad(req)

    def test_2d_cannot_substitute_for_depth(self):
        req=sample();req.pixels[0].axial_depth_m=0;self.assertBad(req)

    def test_missing_and_early_no_return_rejected(self):
        req=sample();req.pixels[0].endpoint_hit=False;self.assertBad(req)
        req.pixels[0].axial_depth_m=req.camera.max_axial_depth_m
        result=gate.project(req)
        self.assertTrue(all(not r.endpoint_hit for r in result.temporal_request.rays))
        self.assertTrue(all(c.hit_count==0 for c in result.temporal_result.cells))

    def test_nonfinite_camera_and_depth(self):
        req=sample();req.camera.fx=float('nan');req.camera_sha256=gate._digest(req.camera);self.assertBad(req)
        req=sample();req.pixels[0].axial_depth_m=float('inf');self.assertBad(req)

    def test_quaternion_must_be_unit(self):
        req=sample();req.camera.qw=1.2;req.camera_sha256=gate._digest(req.camera);self.assertBad(req)

    def test_outside_grid_and_pixel(self):
        req=sample();req.pixels[0].u=8;self.assertBad(req)
        req=sample();req.camera.translation.x=20;req.camera_sha256=gate._digest(req.camera);self.assertBad(req)

    def test_tampered_hash_or_result(self):
        req=sample();req.camera.fx+=1;self.assertBad(req)
        req=sample();result=gate.project(req);result.projections[0].world_endpoint_m.x+=1
        with self.assertRaisesRegex(gate.CalibratedDepthRejected,'PROJECTED_HANDOFF_MISMATCH'):
            gate.verify(req,result)

    def test_invalid_scope_rejected(self):
        req=sample();req.conversation_id='';self.assertBad(req)
        req=sample();req.grants_authority=True;self.assertBad(req)
        req=sample();req.pixels[0].depth_frame_sha256=b'';self.assertBad(req)
        req=sample();req.pixels[0].tick=11;self.assertBad(req)

    def test_unknown_fields_rejected(self):
        req=sample();corrupt=p.P2QDepthRequest.FromString(req.SerializeToString()+b'\x98\x06\x01')
        self.assertBad(corrupt)

    def test_perspective_against_independent_rotation_reference(self):
        from scipy.spatial.transform import Rotation
        rng=random.Random(37)
        for _ in range(40):
            req=sample(u=rng.randint(0,7),v=rng.randint(0,7),depth=rng.uniform(.1,4))
            ang=rng.uniform(-.6,.6)
            req.camera.translation.x=7; req.camera.translation.y=7
            req.camera.qw=math.cos(ang/2)
            req.camera.qz=math.sin(ang/2)
            req.camera_sha256=gate._digest(req.camera)
            o=gate.project(req).projections[0]
            expected_local=(((req.pixels[0].u+.5-req.camera.cx)/req.camera.fx)*req.pixels[0].axial_depth_m,
                            ((req.pixels[0].v+.5-req.camera.cy)/req.camera.fy)*req.pixels[0].axial_depth_m,
                            req.pixels[0].axial_depth_m)
            xyz=Rotation.from_quat([0,0,math.sin(ang/2),math.cos(ang/2)]).apply(expected_local)+[7,7,1]
            for actual,expected in zip(gate._coords(o.world_endpoint_m),xyz):
                self.assertAlmostEqual(actual,expected,places=11)

    def test_batch_order_invariance(self):
        req=sample(u=3,v=3)
        req.pixels.add().CopyFrom(req.pixels[0]);req.pixels[-1].u=4
        first=gate.project(req)
        rev=type(req)();rev.CopyFrom(req);rev.pixels.reverse()
        second=gate.project(rev)
        self.assertEqual(first.temporal_request.SerializeToString(deterministic=True),
                         second.temporal_request.SerializeToString(deterministic=True))
        # Derived hypothesis source incorporates request hash (and request order),
        # so compare evidence coordinates/kinds, not the provenance identity.
        self.assertEqual([(v.x,v.y,v.z,v.kind) for v in first.hypothetical_volume.evidence],
                         [(v.x,v.y,v.z,v.kind) for v in second.hypothetical_volume.evidence])

    def test_t2_audit_cannot_promote_depth_hypothesis(self):
        from tests.test_c15_t2_composition import fixture as graph_fixture
        from cognitum.proto import spatial_structural_audit_pb2 as audit_pb
        from cognitum.spatial_structural_audit import audit
        q=sample()
        output=gate.project(q)
        g=graph_fixture()
        g.conversation_id='chat'
        request=audit_pb.StructuralAuditRequest(schema_version=1,
            conversation_id='chat',graph_id=g.graph_id,volume_id='vox',research_only=True)
        c=request.claims.add(claim_id='depth_claim',node_id='wall',
            source_ref='caller_claim',expected=audit_pb.SPATIAL_EXPECT_OCCUPIED)
        c.box.min_x=c.box.max_x=4
        c.box.min_y=c.box.max_y=4
        c.box.min_z=c.box.max_z=6
        structural=audit(g,output.hypothetical_volume,request)
        self.assertEqual(structural.audits[0].state,audit_pb.SPATIAL_AUDIT_INDETERMINATE)
        self.assertEqual(structural.audits[0].predicted_only_cells,1)
        self.assertEqual(structural.audits[0].claimed_support_cells,0)

    def test_duplicate_same_source_tick_cell_conflict_is_not_silenced(self):
        q=sample()
        q.pixels.add().CopyFrom(q.pixels[0])
        q.pixels[-1].u=4
        q.pixels[-1].endpoint_hit=False
        q.pixels[-1].axial_depth_m=q.camera.max_axial_depth_m
        output=gate.project(q)
        # Correlated same-frame evidence stays flagged and cannot auto-certify
        # any cell, even when the underlying temporal integration agrees.
        self.assertIn('SAME_FRAME_RAYS_ARE_CORRELATED_DESPITE_DISTINCT_DERIVED_EVENT_REFS',output.warnings)
        self.assertTrue(all(e.kind in (volume.VOLUME_PREDICTED_FREE,volume.VOLUME_PREDICTED_OCCUPIED)
                            for e in output.hypothetical_volume.evidence))

    def test_bounded_sample_count(self):
        req=sample()
        for i in range(gate.MAX_SAMPLES):
            req.pixels.add(u=i%8,v=(i//8)%8,axial_depth_m=1.,tick=i+1,
                source_ref='src',depth_frame_sha256=b'0'*32,endpoint_hit=True)
        req.evaluation_tick=1000
        self.assertBad(req)


if __name__=='__main__': unittest.main()
