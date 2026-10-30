"""Five bounded, deterministic C12 planning functional smoke scenarios."""
from cognitum.planning import PlanningRegistry, verify_plan_frame, export_pddl_frame
from cognitum.proto import planning_pb2 as p


def build():
    req=p.PlanningRequest(schema_version=1, trace_id='c12-smoke', engine=p.NETWORKX_DIJKSTRA, timeout_ms=2000)
    task=req.task
    task.facts.extend(['home','key','opened','destination']);task.initial_true.append(0);task.goal_true.append(3)
    task.actions.add(id='take_key',require_true=[0],add=[1],cost=1)
    task.actions.add(id='unlock',require_true=[1],add=[2],cost=2)
    task.actions.add(id='travel',require_true=[2],add=[3],remove=[0],cost=3)
    task.actions.add(id='teleport',require_true=[0],add=[3],cost=30)
    return req


def test():
    cases = 0
    req=build()
    for algorithm in [p.NETWORKX_DIJKSTRA,p.ASTAR_HMAX,p.WEIGHTED_ASTAR_HMAX]:
        req.engine=algorithm
        payload=req.SerializeToString(deterministic=True)
        out_frame=PlanningRegistry(enabled=True).solve_frame(payload,host_authorized=True)
        result=p.PlanningResult.FromString(out_frame)
        receipt=p.PlanReceipt.FromString(verify_plan_frame(payload,out_frame))
        assert result.total_cost==6 and receipt.evidence_valid
        if algorithm == p.WEIGHTED_ASTAR_HMAX:
            assert result.status == p.VERIFIED_PLAN
        else:
            assert result.status == p.VERIFIED_OPTIMAL
        cases+=1
    req.engine=p.NETWORKX_DIJKSTRA
    payload=req.SerializeToString(deterministic=True)
    denial=p.PlanningResult.FromString(PlanningRegistry().solve_frame(payload,host_authorized=True))
    assert denial.status == p.REJECTED
    cases+=1
    exported=p.PddlExport.FromString(export_pddl_frame(payload,host_authorized=True))
    assert '(:requirements' in exported.domain_pddl and '(:metric minimize (total-cost))' in exported.problem_pddl
    cases+=1
    print(f'PASS: C12 classical planning smoke {cases}/{cases} scenarios')


if __name__=='__main__':test()
