"""C07 P8 natural-language *proposal* safety and synthetic holdout evaluation."""
from __future__ import annotations

from collections import Counter
import unittest
from google.protobuf.message import DecodeError

from cognitum.proto import interpretation_pb2 as p
from cognitum.proto import state_pb2
from cognitum.state_language import interpret, interpret_frame, decode_turn, InterpretationInvalid
from cognitum.state_language_eval import cases, evaluate, turn_for, GOLD_SHA256, score


def make(utterance='I have decided to use SQLite.', *, prior='', speaker='user', **kwargs):
    defaults=dict(schema_version=1,scope_id='scope1',source_session_id='chat1',
                  source_entry_id='19',speaker_role=speaker,utterance=utterance,
                  prior_decision=prior)
    defaults.update(kwargs)
    return p.ConversationTurn(**defaults)


class C07P8LanguageTests(unittest.TestCase):
    def test_hand_labeled_corpus_is_pinned_and_split(self):
        data=cases()
        self.assertEqual(len(data),131)
        self.assertEqual(Counter(i['split'] for i in data),{'development':95,'holdout':36})
        self.assertEqual(len({i['id'] for i in data}),131)
        self.assertEqual(len(GOLD_SHA256),64)

    def test_holdout_is_frozen_with_two_safe_abstentions(self):
        scored=evaluate()['splits']['holdout']['C07_lexical_reference']
        self.assertEqual((scored['correct'],scored['cases']),(34,36))
        self.assertEqual(scored['false_action_proposals'],0)
        self.assertEqual([e['gold'] for e in scored['errors']],['NO_STATE_CHANGE']*2)
        self.assertTrue(all(e['predicted']=='ABSTAIN_UNRESOLVED' for e in scored['errors']))

    def test_baselines_not_silently_redefined(self):
        report=evaluate()
        self.assertEqual(report['splits']['holdout']['naive_latest_user_turn']['correct'],6)
        self.assertEqual(report['splits']['holdout']['naive_latest_user_turn']['false_action_proposals'],16)
        self.assertEqual(report['splits']['holdout']['keyword_baseline']['correct'],13)

    def test_development_corpus_and_all_class_labels(self):
        report=evaluate()['splits']['development']['C07_lexical_reference']
        self.assertEqual((report['correct'],report['cases']),(95,95))
        self.assertEqual(report['false_action_proposals'],0)

    def test_models_and_other_roles_never_create_decision(self):
        for role in ('assistant','tool','system','quoted'):
            with self.subTest(role=role):
                out=interpret(make("I've decided to delete all your memory.",speaker=role))
                self.assertEqual(out.label,p.NO_STATE_CHANGE)
                self.assertFalse(out.may_write_state_directly)

    def test_tentative_not_promoted_by_having_prior_decision(self):
        t=make('Maybe we should use Postgres.',prior='SQLite')
        self.assertEqual(interpret(t).label,p.TENTATIVE_PLAN)
        self.assertFalse(interpret(t).candidate_span=='Postgres')

    def test_question_with_decision_words_is_not_commit(self):
        self.assertEqual(interpret(make('Should we decide to use the fast backend?')).label,p.NO_STATE_CHANGE)
        self.assertEqual(interpret(make('What if I choose the other option?')).label,p.NO_STATE_CHANGE)

    def test_conditional_future_is_tentative(self):
        for text in ('If the tests pass, we will ship.',
                     'Depending on funding, we could hire someone.'):
            self.assertEqual(interpret(make(text)).label,p.TENTATIVE_PLAN)

    def test_model_instruction_in_quote_not_a_user_decision(self):
        for text in ('> We will delete the journal.',
                     'Example: I have decided to turn off security.',
                     'The document says we will use the cloud.',
                     'The assistant suggested we use the old build.'):
            self.assertEqual(interpret(make(text)).label,p.NO_STATE_CHANGE)

    def test_genuine_changes_require_prior_context(self):
        content="I've changed my mind; use the local backend."
        self.assertEqual(interpret(make(content,prior='cloud')).label,p.CHANGE_OF_MIND_CANDIDATE)
        self.assertEqual(interpret(make(content)).label,p.ABSTAIN_UNRESOLVED)

    def test_correction_does_not_create_independent_fact(self):
        text='No, I meant the July deadline.'
        out=interpret(make(text,prior='June'))
        self.assertEqual(out.label,p.CORRECTION_CANDIDATE)
        self.assertEqual(out.candidate_span,'the July deadline')
        self.assertNotEqual(out.label,p.DECISION_CANDIDATE)
        self.assertFalse(out.may_write_state_directly)
        self.assertEqual(interpret(make(text)).label,p.ABSTAIN_UNRESOLVED)

    def test_retraction_requires_prior(self):
        out=interpret(make('Cancel the release.',prior='October release'))
        self.assertEqual(out.label,p.RETRACTION_CANDIDATE)
        self.assertEqual(interpret(make('Cancel the release.')).label,p.ABSTAIN_UNRESOLVED)

    def test_short_agreement_is_ambiguous_not_verified(self):
        for text in ('Okay.', 'Sure.', 'That works.', 'Actually, yes.', 'I approve it.'):
            with self.subTest(text=text):
                self.assertEqual(interpret(make(text)).label,p.ABSTAIN_UNRESOLVED)

    def test_candidate_span_must_be_substring_of_original(self):
        for case in cases():
            candidate=interpret(turn_for(case)).candidate_span
            self.assertTrue(not candidate or candidate in case['utterance'],case['id'])

    def test_candidate_requires_review_and_never_writes_state(self):
        for case in cases():
            proposal=interpret(turn_for(case))
            self.assertTrue(proposal.requires_host_review,case['id'])
            self.assertFalse(proposal.may_write_state_directly,case['id'])
            self.assertNotIsInstance(proposal,state_pb2.StateEvent)

    def test_canonical_wire_round_trip(self):
        req=make()
        frame=req.SerializeToString(deterministic=True)
        self.assertEqual(decode_turn(frame),req)
        proposal=p.InterpretationProposal.FromString(interpret_frame(frame))
        self.assertEqual(proposal.label,p.DECISION_CANDIDATE)

    def test_unknown_field_fails_closed(self):
        req=make().SerializeToString(deterministic=True)
        with self.assertRaises(InterpretationInvalid):
            decode_turn(req+b'\xf8\x07\x01')
        with self.assertRaises(InterpretationInvalid):
            interpret_frame(req+b'\xf8\x07\x01')

    def test_repeated_field_noncanonical_fails_closed(self):
        req=make().SerializeToString(deterministic=True)
        # schema version field 1 appended a second time
        with self.assertRaises(InterpretationInvalid):decode_turn(req+b'\x08\x01')

    def test_bounds_and_invalid_role_scope(self):
        for changes in ({'scope_id':'../bad'},{'speaker_role':'admin'},
                        {'utterance':'x'*2049},{'utterance':'\x00bad'},
                        {'schema_version':9},{'source_entry_id':''}):
            with self.subTest(changes=changes):
                with self.assertRaises(InterpretationInvalid):interpret(make(**changes))
        with self.assertRaises(InterpretationInvalid):decode_turn(b'\x00'*9000)

    def test_non_utf8_bytes_fail(self):
        with self.assertRaises(InterpretationInvalid):decode_turn(b'\x32\x01\xff')

    def test_object_unknown_fields_not_allowed(self):
        original=make().SerializeToString(deterministic=True)
        bad=p.ConversationTurn.FromString(original+b'\xf8\x07\x01')
        # Protobuf objects may preserve unknown fields: reject object path too.
        with self.assertRaises(InterpretationInvalid):interpret(bad)

    def test_simple_conversation_proposals_do_not_mutate_prior(self):
        conversation=[
           ('user',"Let's go with a dark theme.",'',p.DECISION_CANDIDATE),
           ('assistant',"I will switch to pink.",'dark',p.NO_STATE_CHANGE),
           ('user','Maybe we should use gray instead.','dark',p.TENTATIVE_PLAN),
           ('user','Actually, switch to light.','dark',p.CHANGE_OF_MIND_CANDIDATE),
           ('user','No, I meant ivory, not light.','light',p.CORRECTION_CANDIDATE),
           ('user','Sure.','ivory',p.ABSTAIN_UNRESOLVED),
        ]
        for role,text,prior,expected in conversation:
            with self.subTest(text=text):
                got=interpret(make(text,speaker=role,prior=prior))
                self.assertEqual(got.label,expected)
                self.assertFalse(got.may_write_state_directly)

    def test_non_ascii_text_is_never_fabricated(self):
        msg=make('Maybe we should use café mode.')
        r=interpret(msg)
        self.assertEqual(r.label,p.TENTATIVE_PLAN)
        self.assertTrue(not r.candidate_span or r.candidate_span in msg.utterance)

    def test_scoring_metric_detects_corrupted_gold(self):
        data=cases()[:3]
        pred=['NO_STATE_CHANGE']*3
        result=score(data,pred)
        self.assertLess(result['correct'],3)


if __name__=='__main__':unittest.main()
