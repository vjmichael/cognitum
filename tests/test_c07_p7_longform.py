"""C07 P7 synthetic multi-chat oracle, restart and negative-source tests."""
from __future__ import annotations

from dataclasses import replace
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from cognitum.proto import state_pb2 as pb
from cognitum.state_host_gate import SourceUnavailable
from cognitum.state_journal import StateJournal
from cognitum.state_revision import StateConflict, StateInvalid, StateLedger
from cognitum.state_temporal import project_as_of
from cognitum.state_longform_eval import (
    SCOPE, PREDICATE, LongCase, evaluate, long_scenarios, oracle_digest,
    filtered_projection, query, expected, _e,
)


class VerifiedSyntheticLease:
    """Test injection only; does not authenticate a real user/ANSF source."""
    def __init__(self, events):
        self.active=True
        self.records={e.source.SerializeToString(deterministic=True):
                      e.SerializeToString(deterministic=True) for e in events}
        self.deleted=set()
        self.verifications=0

    def ensure_active(self):
        return self.active

    def admit_event(self, scope, event):
        key=event.source.SerializeToString(deterministic=True)
        return (self.active and scope==SCOPE and event.scope_id==SCOPE and
                self.records.get(key)==event.SerializeToString(deterministic=True))

    def verify_source(self, scope, source, require_current):
        self.verifications+=1
        key=source.SerializeToString(deterministic=True)
        return (self.active and scope==SCOPE and key in self.records and
                key not in self.deleted)


