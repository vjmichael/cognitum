"""C07 P4 adversarial temporal-correction and host-tombstone rebuild regression.

All host authority is injected synthetic test state. No live Lu identity checks.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from cognitum.proto import state_pb2 as pb
from cognitum.state_host_gate import SourceUnavailable
from cognitum.state_journal import StateJournal, ZERO_HASH, JournalUnavailable
from cognitum.state_revision import StateConflict, StateInvalid, StateLedger, canonical_event
from tests.test_c07_state_revision import evt
from tests.test_c07_adversarial_p2 import FakeHostLease, with_source


class DeletionHost(FakeHostLease):
    def __init__(self):
        super().__init__()
        self.approved = set()
        self.fail_delete = False
        self.revoke_during_delete = False
        self.verify_remaining = True

    def prepare_second(self):
        self.allowed.add('chat2')
        self.live['chat2'] = ('4','b'*64)
        self.retained.add(('chat2','4','b'*64))
        self.snapshots['chat2'] = 'snap1'

    def tombstone(self, session='chat1', revision='2', digest='a'*64):
        key = (session,revision,digest)
        self.retained.discard(key)
        self.approved.add(key)

    def confirm_source_deleted(self, scope_id, source):
        if self.revoke_during_delete:
            self.active = False
        key = (source.session_id,source.revision_entry_id,source.content_sha256)
        return (not self.fail_delete and self.active and scope_id == 'proj1'
                and key in self.approved and key not in self.retained)

    def verify_source(self, scope_id, source, require_current):
        return self.verify_remaining and super().verify_source(scope_id, source, require_current)


def corrected(event_id='e2', effective=250, *, at=2000, old='e1', origin=pb.USER_VERIFIED):
    e=evt(event_id, action=pb.TEMPORAL_CORRECT, rev=1, time=at, origin=origin)
    e.effective_at_ms=effective
    e.corrects_event_id=old
    return e


class TemporalP4Tests(unittest.TestCase):
    def test_explicit_backdated_correction_and_replay(self):
        l=StateLedger('proj1'); l.apply(evt()); self.assertTrue(l.apply(corrected()))
        c=l.projection().claims[0]
        self.assertEqual((c.value_text,c.effective_at_ms,c.revision,c.latest_event_id),('draft',250,2,'e2'))
        self.assertEqual(StateLedger.replay('proj1',l.history()).projection(),l.projection())

    def test_ordinary_update_cannot_backdate(self):
        l=StateLedger('proj1'); l.apply(evt(time=1000))
        e=evt('e2',action=pb.CONFIRM,rev=1,time=2000)
        e.effective_at_ms=500
        with self.assertRaises(StateConflict): l.apply(e)
        self.assertEqual(len(l.history()),1)

    def test_missing_predecessor_fails(self):
        l=StateLedger('proj1');l.apply(evt())
        for predecessor in ('','wrong'):
            with self.subTest(predecessor=predecessor):
                with self.assertRaises((StateConflict,StateInvalid)):
                    l.apply(corrected(old=predecessor))
        self.assertEqual(len(l.history()),1)

    def test_record_time_must_not_regress(self):
        l=StateLedger('proj1');l.apply(evt(time=5000))
        with self.assertRaises(StateConflict):l.apply(corrected(at=4000))

    def test_temporal_correction_must_change_effective_time(self):
        l=StateLedger('proj1');l.apply(evt())
        with self.assertRaises(StateConflict):l.apply(corrected(effective=1000))

    def test_temporal_correction_cannot_change_value(self):
        l=StateLedger('proj1');l.apply(evt())
        e=corrected();e.value_text='different'
        with self.assertRaises(StateConflict):l.apply(e)

    def test_model_import_cannot_correct_verified(self):
        for origin in (pb.MODEL_HYPOTHESIS,pb.IMPORT_OBSERVED):
            l=StateLedger('proj1');l.apply(evt())
            with self.assertRaises(StateInvalid):l.apply(corrected(origin=origin))

    def test_host_cannot_demote_user_temporal_record(self):
        l=StateLedger('proj1');l.apply(evt())
        with self.assertRaises(StateInvalid):l.apply(corrected(origin=pb.HOST_OBSERVED))

    def test_host_can_correct_host_observed_record(self):
        l=StateLedger('proj1');l.apply(evt(origin=pb.HOST_OBSERVED))
        self.assertTrue(l.apply(corrected(origin=pb.HOST_OBSERVED)))

    def test_confirmation_preserves_corrected_effective_time(self):
        l=StateLedger('proj1');l.apply(evt());l.apply(corrected())
        e=evt('e3',action=pb.CONFIRM,rev=2,time=3000)
        e.effective_at_ms=250
        l.apply(e)
        self.assertEqual(l.projection().claims[0].effective_at_ms,250)
        self.assertEqual(l.projection().claims[0].latest_event_id,'e3')

    def test_repeated_temporal_correction_requires_latest_exact_event(self):
        l=StateLedger('proj1');l.apply(evt());l.apply(corrected())
        next_event=evt('e3',action=pb.TEMPORAL_CORRECT,rev=2,time=3000)
        next_event.effective_at_ms=100
        next_event.corrects_event_id='e1'
        with self.assertRaises(StateConflict):l.apply(next_event)
        next_event.corrects_event_id='e2'
        l.apply(next_event)
        self.assertEqual(l.projection().claims[0].effective_at_ms,100)

    def test_challenge_does_not_rewrite_temporal_validity(self):
        l=StateLedger('proj1');l.apply(evt());l.apply(corrected())
        l.apply(evt('e3',action=pb.CHALLENGE,rev=2,time=3000))
        view=l.projection().claims[0]
        self.assertEqual((view.status,view.effective_at_ms),(pb.DISPUTED,250))

    def test_correction_cannot_attach_to_terminal_claim(self):
        l=StateLedger('proj1');l.apply(evt())
        l.apply(evt('e2',action=pb.RETRACT,rev=1,time=2000))
        e=evt('e3',action=pb.TEMPORAL_CORRECT,rev=2,time=3000)
        e.corrects_event_id='e2';e.effective_at_ms=500
        with self.assertRaises(StateConflict):l.apply(e)

    def test_non_temporal_cannot_smuggle_corrects_event_id(self):
        e=evt();e.corrects_event_id='e0'
        with self.assertRaises(StateInvalid):StateLedger('proj1').apply(e)

    def test_unknown_proto_fields_still_rejected(self):
        wire=corrected().SerializeToString(deterministic=True)+b'\xf8\x07\x01'
        with self.assertRaises(StateInvalid):canonical_event(wire)


class PruneP4Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'cache.sqlite'
        self.host=DeletionHost()

    def opened(self):
        j=StateJournal(self.path,'proj1');self.addCleanup(j.close);return j

    def multi(self):
        self.host.prepare_second()
        j=self.opened()
        e2=with_source(evt('e2','c2',value='different',time=2000),session='chat2',revision='4',digest='b'*64)
        j.apply_host_batch([evt(),e2],self.host)
        return j

    def view(self,j):
        captured=[];j.publish_host_fenced(self.host,captured.append)
        self.assertEqual(len(captured),1)
        return pb.StateProjection.FromString(captured[0])

    def prune(self,j,sources=None, *,gen=None,head=None):
        if sources is None:sources=[evt().source]
        return j.rebuild_after_host_deletion(sources,self.host,
            expected_generation=j.generation() if gen is None else gen,
            expected_head_sha256=j.head()[1] if head is None else head)

    def test_deleted_claim_removed_survivor_preserved_restart(self):
        j=self.multi(); self.assertEqual(len(self.view(j).conflicts),1)
        self.host.tombstone()
        with self.assertRaises(SourceUnavailable): self.view(j)
        receipt=self.prune(j)
        self.assertEqual((receipt.removed_claims,receipt.removed_events,receipt.retained_events,receipt.generation),
                         (1,1,1,1))
        self.assertEqual([c.claim_id for c in self.view(j).claims],['c2'])
        self.assertFalse(self.view(j).conflicts)
        j.close(); reopened=self.opened()
        self.assertEqual([c.claim_id for c in self.view(reopened).claims],['c2'])
        self.assertEqual(reopened.generation(),1)

    def test_complete_deletion_rebuilds_empty_cache(self):
        j=self.opened();j.apply_host_batch([evt()],self.host)
        self.host.tombstone()
        r=self.prune(j)
        self.assertEqual((r.retained_events,r.head_sha256),(0,ZERO_HASH))
        self.assertEqual(len(self.view(j).claims),0)

    def test_nested_revision_source_removes_whole_claim(self):
        j=self.multi()
        e3=with_source(evt('e3',action=pb.CHALLENGE,rev=1,time=3000),session='chat2',revision='4',digest='b'*64)
        j.apply_host_batch([e3],self.host)
        self.host.tombstone()
        r=self.prune(j)
        self.assertEqual((r.removed_claims,r.removed_events,r.retained_events),(1,2,1))
        self.assertEqual([c.claim_id for c in self.view(j).claims],['c2'])

    def test_unapproved_source_does_not_compact(self):
        j=self.multi();head=j.head()
        self.host.retained.discard(('chat1','2','a'*64))
        with self.assertRaises(SourceUnavailable):self.prune(j)
        self.assertEqual(j.head(),head)

    def test_revoked_host_cannot_compact(self):
        j=self.multi();self.host.tombstone();self.host.active=False
        with self.assertRaises(SourceUnavailable):self.prune(j)
        self.assertEqual(j.generation(),0)

    def test_missing_source_rejected(self):
        j=self.multi()
        source=evt().source;source.revision_entry_id='999'
        with self.assertRaises(StateInvalid):self.prune(j,[source])
        self.assertEqual(j.generation(),0)

    def test_empty_source_batch_rejected(self):
        j=self.multi()
        with self.assertRaises(StateInvalid):self.prune(j,[])

    def test_unchanged_head_rejected_after_rebuild(self):
        j=self.multi();head=j.head()[1];gen=j.generation()
        self.host.tombstone();self.prune(j)
        with self.assertRaises(StateConflict):self.prune(j,gen=gen,head=head)

    def test_reused_deleted_event_id_cannot_reenter(self):
        j=self.multi();self.host.tombstone();self.prune(j)
        self.host.prepare_second()
        reused=with_source(evt('e1','c3',time=3000),session='chat2',revision='4',digest='b'*64)
        with self.assertRaises(StateConflict):j.apply_host_batch([reused],self.host)
        self.assertEqual(j.head()[0],1)

    def test_multi_source_atomic_deletion(self):
        j=self.multi()
        self.host.tombstone()
        self.host.tombstone('chat2','4','b'*64)
        other=with_source(evt('synthetic'),session='chat2',revision='4',digest='b'*64).source
        result=self.prune(j,[evt().source,other])
        self.assertEqual((result.removed_claims,result.removed_events,result.retained_events),(2,2,0))
        self.assertEqual(j.head()[1],ZERO_HASH)
        self.assertEqual(len(self.view(self.opened()).claims),0)

    def test_generation_matters_even_if_head_is_zero(self):
        j=self.opened();j.apply_host_batch([evt()],self.host)
        self.host.tombstone();self.prune(j)
        self.assertEqual(j.head()[1],ZERO_HASH)
        with self.assertRaises(StateConflict):
            j.rebuild_after_host_deletion([evt().source],self.host,
                expected_generation=0,expected_head_sha256=ZERO_HASH)

    def test_successful_followup_event_after_rebuild(self):
        j=self.multi();self.host.tombstone();self.prune(j)
        e3=with_source(evt('e3','c3',time=3000),session='chat2',revision='4',digest='b'*64)
        self.assertEqual(j.apply_host_batch([e3],self.host).applied,1)
        self.assertEqual(j.head()[0],2)

    def test_rebuild_fails_if_surviving_source_stale(self):
        j=self.multi();self.host.tombstone()
        self.host.live['chat2']=('5','b'*64)
        with self.assertRaises(SourceUnavailable):self.prune(j)
        self.assertEqual(j.generation(),0)

    def test_rebuild_fails_if_surviving_source_deleted(self):
        j=self.multi();self.host.tombstone()
        self.host.retained.discard(('chat2','4','b'*64))
        with self.assertRaises(SourceUnavailable):self.prune(j)
        self.assertEqual(j.generation(),0)

    def test_sqlite_fault_rollback_restores_prior_derived_events(self):
        j=self.multi();self.host.tombstone();old=j.head()
        with closing(sqlite3.connect(self.path)) as c,c:
            c.execute("CREATE TRIGGER deny_rebuild BEFORE UPDATE ON c07_rebuild_meta BEGIN SELECT RAISE(ABORT,'fault'); END")
        with self.assertRaises(JournalUnavailable):self.prune(j)
        self.assertEqual(j.head(),old)
        self.assertEqual(j.generation(),0)
        j.close()
        self.assertEqual(self.opened().head(),old)

    def test_revocation_during_confirmation_rolls_back(self):
        j=self.multi();self.host.tombstone();self.host.revoke_during_delete=True
        with self.assertRaises(SourceUnavailable):self.prune(j)
        self.assertEqual(j.head()[0],2)

    def test_deleted_origin_in_history_cannot_publish_before_rebuild(self):
        j=self.multi();self.host.tombstone()
        emitted=[]
        with self.assertRaises(SourceUnavailable):j.publish_host_fenced(self.host,emitted.append)
        self.assertEqual(emitted,[])

    def test_correction_survives_sqlite_restart(self):
        j=self.opened();j.apply_host_batch([evt(),corrected()],self.host)
        self.assertEqual(self.view(j).claims[0].effective_at_ms,250)
        j.close();self.assertEqual(self.view(self.opened()).claims[0].effective_at_ms,250)

    def test_corrupted_rebuild_generation_is_denied(self):
        j=self.multi();j.close()
        with closing(sqlite3.connect(self.path)) as c,c:
            c.execute('PRAGMA ignore_check_constraints=ON')
            c.execute('UPDATE c07_rebuild_meta SET generation=-1')
        with self.assertRaises(JournalUnavailable):self.opened() # SQLite CHECK itself rejects edit

if __name__=='__main__': unittest.main()
