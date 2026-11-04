"""C11 bounded scheduling using Google's established OR-Tools CP-SAT engine.

Trusted in-process development adapter, NOT a Lu tool, OS sandbox or host
authorization. User intent is not inferred from the typed task input.
"""
from dataclasses import dataclass
from typing import Tuple

MAX_TASKS = 16
MAX_RESOURCES = 8
MAX_HORIZON = 128


@dataclass(frozen=True)
class Job:
    name: str
    duration: int
    release: int
    deadline: int
    eligible_resources: tuple[str, ...]
    after: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScheduleProblem:
    horizon: int
    resources: tuple[str, ...]
    jobs: tuple[Job, ...]
    unit: str = "slot"


@dataclass(frozen=True)
class ScheduledJob:
    name: str
    resource: str
    start: int
    end: int


@dataclass(frozen=True)
class ScheduleResult:
    status: str
    assignments: tuple[ScheduledJob, ...] = ()
    makespan: int | None = None
    solver_bound: float | None = None
    backend: str = "ortools_cp_sat"
    limitations: tuple[str, ...] = ("input_semantics_not_verified", "solver_status_not_independent_proof")


def validate(problem: ScheduleProblem) -> ScheduleProblem:
    if type(problem) is not ScheduleProblem or type(problem.horizon) is not int or not 1 <= problem.horizon <= MAX_HORIZON:
        raise ValueError("invalid scheduling horizon")
    if type(problem.unit) is not str or problem.unit not in ("slot", "minute", "hour", "day"):
        raise ValueError("unsupported scheduling unit")
    if (type(problem.resources) is not tuple or not 1 <= len(problem.resources) <= MAX_RESOURCES
            or type(problem.jobs) is not tuple or not 1 <= len(problem.jobs) <= MAX_TASKS):
        raise ValueError("scheduling size exceeded")
    def ident(s):
        return type(s) is str and 1 <= len(s) <= 32 and s.isascii() and s.isidentifier()
    if any(not ident(r) for r in problem.resources) or len(set(problem.resources)) != len(problem.resources):
        raise ValueError("invalid resources")
    names = set()
    for job in problem.jobs:
        if type(job) is not Job or not ident(job.name) or job.name in names:
            raise ValueError("invalid job identity")
        names.add(job.name)
        if (any(type(v) is not int for v in (job.duration, job.release, job.deadline))
                or not 1 <= job.duration <= problem.horizon
                or not 0 <= job.release < job.deadline <= problem.horizon):
            raise ValueError("invalid job temporal bounds")
        if (type(job.eligible_resources) is not tuple or not job.eligible_resources
                or len(set(job.eligible_resources)) != len(job.eligible_resources)
                or any(r not in problem.resources for r in job.eligible_resources)
                or type(job.after) is not tuple or len(set(job.after)) != len(job.after)):
            raise ValueError("invalid resources or precedence")
    graph = {j.name: j.after for j in problem.jobs}
    if any(dep not in graph for j in problem.jobs for dep in j.after):
        raise ValueError("unknown prerequisite")
    visit = set()
    active = set()
    def check(name):
        if name in active: raise ValueError("cyclic job dependencies")
        if name in visit: return
        active.add(name)
        for dep in graph[name]: check(dep)
        active.remove(name)
        visit.add(name)
    for name in graph: check(name)
    return problem


def verify_schedule(problem: ScheduleProblem, assignments: tuple[ScheduledJob, ...]) -> bool:
    """Independent validation of all temporal/resource/precedence constraints."""
    validate(problem)
    if type(assignments) is not tuple or len(assignments) != len(problem.jobs):
        return False
    by_name = {j.name: j for j in problem.jobs}
    seen = {}
    for item in assignments:
        if type(item) is not ScheduledJob or item.name not in by_name or item.name in seen:
            return False
        job = by_name[item.name]
        if (item.resource not in job.eligible_resources
                or type(item.start) is not int or type(item.end) is not int
                or item.start < job.release or item.end > job.deadline
                or item.end - item.start != job.duration):
            return False
        seen[item.name] = item
    for job in problem.jobs:
        if any(seen[dep].end > seen[job.name].start for dep in job.after):
            return False
    for i,a in enumerate(assignments):
        for b in assignments[i+1:]:
            if a.resource == b.resource and a.start < b.end and b.start < a.end:
                return False
    return True


def optimize_schedule(problem: ScheduleProblem, *, time_limit_ms: int = 3000) -> ScheduleResult:
    validate(problem)
    if type(time_limit_ms) is not int or not 10 <= time_limit_ms <= 10000:
        raise ValueError("invalid scheduling time budget")
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        return ScheduleResult("UNSUPPORTED",limitations=("ortools_not_installed",))
    model = cp_model.CpModel()
    starts = {}
    ends = {}
    resource_intervals = {resource: [] for resource in problem.resources}
    choices = {}
    for job in problem.jobs:
        start = model.new_int_var(job.release, job.deadline-job.duration, "start_"+job.name) if job.release <= job.deadline-job.duration else None
        if start is None:
            return ScheduleResult("INFEASIBLE",limitations=("trivial_time_window_contradiction",))
        end = model.new_int_var(job.release+job.duration, job.deadline, "end_"+job.name)
        model.add(end == start+job.duration)
        starts[job.name], ends[job.name] = start, end
        present = []
        for resource in job.eligible_resources:
            selector = model.new_bool_var("use_"+job.name+"_"+resource)
            interval = model.new_optional_interval_var(start,job.duration,end,selector,
                                                       "slot_"+job.name+"_"+resource)
            resource_intervals[resource].append(interval)
            present.append(selector)
            choices[(job.name,resource)] = selector
        model.add_exactly_one(present)
    for job in problem.jobs:
        for predecessor in job.after:
            model.add(starts[job.name] >= ends[predecessor])
    for intervals in resource_intervals.values():
        model.add_no_overlap(intervals)
    makespan = model.new_int_var(0,problem.horizon,"makespan")
    model.add_max_equality(makespan,[ends[j.name] for j in problem.jobs])
    model.minimize(makespan)
    solver=cp_model.CpSolver()
    solver.parameters.max_time_in_seconds=time_limit_ms/1000
    solver.parameters.num_search_workers=1
    state=solver.solve(model)
    if state not in (cp_model.OPTIMAL,cp_model.FEASIBLE):
        return ScheduleResult("INFEASIBLE" if state==cp_model.INFEASIBLE else "UNKNOWN")
    result=tuple(ScheduledJob(job.name,
              next(resource for resource in job.eligible_resources
                   if solver.value(choices[(job.name,resource)])==1),
              solver.value(starts[job.name]),solver.value(ends[job.name]))
              for job in problem.jobs)
    if not verify_schedule(problem,result):
        return ScheduleResult("INVALID_SOLUTION",limitations=("independent_schedule_check_failed",))
    actual=max(x.end for x in result)
    if actual != int(solver.objective_value):
        return ScheduleResult("INVALID_SOLUTION",limitations=("objective_mismatch",))
    return ScheduleResult(
        "OPTIMAL" if state==cp_model.OPTIMAL else "FEASIBLE",
        result,actual,float(solver.best_objective_bound),
        limitations=("input_semantics_not_verified","solver_optimality_claim_unverified_independently"),
    )
