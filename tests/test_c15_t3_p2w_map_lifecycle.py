"""P2W bounded incremental metadata, full upstream replay and checkpoint integrity."""
import unittest
from cognitum.proto import spatial_map_lifecycle_pb2 as pb
from cognitum.proto import spatial_volume_pb2 as volume_pb
from cognitum.spatial_map_lifecycle import advance,verify,LifecycleRejected,checkpoint_digest
from cognitum.spatial_dynamic_scene_robustness import analyze
from cognitum.spatial_volume import classify
from tests.test_c15_t3_p2v_dynamic_scene_robustness import fixture
from tests.test_c15_t3_p2u_dynamic_scene_mapping import shifted


def request(q=None, **kw):
    q=q or fixture()
    d=dict(schema_version=1,source_request=q,source_result=analyze(q),
           max_resident_cells=30,max_resident_objects=3,max_idle_ticks=1000,
           sequence=1,research_only=True)
    d.update(kw)
    return pb.P2WUpdateRequest(**d)


def next_source(q):
    fresh=type(q)();fresh.CopyFrom(q)
    fresh.dynamic_request.windows.add().CopyFrom(shifted(fresh.dynamic_request.windows[0],200))
    return fresh

class LifecycleTests(unittest.TestCase):
    def bad(self,request_,reason):
        with self.assertRaises(LifecycleRejected) as err:advance(request_)
        self.assertIn(reason,str(err.exception))

    def test_first_snapshot_reproducible_and_read_only(self):
        q=request();old=q.source_result.SerializeToString(deterministic=True)
        a=advance(q);b=advance(q)
        self.assertEqual(a.SerializeToString(deterministic=True),b.SerializeToString(deterministic=True))
        self.assertTrue(verify(q,a));self.assertEqual(old,q.source_result.SerializeToString(deterministic=True))
        self.assertEqual(a.checkpoint.sequence,1)
        self.assertTrue(a.upstream_replay_verified)
        self.assertEqual(checkpoint_digest(a.checkpoint),a.checkpoint.checkpoint_sha256)
        self.assertFalse(a.checkpoint.grants_authority)
        self.assertTrue(a.checkpoint.research_only)

    def test_second_snapshot_new_captures_and_hash_chain(self):
        a=advance(request());n=next_source(fixture())
        b=advance(request(n,previous=a.checkpoint,sequence=2))
        self.assertEqual(b.checkpoint.prior_checkpoint_sha256,a.checkpoint.checkpoint_sha256)
        self.assertGreater(b.checkpoint.max_capture_tick,a.checkpoint.max_capture_tick)
        self.assertGreater(b.checkpoint.last_evaluation_tick,a.checkpoint.last_evaluation_tick)
        self.assertTrue(verify(request(n,previous=a.checkpoint,sequence=2),b))

    def test_no_new_capture_blocks_replay_even_if_eval_tick_changes(self):
        a=advance(request());q=fixture()
        for w in q.dynamic_request.windows:w.temporal_request.evaluation_tick+=300
        self.bad(request(q,previous=a.checkpoint,sequence=2),'STALE_OR_REPLAYED_UPDATE')

    def test_new_capture_but_replayed_evaluation_tick(self):
        a=advance(request(next_source(fixture())))
        # Valid but earlier P2V source must not roll back a newer checkpoint.
        self.bad(request(fixture(),previous=a.checkpoint,sequence=2),'STALE_OR_REPLAYED_UPDATE')

    def test_checkpoint_content_tamper_rejected(self):
        a=advance(request());a.checkpoint.cells[0].last_support_tick=777
        self.bad(request(next_source(fixture()),previous=a.checkpoint,sequence=2),'CHECKPOINT_INTEGRITY_FAILURE')

    def test_wrong_chain_sequence_and_cross_scope_rejected(self):
        a=advance(request());n=next_source(fixture())
        self.bad(request(n,previous=a.checkpoint,sequence=3),'SEQUENCE_OR_SCOPE_MISMATCH')
        prior=a.checkpoint
        prior.conversation_id='other'
        prior.checkpoint_sha256=checkpoint_digest(prior)
        # Internally consistent but different conversation must fail scope gate.
        self.bad(request(n,previous=prior,sequence=2),'SEQUENCE_OR_SCOPE_MISMATCH')

    def test_cap_evicts_explicitly_and_deterministically(self):
        x=advance(request(max_resident_cells=3,max_resident_objects=1))
        self.assertEqual(len(x.checkpoint.cells),3)
        self.assertTrue(x.evicted_cells)
        self.assertTrue(all(e.reason==pb.P2W_CAPACITY_LIMIT for e in x.evicted_cells))
        self.assertEqual(x.current_static_evidence_count,3)
        self.assertEqual(len(x.checkpoint.current_stationary_hypothetical_volume.evidence),3)
        self.assertTrue(verify(request(max_resident_cells=3,max_resident_objects=1),x))

    def test_idle_eviction_can_retire_all_metadata(self):
        # First run can expire older cells but not any future tick.
        x=advance(request(max_idle_ticks=1))
        self.assertTrue(x.evicted_cells)
        self.assertTrue(any(e.reason==pb.P2W_IDLE_EXPIRED for e in x.evicted_cells))
        # Newest supported cells remain eligible; old cells are evicted.
        self.assertLess(x.current_static_evidence_count,x.input_cell_count)

    def test_reusing_stale_static_from_prior_is_disallowed(self):
        old=advance(request());new=next_source(fixture())
        from tests.test_c15_t3_p2v_dynamic_scene_robustness import pose_translate
        pose_translate(new,.05)
        new.max_camera_translation_step_m=.01
        r=advance(request(new,previous=old.checkpoint,sequence=2))
        self.assertEqual(r.current_static_evidence_count,0)
        self.assertTrue(all(not c.retained_now for c in r.checkpoint.cells))

    def test_untrusted_source_result_tamper_rejected(self):
        q=request();q.source_result.cells[0].retained=not q.source_result.cells[0].retained
        self.bad(q,'UNVERIFIED_UPSTREAM_P2V')

    def test_source_hash_binding_and_unknown_wire_rejected(self):
        q=request();q.source_result.request_sha256=b'a'*32
        self.bad(q,'UNVERIFIED_UPSTREAM_P2V')
        q=request();bad=pb.P2WUpdateRequest.FromString(q.SerializeToString()+b'\x98\x06\x01')
        self.bad(bad,'INVALID_P2W_CONTRACT')

    def test_policy_and_no_predecessor_failure(self):
        self.bad(request(max_resident_cells=0),'INVALID_P2W_BUDGET')
        self.bad(request(max_resident_objects=0),'INVALID_P2W_BUDGET')
        self.bad(request(max_idle_ticks=0),'INVALID_P2W_BUDGET')
        self.bad(request(sequence=2),'MISSING_PREDECESSOR')
        self.bad(request(grants_authority=True),'INVALID_P2W_CONTRACT')

    def test_prediction_only_and_t2_indeterminate(self):
        o=advance(request())
        vol=o.checkpoint.current_stationary_hypothetical_volume
        self.assertTrue(all(x.kind in (volume_pb.VOLUME_PREDICTED_FREE,volume_pb.VOLUME_PREDICTED_OCCUPIED) for x in vol.evidence))
        self.assertTrue(all(c.state == volume_pb.CELL_UNKNOWN for c in classify(vol).cells))
        from tests.test_c15_t2_composition import fixture as graph_fixture
        from cognitum.proto import spatial_structural_audit_pb2 as ap
        from cognitum.spatial_structural_audit import audit
        graph=graph_fixture();graph.conversation_id='chat'
        rq=ap.StructuralAuditRequest(schema_version=1,conversation_id='chat',graph_id=graph.graph_id,
           volume_id='vox',research_only=True)
        c=next(iter(vol.evidence))
        z=rq.claims.add(claim_id='not_proven',node_id='wall',source_ref='synthetic',expected=ap.SPATIAL_EXPECT_OCCUPIED)
        z.box.min_x=z.box.max_x=c.x;z.box.min_y=z.box.max_y=c.y;z.box.min_z=z.box.max_z=c.z
        self.assertEqual(audit(graph,vol,rq).audits[0].state,ap.SPATIAL_AUDIT_INDETERMINATE)

    def test_serialized_checkpoint_roundtrip_is_recoverable(self):
        a=advance(request())
        stored=a.checkpoint.SerializeToString(deterministic=True)
        restored=pb.P2WCheckpoint.FromString(stored)
        self.assertEqual(checkpoint_digest(restored),restored.checkpoint_sha256)
        n=next_source(fixture())
        original=advance(request(n,previous=a.checkpoint,sequence=2))
        replayed=advance(request(n,previous=restored,sequence=2))
        self.assertEqual(original.SerializeToString(deterministic=True),
                         replayed.SerializeToString(deterministic=True))

    def test_tampered_checkpoint_static_volume_rejected_even_if_rehashed(self):
        a=advance(request())
        prior=a.checkpoint
        prior.current_stationary_hypothetical_volume.ClearField('evidence')
        prior.checkpoint_sha256=checkpoint_digest(prior)
        self.bad(request(next_source(fixture()),previous=prior,sequence=2),
                 'CHECKPOINT_STATIC_MISMATCH')

    def test_replay_result_mutation_detected(self):
        req=request()
        out=advance(req)
        out.evicted_cells.add(x=101,y=101,z=101,reason=pb.P2W_CAPACITY_LIMIT)
        with self.assertRaisesRegex(LifecycleRejected,'P2W_REPLAY_MISMATCH'):
            verify(req,out)

    def test_no_identity_authentication_and_result_tampering(self):
        req=request();out=advance(req)
        self.assertTrue(all(not o.authenticated for o in out.checkpoint.objects))
        out.checkpoint.objects[0].authenticated=True
        with self.assertRaisesRegex(LifecycleRejected,'P2W_REPLAY_MISMATCH'):verify(req,out)

    def test_prior_checkpoint_unsorted_or_unverified(self):
        prior=advance(request()).checkpoint
        prior.cells.reverse()
        prior.checkpoint_sha256=checkpoint_digest(prior)
        self.bad(request(next_source(fixture()),previous=prior,sequence=2),'NONCANONICAL_CHECKPOINT')

    def test_metadata_budget_always_respected(self):
        o=advance(request(max_resident_cells=1,max_resident_objects=1))
        self.assertEqual(o.output_cell_count,1)
        self.assertLessEqual(o.checkpoint.ByteSize(),3_000_000)
        self.assertEqual(o.output_object_count,1)

if __name__=='__main__':unittest.main()
