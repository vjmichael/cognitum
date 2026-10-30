"""C15 T3 P2Z: contract, recovery authority, crash points and rotation guards."""
import os
from pathlib import Path
import tempfile
import unittest
import hashlib

from cognitum.proto import spatial_host_recovery_readiness_pb2 as zpb
from cognitum.proto import spatial_durable_incremental_volume_pb2 as ypb
from cognitum.spatial_host_recovery_readiness import (
    HostReadinessRejected, P2ZHostReadiness, platform_readiness,
    validate_epoch_transition)
from cognitum.spatial_durable_incremental_volume import (
    DurableRejected, _file_path, _read_proto_exact, _hmac, bits, genesis)
from cognitum.spatial_map_lifecycle import advance as full_advance
from tests.test_c15_t3_p2w_map_lifecycle import request, next_source
from tests.test_c15_t3_p2v_dynamic_scene_robustness import fixture

KEY = b'p2z-synthetic-external-host-test-secret-32+'

class IndependentHostFixture:
    """In-memory host simulation only: NOT an authenticated production host."""
    def __init__(self, anchor, *, key=KEY, key_id='mock-key-epoch-9'):
        self.anchor = ypb.P2YHostAnchor(); self.anchor.CopyFrom(anchor)
        self.key = key
        self.key_id = key_id
        self.reject_updates = False
        self.approved_proof = b'fixture-operator-authorized-once'
        self.proof_used = False
    def read_binding(self):
        return zpb.P2ZHostBinding(schema_version=1,
            conversation_id=self.anchor.conversation_id, volume_id=self.anchor.volume_id,
            authority_epoch=self.anchor.authority_epoch, key_id=self.key_id,
            external_anchor=bits(self.anchor), research_only=True)
    def release_key(self, binding):
        if binding.key_id != self.key_id: raise AssertionError('wrong key id')
        return self.key
    def commit_update(self, binding, expected, newer):
        if self.reject_updates or expected != bits(self.anchor): return False
        self.anchor.CopyFrom(_read_proto_exact(ypb.P2YHostAnchor, newer))
        return True
    def approve_reconciliation(self, binding, expected, proposed, digest, proof):
        if self.proof_used or proof != self.approved_proof or expected != bits(self.anchor):
            return False
        if not digest or len(digest) != 32 or not proposed: return False
        candidate = _read_proto_exact(ypb.P2YHostAnchor, proposed)
        if candidate.sequence != self.anchor.sequence + 1: return False
        self.proof_used = True
        self.anchor.CopyFrom(candidate)
        return True

