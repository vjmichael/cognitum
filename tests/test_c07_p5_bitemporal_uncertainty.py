"""C07/P5 bitemporal queries and explicit source-backed uncertainty.

Synthetic host lease only. Historical output is never a current-memory grant.
"""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from cognitum.proto import state_pb2 as pb
from cognitum.state_revision import StateLedger, StateInvalid, StateConflict
from cognitum.state_temporal import canonical_as_of_query, project_as_of
from cognitum.state_journal import StateJournal
from cognitum.state_host_gate import SourceUnavailable
from tests.test_c07_state_revision import evt
from tests.test_c07_adversarial_p2 import FakeHostLease, with_source


def query(valid=1500, known=5000, *, include=False, scope='proj1'):
    return pb.AsOfQuery(schema_version=1, scope_id=scope, valid_at_ms=valid,
                        known_at_ms=known, include_inactive=include)


def corrected(event_id='e3', rev=2, time=3500, start=500, predecessor='e2'):
    value = evt(event_id, rev=rev, action=pb.TEMPORAL_CORRECT, time=time, value='final')
    value.effective_at_ms = start
    value.corrects_event_id = predecessor
    return value


class BitemporalP5Tests(unittest.TestCase):
    def setUp(self):
        self.ledger = StateLedger('proj1')

    def at(self, valid=1500, known=5000, include=False):
        return project_as_of(self.ledger, query(valid,known,include=include))

    def test_first_assertion_before_and_at_effective_start(self):
        self.ledger.apply(evt(time=1000))
        self.assertFalse(self.at(999).claims)
        self.assertEqual(self.at(1000).claims[0].value_text,'draft')
        self.assertTrue(self.at(1000).historical_only)

    def test_valid_at_and_known_at_independent(self):
        e=evt(time=3000); e.effective_at_ms=1000
        self.ledger.apply(e)
        self.assertFalse(self.at(1200,known=2999).claims)
        self.assertEqual(self.at(1200,known=3000).claims[0].value_text,'draft')

    def test_superseded_value_still_answerable_in_past(self):
        self.ledger.apply(evt())
        self.ledger.apply(evt('e2',rev=1,action=pb.SUPERSEDE,value='final',time=2000))
        self.assertEqual(self.at(1500).claims[0].value_text,'draft')
        self.assertEqual(self.at(2000).claims[0].value_text,'final')
        self.assertEqual(self.at(2500,known=1999).claims[0].value_text,'draft')

    def test_bounded_interval_closed_exclusive_and_gap(self):
        e=evt();e.valid_until_ms=1500;self.ledger.apply(e)
        self.ledger.apply(evt('e2',rev=1,action=pb.SUPERSEDE,value='final',time=2000))
        self.assertEqual(self.at(1499).claims[0].value_text,'draft')
        self.assertFalse(self.at(1500).claims)
        self.assertEqual(self.at(1500,include=True).claims[0].status,pb.EXPIRED)
        self.assertEqual(self.at(2000).claims[0].value_text,'final')

    def test_uncertainty_is_explicit_and_persists_through_challenge(self):
        e=evt();e.uncertainty_kind=pb.CONDITIONAL;e.uncertainty_note='Subject to signed approval.'
        self.ledger.apply(e)
        challenge=evt('e2',rev=1,action=pb.CHALLENGE,time=2000,origin=pb.MODEL_HYPOTHESIS)
        self.ledger.apply(challenge)
        current=self.ledger.projection().claims[0]
        self.assertEqual((current.uncertainty_kind,current.uncertainty_note),
                         (pb.CONDITIONAL,'Subject to signed approval.'))
        self.assertEqual(self.at(1500).claims[0].status,pb.ACTIVE)
        self.assertEqual(self.at(2000).claims[0].status,pb.DISPUTED)
        self.assertEqual(self.at(2000).claims[0].origin,pb.USER_VERIFIED)

    def test_unknown_qualifier_never_means_certain(self):
        self.ledger.apply(evt())
        view=self.at().claims[0]
        self.assertEqual(view.uncertainty_kind,pb.UNCERTAINTY_UNSPECIFIED)
        self.assertEqual(view.uncertainty_note,'')

    def test_supersede_changes_uncertainty_only_with_new_assertion(self):
        e=evt();e.uncertainty_kind=pb.OPEN_QUESTION;e.uncertainty_note='Awaiting answer.'
        self.ledger.apply(e)
        newer=evt('e2',rev=1,action=pb.SUPERSEDE,value='final',time=2000)
        newer.uncertainty_kind=pb.EXPLICITLY_UNCERTAIN
        newer.uncertainty_note='Tentative, source unverified elsewhere.'
        self.ledger.apply(newer)
        self.assertEqual(self.at(1500).claims[0].uncertainty_kind,pb.OPEN_QUESTION)
        self.assertEqual(self.at(2500).claims[0].uncertainty_kind,pb.EXPLICITLY_UNCERTAIN)

    def test_explicit_uncertainty_required_note_and_valid_action(self):
        cases=[lambda e:setattr(e,'uncertainty_kind',pb.EXPLICITLY_UNCERTAIN),
               lambda e:setattr(e,'uncertainty_note','unspecified note'),
               lambda e:setattr(e,'uncertainty_kind',999),
               lambda e:setattr(e,'valid_until_ms',999),
               lambda e:setattr(e,'valid_until_ms',-1),
               lambda e:setattr(e,'uncertainty_note','x'*513)]
        for mutate in cases:
            e=evt();mutate(e)
            with self.subTest(serialized=e.SerializeToString()[:50]):
                with self.assertRaises(StateInvalid):StateLedger('proj1').apply(e)

    def test_markers_cannot_smuggle_uncertainty_or_interval(self):
        self.ledger.apply(evt())
        for field,value in [('uncertainty_kind',pb.OPEN_QUESTION),
                            ('uncertainty_note','x'),('valid_until_ms',3000)]:
            e=evt('e2',rev=1,action=pb.CHALLENGE,time=2000)
            setattr(e,field,value)
            with self.subTest(field=field), self.assertRaises(StateInvalid):self.ledger.apply(e)

    def test_temporal_correction_backdate_changes_known_history_only(self):
        self.ledger.apply(evt())
        self.ledger.apply(evt('e2',rev=1,action=pb.SUPERSEDE,value='final',time=2000))
        self.ledger.apply(corrected())
        self.assertEqual(self.at(800,known=3499).claims.__len__(),0)
        self.assertEqual(self.at(800,known=3500).claims[0].value_text,'final')
        self.assertEqual(self.at(800,known=3500).claims[0].effective_at_ms,500)
        self.assertEqual(self.at(1200,known=3500).claims[0].value_text,'final')
        self.assertEqual(self.at(1200,known=3499).claims[0].value_text,'draft')

    def test_temporal_correction_can_adjust_end_without_rewinding_start(self):
        e=evt(); e.valid_until_ms=3000;self.ledger.apply(e)
        correction=evt('e2',rev=1,action=pb.TEMPORAL_CORRECT,time=2000)
        correction.corrects_event_id='e1'
        correction.effective_at_ms=1000
        correction.valid_until_ms=1500
        self.ledger.apply(correction)
        self.assertFalse(self.at(1700).claims)
        self.assertEqual(self.at(1499).claims[0].valid_until_ms,1500)

    def test_correction_cannot_create_empty_interval(self):
        e=evt();e.valid_until_ms=1200;self.ledger.apply(e)
        correction=evt('e2',rev=1,action=pb.TEMPORAL_CORRECT,time=3000)
        correction.corrects_event_id='e1';correction.effective_at_ms=1300
        with self.assertRaises(StateConflict):self.ledger.apply(correction)

    def test_terminal_retraction_applies_from_effective_time(self):
        self.ledger.apply(evt())
        self.ledger.apply(evt('e2',rev=1,action=pb.RETRACT,time=2000))
        self.assertEqual(self.at(1500).claims[0].status,pb.ACTIVE)
        self.assertEqual(len(self.at(2000).claims),0)
        self.assertEqual(self.at(2500,include=True).claims[0].status,pb.RETRACTED)

    def test_two_conflicting_claims_only_overlap_at_query_time(self):
        e1=evt();e1.valid_until_ms=1500;self.ledger.apply(e1)
        self.ledger.apply(evt('e2',claim_id='c2',value='other',time=1400))
        self.assertEqual(len(self.at(1450).conflicts),1)
        self.assertEqual(len(self.at(1500).conflicts),0)
        self.assertEqual(len(self.at(1350).conflicts),0)

    def test_historical_replay_equivalent(self):
        self.ledger.apply(evt())
        self.ledger.apply(evt('e2',rev=1,action=pb.CHALLENGE,time=2000))
        reread=StateLedger.replay('proj1',self.ledger.history())
        for t in (900,1000,1200,2000,3000):
            self.assertEqual(project_as_of(reread,query(t)).SerializeToString(),
                             self.at(t).SerializeToString())

    def test_query_rejects_unsafe_frames(self):
        q=query(); encoded=q.SerializeToString(deterministic=True)
        cases=[b'',b'bad',encoded+b'\xf8\x07\x01',encoded+b'\x08\x01',
               query(valid=0).SerializeToString(),query(known=0).SerializeToString(),
               query(scope='?').SerializeToString()]
        for frame in cases:
            with self.subTest(frame=frame[:20]), self.assertRaises(StateInvalid):
                canonical_as_of_query(frame)

    def test_verified_confirmation_preserves_explicit_uncertainty(self):
        first=evt(origin=pb.MODEL_HYPOTHESIS)
        first.uncertainty_kind=pb.OPEN_QUESTION
        first.uncertainty_note='User has not yet confirmed.'
        self.ledger.apply(first)
        self.ledger.apply(evt('e2',rev=1,action=pb.CONFIRM,time=2000,origin=pb.USER_VERIFIED))
        view=self.at(2500).claims[0]
        self.assertEqual(view.origin,pb.USER_VERIFIED)
        self.assertEqual(view.uncertainty_kind,pb.OPEN_QUESTION)
        self.assertEqual(view.uncertainty_note,'User has not yet confirmed.')

    def test_second_claim_known_later_does_not_create_early_conflict(self):
        self.ledger.apply(evt())
        other=evt('e2',claim_id='c2',value='other',time=3000)
        other.effective_at_ms=1100
        self.ledger.apply(other)
        self.assertFalse(self.at(1500,known=2999).conflicts)
        self.assertEqual(len(self.at(1500,known=3000).conflicts),1)

    def test_temporal_correction_does_not_demote_uncertainty(self):
        first=evt();first.uncertainty_kind=pb.CONDITIONAL
        first.uncertainty_note='Subject to legal review.'
        self.ledger.apply(first)
        correction=evt('e2',rev=1,action=pb.TEMPORAL_CORRECT,time=2000)
        correction.effective_at_ms=800
        correction.corrects_event_id='e1'
        self.ledger.apply(correction)
        assert_view=self.at(900).claims[0]
        self.assertEqual(assert_view.uncertainty_kind,pb.CONDITIONAL)
        self.assertEqual(assert_view.uncertainty_note,'Subject to legal review.')

    def test_scope_mismatch_refused(self):
        self.ledger.apply(evt())
        with self.assertRaises(StateInvalid): project_as_of(self.ledger,query(scope='other'))

    def test_host_only_mode_refuses_unfenced_historical_projection(self):
        ledger=StateLedger('proj1',require_host=True)
        with self.assertRaises(StateInvalid):project_as_of(ledger,query())


