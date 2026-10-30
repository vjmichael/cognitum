"""C15 T3 P2R: correlation-ablation, provenance, tamper, and handoff gates."""
import hashlib
import math
import random
import unittest

from cognitum.proto import spatial_correlated_fusion_pb2 as pb
from cognitum.proto import spatial_volume_pb2 as vp
from cognitum.spatial_correlated_fusion import fuse, verify, CorrelatedFusionRejected
from tests.test_c15_t3_p2q_calibrated_depth import sample


def make(rho=1., *, same_frame=True, n=2, same_source=True, repeat_tick=False):
    depth = sample(u=3, v=3, tick=10)
    for i in range(1,n):
        px=depth.pixels.add()
        px.CopyFrom(depth.pixels[0])
        px.u=3+i
        if not same_frame:
            px.depth_frame_sha256=hashlib.sha256(('frame'+str(i)).encode()).digest()
            px.tick=9-i if i<9 else 1
        if not same_source:
            px.source_ref='distinct'+str(i)
        if repeat_tick:
            px.tick=9-i
    return pb.P2RFusionRequest(schema_version=1, depth=depth,
              assumed_within_capture_rho=rho, research_only=True)


def selected(out, coord=(4,4,2)):
    return next(c for c in out.cells if (c.x,c.y,c.z)==coord)


class CorrelatedFusionTests(unittest.TestCase):
    def bad(self, q, why=None):
        with self.assertRaises(CorrelatedFusionRejected) as caught:
            fuse(q)
        if why is not None:
            self.assertIn(why,str(caught.exception))

    def test_identical_frame_at_rho_one_is_not_double_confidence(self):
        # Pixel rays overlap in their free-space traversal through (4,4,2).
        a=fuse(make(n=1, rho=1.))
        b=fuse(make(n=2, rho=1.))
        x=selected(a);y=selected(b)
        self.assertAlmostEqual(x.adjusted_log_odds,y.adjusted_log_odds,places=10)
        self.assertLess(y.independent_probability,y.adjusted_probability)
        self.assertEqual(y.largest_correlated_group,2)
        self.assertEqual(y.capture_group_count,1)
        self.assertTrue(verify(make(n=2,rho=1.),b))

    def test_rho_zero_bitwise_equivalent_to_p2q_independent_baseline(self):
        out=fuse(make(rho=0.))
        for c in out.cells:
            self.assertEqual(c.adjusted_log_odds,c.independent_log_odds)
            self.assertEqual(c.adjusted_probability,c.independent_probability)
        self.assertEqual(out.independent_baseline.temporal_result.cells[0].log_odds,
                         out.cells[0].independent_log_odds)

    def test_no_group_adjustment_for_different_images(self):
        out=fuse(make(rho=1., same_frame=False))
        for c in out.cells:
            self.assertEqual(c.adjusted_log_odds,c.independent_log_odds)
        self.assertEqual(selected(out).capture_group_count,2)

    def test_no_group_adjustment_for_different_sources(self):
        out=fuse(make(rho=1., same_source=False))
        self.assertEqual(selected(out).capture_group_count,2)
        for c in out.cells:
            self.assertEqual(c.adjusted_log_odds,c.independent_log_odds)

    def test_replayed_same_digest_different_tick_is_correlated(self):
        q=make(rho=1.,repeat_tick=True)
        q.depth.evaluation_tick=10
        out=fuse(q)
        self.assertEqual(selected(out).largest_correlated_group,2)
        self.assertGreater(selected(out).adjusted_probability,
                           selected(out).independent_probability)

    def test_sensitivity_grid_contains_adjustment_at_tabulated_rhos(self):
        for rho in (0.,.25,.5,.75,1.):
            out=fuse(make(rho))
            for c in out.cells:
                self.assertLessEqual(c.sensitivity_min_probability-1e-12,c.adjusted_probability)
                self.assertGreaterEqual(c.sensitivity_max_probability+1e-12,c.adjusted_probability)

    def test_independent_group_weight_is_not_clamped_early(self):
        # More observations on the same cell can saturate the baseline at -8,
        # while rho=1 remains equivalent to a single observation.
        q=make(rho=1., n=5)
        for i,p in enumerate(q.depth.pixels):
            p.u=i+1
        out=fuse(q)
        self.assertTrue(any(c.largest_correlated_group>1 for c in out.cells))
        self.assertTrue(all(-8 <= c.adjusted_log_odds <= 8 for c in out.cells))

    def test_conflicts_retained_and_never_handed_off(self):
        q=make(rho=.8)
        q.depth.pixels[-1].endpoint_hit=False
        q.depth.pixels[-1].axial_depth_m=q.depth.camera.max_axial_depth_m
        q.depth.pixels[-1].u=3
        q.depth.pixels[-1].tick=9
        out=fuse(q)
        conflicts={(c.x,c.y,c.z) for c in out.cells if c.conflicting_observations}
        forwarded={(v.x,v.y,v.z) for v in out.hypothetical_volume.evidence}
        self.assertTrue(conflicts)
        self.assertFalse(conflicts & forwarded)

    def test_t2_handoff_is_predicted_only(self):
        from cognitum.spatial_volume import classify
        out=fuse(make(.6))
        self.assertTrue(out.hypothetical_volume.research_only)
        self.assertFalse(out.hypothetical_volume.grants_authority)
        self.assertTrue(all(c.state==vp.CELL_UNKNOWN for c in classify(out.hypothetical_volume).cells))
        self.assertTrue(all(v.kind in (vp.VOLUME_PREDICTED_OCCUPIED, vp.VOLUME_PREDICTED_FREE)
                            for v in out.hypothetical_volume.evidence))

    def test_unknown_proto_field_is_rejected(self):
        q=make()
        corrupt=pb.P2RFusionRequest.FromString(q.SerializeToString()+b'\x98\x06\x01')
        self.bad(corrupt, 'INVALID_RESEARCH_FUSION_CONTRACT')

    def test_invalid_rho_rejected(self):
        for rho in (-.001,1.0001,float('inf'),float('nan')):
            self.bad(make(rho),'INVALID_CORRELATION_ASSUMPTION')

    def test_invalid_scope_camera_and_source_fail_closed(self):
        q=make();q.research_only=False;self.bad(q)
        q=make();q.grants_authority=True;self.bad(q)
        q=make();q.depth.conversation_id='';self.bad(q, 'INVALID_P2Q_DEPTH')
        q=make();q.depth.pixels[0].depth_frame_sha256=b'bad';self.bad(q, 'INVALID_P2Q_DEPTH')
        q=make();q.depth.camera.fx=-1;self.bad(q, 'INVALID_P2Q_DEPTH')

    def test_result_tampering_rejected(self):
        q=make(.75);out=fuse(q);self.assertTrue(verify(q,out))
        out.cells[0].adjusted_probability+=0.1
        with self.assertRaisesRegex(CorrelatedFusionRejected,'FUSION_EVIDENCE_MISMATCH'):
            verify(q,out)

    def test_deterministic_replay_and_pixel_order(self):
        q=make(.5)
        a=fuse(q)
        b=fuse(q)
        self.assertEqual(a.SerializeToString(deterministic=True), b.SerializeToString(deterministic=True))
        q2=type(q)();q2.CopyFrom(q);q2.depth.pixels.reverse()
        b=fuse(q2)
        self.assertEqual([(c.x,c.y,c.z,c.adjusted_probability) for c in a.cells],
                         [(c.x,c.y,c.z,c.adjusted_probability) for c in b.cells])

    def test_random_oracle_for_equicorrelation_free_only(self):
        rng=random.Random(8171)
        for _ in range(48):
            rho=rng.random()
            q=make(rho)
            q.depth.free_probability=rng.uniform(.05,.45)
            out=fuse(q)
            c=selected(out)
            # Independent reference: two same-capture log-odds contributions.
            expected=2*math.log(q.depth.free_probability/(1-q.depth.free_probability))/(1+rho)
            self.assertAlmostEqual(c.adjusted_log_odds, expected,places=10)


