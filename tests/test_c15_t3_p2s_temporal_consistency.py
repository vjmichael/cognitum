"""P2S independent temporal oracle, tampering, transition, and T2 isolation tests."""
import hashlib
import math
import random
import unittest

from cognitum.proto import spatial_temporal_consistency_pb2 as p
from cognitum.proto import spatial_correlated_fusion_pb2 as r
from cognitum.proto import spatial_volume_pb2 as v
from cognitum.spatial_temporal_consistency import reconcile, verify, TemporalConsistencyRejected
from cognitum.spatial_correlated_fusion import fuse
from cognitum.spatial_calibrated_depth import _digest
from cognitum.spatial_volume import classify
from tests.test_c15_t3_p2q_calibrated_depth import sample

TARGET = (4, 4, 6)


def capture(tick, hit=True, u=3, rho=0):
    depth = sample(u=u, tick=tick, hit=hit)
    depth.evaluation_tick = tick
    depth.capture_id = f'capture{tick}'
    depth.pixels[0].depth_frame_sha256 = hashlib.sha256(f'frame:{tick}'.encode()).digest()
    if not hit:
        depth.pixels[0].axial_depth_m = depth.camera.max_axial_depth_m
    return r.P2RFusionRequest(schema_version=1, depth=depth,
                             assumed_within_capture_rho=rho, research_only=True)


def request(pattern=(True, True, False, False), retention=.05, half_life=1000., age=50, rho=0):
    out = p.P2STemporalRequest(schema_version=1, conversation_id='chat',
        volume_id='vox', half_life_ticks=half_life, historical_retention=retention,
        min_stable_observations=2, max_age_ticks=age, research_only=True)
    for index, hit in enumerate(pattern):
        out.captures.add().CopyFrom(capture(10 * (index + 1), hit=hit, rho=rho))
    out.evaluation_tick = 10 * len(pattern)
    return out


def cell(result, coord=TARGET):
    return next(c for c in result.cells if (c.x, c.y, c.z) == coord)