class FencedHistoricalP5Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'state.sqlite'
        self.host=FakeHostLease()
        self.journal=StateJournal(self.path,'proj1')
        self.addCleanup(self.journal.close)

    def publish(self,valid=1500,known=5000):
        emitted=[]
        self.journal.publish_host_as_of(query(valid,known),self.host,emitted.append)
        self.assertEqual(len(emitted),1)
        return pb.HistoricalProjection.FromString(emitted[0])

    def test_fenced_as_of_replay_after_restart(self):
        self.journal.apply_host_batch([evt()],self.host)
        self.assertEqual(self.publish().claims[0].value_text,'draft')
        self.journal.close()
        self.journal=StateJournal(self.path,'proj1')
        self.assertTrue(self.publish().historical_only)

    def test_verified_historical_old_revision_does_not_require_current(self):
        self.journal.apply_host_batch([evt()],self.host)
        second=with_source(evt('e2',rev=1,action=pb.SUPERSEDE,value='final',time=2000),revision='3',digest='b'*64)
        self.host.live['chat1']=('3','b'*64)
        self.host.retained.add(('chat1','3','b'*64))
        self.journal.apply_host_batch([second],self.host)
        self.host.verify_calls.clear()  # Exclude admission-time current checks.
        self.assertEqual(self.publish().claims[0].value_text,'draft')
        self.assertIn(('chat1','2',False),self.host.verify_calls)
        self.assertFalse(any(current for _,_,current in self.host.verify_calls if current))
        self.assertEqual(self.publish(2200).claims[0].value_text,'final')

    def test_subsequent_delete_blocks_even_pre_deletion_cutoff(self):
        self.journal.apply_host_batch([evt()],self.host)
        self.host.retained.clear()
        emitted=[]
        with self.assertRaises(SourceUnavailable):
            self.journal.publish_host_as_of(query(1500,1500),self.host,emitted.append)
        self.assertFalse(emitted)

    def test_revoked_host_cannot_retrieve_historical(self):
        self.journal.apply_host_batch([evt()],self.host)
        self.host.active=False
        with self.assertRaises(SourceUnavailable):self.publish()

    def test_source_snapshot_changed_blocks(self):
        self.journal.apply_host_batch([evt()],self.host)
        self.host.snapshots['chat1']='other'
        with self.assertRaises(SourceUnavailable):self.publish()

    def test_callback_cannot_mutate_journal(self):
        self.journal.apply_host_batch([evt()],self.host)
        with self.assertRaises(Exception):
            self.journal.publish_host_as_of(query(),self.host,
                lambda data:self.journal.apply_host_batch([evt('e2','c2')],self.host))
        self.assertEqual(self.journal.head()[0],1)

    def test_query_known_cutoff_cannot_skip_deleted_later_source(self):
        self.journal.apply_host_batch([evt()],self.host)
        second=with_source(evt('e2',rev=1,action=pb.CHALLENGE,origin=pb.MODEL_HYPOTHESIS,time=2000),revision='3',digest='b'*64)
        self.host.origins.add(pb.MODEL_HYPOTHESIS)
        self.host.live['chat1']=('3','b'*64);self.host.retained.add(('chat1','3','b'*64))
        self.journal.apply_host_batch([second],self.host)
        self.host.retained.discard(('chat1','3','b'*64))
        with self.assertRaises(SourceUnavailable):self.publish(valid=1500,known=1500)

    def test_journal_scope_mismatch_fails_before_output(self):
        self.journal.apply_host_batch([evt()],self.host)
        emitted=[]
        with self.assertRaises(StateInvalid):
            self.journal.publish_host_as_of(query(scope='other'),self.host,emitted.append)
        self.assertFalse(emitted)

    def test_lease_revoked_mid_verification_yields_no_output(self):
        self.journal.apply_host_batch([evt()],self.host)
        original=self.host.verify_source
        def revoke(scope,source,current):
            result=original(scope,source,current)
            self.host.active=False
            return result
        self.host.verify_source=revoke
        emitted=[]
        with self.assertRaises(SourceUnavailable):
            self.journal.publish_host_as_of(query(),self.host,emitted.append)
        self.assertFalse(emitted)

    def test_serialized_restart_keeps_uncertainty_qualifier(self):
        e=evt();e.uncertainty_kind=pb.EXPLICITLY_UNCERTAIN;e.uncertainty_note='Awaiting confirmation.'
        e.valid_until_ms=6000
        self.journal.apply_host_batch([e],self.host)
        self.journal.close();self.journal=StateJournal(self.path,'proj1')
        response=self.publish()
        self.assertEqual((response.claims[0].uncertainty_kind,response.claims[0].valid_until_ms),
                         (pb.EXPLICITLY_UNCERTAIN,6000))


if __name__=='__main__':unittest.main()