class P2ZTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'records'
        r=request()
        self.host=IndependentHostFixture(genesis(
            r.source_request.dynamic_request.conversation_id,
            r.source_request.dynamic_request.volume_id, 9))
        self.z=P2ZHostReadiness(self.root, host=self.host)

    def make_unanchored_tail(self):
        s=self.z.open_session()
        self.host.reject_updates=True
        with self.assertRaisesRegex(DurableRejected,'DURABLE_COMMIT_IN_DOUBT'):
            s.advance(request())
        self.host.reject_updates=False

    def intent(self, preview, proof=None):
        return zpb.P2ZReconcileIntent(schema_version=1,
            expected_anchor=bits(self.host.anchor),
            candidate_anchor=preview.candidate_anchor,
            candidate_record_sha256=preview.candidate_record_sha256,
            key_id=self.host.key_id,
            host_proof=self.host.approved_proof if proof is None else proof,
            research_only=True)

    def test_clean_genesis_and_restart_output_parity(self):
        self.assertEqual(self.z.inspect().status,'CLEAN')
        s=self.z.open_session()
        out=s.advance(request())
        self.assertEqual(bits(out.lifecycle),bits(full_advance(request())))
        self.assertEqual(self.z.inspect().status,'CLEAN')
        restarted=P2ZHostReadiness(self.root,host=self.host).open_session()
        self.assertEqual(bits(restarted.anchor),bits(self.host.anchor))
        self.assertEqual(restarted._session._sequence,1)

    def test_unanchored_tail_is_read_only_until_independent_host_approves(self):
        self.make_unanchored_tail()
        first=_file_path(self.root,1).read_bytes()
        preview=self.z.inspect()
        self.assertEqual(preview.status,'AUTHENTIC_UNANCHORED_TAIL')
        self.assertTrue(preview.requires_host_approval)
        self.assertEqual(preview.candidate_sequence,1)
        self.assertEqual(hashlib.sha256(first).digest(),preview.candidate_record_sha256)
        self.assertEqual(first,_file_path(self.root,1).read_bytes())
        with self.assertRaisesRegex(HostReadinessRejected,'HOST_RECONCILIATION_DENIED'):
            self.z.reconcile(self.intent(preview, b'invalid-operator-proof'))
        self.assertEqual(self.host.anchor.sequence,0)
        recovered=self.z.reconcile(self.intent(preview))
        self.assertEqual(recovered.anchor.sequence,1)
        self.assertEqual(first,_file_path(self.root,1).read_bytes())
        self.assertEqual(self.z.inspect().status,'CLEAN')
        out=full_advance(request())
        q=request(next_source(fixture()),previous=out.checkpoint,sequence=2)
        self.assertEqual(bits(recovered.advance(q).lifecycle),bits(full_advance(q)))

    def test_replay_rejection_if_tail_is_authentic_but_semantically_corrupt(self):
        self.make_unanchored_tail()
        p=_file_path(self.root,1)
        record=ypb.P2YDurableRecord.FromString(p.read_bytes())
        # A synthetic malicious key-holder can authenticate a bad saved result;
        # independent P2W replay must STILL reject it.
        result=__import__('cognitum.proto.spatial_map_lifecycle_pb2',fromlist=['P2WUpdateResult']).P2WUpdateResult.FromString(record.lifecycle)
        result.checkpoint.checkpoint_sha256 = b'X'*32
        record.lifecycle=bits(result)
        record.record_hmac_sha256=_hmac(KEY,record)
        p.write_bytes(bits(record))
        self.assertEqual(self.z.inspect().status,'REJECTED')
        self.assertEqual(self.host.anchor.sequence,0)

    def test_reject_tampered_tail_hash_even_with_valid_format(self):
        self.make_unanchored_tail()
        p=_file_path(self.root,1)
        data=bytearray(p.read_bytes());data[-3]^=1;p.write_bytes(data)
        self.assertEqual(self.z.inspect().status,'REJECTED')

    def test_stale_intent_cannot_commit_a_different_candidate(self):
        self.make_unanchored_tail()
        p=self.z.inspect();i=self.intent(p)
        i.candidate_record_sha256=b'Z'*32
        with self.assertRaisesRegex(HostReadinessRejected,'MISMATCHED'):
            self.z.reconcile(i)
        self.assertEqual(self.host.anchor.sequence,0)

    def test_empty_proof_does_not_invoke_host(self):
        self.make_unanchored_tail();p=self.z.inspect()
        with self.assertRaisesRegex(HostReadinessRejected,'MISSING_HOST'):
            self.z.reconcile(self.intent(p,b''))
        self.assertFalse(self.host.proof_used)

    def test_reused_approval_is_rejected(self):
        self.make_unanchored_tail();p=self.z.inspect();self.z.reconcile(self.intent(p))
        with self.assertRaisesRegex(HostReadinessRejected,'MISMATCHED'):
            self.z.reconcile(self.intent(p))

    def test_incomplete_temp_write_never_auto_deleted(self):
        self.z.open_session()
        tmp=self.root/'.tmp-powerloss'
        tmp.write_bytes(b'partial')
        self.assertEqual(self.z.inspect().status,'REJECTED')
        self.assertTrue(tmp.exists())

    def test_missing_committed_record_rejected(self):
        self.z.open_session().advance(request())
        _file_path(self.root,1).unlink()
        self.assertEqual(self.z.inspect().status,'REJECTED')

    def test_more_than_one_tail_never_reconciled(self):
        self.make_unanchored_tail()
        _file_path(self.root,2).write_bytes(_file_path(self.root,1).read_bytes())
        self.assertEqual(self.z.inspect().status,'REJECTED')

    def test_revocation_and_key_id_change_rejected(self):
        self.z.open_session()
        self.host.anchor.revoked=True
        with self.assertRaises(HostReadinessRejected):self.z.inspect()
        self.host.anchor.revoked=False
        self.host.key_id='different-host-key-id'
        with self.assertRaisesRegex(HostReadinessRejected,'KEY_OR_EPOCH'):
            self.z.open_session()

    def test_key_rotation_requires_distinct_epoch_key_and_journal(self):
        original=self.host.read_binding()
        next_anchor=genesis(self.host.anchor.conversation_id,
                            self.host.anchor.volume_id,10)
        successor=IndependentHostFixture(next_anchor,key=b'N'*32,key_id='rotated-key-epoch-10')
        different_root=Path(self.temp.name)/'epoch10'
        self.assertTrue(validate_epoch_transition(original,successor.read_binding(),self.root,different_root))
        next_research=P2ZHostReadiness(different_root,host=successor)
        next_research.open_session().advance(request()) if False else None
        with self.assertRaises(HostReadinessRejected):
            validate_epoch_transition(original,successor.read_binding(),self.root,self.root)
        successor.key_id=self.host.key_id
        with self.assertRaises(HostReadinessRejected):
            validate_epoch_transition(original,successor.read_binding(),self.root,different_root)

    def test_epoch_enrollment_no_reuse_of_old_records(self):
        self.z.open_session().advance(request())
        self.host.anchor.authority_epoch=10
        self.host.key_id='new-key-epoch-10'
        self.host.key=b'R'*32
        with self.assertRaises(HostReadinessRejected):self.z.open_session()
        # A genuinely new epoch may start only in its own empty journal.
        self.host.anchor=genesis(self.host.anchor.conversation_id,self.host.anchor.volume_id,10)
        new=P2ZHostReadiness(Path(self.temp.name)/'fresh-epoch',host=self.host)
        self.assertEqual(new.inspect().status,'CLEAN')
        self.assertEqual(new.open_session().anchor.sequence,0)
        self.assertTrue(_file_path(self.root,1).is_file())

    def test_wrong_key_blocks_existing_host_journal(self):
        self.z.open_session().advance(request())
        self.host.key=b'x'*32
        with self.assertRaises(DurableRejected):
            P2ZHostReadiness(self.root,host=self.host).open_session()

    def test_platform_readiness_never_claims_windows_certification(self):
        result=platform_readiness()
        self.assertFalse(result['windows_native_crash_powerloss_certified'])
        self.assertFalse(result['real_host_key_custody_verified'])

    @unittest.skipUnless(os.name=='nt','requires actual Windows NT kernel and filesystem')
    def test_windows_native_recovery_smoke(self):
        # This is intentionally not emulated on Linux. A Windows agent must
        # execute and extend this into ACL, crash, restart and power-loss tests.
        self.z.open_session().advance(request())
        self.assertEqual(P2ZHostReadiness(self.root,host=self.host).inspect().status,'CLEAN')

if __name__=='__main__':unittest.main()
