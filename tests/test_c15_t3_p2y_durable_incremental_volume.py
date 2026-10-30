"""P2Y host-boundary, restart replay and durable journal adversarial tests."""
import os
from pathlib import Path
import tempfile
import unittest

from cognitum.proto import spatial_durable_incremental_volume_pb2 as yp
from cognitum.proto import spatial_volume_pb2 as vol
from cognitum.spatial_durable_incremental_volume import (
    P2YDurableSession, DurableRejected, genesis, bits, _file_path)
from cognitum.spatial_map_lifecycle import advance as full_advance
from tests.test_c15_t3_p2w_map_lifecycle import request, next_source
from tests.test_c15_t3_p2v_dynamic_scene_robustness import fixture

KEY = b'host-key-32-bytes-test-ONLY!!!!!!!'

class SimulatedHost:
    """Only a test double: actual host-issued anchors are not implemented."""
    def __init__(self, anchor):
        self.anchor=yp.P2YHostAnchor();self.anchor.CopyFrom(anchor)
        self.reject=False
    def read(self):
        c=yp.P2YHostAnchor();c.CopyFrom(self.anchor);return c
    def compare_and_swap(self, old, new):
        if self.reject or bits(old)!=bits(self.anchor):return False
        self.anchor.CopyFrom(new);return True

