"""C12 fixed-case native NetworkX benchmark, no invented timings.

Not a Lu model-planning A/B test, not a production host/sandbox, and not
a stochastic Monte Carlo tree search benchmark.
"""
import json
import platform
from time import perf_counter,process_time
from cognitum.planning_graph import Action,PlanProblem,plan,check_plan


def cases():
    production=PlanProblem(
        facts=("raw","assembled","tested","shipped"),
        initial=("raw",),goal=("shipped",),goal_forbids=("raw",),
        actions=(
            Action("build",requires=("raw",),add=("assembled",),
                   delete=("raw",),cost=2),
            Action("inspect",requires=("assembled",),add=("tested",),cost=3),
            Action("send",requires=("tested",),add=("shipped",),cost=1),
            Action("emergency_send",requires=("raw",),add=("shipped",),
                   delete=("raw",),cost=20),
        ),horizon=5)
    unreachable=PlanProblem(
        facts=("unavailable","goal"),initial=(),goal=("goal",),
        goal_forbids=(),actions=(Action("wait",requires=("unavailable",)),),
        horizon=7)
    risk=PlanProblem(
        facts=("at_start","at_goal"),initial=("at_start",),
        goal=("at_goal",),goal_forbids=("at_start",),
        actions=(Action("safe",requires=("at_start",),add=("at_goal",),
                        delete=("at_start",),cost=6,risk=0),
                 Action("unsafe",requires=("at_start",),add=("at_goal",),
                        delete=("at_start",),cost=1,risk=2)),
        horizon=2,risk_budget=0)
    return (("production",production),("unreachable",unreachable),
            ("risk_guard",risk))


def main():
    results=[]
    for name,problem in cases():
        for algorithm in ("dijkstra","astar","bfs","dag_dp"):
            wall=perf_counter();cpu=process_time()
            r=plan(problem,algorithm=algorithm)
            measured_wall=round(1000*(perf_counter()-wall),3)
            measured_cpu=round(1000*(process_time()-cpu),3)
            if r.status in ("OPTIMAL","FEASIBLE"):
                checked=check_plan(problem,r.actions)
                if checked is None or checked[1]!=r.total_cost:
                    raise RuntimeError("C12 benchmark plan was not independently valid")
            elif name!="unreachable" or r.status!="UNREACHABLE_EXHAUSTIVE":
                raise RuntimeError("C12 benchmark failed "+name+" "+algorithm+" "+r.status)
            results.append(dict(case=name,algorithm=algorithm,
                status=r.status,steps=list(r.actions),cost=r.total_cost,
                expanded_states=r.expanded_states,
                wall_ms=measured_wall,cpu_ms=measured_cpu,
                independently_validated=r.status in ("OPTIMAL","FEASIBLE")))
    output={"schema_version":1,"benchmark":"C12_deterministic_graph_planning",
            "platform":platform.platform(),"cases":results,
            "limitations":["not_Lu_model_A_B",
                           "single_run_timing_not_precision_latency",
                           "not_OS_isolated_host",
                           "caller_supplied_symbolic_domain_not_authenticated",
                           "no_stochastic_MCTS_efficacy_claim"]}
    print(json.dumps(output,sort_keys=True,indent=2))


if __name__=="__main__":
    main()