class C07P7LongformTests(unittest.TestCase):
    def test_corpus_size_ids_and_six_chat_sources(self):
        scenarios=long_scenarios()
        self.assertEqual(len(scenarios),4)
        self.assertEqual(sum(len(s.events) for s in scenarios),126)
        self.assertEqual(sum(len(s.cases) for s in scenarios),67)
        self.assertEqual(len({e.source.session_id for s in scenarios for e in s.events}),6)
        self.assertEqual({s.name for s in scenarios},{'goals','deadline','backdate','imports'})
        for scenario in scenarios:
            ids=[e.event_id for e in scenario.events]
            self.assertEqual(len(ids),len(set(ids)))
            source_rows=[(e.source.session_id,e.source.root_entry_id) for e in scenario.events]
            self.assertEqual(len(source_rows),len(set(source_rows)))
            self.assertEqual(len([e for e in scenario.events if e.predicate=='background_setting']),24)
            self.assertEqual(ids, [e.event_id for e in sorted(scenario.events,
                                      key=lambda e:(e.recorded_at_ms,e.event_id))])

    def test_oracle_digest_is_pinned(self):
        self.assertEqual(oracle_digest(),
            '687d1c8cca705b3113ecd5de633743150d14c8df34501a39c8253b59e5a4bc59')
        self.assertEqual(evaluate()['golden_sha256'],oracle_digest())

    def test_longform_oracle_and_baselines(self):
        report=evaluate()
        self.assertEqual(report['C07_oracle_mismatches'],[])
        self.assertEqual(report['positive_conflict_queries'],26)
        self.assertEqual(report['exact_target_answer_correct'],
                         {'C07':67,'chronological':22,'effective':26})
        self.assertTrue(report['no_model_or_Lu_executed'])
        self.assertEqual(report['evaluation_tier'],
                         'hand_annotated_synthetic_multiconversation_no_model')

    def test_oracle_corruption_is_detected(self):
        old=long_scenarios()
        s=old[0]; c=s.cases[1]
        bad=replace(c,values=())
        alt=(replace(s,cases=s.cases[:1]+(bad,)+s.cases[2:]),)+old[1:]
        original_digest=oracle_digest()
        with patch('cognitum.state_longform_eval.long_scenarios',return_value=alt):
            self.assertIn('goals/initial boundary',evaluate()['C07_oracle_mismatches'])
            self.assertNotEqual(original_digest,oracle_digest(alt))

    def test_asof_full_projection_contains_background_but_label_filter_does_not(self):
        s=long_scenarios()[0]
        ledger=StateLedger(SCOPE);ledger.apply_batch(s.events)
        case=s.cases[-1]
        answer=project_as_of(ledger,query(case))
        self.assertGreater(len(answer.claims),len(case.values))
        self.assertEqual(filtered_projection(answer,s.subject_id),expected(case))
        self.assertTrue(answer.historical_only)

    def test_reopened_journal_all_independent_annotated_queries(self):
        evaluated=0
        for s in long_scenarios():
            with self.subTest(scenario=s.name),tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'derived.sqlite'
                lease=VerifiedSyntheticLease(s.events)
                with StateJournal(path,SCOPE) as journal:
                    receipt=journal.apply_host_batch(s.events,lease)
                    self.assertEqual(receipt.applied,len(s.events))
                    self.assertEqual(journal.head()[0],len(s.events))
                with StateJournal(path,SCOPE) as reopened:
                    for c in s.cases:
                        ans=reopened.publish_host_as_of(query(c),lease,
                            lambda data: pb.HistoricalProjection.FromString(data))
                        self.assertEqual(filtered_projection(ans,s.subject_id),expected(c),
                                         (s.name,c.name))
                        self.assertTrue(ans.historical_only)
                        evaluated+=1
                self.assertGreater(lease.verifications,len(s.events))
        self.assertEqual(evaluated,67)

    def test_deleted_background_source_blocks_target_disclosure_after_restart(self):
        s=long_scenarios()[0]
        lease=VerifiedSyntheticLease(s.events)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'derived.sqlite'
            with StateJournal(p,SCOPE) as j: j.apply_host_batch(s.events,lease)
            unrelated=next(e for e in s.events if e.predicate=='background_setting')
            lease.deleted.add(unrelated.source.SerializeToString(deterministic=True))
            with StateJournal(p,SCOPE) as j:
                out=[]
                with self.assertRaises(SourceUnavailable):
                    j.publish_host_as_of(query(s.cases[-1]),lease,out.append)
                self.assertEqual(out,[])

    def test_revocation_blocks_all_historical_queries(self):
        s=long_scenarios()[2]
        lease=VerifiedSyntheticLease(s.events)
        with tempfile.TemporaryDirectory() as d, StateJournal(Path(d)/'derived.sqlite',SCOPE) as j:
            j.apply_host_batch(s.events,lease)
            lease.active=False
            delivered=[]
            with self.assertRaises(SourceUnavailable):
                j.publish_host_as_of(query(s.cases[1]),lease,delivered.append)
            self.assertEqual(delivered,[])

    def test_forged_event_source_rejected_by_host_before_commit(self):
        s=long_scenarios()[0]
        lease=VerifiedSyntheticLease(s.events)
        bogus=pb.StateEvent();bogus.CopyFrom(s.events[0]);bogus.source.snapshot_id='forged'
        with tempfile.TemporaryDirectory() as d, StateJournal(Path(d)/'derived.sqlite',SCOPE) as j:
            with self.assertRaises(SourceUnavailable):j.apply_host_batch([bogus],lease)
            self.assertEqual(j.head()[0],0)

    def test_model_suggestion_cannot_supersede_user_verified_goal(self):
        first=next(e for e in long_scenarios()[0].events if e.event_id=='goals_main_01')
        s=StateLedger(SCOPE);s.apply(first)
        proposed=_e('goals','main',2,session='chat_2',action=pb.SUPERSEDE,
                    value='maybe October',recorded=2000,origin=pb.MODEL_HYPOTHESIS)
        with self.assertRaises(StateInvalid):s.apply(proposed)
        self.assertEqual(s.projection().claims[0].value_text,'June')
        self.assertEqual(len(s.history()),1)

    def test_import_suggestion_cannot_retract_human_decision(self):
        first=next(e for e in long_scenarios()[3].events if e.event_id=='imports_main_01')
        s=StateLedger(SCOPE);s.apply(first)
        proposed=_e('imports','main',2,session='chat_1',action=pb.RETRACT,
                    value='local-only',recorded=2000,origin=pb.IMPORT_OBSERVED)
        with self.assertRaises(StateInvalid):s.apply(proposed)
        self.assertEqual(s.projection().claims[0].status,pb.ACTIVE)

    def test_unverified_temporal_correction_cannot_backdate_user_claim(self):
        first=next(e for e in long_scenarios()[2].events if e.event_id=='backdate_main_01')
        s=StateLedger(SCOPE);s.apply(first)
        proposed=_e('backdate','main',2,session='chat_2',action=pb.TEMPORAL_CORRECT,
                    value='phase-A',recorded=2500,effective=500,
                    corrects='backdate_main_01',origin=pb.MODEL_HYPOTHESIS)
        with self.assertRaises(StateInvalid):s.apply(proposed)
        self.assertEqual(len(s.history()),1)

    def test_stale_revision_after_user_change_rejected(self):
        events=[e for e in long_scenarios()[0].events if e.event_id in ('goals_main_01','goals_main_02')]
        s=StateLedger(SCOPE);s.apply_batch(events)
        stale=_e('goals','main',2,session='chat_0',action=pb.SUPERSEDE,
                 value='October',recorded=3000)
        with self.assertRaises(StateConflict):s.apply(stale)
        self.assertEqual(len(s.history()),2)

    def test_source_deleted_during_verification_blocks_publication(self):
        scenario=long_scenarios()[0]
        lease=VerifiedSyntheticLease(scenario.events)
        with tempfile.TemporaryDirectory() as d, StateJournal(Path(d)/'derived.sqlite',SCOPE) as j:
            j.apply_host_batch(scenario.events,lease)
            first=next(e for e in scenario.events if e.predicate=='background_setting')
            deleted_key=first.source.SerializeToString(deterministic=True)
            original=lease.verify_source
            triggered=[False]
            def deletion_mid_verification(scope,source,current):
                if not triggered[0]:
                    triggered[0]=True
                    lease.deleted.add(deleted_key)
                return original(scope,source,current)
            lease.verify_source=deletion_mid_verification
            output=[]
            with self.assertRaises(SourceUnavailable):
                j.publish_host_as_of(query(scenario.cases[-1]),lease,output.append)
            self.assertEqual(output,[])
            self.assertTrue(triggered[0])

    def test_source_sessions_not_inferred_from_model_text(self):
        s=long_scenarios()[0]
        source_ids={e.source.session_id for e in s.events}
        self.assertTrue(all(x.startswith('chat_') for x in source_ids))
        self.assertEqual(len(source_ids),6)
        # A different conversation ID on an otherwise identical event lacks admission.
        lease=VerifiedSyntheticLease(s.events)
        changed=pb.StateEvent();changed.CopyFrom(s.events[0]);changed.source.session_id='chat_unverified'
        self.assertFalse(lease.admit_event(SCOPE,changed))


