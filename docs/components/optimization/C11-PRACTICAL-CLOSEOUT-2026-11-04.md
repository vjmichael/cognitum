# C11 — Combinatorial Optimization and Scheduling: practical component closeout

**Date:** November 4, 2026.
**Status:** Implementation committed; native acceptance and merge require CI evidence.
**Primary decision:** Mature solver engines first; **no bespoke scheduler/MIP solver**.

## Problem and implementation

C11 accepts only prevalidated, **typed scheduling** or **integer allocation** tasks and returns feasible candidate assignments with independently checked hard constraints and exact integer objectives.

- **Scheduling:** Google OR-Tools CP-SAT. Resource-assigned jobs with integer duration/release/deadline, eligibility, precedence, no-overlap, explicit slot units, and minimum makespan objective.
- **Allocation:** SciPy `scipy.optimize.milp` (HiGHS backend). Bounded nonnegative integer quantities, explicit item/unit/hour/kg unit tag, linear `<=`, `>=`, `==` hard resource constraints, and linear minimization cost. This is the existing mature MIP engine, not custom branch-and-bound.
- **Contracts:** `proto/cognitum/optimization/v1/optimization.proto`, checked-in descriptor-backed `optimization_pb2.py`, independent domain dispatch in `optimization_wire.py`. Strict canonical wire checks, request SHA-256 correlation (NOT authorization), negative and malformed-frame rejection. No executable code/solver scripts enter the wire.
- **Validation:** exact `verify_schedule` enforces durations, windows, precedence, assignment resource eligibility and pairwise nonoverlap. `verify_allocation` checks exact integer bounds and all original resource constraints. The decoder rechecks feasible results and objective consistency independently before handing results back.

## Explicit bounded v1 scope

| Dimension | Scheduling | Integer allocation |
|---|---|---|
| Engine | OR-Tools CP-SAT | SciPy/HiGHS MILP |
| Number of decision items | 1–16 jobs | 1–16 integer quantities |
| Resources / constraints | 1–8 resources | up to 64 linear constraints |
| Time / quantity bound | 1–128 slots | each integer quantity in [0,100] |
| Other model constraints | precedence, eligible resource, release/deadline | <=10000 integer coefficients, <=100000000 RHS |
| Runtime solver budget | 10–10000 ms | 10–10000 ms |
| Objective | minimum makespan | minimum integer linear cost |
| Unit tag | slot/minute/hour/day (uniform) | item/unit/hour/kg (uniform) |

The unit labels are **caller-declared**, not dimensionally proven. Mixed physical units, stochastic scheduling, multiobjective preferences, soft constraint penalties, optimization over arbitrary languages, numerical real arithmetic LP, maintenance calendars, network flows, continuous MIP variables and project-level workforce management are not exposed by this narrow first-party typed adapter. The underlying established libraries can solve many richer problems, but those capabilities must have explicit validated input contracts.

## Result semantics (do not overclaim)

- **OPTIMAL**: a trusted native solver returned `OPTIMAL` and the independent checker validated the candidate and objective. The optimality *proof* is **solver-reported**, not independently certified by Cognitum.
- **FEASIBLE**: a candidate satisfies **every independently checked hard constraint**, but optimality is not established.
- **INFEASIBLE**: solver reported no feasible solution or an objectively impossible single-job window was detected. General infeasibility does **not** currently carry independently verified Farkas/SAT unsat certificates.
- **UNKNOWN**: no usable incumbent established within budget, no solver proof, or backend error.
- **UNSUPPORTED**: optional real backend unavailable.
- **INVALID_SOLUTION**: solver provided a candidate that fails independent exact verification; never pass it through as usable.

Bound/gap metadata is an **advisory native solver report**, not an independent certificate. Never turn a gap or status into a false objective guarantee.

## Verification and artifacts

- `tests/test_c11_schedule.py`: feasibility verifier negative cases, cyclic/invalid precedence and eligibility, actual CP-SAT optimum for small fixtures, independently enumerated 3-job global optimum, no-overlap infeasibility.
- `tests/test_c11_allocation.py`: exact quantity/constraint checks, actual SciPy/HiGHS MIP optimum, independent exhaustive 2-variable minimum, conflict infeasibility, negative costs and bad input.
- `tests/test_c11_wire.py`: native end-to-end Protobuf requests with real solver backends, strict noncanonical frame/unknown field refusal, forged feasible/optimal results and illegal units.
- `.github/workflows/c11-optimization.yml`: Windows/Linux × Python 3.11/3.13 installs actual engines, proves imports and `pip check`, executes regression and independently compiles the Protobuf schema for binding parity.

**Acceptance:** no native-CI PASS is claimed until the relevant head SHA workflows complete. The branch is intentionally unmerged until that evidence exists.

## Library adoption and distribution

Preferred dependencies: maintained `ortools`, `scipy`/HiGHS and `numpy`; separate optional `optimization-schedule` and `optimization-mip` extras in `pyproject.toml`, not forced into Cognitum core. Review exact shipped library versions, C/C++ binary provenance, redistribution licenses and platform availability before final Lu packaging.

Lu host authority, native worker process confinement/cancellation, C03 real-model formalization and baseline comparisons, temporal data provenance, and model-tool discoverability remain separate integration gates. A typed solver can validate a stated model; it **cannot** establish that an LLM chose the right model or business constraints.

## Stop rule

No C14-style optimization/research escalation. C11 implementation scope is frozen at two competent mature conventional solver engines, strict domain contracts and independent candidate checking. Expand only for a demonstrated task gap. Merge after real acceptance passes. C10 proof-checker work and C05 closure are independent workstreams, not preconditions to running C11 component reference tests.
