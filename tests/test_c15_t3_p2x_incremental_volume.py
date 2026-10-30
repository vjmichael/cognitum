"""P2X exact-bit parity, per-window reuse, fail-closed cache and receipt tests."""
import unittest
from cognitum.spatial_incremental_volume import P2XSession, IncrementalRejected
from cognitum.spatial_map_lifecycle import advance as full_advance, LifecycleRejected
from tests.test_c15_t3_p2w_map_lifecycle import request, next_source
from tests.test_c15_t3_p2v_dynamic_scene_robustness import fixture
from cognitum.proto import spatial_incremental_volume_pb2 as px


def encoded(msg):
    return msg.SerializeToString(deterministic=True)


class P2XTests(unittest.TestCase):
    def test_exact_parity_two_sequential_windows(self):
        session = P2XSession()
        one_req = request()
        one = session.advance(one_req, validate_parity=True)
        self.assertEqual(encoded(one.lifecycle), encoded(full_advance(one_req)))
        two_req = request(next_source(fixture()), previous=one.lifecycle.checkpoint,sequence=2)
        two = session.advance(two_req,validate_parity=True)
        self.assertEqual(encoded(two.lifecycle),encoded(full_advance(two_req)))
        self.assertGreater(two.reused_p2t_windows,0)
        self.assertGreater(two.reused_temporal_windows,0)
        self.assertGreater(two.recomputed_p2t_windows,0)
        self.assertTrue(session.verify_receipt(one.receipt))
        self.assertTrue(session.verify_receipt(two.receipt))
        self.assertEqual(two.receipt.previous_receipt_hmac_sha256,one.receipt.receipt_hmac_sha256)
        self.assertTrue(one.full_replay_parity_verified)
        self.assertTrue(two.full_replay_parity_verified)

    def test_replayed_source_hash_detected(self):
        q=request()
        q.source_result.cells[0].retained=not q.source_result.cells[0].retained
        with self.assertRaisesRegex(IncrementalRejected,'UNVERIFIED_UPSTREAM_P2V_RESULT'):
            P2XSession().advance(q)

    def test_cached_output_tamper_fails_closed(self):
        session=P2XSession()
        q=request()
        session._stats={s:[0,0] for s in ('p2s','p2t','p2v')}
        session._p2v(q.source_request)
        key=next(x for x in session._entries if x[0]=='p2v')
        data,tag=session._entries[key]
        session._entries[key]=(data+b'\x00',tag)
        with self.assertRaisesRegex(IncrementalRejected,'CACHE_INTEGRITY_FAILURE'):
            session.advance(q)
        self.assertEqual(session.cached_bytes,0)

    def test_different_session_does_not_accept_receipt(self):
        original=P2XSession(); out=original.advance(request())
        altered=px.P2XReceipt.FromString(encoded(out.receipt))
        altered.checkpoint_sha256=b'1'*32
        self.assertFalse(original.verify_receipt(altered))
        self.assertFalse(P2XSession().verify_receipt(out.receipt))

    def test_sequence_and_scope_are_isolated(self):
        s=P2XSession()
        out=s.advance(request())
        with self.assertRaisesRegex(IncrementalRejected,'SESSION_SEQUENCE_MISMATCH'):
            s.advance(request())
        q=request(next_source(fixture()),previous=out.lifecycle.checkpoint,sequence=2)
        q.source_request.dynamic_request.volume_id='different'
        with self.assertRaisesRegex(IncrementalRejected,'CROSS_SCOPE_SESSION'):
            s.advance(q)

    def test_chain_rejects_different_checkpoint_even_rehashed(self):
        from cognitum.spatial_map_lifecycle import checkpoint_digest
        s=P2XSession(); initial=s.advance(request())
        q=request(next_source(fixture()),previous=initial.lifecycle.checkpoint,sequence=2)
        q.previous.cells[0].last_support_tick += 1
        q.previous.checkpoint_sha256=checkpoint_digest(q.previous)
        with self.assertRaisesRegex(IncrementalRejected,'SESSION_CHECKPOINT_CHAIN_MISMATCH'):
            s.advance(q)

    def test_budget_and_lru_eviction(self):
        with self.assertRaises(ValueError):P2XSession(max_cache_bytes=100)
        s=P2XSession(max_cache_bytes=128000,max_entries=2)
        out=s.advance(request())
        self.assertLessEqual(s.cached_bytes,128000)
        self.assertLessEqual(s.cache_entries,2)
        self.assertEqual(out.lifecycle.checkpoint.sequence,1)

    def test_unchanged_legacy_p2u_and_p2v_full_replay(self):
        from cognitum.spatial_dynamic_scene_robustness import analyze, _analyze
        from cognitum.spatial_dynamic_scene_mapping import map_scene, _map_scene
        q=fixture()
        self.assertEqual(encoded(analyze(q)),encoded(_analyze(q)))
        self.assertEqual(encoded(map_scene(q.dynamic_request)),
                         encoded(_map_scene(q.dynamic_request)))

    def test_policy_change_invalidates_p2v_but_preserves_substage_cache(self):
        from cognitum.spatial_dynamic_scene_robustness import analyze
        session=P2XSession()
        one=session.advance(request())
        q=next_source(fixture())
        q.max_static_age_ticks += 10
        two_req=request(q,previous=one.lifecycle.checkpoint,sequence=2)
        two_req.source_result.CopyFrom(analyze(q))
        two=session.advance(two_req)
        self.assertFalse(two.reused_p2v_result)
        self.assertGreater(two.reused_p2t_windows,0)
        self.assertEqual(encoded(two.lifecycle),encoded(full_advance(two_req)))

    def test_cache_eviction_forces_recompute_without_changing_result(self):
        session=P2XSession(max_entries=2,max_cache_bytes=128_000)
        one=session.advance(request())
        q=request(next_source(fixture()),previous=one.lifecycle.checkpoint,sequence=2)
        two=session.advance(q)
        self.assertEqual(encoded(two.lifecycle),encoded(full_advance(q)))
        self.assertLessEqual(session.cache_entries,2)

    def test_source_input_unknown_wire_fails_before_cache_access(self):
        from cognitum.proto import spatial_map_lifecycle_pb2 as lifecycle_pb
        source=request()
        polluted=lifecycle_pb.P2WUpdateRequest.FromString(encoded(source)+b'\x98\x06\x01')
        with self.assertRaisesRegex(LifecycleRejected,'INVALID_P2W_CONTRACT'):
            P2XSession().advance(polluted)

    def test_reused_substage_cache_corruption_is_rejected(self):
        session=P2XSession()
        first=session.advance(request())
        key=next(x for x in session._entries if x[0]=='p2t')
        data,tag=session._entries[key]
        session._entries[key]=(data[:-1]+bytes([data[-1]^1]),tag)
        q=request(next_source(fixture()),previous=first.lifecycle.checkpoint,sequence=2)
        with self.assertRaisesRegex(IncrementalRejected,'CACHE_INTEGRITY_FAILURE'):
            session.advance(q)

    def test_stationary_evidence_stays_non_authoritative(self):
        from cognitum.proto import spatial_volume_pb2 as v
        from cognitum.spatial_volume import classify
        out=P2XSession().advance(request())
        grid=out.lifecycle.checkpoint.current_stationary_hypothetical_volume
        self.assertFalse(grid.grants_authority)
        self.assertTrue(all(c.state==v.CELL_UNKNOWN for c in classify(grid).cells))
        self.assertTrue(all(e.kind in (v.VOLUME_PREDICTED_FREE,v.VOLUME_PREDICTED_OCCUPIED) for e in grid.evidence))

    def test_first_update_without_parity_does_not_claim_it(self):
        s=P2XSession()
        out=s.advance(request())
        self.assertFalse(out.full_replay_parity_verified)
        self.assertEqual(encoded(out.lifecycle),encoded(full_advance(request())))

    def test_full_parity_stays_false_after_rejected_source(self):
        s=P2XSession()
        q=request();q.source_result.pose_discontinuity_found=True
        with self.assertRaises(IncrementalRejected):s.advance(q,validate_parity=True)
        self.assertEqual(s._sequence,0)

if __name__=='__main__':unittest.main()
