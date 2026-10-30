"""C06 P5 durable crash-gap fencing on synthetic Lu ANSF source mutations."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from cognitum.ansf_host_policy_reference import DurableAnsfPolicy, HostPolicyError, ReferenceAnsfGateway, SyntheticPrincipal
from cognitum.memory_host_gate import dispatch_host_fenced
from cognitum.proto import memory_pb2 as pb
from test_c06_ansf_reference import fresh_db, entry, query


class SourceRecoveryGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'policy.db'
        self.policy = DurableAnsfPolicy(self.path)
        self.addCleanup(lambda: self.policy.close())
        self.db = fresh_db()
        self.addCleanup(self.db.close)
        self.owner = SyntheticPrincipal('alice', 'ownerA')
        self.policy.enroll(self.owner, 'sa')
        entry(self.db, 'sa', 'nebula initial')
        self.outputs = []
        self.host = ReferenceAnsfGateway(self.policy, self.db, self.owner, 'sa', sink=self.outputs.append)

    def search(self):
        return dispatch_host_fenced('ansf_fts', query('nebula'), gateway=self.host)

    def test_dirty_fence_drops_all_evidence_even_if_source_readable(self):
        self.assertEqual(self.search().status, pb.VERIFIED)
        self.assertTrue(pb.RetrievalReply.FromString(self.outputs[-1]).evidence)
        self.policy.begin_source_update(self.owner, 'sa')
        receipt = self.search()
        self.assertEqual(receipt.status, pb.DENIED)
        self.assertFalse(pb.RetrievalReply.FromString(self.outputs[-1]).evidence)

    def test_crash_window_survives_restart_and_recovery_bumps_epoch(self):
        self.assertEqual(self.search().status, pb.VERIFIED)
        old = pb.RetrievalReply.FromString(self.outputs[-1]).evidence[0]
        self.policy.begin_source_update(self.owner, 'sa')
        self.policy.close()
        self.policy = DurableAnsfPolicy(self.path)
        self.host = ReferenceAnsfGateway(self.policy, self.db, self.owner, 'sa', sink=self.outputs.append)
        self.assertEqual(self.search().status, pb.DENIED)
        self.policy.finish_source_update(self.owner, 'sa')
        self.assertEqual(self.search().status, pb.VERIFIED)
        new = pb.RetrievalReply.FromString(self.outputs[-1]).evidence[0]
        self.assertNotEqual(old.snapshot_id, new.snapshot_id)

    def test_finish_without_begin_fails_closed(self):
        with self.assertRaises(HostPolicyError):
            self.policy.finish_source_update(self.owner, 'sa')

    def test_cross_owner_cannot_open_or_clear_fence(self):
        other = SyntheticPrincipal('bob', 'ownerB')
        with self.assertRaises(HostPolicyError):
            self.policy.begin_source_update(other, 'sa')
        self.policy.begin_source_update(self.owner, 'sa')
        with self.assertRaises(HostPolicyError):
            self.policy.finish_source_update(other, 'sa')
        self.assertEqual(self.search().status, pb.DENIED)

    def test_double_begin_requires_reconciliation(self):
        self.policy.begin_source_update(self.owner, 'sa')
        with self.assertRaises(HostPolicyError):
            self.policy.begin_source_update(self.owner, 'sa')

    def test_dirty_fence_blocks_concurrent_lease(self):
        self.policy.begin_source_update(self.owner, 'sa')
        with self.host.acquire() as lease:
            self.assertFalse(lease.context.active)
            self.assertNotEqual(lease.recheck(), pb.VERIFIED)

if __name__ == '__main__':
    unittest.main()
