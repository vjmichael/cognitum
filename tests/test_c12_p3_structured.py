"""C12 P3 hierarchical/temporal functional and independent receipt tests."""
import unittest
from cognitum.proto import planning_structured_pb2 as p
from cognitum.planning_structured import run_htn,verify_htn,run_temporal,verify_temporal,audit
from tests.test_c12_planning import example


def wire(x):return x.SerializeToString(deterministic=True)


def htn():
    c=example()
    req=p.HtnRequest(schema_version=1,trace_id='structured-test',classical_request=wire(c),
                     root_tasks=['solve'],max_expansions=200)
    req.methods.add(method_id='cheap',abstract_task_id='solve',subtasks=['get_key','open_door','move'])
    req.methods.add(method_id='expensive',abstract_task_id='solve',subtasks=['expensive_teleport'])
    return req


def temporal():
    q=p.TemporalRequest(schema_version=1,trace_id='temporal-test')
    q.actions.add(id='A',duration=3,earliest_start=2)
    q.actions.add(id='B',duration=2,predecessors=['A'])
    q.actions.add(id='C',duration=4,predecessors=['A'],earliest_start=6)
    return q


def solve_htn(q,**kw):return p.HtnResult.FromString(run_htn(wire(q),enabled=True,host_authorized=True,**kw))
def solve_temporal(q):return p.TemporalResult.FromString(run_temporal(wire(q),enabled=True,host_authorized=True))
def checked_htn(q,r):return verify_htn(wire(q),wire(r))
def checked_temp(q,r):return verify_temporal(wire(q),wire(r))


class HtnTests(unittest.TestCase):
    def test_min_cost_decomposition(self):
        q=htn();r=solve_htn(q)
        self.assertEqual(r.status,p.VERIFIED_HTN_OPTIMAL)
        self.assertEqual(r.total_cost,7)
        self.assertEqual(list(r.action_indices),[0,1,2])
        self.assertTrue(checked_htn(q,r).optimality_verified)

    def test_partial_budget_never_certifies(self):
        q=htn();q.max_expansions=2
        r=solve_htn(q)
        self.assertIn(r.status,(p.HTN_UNKNOWN,p.VERIFIED_HTN_PLAN))
        self.assertFalse(r.complete_search_verified)

    def test_partial_valid_witness_under_budget(self):
        q=htn();q.max_expansions=2
        r=solve_htn(q)
        self.assertEqual(r.status,p.VERIFIED_HTN_PLAN)
        self.assertEqual(r.total_cost,20)
        self.assertTrue(checked_htn(q,r).evidence_valid)
        self.assertFalse(checked_htn(q,r).optimality_verified)

    def test_known_no_plan_only_grammar(self):
        q=htn();del q.methods[:]
        q.methods.add(method_id='cannot',abstract_task_id='solve',subtasks=['move'])
        r=solve_htn(q)
        self.assertEqual(r.status,p.VERIFIED_HTN_NO_PLAN)
        self.assertTrue(checked_htn(q,r).evidence_valid)

    def test_cyclic_decomposition_rejected(self):
        q=htn();q.methods[0].subtasks[:]=['solve']
        self.assertEqual(solve_htn(q).status,p.HTN_REJECTED)

    def test_undeclared_task_rejected(self):
        q=htn();q.methods[0].subtasks.append('evil')
        self.assertEqual(solve_htn(q).status,p.HTN_REJECTED)

    def test_incorrect_action_cost_rejected(self):
        q=htn();r=solve_htn(q);r.total_cost=20
        self.assertFalse(checked_htn(q,r).evidence_valid)

    def test_forged_action_sequence_rejected(self):
        q=htn();r=solve_htn(q)
        r.action_indices[:]=[3]
        r.total_cost=20
        self.assertFalse(checked_htn(q,r).evidence_valid)

    def test_claimed_optimal_but_suboptimal_rejected(self):
        q=htn();r=solve_htn(q)
        r.action_indices[:]=[3]
        r.total_cost=20
        self.assertFalse(checked_htn(q,r).evidence_valid)

    def test_forged_expansion_count(self):
        q=htn();r=solve_htn(q);r.explored_decompositions=999
        self.assertFalse(checked_htn(q,r).evidence_valid)

    def test_tampered_method_request(self):
        q=htn();r=solve_htn(q);q.methods[0].subtasks[:]=['expensive_teleport']
        self.assertFalse(checked_htn(q,r).evidence_valid)

    def test_denied_by_default(self):
        q=htn();r=p.HtnResult.FromString(run_htn(wire(q)))
        self.assertEqual(r.status,p.HTN_REJECTED)

    def test_missing_host_grant(self):
        q=htn();r=p.HtnResult.FromString(run_htn(wire(q),enabled=True))
        self.assertEqual(r.reason_code,'HOST_AUTHORIZATION_REQUIRED')

    def test_nested_decomposition(self):
        q=htn();q.methods[0].subtasks[:]=['unlock_and_move'];q.methods.add(method_id='nested',abstract_task_id='unlock_and_move',subtasks=['get_key','open_door','move'])
        r=solve_htn(q)
        self.assertTrue(checked_htn(q,r).optimality_verified)

    def test_decomposition_audit_no_task_names(self):
        q=htn();r=solve_htn(q)
        x=audit(wire(q),wire(r),'htn')
        self.assertNotIn(b'get_key',x)
        self.assertTrue(p.StructuredAudit.FromString(x).evidence_valid)


