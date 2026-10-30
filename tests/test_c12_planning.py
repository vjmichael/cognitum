"""Focused C12 P1 classical planning functional/security tests; no model benchmarks."""
import hashlib
import random
import unittest
from cognitum.planning import PlanningRegistry, _decode, _encode, _task, replay_plan, _hmax, verify_plan_frame, make_planning_audit, capability_manifest, verify_manifest, export_pddl_frame
from cognitum.proto import planning_pb2 as p


def example(engine=p.NETWORKX_DIJKSTRA):
    r=p.PlanningRequest(schema_version=1, trace_id='fixture:12', engine=engine, timeout_ms=2000)
    t=r.task
    t.facts.extend(['at_start','have_key','door_open','at_goal'])
    t.initial_true.append(0)
    t.goal_true.append(3)
    t.actions.add(id='get_key',require_true=[0],add=[1],cost=1)
    t.actions.add(id='open_door',require_true=[0,1],add=[2],cost=2)
    t.actions.add(id='move',require_true=[0,2],add=[3],remove=[0],cost=4)
    t.actions.add(id='expensive_teleport',require_true=[0],add=[3],remove=[0],cost=20)
    return r


def frame(r): return r.SerializeToString(deterministic=True)


def run(r, *, enabled=True, authorized=True):
    return p.PlanningResult.FromString(PlanningRegistry(enabled=enabled).solve_frame(frame(r),host_authorized=authorized))


def receipt(r, result):
    return p.PlanReceipt.FromString(verify_plan_frame(frame(r),frame(result)))


