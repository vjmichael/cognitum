import unittest
from cognitum.proto import state_pb2 as p
from cognitum.state_revision import StateLedger, StateInvalid, StateConflict, canonical_event


def evt(event_id='e1', claim_id='c1', value='draft', action=p.ASSERT,
        rev=0, origin=p.USER_VERIFIED, scope='proj1', time=1000,
        subject='project', predicate='plan', kind=p.TEXT):
    return p.StateEvent(schema_version=1,event_id=event_id,scope_id=scope,
        claim_id=claim_id,subject_id=subject,predicate=predicate,
        value_kind=kind,value_text=value,origin=origin,action=action,
        expected_revision=rev,recorded_at_ms=time,effective_at_ms=time,
        source=p.SourceEvidence(session_id='chat1',root_entry_id='1',
            revision_entry_id='2',content_sha256='a'*64,snapshot_id='snap1'))

class C07StateTests(unittest.TestCase):
    def setUp(self): self.ledger=StateLedger('proj1')
    def test_new_claim_and_exact_replay(self):
        e=evt(); self.assertTrue(self.ledger.apply(e)); self.assertFalse(self.ledger.apply(e))
        self.assertEqual(self.ledger.projection().claims[0].revision,1)
    def test_reused_event_id_rejected(self):
        self.ledger.apply(evt())
        with self.assertRaises(StateConflict): self.ledger.apply(evt(value='changed'))
    def test_stale_expected_revision(self):
        self.ledger.apply(evt())
        with self.assertRaises(StateConflict): self.ledger.apply(evt('e2',action=p.SUPERSEDE,value='new',rev=0))
    def test_human_update_preserves_history(self):
        self.ledger.apply(evt())
        self.ledger.apply(evt('e2',rev=1,action=p.SUPERSEDE,value='approved',time=2000))
        self.assertEqual(len(self.ledger.history()),2)
        self.assertEqual(self.ledger.projection().claims[0].value_text,'approved')
        self.assertEqual(StateLedger.replay('proj1',self.ledger.history()).projection(),self.ledger.projection())
    def test_model_cannot_supersede_human(self):
        self.ledger.apply(evt())
        with self.assertRaises(StateInvalid): self.ledger.apply(evt('e2',rev=1,action=p.SUPERSEDE,
            value='malicious',origin=p.MODEL_HYPOTHESIS,time=2000))
        self.assertEqual(self.ledger.projection().claims[0].value_text,'draft')
    def test_model_cannot_retract_human(self):
        self.ledger.apply(evt())
        with self.assertRaises(StateInvalid): self.ledger.apply(evt('e2',rev=1,action=p.RETRACT,
            origin=p.MODEL_HYPOTHESIS,time=2000))
    def test_import_cannot_confirm(self):
        self.ledger.apply(evt())
        with self.assertRaises(StateInvalid): self.ledger.apply(evt('e2',rev=1,action=p.CONFIRM,
            origin=p.IMPORT_OBSERVED,time=2000))
    def test_conflicting_claims_no_silent_winner(self):
        self.ledger.apply(evt())
        self.ledger.apply(evt('e2','c2','final',origin=p.MODEL_HYPOTHESIS,time=2000))
        projection=self.ledger.projection()
        self.assertEqual(len(projection.claims),2)
        self.assertEqual(len(projection.conflicts),1)
        self.assertEqual(projection.conflicts[0].first_claim_id,'c1')
    def test_retraction_removes_active_conflict_only(self):
        self.ledger.apply(evt()); self.ledger.apply(evt('e2','c2','other',time=2000))
        self.ledger.apply(evt('e3','c2','other',p.RETRACT,1,time=3000))
        self.assertFalse(self.ledger.projection().conflicts)
        self.assertEqual(self.ledger.projection().claims[1].status,p.RETRACTED)
    def test_retracted_claim_terminal(self):
        self.ledger.apply(evt()); self.ledger.apply(evt('e2',action=p.RETRACT,rev=1,time=2000))
        with self.assertRaises(StateConflict): self.ledger.apply(evt('e3',action=p.CONFIRM,rev=2,time=3000))
    def test_challenge_then_confirm(self):
        self.ledger.apply(evt()); self.ledger.apply(evt('e2',action=p.CHALLENGE,rev=1,time=2000))
        self.assertEqual(self.ledger.projection().claims[0].status,p.DISPUTED)
        self.ledger.apply(evt('e3',action=p.CONFIRM,rev=2,time=3000))
        self.assertEqual(self.ledger.projection().claims[0].status,p.ACTIVE)
    def test_model_challenge_does_not_demote_verified_source(self):
        self.ledger.apply(evt())
        self.ledger.apply(evt('e2',action=p.CHALLENGE,rev=1,
            origin=p.MODEL_HYPOTHESIS,time=2000))
        claim=self.ledger.projection().claims[0]
        self.assertEqual(claim.origin,p.USER_VERIFIED)
        self.assertEqual(claim.source.content_sha256,'a'*64)
        with self.assertRaises(StateInvalid):
            self.ledger.apply(evt('e3',action=p.SUPERSEDE,rev=2,
                origin=p.MODEL_HYPOTHESIS,value='override',time=3000))

    def test_unknown_field_in_object_is_rejected(self):
        data=evt().SerializeToString(deterministic=True)
        decoded=p.StateEvent.FromString(data+b'\xf8\x07\x01')
        with self.assertRaises(StateInvalid): self.ledger.apply(decoded)

    def test_wrong_scope_and_unknown_origin_rejected(self):
        with self.assertRaises(StateInvalid): self.ledger.apply(evt(scope='other'))
        with self.assertRaises(StateInvalid): self.ledger.apply(evt(origin=0))
    def test_source_hash_rejected(self):
        e=evt(); e.source.content_sha256='xyz'
        with self.assertRaises(StateInvalid): self.ledger.apply(e)
    def test_atomic_batch(self):
        a=evt(); b=evt('e2',action=p.SUPERSEDE,rev=99,value='bad')
        with self.assertRaises(StateConflict): self.ledger.apply_batch([a,b])
        self.assertFalse(self.ledger.history())
    def test_canonical_wire_rejects_unknown(self):
        data=evt().SerializeToString(deterministic=True)
        self.assertEqual(canonical_event(data),evt())
        with self.assertRaises(StateInvalid): canonical_event(data + b'\xf8\x07\x01')
    def test_noncanonical_integer(self):
        with self.assertRaises(StateInvalid): self.ledger.apply(evt(value='01',kind=p.INTEGER))
        self.ledger.apply(evt(value='12',kind=p.INTEGER))
        self.assertEqual(self.ledger.projection().claims[0].value_text,'12')
    def test_provenance_separate_from_truth(self):
        self.ledger.apply(evt(origin=p.MODEL_HYPOTHESIS))
        self.assertEqual(self.ledger.projection().claims[0].origin,p.MODEL_HYPOTHESIS)
    def test_topic_switch_does_not_create_conflict(self):
        self.ledger.apply(evt()); self.ledger.apply(evt('e2','c2','other',time=2000,predicate='deadline'))
        self.assertFalse(self.ledger.projection().conflicts)
    def test_timestamp_reversal_fails(self):
        self.ledger.apply(evt(time=5000))
        with self.assertRaises(StateConflict): self.ledger.apply(evt('e2',action=p.CONFIRM,rev=1,time=1000))
    def test_expired_claim_not_active(self):
        self.ledger.apply(evt())
        self.ledger.apply(evt('e2',action=p.EXPIRE,rev=1,time=2000))
        self.assertEqual(self.ledger.projection().claims[0].status,p.EXPIRED)

if __name__=='__main__':unittest.main()