if __name__=='__main__':unittest.main()

class CorrelatedFusionIntegrationTests(unittest.TestCase):
    def test_occupancy_endpoint_single_replayed_hit_never_gains_independent_weight(self):
        req=make(rho=1.,repeat_tick=True)
        req.depth.pixels[-1].u=3  # same pixel, different tick, same declared frame hash
        out=fuse(req)
        occupied=(4,4,6)
        endpoint=selected(out,occupied)
        self.assertEqual((endpoint.hit_count,endpoint.free_count),(2,0))
        self.assertEqual(endpoint.largest_correlated_group,2)
        # Temporal decay makes older hit slightly weaker; averaging the two
        # cannot be larger than the newer single-frame likelihood.
        self.assertLess(endpoint.adjusted_log_odds,math.log(.8/.2)+1e-12)
        self.assertLess(endpoint.adjusted_probability,endpoint.independent_probability)

    def test_numpy_independent_oracle_for_mixed_group_contributions(self):
        import numpy as np
        req=make(.65)
        req.depth.pixels[-1].endpoint_hit=False
        req.depth.pixels[-1].axial_depth_m=req.depth.camera.max_axial_depth_m
        req.depth.pixels[-1].u=3
        req.depth.pixels[-1].tick=9
        out=fuse(req)
        cell=selected(out,(4,4,6))
        hit=np.log(.8/.2)
        free=np.log(.3/.7) * 2**(-1/5)
        expected=(hit+free)/(1+.65)
        self.assertAlmostEqual(cell.adjusted_log_odds, float(expected),places=10)
        self.assertTrue(cell.conflicting_observations)

    def test_t2_structural_audit_never_confirms_hypothetical_occupancy(self):
        from tests.test_c15_t2_composition import fixture as graph_fixture
        from cognitum.spatial_structural_audit import audit
        from cognitum.proto import spatial_structural_audit_pb2 as sp
        q=make(.9)
        out=fuse(q)
        g=graph_fixture();g.conversation_id='chat'
        request=sp.StructuralAuditRequest(schema_version=1,conversation_id='chat',
            graph_id=g.graph_id,volume_id='vox',research_only=True)
        c=request.claims.add(claim_id='p2r_claim',node_id='wall',source_ref='unverified',
                expected=sp.SPATIAL_EXPECT_FREE)
        c.box.min_x=c.box.max_x=4
        c.box.min_y=c.box.max_y=4
        c.box.min_z=c.box.max_z=2
        report=audit(g,out.hypothetical_volume,request)
        self.assertEqual(report.audits[0].state,sp.SPATIAL_AUDIT_INDETERMINATE)
        self.assertGreaterEqual(report.audits[0].predicted_only_cells,1)
        self.assertEqual(report.audits[0].claimed_support_cells,0)