class TemporalTests(unittest.TestCase):
    def test_earliest_parallel_schedule(self):
        q=temporal();r=solve_temporal(q)
        self.assertEqual(r.status,p.VERIFIED_TEMPORAL_EARLIEST)
        self.assertEqual({x.id:x.start for x in r.starts},{'A':2,'B':5,'C':6})
        self.assertEqual(r.makespan,10)
        self.assertTrue(checked_temp(q,r).optimality_verified)

    def test_deadline_exactly_met(self):
        q=temporal();q.actions[2].latest_finish=10
        self.assertTrue(checked_temp(q,solve_temporal(q)).evidence_valid)

    def test_infeasible_deadline(self):
        q=temporal();q.actions[2].latest_finish=9
        r=solve_temporal(q)
        self.assertEqual(r.status,p.VERIFIED_TEMPORAL_INFEASIBLE)
        self.assertTrue(checked_temp(q,r).evidence_valid)

    def test_infeasible_positive_cycle(self):
        q=temporal();q.actions[0].predecessors.append('C')
        r=solve_temporal(q)
        self.assertEqual(r.status,p.VERIFIED_TEMPORAL_INFEASIBLE)
        self.assertTrue(checked_temp(q,r).evidence_valid)

    def test_forged_early_start(self):
        q=temporal();r=solve_temporal(q);r.starts[1].start=3
        self.assertFalse(checked_temp(q,r).evidence_valid)

    def test_forged_delay_is_not_earliest(self):
        q=temporal();r=solve_temporal(q);r.starts[1].start=7;r.makespan=10
        self.assertFalse(checked_temp(q,r).evidence_valid)

    def test_forged_infeasible(self):
        q=temporal();r=solve_temporal(q)
        r.status=p.VERIFIED_TEMPORAL_INFEASIBLE
        r.ClearField('starts');r.makespan=0
        self.assertFalse(checked_temp(q,r).evidence_valid)

    def test_duplicate_ids_invalid(self):
        q=temporal();q.actions.add().CopyFrom(q.actions[0])
        self.assertEqual(solve_temporal(q).status,p.TEMPORAL_REJECTED)

    def test_unknown_predecessor_invalid(self):
        q=temporal();q.actions[0].predecessors.append('D')
        self.assertEqual(solve_temporal(q).status,p.TEMPORAL_REJECTED)

    def test_zero_duration_invalid(self):
        q=temporal();q.actions[0].duration=0
        self.assertEqual(solve_temporal(q).status,p.TEMPORAL_REJECTED)

    def test_denial_default(self):
        q=temporal();r=p.TemporalResult.FromString(run_temporal(wire(q)))
        self.assertEqual(r.status,p.TEMPORAL_REJECTED)

    def test_receipt_request_tamper(self):
        q=temporal();r=solve_temporal(q);q.actions[0].duration=5
        self.assertFalse(checked_temp(q,r).evidence_valid)

    def test_random_precedence_dags(self):
        import random
        rng=random.Random(88)
        for _ in range(40):
            q=p.TemporalRequest(schema_version=1,trace_id='random-precedence')
            n=rng.randint(1,9)
            for i in range(n):
                a=q.actions.add(id='task'+str(i),duration=rng.randint(1,6),earliest_start=rng.randint(0,7))
                for j in range(i):
                    if rng.random()<.2:a.predecessors.append('task'+str(j))
            r=solve_temporal(q)
            self.assertEqual(r.status,p.VERIFIED_TEMPORAL_EARLIEST)
            self.assertTrue(checked_temp(q,r).optimality_verified)

    def test_audit_no_source_action_ids(self):
        q=temporal();r=solve_temporal(q)
        x=audit(wire(q),wire(r),'temporal')
        self.assertTrue(p.StructuredAudit.FromString(x).evidence_valid)
        self.assertNotIn(b'predecessors',x)


if __name__=='__main__':unittest.main()
