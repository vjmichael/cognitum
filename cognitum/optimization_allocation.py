"""C11 bounded integer resource allocation via SciPy's mature HiGHS MIP.

No custom branch-and-bound, no raw model-authored solver scripts, no Lu rights.
The independent verifier checks integer solutions and hard constraints exactly.
"""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class Quantity:
    name: str
    lower: int
    upper: int
    cost: int


@dataclass(frozen=True)
class ResourceConstraint:
    coefficients: tuple[int, ...]
    relation: str
    rhs: int


@dataclass(frozen=True)
class AllocationProblem:
    quantities: tuple[Quantity, ...]
    constraints: tuple[ResourceConstraint, ...]
    unit: str = "item"


@dataclass(frozen=True)
class AllocationResult:
    status: str
    values: tuple[int, ...] = ()
    objective: int | None = None
    solver_bound: float | None = None
    gap: float | None = None
    backend: str = "scipy_highs_milp"
    limitations: tuple[str, ...] = ("input_semantics_not_verified", "solver_optimality_claim_unverified_independently")


def validate(problem: AllocationProblem) -> AllocationProblem:
    if type(problem) is not AllocationProblem or type(problem.quantities) is not tuple or type(problem.constraints) is not tuple:
        raise ValueError("typed allocation problem required")
    if not 1 <= len(problem.quantities) <= 16 or len(problem.constraints) > 64:
        raise ValueError("allocation dimensions exceed bound")
    if type(problem.unit) is not str or problem.unit not in ("item", "unit", "hour", "kg"):
        raise ValueError("unsupported allocation unit")
    names=set()
    for q in problem.quantities:
        if (type(q) is not Quantity or type(q.name) is not str
                or not q.name.isascii() or not q.name.isidentifier()
                or not 1 <= len(q.name) <= 32 or q.name in names
                or any(type(x) is not int for x in (q.lower,q.upper,q.cost))
                or not 0 <= q.lower <= q.upper <= 100
                or abs(q.cost) > 10000):
            raise ValueError("invalid allocation quantity")
        names.add(q.name)
    for row in problem.constraints:
        if (type(row) is not ResourceConstraint or row.relation not in ("le","ge","eq")
                or type(row.coefficients) is not tuple
                or len(row.coefficients) != len(problem.quantities)
                or any(type(c) is not int or abs(c) > 10000 for c in row.coefficients)
                or type(row.rhs) is not int or abs(row.rhs) > 100000000):
            raise ValueError("invalid resource constraint")
    return problem


def verify_allocation(problem: AllocationProblem, values: tuple[int, ...]) -> bool:
    validate(problem)
    if (type(values) is not tuple or len(values)!=len(problem.quantities)
            or any(type(v) is not int or not q.lower <= v <= q.upper
                   for q,v in zip(problem.quantities,values))):
        return False
    for row in problem.constraints:
        actual=sum(v*c for v,c in zip(values,row.coefficients))
        if (row.relation=="le" and actual>row.rhs
                or row.relation=="ge" and actual<row.rhs
                or row.relation=="eq" and actual!=row.rhs):
            return False
    return True


def minimize_allocation(problem: AllocationProblem, *, time_limit_ms: int = 3000) -> AllocationResult:
    validate(problem)
    if type(time_limit_ms) is not int or not 10 <= time_limit_ms <= 10000:
        raise ValueError("invalid allocation time budget")
    try:
        import numpy as np
        from scipy.optimize import milp, Bounds, LinearConstraint
    except ImportError:
        return AllocationResult("UNSUPPORTED",limitations=("scipy_highs_unavailable",))
    objective=np.array([q.cost for q in problem.quantities],dtype=np.float64)
    bounds=Bounds([q.lower for q in problem.quantities],
                  [q.upper for q in problem.quantities])
    constraints=[]
    if problem.constraints:
        a=np.asarray([r.coefficients for r in problem.constraints],dtype=np.float64)
        lower=np.asarray([r.rhs if r.relation in ("ge","eq") else -np.inf for r in problem.constraints])
        upper=np.asarray([r.rhs if r.relation in ("le","eq") else np.inf for r in problem.constraints])
        constraints=[LinearConstraint(a,lower,upper)]
    try:
        result=milp(c=objective,integrality=np.ones(len(problem.quantities),dtype=int),
                    bounds=bounds,constraints=constraints,
                    options={"time_limit":time_limit_ms/1000, "disp":False})
    except (ValueError,RuntimeError,MemoryError):
        return AllocationResult("UNKNOWN",limitations=("backend_solver_failure",))
    if result.status == 2:
        return AllocationResult("INFEASIBLE",limitations=("solver_reported_infeasible_not_independent_proof",))
    if result.x is None or len(result.x)!=len(problem.quantities):
        return AllocationResult("UNKNOWN",limitations=("no_incumbent",))
    if any(not isfinite(float(x)) or abs(float(x)-round(float(x)))>1e-6 for x in result.x):
        return AllocationResult("INVALID_SOLUTION",limitations=("nonintegral_incumbent",))
    values=tuple(int(round(float(x))) for x in result.x)
    if not verify_allocation(problem,values):
        return AllocationResult("INVALID_SOLUTION",limitations=("failed_exact_constraint_check",))
    exact=sum(q.cost*v for q,v in zip(problem.quantities,values))
    if result.fun is not None and abs(float(result.fun)-exact)>1e-5:
        return AllocationResult("INVALID_SOLUTION",limitations=("objective_mismatch",))
    raw_bound=getattr(result,"mip_dual_bound",None)
    bound=float(raw_bound) if raw_bound is not None and isfinite(float(raw_bound)) else None
    raw_gap=getattr(result,"mip_gap",None)
    gap=float(raw_gap) if raw_gap is not None and isfinite(float(raw_gap)) else None
    return AllocationResult(
        "OPTIMAL" if result.status==0 else "FEASIBLE",
        values,exact,bound,gap,
    )