if __name__=='__main__':unittest.main()

class C07P7BenchmarkTests(unittest.TestCase):
    def test_benchmark_rejects_invalid_repetitions(self):
        from tools.benchmark_c07_p7 import benchmark
        for number in (0,6,-1,2.5,True,'2'):
            with self.subTest(number=number),self.assertRaises(ValueError):
                benchmark(number)

    def test_restarted_journal_and_denial_counts(self):
        from tools.benchmark_c07_p7 import benchmark
        r=benchmark(1)
        self.assertEqual(r['restarted_journal_labeled_queries'],67)
        self.assertEqual(r['deleted_background_denials'],4)
        self.assertEqual(r['revoked_lease_denials'],4)
        self.assertEqual(r['exact_target_answer_correct']['C07'],67)
        self.assertGreater(r['source_checks'],126)
        self.assertGreater(r['median_sqlite_file_bytes'],0)

    def test_cannot_benchmark_with_tampered_answer_key(self):
        from tools.benchmark_c07_p7 import benchmark
        scenario=long_scenarios()[0]
        altered=(replace(scenario,cases=(replace(scenario.cases[1],values=()),)+scenario.cases[1:]),)+long_scenarios()[1:]
        with patch('cognitum.state_longform_eval.long_scenarios',return_value=altered):
            with self.assertRaises(AssertionError):benchmark(1)