class P2YTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'journal'
        q=request()
        self.chat=q.source_request.dynamic_request.conversation_id
        self.vol=q.source_request.dynamic_request.volume_id
        self.host=SimulatedHost(genesis(self.chat,self.vol,9))
    def session(self, secret=KEY):
        return P2YDurableSession(self.path,host_secret=secret,authority=self.host)
    def advance_two(self):
        s=self.session()
        q1=request()
        one=s.advance(q1)
        q2=request(next_source(fixture()),previous=one.lifecycle.checkpoint,sequence=2)
        two=s.advance(q2)
        return s,q1,q2,one,two

    def test_genesis_then_restart_full_replay_parity_and_continuation(self):
        s,q1,q2,one,two=self.advance_two()
        self.assertEqual(s.anchor.sequence,2)
        self.assertEqual(bits(one.lifecycle),bits(full_advance(q1)))
        self.assertEqual(bits(two.lifecycle),bits(full_advance(q2)))
        restarted=self.session()
        self.assertEqual(bits(restarted.anchor),bits(self.host.anchor))
        self.assertEqual(restarted._session._sequence,2)
        self.assertEqual(restarted._session._checkpoint_sha,two.lifecycle.checkpoint.checkpoint_sha256)
        self.assertTrue(two.full_replay_parity_verified)
        self.assertEqual(len(list(self.path.glob('*.p2y'))),2)
        self.assertFalse(two.lifecycle.checkpoint.grants_authority)
        self.assertTrue(all(e.kind in (vol.VOLUME_PREDICTED_FREE,vol.VOLUME_PREDICTED_OCCUPIED)
           for e in two.lifecycle.checkpoint.current_stationary_hypothetical_volume.evidence))

    def test_disk_tamper_rejected_even_when_length_matches(self):
        self.session().advance(request())
        p=_file_path(self.path,1)
        b=bytearray(p.read_bytes());b[-2]^=1;p.write_bytes(b)
        with self.assertRaises(DurableRejected):self.session()

    def test_deleted_committed_record_is_detected_as_rollback(self):
        self.advance_two()
        _file_path(self.path,2).unlink()
        with self.assertRaisesRegex(DurableRejected,'JOURNAL_ROLLBACK'):
            self.session()

    def test_stale_external_anchor_detects_unanchored_extra_record(self):
        self.advance_two()
        self.host.anchor.sequence=1
        with self.assertRaisesRegex(DurableRejected,'JOURNAL_ROLLBACK'):
            self.session()

    def test_wrong_host_key_or_anchor_fails(self):
        self.session().advance(request())
        with self.assertRaisesRegex(DurableRejected,'JOURNAL_CHAIN_OR_AUTHENTICATION'):
            self.session(b'x'*32)
        self.host.anchor.head_hmac_sha256=b'Z'*32
        with self.assertRaisesRegex(DurableRejected,'HOST_ANCHOR_MISMATCH'):
            self.session()

    def test_revoke_blocks_live_and_recovery(self):
        s=self.session()
        one=s.advance(request())
        self.host.anchor.revoked=True
        q=request(next_source(fixture()),previous=one.lifecycle.checkpoint,sequence=2)
        with self.assertRaisesRegex(DurableRejected,'MISSING_REVOKED'):
            s.advance(q)
        with self.assertRaisesRegex(DurableRejected,'MISSING_REVOKED'):
            self.session()

    def test_epoch_change_blocks_old_journal(self):
        s=self.session()
        one=s.advance(request())
        self.host.anchor.authority_epoch=10
        q=request(next_source(fixture()),previous=one.lifecycle.checkpoint,sequence=2)
        with self.assertRaisesRegex(DurableRejected,'STALE_WRITER'):
            s.advance(q)
        with self.assertRaisesRegex(DurableRejected,'JOURNAL_CHAIN'):
            self.session()

    def test_unanchored_tail_after_host_commit_failure_fails_closed(self):
        s=self.session()
        self.host.reject=True
        with self.assertRaisesRegex(DurableRejected,'DURABLE_COMMIT_IN_DOUBT'):
            s.advance(request())
        with self.assertRaisesRegex(DurableRejected,'UNCERTAIN_COMMIT'):
            s.advance(request())
        with self.assertRaisesRegex(DurableRejected,'JOURNAL_ROLLBACK'):
            self.session()
        self.assertEqual(self.host.anchor.sequence,0)

    def test_concurrent_writer_rejected_on_anchor_change(self):
        a=self.session();b=self.session()
        a.advance(request())
        with self.assertRaisesRegex(DurableRejected,'STALE_WRITER'):
            b.advance(request())

    def test_forged_source_and_scope_rejected_without_commit(self):
        s=self.session()
        bad=request();bad.source_result.cells[0].retained=not bad.source_result.cells[0].retained
        with self.assertRaises(ValueError):s.advance(bad)
        self.assertEqual(self.host.anchor.sequence,0)
        self.assertFalse(list(self.path.glob('*.p2y')))
        q=request();q.source_request.dynamic_request.volume_id='wrong'
        with self.assertRaisesRegex(DurableRejected,'DURABLE_CROSS_SCOPE'):
            s.advance(q)

    def test_extra_file_symlink_and_unknown_wire_rejected(self):
        self.session().advance(request())
        (self.path/'notes.txt').write_text('untrusted')
        with self.assertRaisesRegex(DurableRejected,'UNEXPECTED_JOURNAL_ENTRY'):
            self.session()
        (self.path/'notes.txt').unlink()
        p=_file_path(self.path,1)
        with p.open('ab') as f:f.write(b'\x98\x06\x01')
        with self.assertRaisesRegex(DurableRejected,'NON_CANONICAL_OR_UNKNOWN'):
            self.session()

    def test_symlink_root_and_weak_key_rejected(self):
        link=Path(self.temp.name)/'link'
        link.symlink_to(self.path)
        with self.assertRaisesRegex(DurableRejected,'UNSAFE_JOURNAL_DIRECTORY'):
            P2YDurableSession(link,host_secret=KEY,authority=self.host)
        with self.assertRaisesRegex(DurableRejected,'MISSING_HOST_KEY'):
            self.session(b'short')

    def test_genesis_invalid_epoch(self):
        with self.assertRaises(ValueError):genesis(self.chat,self.vol,0)
        with self.assertRaises(ValueError):genesis(self.chat,self.vol,-1)

if __name__=='__main__':unittest.main()

class P2YAdditionalTests(unittest.TestCase):
    setUp = P2YTests.setUp
    session = P2YTests.session
    def test_incomplete_temp_write_requires_operator_resolution(self):
        self.session()
        (self.path/'.tmp-crash').write_bytes(b'partial')
        with self.assertRaisesRegex(DurableRejected,'INCOMPLETE_RECORD_WRITE'):
            self.session()

    def test_world_readable_file_is_not_recovered(self):
        self.session().advance(request())
        p=_file_path(self.path,1)
        p.chmod(0o644)
        with self.assertRaisesRegex(DurableRejected,'UNSAFE_JOURNAL_FILE'):
            self.session()

    def test_world_readable_directory_is_not_used(self):
        self.session()
        self.path.chmod(0o755)
        with self.assertRaisesRegex(DurableRejected,'UNSAFE_JOURNAL_DIRECTORY'):
            self.session()
        self.path.chmod(0o700)