class TemporalConsistencyTests(unittest.TestCase):
    def bad(self, req, diagnostic=None):
        with self.assertRaises(TemporalConsistencyRejected) as ctx:
            reconcile(req)
        if diagnostic:
            self.assertIn(diagnostic, str(ctx.exception))

    def test_pending_single_opposition_not_committed(self):
        q = request((True, True, False))
        out = reconcile(q)
        c = cell(out)
        self.assertEqual(c.state, p.P2S_CONTESTED)
        self.assertTrue(c.opposed_across_captures)
        self.assertFalse(c.change_confirmed)
        self.assertEqual(c.latest_consistent_streak, 1)
        self.assertEqual(c.change_candidate_tick, 30)
        self.assertEqual(out.pending_change_cell_count, 1)
        self.assertTrue(verify(q, out))
        self.assertNotIn(TARGET, {(x.x, x.y, x.z) for x in out.hypothetical_volume.evidence})

    def test_two_sequential_free_rays_confirm_change_but_not_handoff(self):
        q = request()
        result = reconcile(q)
        c = cell(result)
        self.assertEqual(c.state, p.P2S_RECOVERED_FREE)
        self.assertTrue(c.change_confirmed)
        self.assertEqual(c.change_candidate_tick, 30)
        self.assertLess(c.adjusted_probability, .5)
        self.assertGreater(c.baseline_probability, c.adjusted_probability)
        self.assertEqual([v.retention_multiplier for v in c.provenance], [.05, .05, 1., 1.])
        self.assertNotIn(TARGET, {(x.x, x.y, x.z) for x in result.hypothetical_volume.evidence})
        self.assertEqual(result.confirmed_change_cell_count, 1)

    def test_third_consistent_free_ray_recovers_predicted_handoff(self):
        q = request((True, True, False, False, False))
        out = reconcile(q)
        c = cell(out)
        self.assertEqual(c.state, p.P2S_RECOVERED_FREE)
        self.assertEqual(c.latest_consistent_streak, 3)
        self.assertIn(TARGET, {(x.x, x.y, x.z) for x in out.hypothetical_volume.evidence})
        for ev in out.hypothetical_volume.evidence:
            self.assertIn(ev.kind, (v.VOLUME_PREDICTED_OCCUPIED, v.VOLUME_PREDICTED_FREE))
        self.assertTrue(out.hypothetical_volume.research_only)
        self.assertFalse(out.hypothetical_volume.grants_authority)
        self.assertTrue(all(c.state == v.CELL_UNKNOWN for c in classify(out.hypothetical_volume).cells))

    def test_reverse_transition_occupancy_recovered(self):
        q = request((False, False, True, True, True))
        c = cell(reconcile(q))
        self.assertEqual(c.state, p.P2S_RECOVERED_OCCUPIED)
        self.assertGreater(c.adjusted_probability, .75)

    def test_stale_evidence_never_forwarded(self):
        q = request((True, True))
        q.max_age_ticks = 1
        q.evaluation_tick = 50
        out = reconcile(q)
        self.assertEqual(cell(out).state, p.P2S_STALE)
        self.assertEqual(len(out.hypothetical_volume.evidence), 0)

    def test_age_and_strength_mark_uncertain(self):
        q = request((True, True))
        q.min_stable_observations = 3
        self.assertEqual(cell(reconcile(q)).state, p.P2S_INDETERMINATE)

    def test_opposing_streak_not_a_prediction_when_score_favors_old_state(self):
        q = request((True, True, False, False), retention=1)
        out = reconcile(q)
        c = cell(out)
        self.assertTrue(c.change_confirmed)
        self.assertGreater(c.adjusted_log_odds, 0)
        self.assertEqual(c.state, p.P2S_INDETERMINATE)
        self.assertNotIn(TARGET, {(x.x, x.y, x.z) for x in out.hypothetical_volume.evidence})

    def test_mixed_frame_does_not_extend_streak_or_leak_to_t2(self):
        q = request((True, True))
        q.captures[-1].depth.camera.fx = 100
        q.captures[-1].depth.camera_sha256 = _digest(q.captures[-1].depth.camera)
        px = q.captures[-1].depth.pixels.add()
        px.CopyFrom(q.captures[-1].depth.pixels[0])
        px.endpoint_hit = False
        px.axial_depth_m = q.captures[-1].depth.camera.max_axial_depth_m
        px.u = 4  # nearby ray yields contradictory endpoint evidence at some voxels
        out = reconcile(q)
        conflict_cells = {(c.x,c.y,c.z) for c in fuse(q.captures[-1]).cells if c.conflicting_observations}
        self.assertTrue(conflict_cells)
        forward = {(v.x,v.y,v.z) for v in out.hypothetical_volume.evidence}
        self.assertFalse(conflict_cells & forward)
        for c in out.cells:
            if (c.x,c.y,c.z) in conflict_cells:
                self.assertEqual(c.state, p.P2S_CONTESTED)

    def test_mixed_frame_breaks_consecutive_change_streak(self):
        q = request((True, True, False, False, False))
        q.captures[3].depth.camera.fx = 100
        q.captures[3].depth.camera_sha256 = _digest(q.captures[3].depth.camera)
        px = q.captures[3].depth.pixels.add()
        px.CopyFrom(q.captures[3].depth.pixels[0])
        px.endpoint_hit = True
        px.axial_depth_m = 2.
        px.u = 4
        out = reconcile(q)
        c = cell(out)
        self.assertFalse(c.change_confirmed)
        self.assertEqual(c.latest_consistent_streak, 1)

    def test_no_retention_change_when_stable(self):
        a = request((True, True, True), retention=0)
        b = request((True, True, True), retention=1)
        aa, bb = cell(reconcile(a)), cell(reconcile(b))
        self.assertEqual(aa.adjusted_log_odds, bb.adjusted_log_odds)
        self.assertEqual(aa.baseline_log_odds, aa.adjusted_log_odds)

    def test_retention_one_equals_cross_capture_baseline(self):
        q = request((True, True, False, False), retention=1)
        c = cell(reconcile(q))
        self.assertEqual(c.baseline_log_odds, c.adjusted_log_odds)

    def test_external_oracle_temporal_math_and_p2r_partition(self):
        rng = random.Random(3221)
        for _ in range(32):
            pattern = [rng.random() > .5 for _ in range(4)]
            q = request(pattern, retention=1, half_life=rng.uniform(7, 1000), rho=.5)
            got = cell(reconcile(q))
            terms = []
            for cap in q.captures:
                tick = cap.depth.pixels[0].tick
                part = next(c for c in fuse(cap).cells if (c.x, c.y, c.z) == TARGET)
                terms.append(part.adjusted_log_odds * 2 ** (- (q.evaluation_tick - tick) / q.half_life_ticks))
            oracle = max(-8, min(8, math.fsum(terms)))
            self.assertAlmostEqual(got.adjusted_log_odds, oracle, places=12)

    def test_mixed_capture_different_frames_rejected(self):
        q = request((True, True))
        q.captures[0].depth.pixels.add().CopyFrom(q.captures[0].depth.pixels[0])
        q.captures[0].depth.pixels[-1].u = 4
        q.captures[0].depth.pixels[-1].depth_frame_sha256 = b'x' * 32
        self.bad(q, 'OUT_OF_ORDER_OR_MIXED_CAPTURE')

    def test_duplicate_capture_id_or_replayed_frame_rejected(self):
        q = request((True, True))
        q.captures[1].depth.capture_id = q.captures[0].depth.capture_id
        self.bad(q, 'REPLAYED_OR_DUPLICATE_CAPTURE')
        q = request((True, True))
        q.captures[1].depth.pixels[0].depth_frame_sha256 = q.captures[0].depth.pixels[0].depth_frame_sha256
        self.bad(q, 'REPLAYED_OR_DUPLICATE_CAPTURE')

    def test_out_of_order_and_future_rejected(self):
        q = request((True, False))
        q.captures.reverse()
        self.bad(q, 'OUT_OF_ORDER_OR_MIXED_CAPTURE')
        q = request((True, False))
        q.evaluation_tick = 15
        self.bad(q, 'OUT_OF_ORDER_OR_MIXED_CAPTURE')

    def test_grid_and_scope_isolation(self):
        q = request((True, True))
        q.captures[1].depth.conversation_id = 'different'
        self.bad(q, 'INVALID_OR_CROSS_SCOPE_CAPTURE')
        q = request((True, True))
        q.captures[1].depth.max_axis = 31
        self.bad(q, 'INCOMPATIBLE_VOLUME_GRID')

    def test_reject_unknown_fields_and_modifying_authority(self):
        q = request((True, True))
        self.bad(p.P2STemporalRequest.FromString(q.SerializeToString() + b'\x98\x06\x01'), 'INVALID_P2S_CONTRACT')
        q.grants_authority = True
        self.bad(q, 'INVALID_P2S_CONTRACT')
        q = request((True, True)); q.captures[0].depth.grants_authority = True
        self.bad(q, 'INVALID_OR_CROSS_SCOPE_CAPTURE')

    def test_invalid_policy_and_capacity(self):
        q = request((True, True)); q.historical_retention = float('nan')
        self.bad(q, 'INVALID_TEMPORAL_POLICY')
        q = request((True, True)); q.min_stable_observations = 1
        self.bad(q, 'INVALID_TEMPORAL_POLICY')
        q = request((True,) * 13)
        self.bad(q, 'INVALID_TEMPORAL_POLICY')

    def test_replay_and_result_tamper(self):
        q = request((True, True, False, False, False))
        a, b = reconcile(q), reconcile(q)
        self.assertEqual(a.SerializeToString(deterministic=True), b.SerializeToString(deterministic=True))
        self.assertTrue(verify(q, a))
        a.cells[0].adjusted_probability += .01
        with self.assertRaisesRegex(TemporalConsistencyRejected, 'P2S_REPLAY_MISMATCH'):
            verify(q, a)

    def test_t2_structural_audit_cannot_promote_recovered_state(self):
        from tests.test_c15_t2_composition import fixture
        from cognitum.spatial_structural_audit import audit
        from cognitum.proto import spatial_structural_audit_pb2 as a
        q = request((True, True, False, False, False))
        out = reconcile(q)
        graph = fixture(); graph.conversation_id = 'chat'
        claim = a.StructuralAuditRequest(schema_version=1,
            conversation_id='chat',graph_id=graph.graph_id,volume_id='vox',
            research_only=True)
        item = claim.claims.add(claim_id='p2s-claim',node_id='wall',
            source_ref='unverified',expected=a.SPATIAL_EXPECT_FREE)
        item.box.min_x = item.box.max_x = 4
        item.box.min_y = item.box.max_y = 4
        item.box.min_z = item.box.max_z = 6
        report = audit(graph,out.hypothetical_volume,claim)
        self.assertEqual(report.audits[0].state,a.SPATIAL_AUDIT_INDETERMINATE)
        self.assertGreaterEqual(report.audits[0].predicted_only_cells,1)
        self.assertEqual(report.audits[0].claimed_support_cells,0)

    def test_within_frame_correlation_is_not_counted_twice(self):
        q = request((True, True), rho=1)
        for cap in q.captures:
            cap.depth.pixels.add().CopyFrom(cap.depth.pixels[0])
            cap.depth.pixels[-1].u = 4
        c = cell(reconcile(q))
        self.assertEqual(c.observed_capture_count, 2)
        self.assertEqual(len(c.provenance), 2)
        self.assertEqual(c.state, p.P2S_PREDICTED_OCCUPIED)


if __name__ == '__main__':
    unittest.main()
