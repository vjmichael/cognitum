"""C06/P4 persistent policy fixture, not Lu authentication or physical erasure."""
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path

from cognitum.ansf_host_policy_reference import (
    DurableAnsfPolicy, HostPolicyError, ReferenceAnsfGateway, SyntheticPrincipal,
)
from cognitum.memory_evidence import encode_frame
from cognitum.memory_host_gate import dispatch_host_fenced
from cognitum.proto import memory_pb2 as pb
from test_c06_ansf_reference import fresh_db, entry, edit, query


class DurableHostConformance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'lu_policy_test.sqlite'
        self.db = fresh_db()
        self.addCleanup(self.db.close)
        self.policy = DurableAnsfPolicy(self.path)
        self.addCleanup(lambda: self.policy.close())
        self.alice = SyntheticPrincipal('alice', 'ownerA')
        self.bob = SyntheticPrincipal('bob', 'ownerB')
        self.policy.enroll(self.alice, 'sa')
        self.policy.enroll(self.bob, 'sb')
        self.out = []
        self.host = ReferenceAnsfGateway(self.policy, self.db, self.alice, 'sa', sink=self.out.append)

    def search(self, text='nebula', *, host=None, historical=False):
        return dispatch_host_fenced('ansf_fts', query(text, historical=historical),
                                    gateway=host or self.host)

    def latest(self):
        return pb.RetrievalReply.FromString(self.out[-1])

    def lookup(self, evidence):
        lookup = pb.CitationLookup(schema_version=1, request_id='lookup',
            citation_handle=evidence.citation_handle, source=evidence.source,
            snapshot_id=evidence.snapshot_id, content_sha256=evidence.content_sha256,
            start_utf8_byte=evidence.start_utf8_byte,
            length_utf8_byte=len(evidence.excerpt.encode()))
        return dispatch_host_fenced('ansf_citation', encode_frame(lookup), gateway=self.host)

    def test_authorized_read_and_citation_roundtrip(self):
        root = entry(self.db, 'sa', 'nebula secret')
        r = self.search()
        self.assertEqual((r.status, r.published), (pb.VERIFIED, True))
        e = self.latest().evidence[0]
        self.assertEqual(e.source.entry_id, str(root))
        self.assertEqual(self.lookup(e).status, pb.VERIFIED)
        self.assertIn(b'nebula secret', self.out[-1])
        self.assertEqual(self.db.execute('PRAGMA query_only').fetchone()[0], 0)

    def test_owner_and_workspace_identity_cannot_be_crossed(self):
        entry(self.db, 'sa', 'nebula owner secret')
        wrong = ReferenceAnsfGateway(self.policy, self.db, self.bob, 'sa', sink=self.out.append)
        result = self.search(host=wrong)
        self.assertEqual(result.status, pb.DENIED)
        self.assertFalse(self.latest().evidence)
        self.assertNotIn(b'owner secret', self.out[-1])
        # The underlying ANSF workspace must match the durable host enrollment.
        self.db.execute("UPDATE ansf_sessions SET workspace_id='tampered' WHERE id='sa'")
        self.assertEqual(self.search().status, pb.DENIED)
        self.assertFalse(self.latest().evidence)

    def test_no_silent_rebinding_or_policy_reenabling(self):
        self.assertFalse(self.policy.enroll(self.alice, 'sa'))
        with self.assertRaises(HostPolicyError):
            self.policy.enroll(self.bob, 'sa')
        with self.assertRaises(HostPolicyError):
            self.policy.enroll(self.alice, 'sa', allow_historical=True)
        self.assertTrue(self.policy.revoke(self.alice, 'sa'))
        self.assertFalse(self.policy.revoke(self.alice, 'sa'))
        self.assertEqual(self.search().status, pb.DENIED)
        with self.assertRaises(sqlite3.DatabaseError):
            self.policy._conn.execute("UPDATE session_policy SET enabled=1 WHERE session_id='sa'")
        with self.assertRaises(sqlite3.DatabaseError):
            self.policy._conn.execute("DELETE FROM session_policy WHERE session_id='sa'")

    def test_tombstone_root_persists_across_restart_and_blocks_history(self):
        root = entry(self.db, 'sa', 'nebula old secret')
        current = edit(self.db, 'sa', root, 'nebula new secret')
        self.assertEqual(self.search().status, pb.VERIFIED)
        e = self.latest().evidence[0]
        self.assertEqual(e.source.revision_id, str(current))
        self.assertTrue(self.policy.tombstone(self.alice, 'sa', root, self.db))
        self.assertFalse(self.policy.tombstone(self.alice, 'sa', root, self.db))
        self.assertEqual(self.search().status, pb.VERIFIED)
        self.assertEqual(len(self.latest().evidence), 0)
        self.assertNotIn(b'secret', self.out[-1])
        # A saved citation is a stale *locator*, not a grant.
        self.assertIn(self.lookup(e).status, (pb.STALE, pb.DELETED))
        self.assertNotIn(b'secret', self.out[-1])
        self.policy.close()
        self.policy = DurableAnsfPolicy(self.path)
        self.host = ReferenceAnsfGateway(self.policy, self.db, self.alice, 'sa', sink=self.out.append)
        self.assertEqual(self.search().status, pb.VERIFIED)
        self.assertFalse(self.latest().evidence)
        self.assertEqual(self.policy._tombstones('sa'), frozenset({root}))
        with self.assertRaises(sqlite3.DatabaseError):
            self.policy._conn.execute('DELETE FROM logical_tombstones')
        # Explicitly NOT erased: the original bytes remain in ANSF storage.
        self.assertIn('old secret', self.db.execute('SELECT content FROM ansf_entries WHERE id=?', (root,)).fetchone()[0])

    def test_tombstone_invalid_root_and_cross_session_refused(self):
        root = entry(self.db, 'sa', 'nebula original')
        revision = edit(self.db, 'sa', root, 'nebula revision')
        for principal, session, ident in [
            (self.alice, 'sa', revision), (self.alice, 'sa', 0),
            (self.alice, 'sa', 2**61), (self.bob, 'sa', root),
            (self.bob, 'sb', root),
        ]:
            with self.subTest(principal=principal, session=session, ident=ident):
                with self.assertRaises(HostPolicyError):
                    self.policy.tombstone(principal, session, ident, self.db)
        self.assertEqual(self.policy._tombstones('sa'), frozenset())

    def test_index_epoch_invalidates_citations_after_host_mutation(self):
        entry(self.db, 'sa', 'nebula remains')
        self.assertEqual(self.search().status, pb.VERIFIED)
        e = self.latest().evidence[0]
        self.policy.advance_index(self.alice, 'sa')
        self.assertEqual(self.lookup(e).status, pb.STALE)
        self.assertEqual(self.search().status, pb.VERIFIED)

    def test_cancellation_never_publishes_evidence(self):
        entry(self.db, 'sa', 'nebula secret')
        self.host.cancel()
        r = self.search()
        self.assertFalse(r.published)
        self.assertEqual(r.status, pb.UNAVAILABLE)
        self.assertFalse(self.out)

    def test_revocation_ack_waits_for_host_held_read_publication(self):
        entry(self.db, 'sa', 'nebula confidential')
        entered = threading.Event()
        release = threading.Event()
        revoked = threading.Event()
        events = []

        def sink(frame):
            entered.set()
            self.assertTrue(release.wait(timeout=3))
            events.append(('published', pb.RetrievalReply.FromString(frame).status))
            self.out.append(frame)

        gateway = ReferenceAnsfGateway(self.policy, self.db, self.alice, 'sa', sink=sink)
        def reader():
            events.append(('read', self.search(host=gateway).status))
        def revoker():
            events.append(('revoke', self.policy.revoke(self.alice, 'sa')))
            revoked.set()
        a = threading.Thread(target=reader)
        b = threading.Thread(target=revoker)
        a.start()
        self.assertTrue(entered.wait(timeout=3))
        b.start()
        self.assertFalse(revoked.wait(timeout=0.06))
        release.set()
        a.join(timeout=3)
        b.join(timeout=3)
        self.assertFalse(a.is_alive())
        self.assertFalse(b.is_alive())
        self.assertEqual([x[0] for x in events], ['published', 'read', 'revoke'])
        self.assertEqual(events[-1], ('revoke', True))
        self.assertEqual(self.search().status, pb.DENIED)
        self.assertNotIn(b'confidential', self.out[-1])

    def test_tombstone_ack_waits_for_read_publication(self):
        root = entry(self.db, 'sa', 'nebula restricted')
        entered = threading.Event()
        release = threading.Event()
        marked = threading.Event()
        sink = lambda frame: (entered.set(), release.wait(3), self.out.append(frame))
        g = ReferenceAnsfGateway(self.policy, self.db, self.alice, 'sa', sink=sink)
        t = threading.Thread(target=lambda: self.search(host=g))
        t.start()
        self.assertTrue(entered.wait(3))
        writer = threading.Thread(target=lambda: (self.policy.tombstone(self.alice, 'sa', root, self.db), marked.set()))
        writer.start()
        self.assertFalse(marked.wait(0.06))
        release.set()
        t.join(3)
        writer.join(3)
        self.assertTrue(marked.is_set())
        self.assertEqual(self.search().status, pb.VERIFIED)
        self.assertFalse(self.latest().evidence)

    def test_independent_sqlite_connection_cannot_commit_mutation_during_read(self):
        entry(self.db, 'sa', 'nebula restricted')
        other = sqlite3.connect(self.path, isolation_level=None, timeout=0.06)
        self.addCleanup(other.close)
        with self.host.acquire() as held:
            self.assertTrue(held.context.active)
            with self.assertRaises(sqlite3.OperationalError) as caught:
                other.execute("UPDATE session_policy SET enabled=0, "
                              "authorization_epoch=authorization_epoch+1 WHERE session_id='sa'")
            self.assertIn('locked', str(caught.exception))
            with self.assertRaises(HostPolicyError):
                self.policy.revoke(self.alice, 'sa')
            with self.assertRaises(HostPolicyError):
                self.policy.advance_index(self.alice, 'sa')
            with self.assertRaises(HostPolicyError):
                with self.host.acquire():
                    pass
        self.assertEqual(self.search().status, pb.VERIFIED)
        other.execute("UPDATE session_policy SET enabled=0, "
                      "authorization_epoch=authorization_epoch+1 WHERE session_id='sa'")
        self.assertEqual(self.search().status, pb.DENIED)

    def test_reentrant_publish_cannot_acknowledge_revocation_that_rolls_back(self):
        entry(self.db, 'sa', 'nebula secret')
        g = ReferenceAnsfGateway(self.policy, self.db, self.alice, 'sa',
                                 sink=lambda _: self.policy.revoke(self.alice, 'sa'))
        result = self.search(host=g)
        self.assertEqual((result.status, result.published), (pb.UNAVAILABLE, False))
        self.assertFalse(self.out)
        # The attempted reentrant mutation must NOT claim it committed.
        self.assertEqual(self.search().status, pb.VERIFIED)

    def test_revocation_survives_policy_database_restart(self):
        entry(self.db, 'sa', 'nebula never after revoke')
        self.assertEqual(self.search().status, pb.VERIFIED)
        self.assertTrue(self.policy.revoke(self.alice, 'sa'))
        self.policy.close()
        self.policy = DurableAnsfPolicy(self.path)
        self.host = ReferenceAnsfGateway(self.policy, self.db, self.alice, 'sa', sink=self.out.append)
        self.assertEqual(self.search().status, pb.DENIED)
        self.assertFalse(self.latest().evidence)
        self.assertNotIn(b'never after revoke', self.out[-1])
        with self.assertRaises(HostPolicyError):
            self.policy.tombstone(self.alice, 'sa', 1, self.db)

    def test_read_lease_restores_preexisting_sqlite_query_only_setting(self):
        entry(self.db, 'sa', 'nebula immutable')
        self.db.execute('PRAGMA query_only=ON')
        self.assertEqual(self.search().status, pb.VERIFIED)
        self.assertEqual(self.db.execute('PRAGMA query_only').fetchone()[0], 1)
        self.db.execute('PRAGMA query_only=OFF')

    def test_foreign_workspace_cannot_be_tombstoned(self):
        root = entry(self.db, 'sa', 'nebula confidential')
        self.db.execute("UPDATE ansf_sessions SET workspace_id='ownerB' WHERE id='sa'")
        with self.assertRaises(HostPolicyError):
            self.policy.tombstone(self.alice, 'sa', root, self.db)
        self.assertEqual(self.policy._tombstones('sa'), frozenset())

    def test_no_host_file_access_from_model_input(self):
        entry(self.db, 'sa', 'nebula')
        q = query('/etc/passwd OR nebula')
        self.assertEqual(dispatch_host_fenced('ansf_fts', q, gateway=self.host).status, pb.VERIFIED)
        self.assertFalse(self.latest().evidence)
        self.assertNotIn('path', vars(self.host))


if __name__ == '__main__':
    unittest.main()
