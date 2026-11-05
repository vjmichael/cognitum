"""C11 reproducible component benchmark — genuine incumbent libraries, no fake results.

Run with installed optimization-schedule,optimization-mip extras.
Prints deterministic JSON with exact feasibility and measured local timings.
Not a Lu/model A/B benchmark, and no claim of wall-clock reproducibility.
"""
import json
import platform
import sys
from time import perf_counter, process_time

from cognitum.optimization_schedule import Job, ScheduleProblem, verify_schedule, optimize_schedule
from cognitum.optimization_allocation import (
    Quantity, ResourceConstraint, AllocationProblem, verify_allocation, minimize_allocation,
)


def scenarios():
    return (
        ("schedule_sequential", "schedule", ScheduleProblem(
            20,("craft","paint"),(
                Job("cut",4,0,18,("craft",)),
                Job("polish",3,0,20,("craft","paint"),("cut",)),
                Job("final",2,0,20,("paint",),("polish",)),
            ))),
        ("schedule_parallel", "schedule", ScheduleProblem(
            12,("a","b"),(
                Job("one",4,0,12,("a","b")),
                Job("two",4,0,12,("a","b")),
                Job("three",2,0,12,("a","b"),("one",)),
            ))),
        ("schedule_infeasible", "schedule", ScheduleProblem(
            4,("only",),(
                Job("a",4,0,4,("only",)),
                Job("b",4,0,4,("only",)),
            ))),
        ("allocate_inventory", "allocation", AllocationProblem(
            (Quantity("a",0,10,7),Quantity("b",0,12,2),Quantity("c",0,4,1)),
            (ResourceConstraint((1,1,1),"ge",10),
             ResourceConstraint((0,1,2),"le",18)),
        )),
        ("allocate_conflicting", "allocation", AllocationProblem(
            (Quantity("a",0,5,1),),
            (ResourceConstraint((1,),"le",1),ResourceConstraint((1,),"ge",4)),
        )),
    )


def run():
    recorded=[]
    for name,kind,problem in scenarios():
        start_cpu=process_time()
        start_wall=perf_counter()
        result=(optimize_schedule(problem,time_limit_ms=5000) if kind=="schedule"
                else minimize_allocation(problem,time_limit_ms=5000))
        cpu_ms=round(1000*(process_time()-start_cpu),3)
        wall_ms=round(1000*(perf_counter()-start_wall),3)
        if kind=="schedule":
            valid=verify_schedule(problem,result.assignments) if result.assignments else None
            objective=result.makespan
        else:
            valid=verify_allocation(problem,result.values) if result.values else None
            objective=result.objective
        if result.status in ("OPTIMAL","FEASIBLE") and valid is not True:
            raise RuntimeError("benchmark returned unchecked invalid candidate: "+name)
        if result.status in ("UNKNOWN","UNSUPPORTED","INVALID_SOLUTION"):
            raise RuntimeError("native C11 solver did not provide expected answer: "+name+": "+result.status)
        if name.endswith("infeasible") or name.endswith("conflicting"):
            if result.status!="INFEASIBLE":
                raise RuntimeError("expected inconsistent model: "+name)
        elif result.status not in ("OPTIMAL","FEASIBLE"):
            raise RuntimeError("expected usable incumbent: "+name)
        recorded.append(dict(case=name,backend=result.backend,status=result.status,
                             exact_objective=objective,feasibility_validated=valid,
                             wall_ms=wall_ms,cpu_ms=cpu_ms))
    output=dict(schema_version=1,benchmark="C11_fixed_component_incumbent",
                python=sys.version.split()[0],platform=platform.platform(),
                trials=recorded,limitations=[
                    "native_solver_in_process_not_os_isolated",
                    "not_Lu_model_A_B_or_user_task_performance",
                    "single_run_timings_no_energy_or_peak_native_memory",
                    "solver_optimality_claim_not_independently_proved",
                ])
    print(json.dumps(output,sort_keys=True,indent=2))


if __name__=="__main__":
    run()
