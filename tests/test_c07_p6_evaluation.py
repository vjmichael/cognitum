"""P6 evaluation invariants; synthetic results are NOT live model performance."""
from __future__ import annotations

from dataclasses import replace
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from cognitum.proto import state_pb2 as pb
from cognitum.state_evaluation import (
    SCOPE, Expected, Case, Scenario, golden_scenarios, corpus_sha256, query,
    evaluate, event, observed, expected, chronological_register,
    effective_clock_register,
)
from cognitum.state_revision import StateLedger, StateInvalid, StateConflict
from cognitum.state_temporal import project_as_of
from cognitum.state_host_gate import SourceUnavailable
from cognitum.state_journal import StateJournal
from tools.benchmark_c07_p6 import FixtureLease, benchmark


class P6EvaluationTests(unittest.TestCase):
    def test_golden_corpus_is_fixed_and_nontrivial(self):
        scenarios=golden_scenarios()
        self.assertEqual(len(scenarios),9)
        self.assertEqual(sum(len(s.cases) for s in scenarios),44)
        self.assertEqual(sum(len(s.events) for s in scenarios),19)
        ids=[e.event_id for s in scenarios for e in s.events]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual([s.name for s in scenarios],
            ['switch','retro','bounded','challenge','retract','conflict',
             'delayed','uncertain','interval'])

    def test_hand_labeled_corpus_hash_is_pinned(self):
        self.assertEqual(corpus_sha256(),
            '54a0aac98d4a6b77126d2adb8b3a3e67873e56b22f9516f0cac3cd712f341fe6')
        self.assertEqual(evaluate()['golden_corpus_sha256'],corpus_sha256())

    def test_goldens_independent_from_reducer(self):
        result=evaluate()
        self.assertFalse(result['C07_oracle_mismatches'])
        self.assertEqual(result['results']['C07_bitemporal']['exact_case_correct'],44)
        self.assertEqual(result['results']['chronological_register']['exact_case_correct'],21)
        self.assertEqual(result['results']['effective_clock_register']['exact_case_correct'],25)

    def test_expected_key_corruption_is_detected(self):
        scenarios=golden_scenarios()
        first=scenarios[0]
        valid=first.cases[1]
        tampered=replace(valid,claims=(Expected('switch_main','incorrect'),))
        fake=(replace(first,cases=first.cases[:1]+(tampered,)+first.cases[2:]),)+scenarios[1:]
        with patch('cognitum.state_evaluation.golden_scenarios',return_value=fake):
            self.assertIn('switch/old value historically',evaluate()['C07_oracle_mismatches'])

    def test_unknown_source_leases_deny_publish(self):
        scenario=golden_scenarios()[0]
        wrong=FixtureLease(())
        with tempfile.TemporaryDirectory() as td:
            with StateJournal(Path(td)/'derived.sqlite',SCOPE) as journal:
                with self.assertRaises(SourceUnavailable):
                    journal.apply_host_batch(scenario.events,wrong)
                self.assertEqual(journal.head()[0],0)

    def test_deletion_after_admission_fails_historical_disclosure(self):
        scenario=golden_scenarios()[0]
        lease=FixtureLease(scenario.events)
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/'derived.sqlite'
            with StateJournal(db,SCOPE) as journal:
                journal.apply_host_batch(scenario.events,lease)
            with StateJournal(db,SCOPE) as journal:
                lease.deleted.add(scenario.events[0].source.SerializeToString(deterministic=True))
                seen=[]
                with self.assertRaises(SourceUnavailable):
                    journal.publish_host_as_of(query(scenario.cases[1]),lease,seen.append)
                self.assertEqual(seen,[])

    def test_lease_revoked_before_publish_fails(self):
        scenario=golden_scenarios()[0]
        lease=FixtureLease(scenario.events)
        with tempfile.TemporaryDirectory() as td:
            with StateJournal(Path(td)/'derived.sqlite',SCOPE) as journal:
                journal.apply_host_batch(scenario.events,lease)
                lease.active=False
                seen=[]
                with self.assertRaises(SourceUnavailable):
                    journal.publish_host_as_of(query(scenario.cases[1]),lease,seen.append)
                self.assertEqual(seen,[])

    def test_restarted_journal_equals_independent_goldens(self):
        for scenario in golden_scenarios():
            with self.subTest(scenario=scenario.name),tempfile.TemporaryDirectory() as td:
                path=Path(td)/'derived.sqlite'
                lease=FixtureLease(scenario.events)
                with StateJournal(path,SCOPE) as journal:
                    self.assertEqual(journal.apply_host_batch(scenario.events,lease).applied,len(scenario.events))
                with StateJournal(path,SCOPE) as journal:
                    for case in scenario.cases:
                        result=journal.publish_host_as_of(query(case),lease,
                            lambda b: pb.HistoricalProjection.FromString(b))
                        self.assertEqual(observed(result),expected(case))
                        self.assertTrue(result.historical_only)

    def test_scope_is_not_provided_by_model(self):
        scenario=golden_scenarios()[0]
        ledger=StateLedger(SCOPE)
        ledger.apply_batch(scenario.events)
        altered=query(scenario.cases[0]);altered.scope_id='other'
        with self.assertRaises(StateInvalid):project_as_of(ledger,altered)

    def test_current_value_and_recorded_cutoff_are_distinct(self):
        scenarios={s.name:s for s in golden_scenarios()}
        e=scenarios['switch'].events
        older=scenarios['switch'].cases[2]
        self.assertEqual(chronological_register(e,older)[0][0].value,'draft')
        self.assertEqual(effective_clock_register(e,older)[0][0].value,'final')
        ledger=StateLedger(SCOPE);ledger.apply_batch(e)
        self.assertEqual(observed(project_as_of(ledger,query(older)))[0][0].value,'draft')

    def test_baselines_are_not_claimed_security_equivalent(self):
        data=evaluate()
        self.assertFalse(data['Lu_or_model_executed'])
        self.assertEqual(data['evaluation_tier'],'hand_labeled_synthetic_no_model')
        self.assertTrue(any('authorization' in x for x in data['warnings']))

    def test_benchmark_rejects_bad_repetition_count(self):
        for reps in (0,-1,11,1.5,'3'):
            with self.subTest(reps=reps),self.assertRaises(ValueError):
                benchmark(reps)

    def test_end_to_end_benchmark_has_no_oracle_mismatch(self):
        result=benchmark(1)
        self.assertEqual(result['golden_query_count'],44)
        self.assertEqual(result['journal_restart_oracle_queries'],44)
        self.assertTrue(result['deleted_evidence_and_revoked_lease_denial'])
        self.assertFalse(result['C07_oracle_mismatches'])
        self.assertEqual(len(result['synthetic_fixture_event_frames_sha256']),64)
        self.assertTrue(result['persisted_sqlite_file_bytes_median']>0)
        self.assertIn('C07_SQLite_fenced_query',result['timing_ms_median'])
        self.assertFalse(result['Lu_or_model_executed'])


if __name__ == '__main__': unittest.main()
