"""C07/P3 durable derived-journal and restart tests (synthetic host ONLY)."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from cognitum.proto import state_pb2 as pb
from cognitum.state_host_gate import SourceUnavailable
from cognitum.state_journal import StateJournal, JournalCorrupt, JournalUnavailable, ZERO_HASH
from cognitum.state_revision import StateConflict, StateInvalid
from tests.test_c07_state_revision import evt
from tests.test_c07_adversarial_p2 import FakeHostLease, with_source


class JournalP3Tests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'derived.sqlite'
        self.host = FakeHostLease()

    def opened(self):
        j=StateJournal(self.path,'proj1')
        self.addCleanup(j.close)
        return j

    def projection(self, j):
        captured=[]
        j.publish_host_fenced(self.host,captured.append)
        self.assertEqual(len(captured),1)
        return pb.StateProjection.FromString(captured[0])

    def test_restart_replays_verbatim_projection_and_hash(self):
        j=self.opened()
        first=j.apply_host_batch([evt()],self.host)
        second=j.apply_host_batch([evt('e2',action=pb.CONFIRM,rev=1,time=2000)],self.host)
        self.assertEqual((first.applied,first.sequence),(1,1))
        self.assertEqual((second.applied,second.sequence),(1,2))
        raw=self.projection(j).SerializeToString(deterministic=True)
        j.close()
        reopened=self.opened()
        self.assertEqual(raw,self.projection(reopened).SerializeToString(deterministic=True))
        self.assertEqual(reopened.head(),(2,second.head_sha256))

    def test_replay_idempotence_and_no_duplicate_row(self):
        j=self.opened()
        j.apply_host_batch([evt()],self.host)
        receipt=j.apply_host_batch([evt()],self.host)
        self.assertEqual((receipt.applied,receipt.sequence),(0,1))
        with closing(sqlite3.connect(self.path)) as connection, connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM c07_events').fetchone()[0],1)

    def test_failed_cas_entire_batch_rolls_back(self):
        j=self.opened()
        good=evt()
        bad=evt('e2',action=pb.SUPERSEDE,rev=99,value='wrong',time=2000)
        with self.assertRaises(StateConflict):
            j.apply_host_batch([good,bad],self.host)
        self.assertEqual(j.head(),(0,ZERO_HASH))
        self.assertEqual(len(self.projection(j).claims),0)

    def test_restart_rejects_changed_identity_scope(self):
        self.opened().apply_host_batch([evt()],self.host)
        with self.assertRaises(JournalCorrupt):
            StateJournal(self.path,'different-scope')

    def test_cross_connection_conflicting_cas_fails(self):
        a=self.opened(); b=self.opened()
        a.apply_host_batch([evt()],self.host)
        self.assertEqual(a.apply_host_batch([evt('e2',action=pb.SUPERSEDE,
                                                rev=1,value='final',time=2000)],self.host).applied,1)
        with self.assertRaises(StateConflict):
            b.apply_host_batch([evt('e3',action=pb.SUPERSEDE,
                                    rev=1,value='stale',time=2000)],self.host)
        self.assertEqual(self.projection(b).claims[0].value_text,'final')

    def test_parallel_connections_one_wins(self):
        self.opened().apply_host_batch([evt()],self.host)
        gate=threading.Barrier(3)
        def update(num):
            journal=StateJournal(self.path,'proj1')
            try:
                gate.wait(timeout=6)
                journal.apply_host_batch([evt(f'e{num}',action=pb.SUPERSEDE,rev=1,
                                                 value=f'value{num}',time=2000)],self.host)
                return 'ok'
            except StateConflict:
                return 'stale'
            finally:
                journal.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            x=pool.submit(update,2); y=pool.submit(update,3)
            gate.wait(timeout=6)
            self.assertCountEqual([x.result(timeout=12),y.result(timeout=12)], ['ok','stale'])
        self.assertEqual(self.opened().head()[0],2)

    def test_disallowed_source_atomic_rollback(self):
        j=self.opened()
        bad=with_source(evt('e2','c2'),session='other')
        with self.assertRaises(SourceUnavailable):
            j.apply_host_batch([evt(),bad],self.host)
        self.assertEqual(j.head()[0],0)

    def test_revoked_after_commit_blocks_restart_publication(self):
        j=self.opened(); j.apply_host_batch([evt()],self.host); j.close()
        self.host.active=False
        emitted=[]
        with self.assertRaises(SourceUnavailable):
            self.opened().publish_host_fenced(self.host,emitted.append)
        self.assertEqual(emitted,[])

    def test_deleted_source_blocks_restart_publication(self):
        self.opened().apply_host_batch([evt()],self.host)
        self.host.retained.clear()
        emitted=[]
        with self.assertRaises(SourceUnavailable):
            self.opened().publish_host_fenced(self.host,emitted.append)
        self.assertFalse(emitted)

    def test_changed_snapshot_blocks_restart_publication(self):
        self.opened().apply_host_batch([evt()],self.host)
        self.host.snapshots['chat1']='new'
        with self.assertRaises(SourceUnavailable):
            self.projection(self.opened())

    def test_new_edition_preserves_historical_source(self):
        j=self.opened()
        j.apply_host_batch([evt()],self.host)
        second=with_source(evt('e2',action=pb.SUPERSEDE,rev=1,
                               value='approved',time=2000),revision='3',digest='b'*64)
        self.host.live['chat1']=('3','b'*64)
        self.host.retained.add(('chat1','3','b'*64))
        j.apply_host_batch([second],self.host)
        self.assertEqual(self.projection(self.opened()).claims[0].value_text,'approved')
        self.host.retained.remove(('chat1','2','a'*64))
        with self.assertRaises(SourceUnavailable): self.projection(self.opened())

    def test_deleted_challenge_source_also_blocks(self):
        j=self.opened(); j.apply_host_batch([evt()],self.host)
        challenge=with_source(evt('e2',action=pb.CHALLENGE,rev=1,time=2000),
                              revision='3',digest='b'*64)
        self.host.live['chat1']=('3','b'*64)
        self.host.retained.add(('chat1','3','b'*64))
        j.apply_host_batch([challenge],self.host)
        self.host.retained.remove(('chat1','3','b'*64))
        with self.assertRaises(SourceUnavailable): self.projection(self.opened())

    def test_event_frame_tamper_detected_at_restart(self):
        j=self.opened(); j.apply_host_batch([evt()],self.host); j.close()
        with closing(sqlite3.connect(self.path)) as c, c:
            c.execute('DROP TRIGGER c07_events_no_update')
            c.execute("UPDATE c07_events SET frame=x'0801' WHERE seq=1")
        with self.assertRaises(JournalCorrupt): StateJournal(self.path,'proj1')

    def test_gap_and_head_mismatch_detected(self):
        j=self.opened(); j.apply_host_batch([evt()],self.host); j.close()
        with closing(sqlite3.connect(self.path)) as c, c:
            c.execute('UPDATE c07_meta SET last_seq=44 WHERE singleton=1')
        with self.assertRaises(JournalCorrupt): StateJournal(self.path,'proj1')

    def test_transaction_rollback_when_sqlite_rejects_insert(self):
        j=self.opened()
        with closing(sqlite3.connect(self.path)) as c, c:
            c.execute('CREATE TRIGGER fail_events BEFORE INSERT ON c07_events BEGIN SELECT RAISE(ABORT,\'disk simulation\'); END;')
        with self.assertRaises(JournalUnavailable): j.apply_host_batch([evt()],self.host)
        self.assertEqual(j.head(),(0,ZERO_HASH))
        j.close()
        self.assertEqual(self.opened().head(),(0,ZERO_HASH))

    def test_uncommitted_sqlite_write_not_replayed(self):
        j=self.opened(); j.apply_host_batch([evt()],self.host); j.close()
        c=sqlite3.connect(self.path)
        c.execute('BEGIN IMMEDIATE')
        c.execute('UPDATE c07_meta SET last_seq=99 WHERE singleton=1')
        c.close()  # simulated interruption, uncommitted transaction rolled back
        self.assertEqual(self.opened().head()[0],1)

    def test_publication_blocked_on_corruption_without_delivery(self):
        j=self.opened(); j.apply_host_batch([evt()],self.host)
        with closing(sqlite3.connect(self.path)) as c, c:
            c.execute("UPDATE c07_meta SET head_hash='f' || substr(head_hash,2)")
        delivered=[]
        with self.assertRaises(JournalCorrupt):
            j.publish_host_fenced(self.host,delivered.append)
        self.assertEqual(delivered,[])

    def test_reentrant_callback_cannot_mutate_journal(self):
        j=self.opened(); j.apply_host_batch([evt()],self.host)
        def callback(_data):
            j.apply_host_batch([evt('e3','c3')],self.host)
        with self.assertRaises(JournalUnavailable):
            j.publish_host_fenced(self.host,callback)
        self.assertEqual(j.head()[0],1)

    def test_revocation_waits_for_host_lease_publishing(self):
        j=self.opened(); j.apply_host_batch([evt()],self.host)
        # The lock is supplied by Lu; this test makes that dependency visible.
        host_lock=threading.Lock(); entered=threading.Event()
        release=threading.Event(); revoked=threading.Event(); emitted=[]
        def publish():
            with host_lock:
                j.publish_host_fenced(self.host,lambda x:(entered.set(),release.wait(timeout=5),emitted.append(x)))
        def revoke():
            with host_lock:
                self.host.active=False
                revoked.set()
        with ThreadPoolExecutor(2) as pool:
            a=pool.submit(publish)
            self.assertTrue(entered.wait(timeout=5))
            b=pool.submit(revoke)
            self.assertFalse(revoked.wait(timeout=0.1))
            release.set(); a.result(timeout=5); b.result(timeout=5)
        self.assertEqual(len(emitted),1)
        with self.assertRaises(SourceUnavailable): self.projection(j)

    def test_host_reconciliation_metadata_without_claim_text(self):
        j=self.opened(); j.apply_host_batch([evt()],self.host)
        info=j.reconcile_host_fenced(self.host)
        self.assertEqual(info['event_count'],1)
        self.assertEqual(len(info['derived_projection_sha256']),64)
        self.assertNotIn('draft',str(info))
        self.host.active=False
        with self.assertRaises(SourceUnavailable): j.reconcile_host_fenced(self.host)

    def test_meta_update_failure_rolls_back_event_insertion(self):
        j=self.opened()
        with closing(sqlite3.connect(self.path)) as c, c:
            c.execute("CREATE TRIGGER deny_head BEFORE UPDATE ON c07_meta BEGIN SELECT RAISE(ABORT,'fail'); END;")
        with self.assertRaises(JournalUnavailable): j.apply_host_batch([evt()],self.host)
        self.assertEqual(j.head(),(0,ZERO_HASH))
        with closing(sqlite3.connect(self.path)) as c, c:
            self.assertEqual(c.execute('SELECT count(*) FROM c07_events').fetchone()[0],0)

    def test_malformed_event_chain_sha_fails_closed(self):
        j=self.opened(); j.apply_host_batch([evt()],self.host); j.close()
        with closing(sqlite3.connect(self.path)) as c,c:
            c.execute("UPDATE c07_meta SET head_hash='BAD' WHERE singleton=1")
        with self.assertRaises(JournalCorrupt): StateJournal(self.path,'proj1')

    def test_empty_scope_and_symlink_rejected(self):
        with self.assertRaises(StateInvalid): StateJournal(self.path,'')
        anchor=Path(self.directory.name)/'anchor'
        anchor.write_text('x')
        link=Path(self.directory.name)/'link'
        link.symlink_to(anchor)
        with self.assertRaises(JournalUnavailable): StateJournal(link,'proj1')

    def test_correct_projection_conflicts_across_restart(self):
        j=self.opened()
        j.apply_host_batch([evt(),evt('e2','c2',value='other',time=2000)],self.host)
        self.assertEqual(len(self.projection(j).conflicts),1)
        self.assertEqual(len(self.projection(self.opened()).conflicts),1)

    def test_corrupt_unknown_field_even_with_reforged_hash_fails(self):
        from cognitum.state_journal import _digest
        j=self.opened(); j.apply_host_batch([evt()],self.host); j.close()
        frame=evt().SerializeToString(deterministic=True)+b'\xf8\x07\x01'
        changed=_digest(ZERO_HASH,1,frame)
        with closing(sqlite3.connect(self.path)) as c, c:
            c.execute('DROP TRIGGER c07_events_no_update')
            c.execute('UPDATE c07_events SET frame=?,event_hash=? WHERE seq=1',(frame,changed))
            c.execute('UPDATE c07_meta SET head_hash=? WHERE singleton=1',(changed,))
        with self.assertRaises(JournalCorrupt): StateJournal(self.path,'proj1')


if __name__ == '__main__': unittest.main()