class PlanningTests(unittest.TestCase):
    def test_networkx_dijkstra_optimal(self):
        r=example(); out=run(r)
        self.assertEqual(out.status,p.VERIFIED_OPTIMAL)
        self.assertEqual(out.total_cost,7)
        self.assertEqual(list(out.actions),[0,1,2])
        self.assertTrue(receipt(r,out).evidence_valid)
        self.assertTrue(receipt(r,out).optimality_verified)

    def test_astar_hmax_optimal(self):
        r=example(p.ASTAR_HMAX);out=run(r)
        self.assertEqual(out.status,p.VERIFIED_OPTIMAL)
        self.assertEqual(out.total_cost,7)
        self.assertEqual(_hmax(_task(r),_task(r).start),7)

    def test_weighted_astar_never_certifies(self):
        r=example(p.WEIGHTED_ASTAR_HMAX);out=run(r)
        self.assertEqual(out.status,p.VERIFIED_PLAN)
        self.assertFalse(out.optimality_verified)
        self.assertTrue(receipt(r,out).evidence_valid)

    def test_negative_precondition_and_effect(self):
        r=example();t=r.task
        t.actions[1].require_false.extend([2]);t.goal_false.append(0)
        out=run(r)
        self.assertEqual(out.total_cost,7)
        self.assertEqual(out.status,p.VERIFIED_OPTIMAL)

    def test_negative_goal_initially_satisfied(self):
        r=example();r.task.ClearField('goal_true');r.task.goal_false.append(1)
        out=run(r)
        self.assertEqual(out.total_cost,0)
        self.assertEqual(out.status,p.VERIFIED_OPTIMAL)
        self.assertTrue(receipt(r,out).evidence_valid)

    def test_known_unreachable_certified(self):
        r=example();r.task.actions[1].require_true.append(3)
        del r.task.actions[3]
        out=run(r)
        self.assertEqual(out.status,p.VERIFIED_UNREACHABLE)
        self.assertTrue(out.optimality_verified)
        self.assertTrue(receipt(r,out).optimality_verified)

    def test_unknown_under_state_budget(self):
        r=example();r.task.max_states=2
        out=run(r)
        self.assertEqual(out.status,p.UNKNOWN)
        self.assertFalse(out.optimality_verified)

    def test_unknown_under_expansion_budget(self):
        r=example(p.ASTAR_HMAX);r.task.max_expansions=1
        out=run(r)
        self.assertEqual(out.status,p.UNKNOWN)

    def test_solvable_but_not_independently_optimal_under_budget(self):
        r=example();r.task.max_states=4
        # Search sees the cheap route but proof may fail due to extra reachable states.
        out=run(r)
        self.assertIn(out.status,(p.VERIFIED_PLAN,p.UNKNOWN))
        self.assertFalse(out.optimality_verified)

    def test_bfs_unit_cost(self):
        r=example(p.NETWORKX_BFS)
        for action in r.task.actions: action.cost=1
        out=run(r)
        self.assertEqual(out.status,p.VERIFIED_OPTIMAL)
        self.assertEqual(out.total_cost,1)

    def test_bfs_nonunit_rejected(self):
        r=example(p.NETWORKX_BFS)
        self.assertEqual(run(r).status,p.REJECTED)

    def test_disabled_by_default(self):
        self.assertEqual(run(example(),enabled=False).reason_code,'PLANNING_DISABLED')

    def test_host_denied(self):
        self.assertEqual(run(example(),authorized=False).reason_code,'HOST_AUTHORIZATION_REQUIRED')

    def test_result_never_host_approves(self):
        self.assertFalse(run(example()).host_approved)
        self.assertFalse(p.PlanningAudit.FromString(make_planning_audit(frame(example()),frame(run(example())))).host_approved)

    def test_invalid_missing_schema(self):
        r=example();r.schema_version=2
        self.assertEqual(run(r).status,p.REJECTED)

    def test_invalid_goal_overlap(self):
        r=example();r.task.goal_false.append(3)
        self.assertEqual(run(r).status,p.REJECTED)

    def test_conflicting_precondition(self):
        r=example();r.task.actions[0].require_false.append(0)
        self.assertEqual(run(r).status,p.REJECTED)

    def test_conflicting_effect(self):
        r=example();r.task.actions[0].remove.append(1)
        self.assertEqual(run(r).status,p.REJECTED)

    def test_duplicate_fact_or_action(self):
        r=example();r.task.facts.append('at_goal')
        self.assertEqual(run(r).status,p.REJECTED)
        r=example();r.task.actions[0].id='move'
        self.assertEqual(run(r).status,p.REJECTED)

    def test_out_of_range_fact(self):
        r=example();r.task.goal_true.append(77)
        self.assertEqual(run(r).status,p.REJECTED)

    def test_action_no_effect(self):
        r=example();r.task.actions[0].ClearField('add')
        self.assertEqual(run(r).status,p.REJECTED)

    def test_zero_cost(self):
        r=example();r.task.actions[0].cost=0
        self.assertEqual(run(r).status,p.REJECTED)

    def test_forged_cost(self):
        r=example();out=run(r);out.total_cost+=1
        self.assertFalse(receipt(r,out).evidence_valid)

    def test_forged_action_path(self):
        r=example();out=run(r);out.ClearField('actions');out.actions.extend([2,1,0])
        self.assertFalse(receipt(r,out).evidence_valid)

    def test_forged_proof_flag(self):
        r=example(p.WEIGHTED_ASTAR_HMAX);out=run(r);out.optimality_verified=True
        self.assertFalse(receipt(r,out).evidence_valid)

    def test_forged_optimality(self):
        r=example();out=run(r)
        out.ClearField('actions');out.actions.append(3);out.total_cost=20
        self.assertFalse(receipt(r,out).evidence_valid)

    def test_forged_unreachable(self):
        r=example();out=run(r);out.ClearField('actions');out.total_cost=0;out.plan_verified=False
        out.status=p.VERIFIED_UNREACHABLE
        self.assertFalse(receipt(r,out).evidence_valid)

    def test_tampered_backend_and_proof_metadata(self):
        r=example();out=run(r);out.backend_id="research-fantasy"
        self.assertFalse(receipt(r,out).evidence_valid)
        out=run(r);out.reason_code="self_asserted_proven"
        self.assertFalse(receipt(r,out).evidence_valid)

    def test_result_bound_to_request(self):
        r=example();out=run(r)
        r.task.actions[0].cost=2
        self.assertFalse(receipt(r,out).evidence_valid)

    def test_forged_host_authorization(self):
        r=example();out=run(r);out.host_approved=True
        self.assertFalse(receipt(r,out).evidence_valid)

    def test_unknown_proto_fields_rejected(self):
        r=example()
        raw=frame(r)+b'\xc0\x0c\x01'
        self.assertEqual(p.PlanningResult.FromString(PlanningRegistry(enabled=True).solve_frame(raw,host_authorized=True)).status,p.REJECTED)

    def test_audit_hashes_and_no_source_leak(self):
        r=example();out=run(r)
        aud=p.PlanningAudit.FromString(make_planning_audit(frame(r),frame(out)))
        self.assertEqual(aud.request_sha256,hashlib.sha256(frame(r)).digest())
        self.assertTrue(aud.evidence_valid)
        self.assertTrue(aud.optimality_verified)
        self.assertNotIn(b'at_start',frame(aud))

    def test_manifest_includes_mature_and_disabled_research(self):
        manifest=p.PlanningManifest.FromString(capability_manifest())
        self.assertTrue(verify_manifest(capability_manifest()))
        self.assertTrue(any(x.backend_id=='fast-downward' and not x.available for x in manifest.backends))
        self.assertEqual(sum(x.experimental for x in manifest.backends),3)
        manifest.backends[0].available=False
        self.assertFalse(verify_manifest(frame(manifest)))

    def test_pddl_export_is_restricted_and_typed(self):
        r=example()
        with self.assertRaises(PermissionError):
            export_pddl_frame(frame(r))
        output=p.PddlExport.FromString(export_pddl_frame(frame(r),host_authorized=True))
        self.assertIn('(:action act0',output.domain_pddl)
        self.assertIn('(:action act3',output.domain_pddl)
        self.assertIn('(increase (total-cost) 4)',output.domain_pddl)
        self.assertIn('(not (f0))',output.domain_pddl)
        self.assertNotIn('expensive_teleport',output.domain_pddl)
        self.assertIn('(:metric minimize (total-cost))',output.problem_pddl)
        self.assertEqual(output.request_sha256,hashlib.sha256(frame(r)).digest())

    def test_pddl_bad_domain_rejected(self):
        r=example();r.task.actions[0].id='(system command)'
        with self.assertRaises(ValueError):
            export_pddl_frame(frame(r),host_authorized=True)

    def test_small_random_graph_oracle(self):
        # Independent exhaustive shortest-path oracle over three Boolean facts.
        for seed in range(48):
            rng=random.Random(seed)
            r=p.PlanningRequest(schema_version=1,trace_id='seed',engine=p.ASTAR_HMAX,timeout_ms=2000)
            t=r.task;t.facts.extend(['a','b','c']);t.initial_true.append(0);t.goal_true.append(2)
            for i in range(5):
                x,y=rng.randrange(3),rng.randrange(3)
                t.actions.add(id=f'act{i}',require_true=[x],add=[y],cost=rng.randint(1,5))
            from collections import deque
            import heapq
            dist={1:0};q=[(0,1)]
            while q:
                cost,state=heapq.heappop(q)
                if dist[state]!=cost:continue
                for a in t.actions:
                    if state & (1<<a.require_true[0])==0:continue
                    nxt=state | (1<<a.add[0]);new=cost+a.cost
                    if new<dist.get(nxt,float('inf')):
                        dist[nxt]=new;heapq.heappush(q,(new,nxt))
            optimum=min((v for s,v in dist.items() if s & 4),default=None)
            out=run(r)
            if optimum is None:
                self.assertEqual(out.status,p.VERIFIED_UNREACHABLE)
            else:
                self.assertEqual(out.total_cost,optimum)
                self.assertEqual(out.status,p.VERIFIED_OPTIMAL)
            self.assertTrue(receipt(r,out).evidence_valid)

if __name__ == '__main__':unittest.main()
