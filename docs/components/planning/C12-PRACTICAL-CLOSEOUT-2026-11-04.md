# C12 — Deterministic Planning and Search: practical implementation closeout

**2026-11-04. Status:** bounded code implementation committed, native CI and merge pending. No Lu worker/runtime integration or model-level efficacy claim.

## Standard libraries first

We use **NetworkX** (maintained graph library) for shortest-path algorithms and graph traversal: Dijkstra for nonnegative action costs, A* with a zero/admissible heuristic, and unweighted shortest path for the fewest steps. A small DAG dynamic-programming reference operates on the same finite horizon-expanded graph and uses NetworkX's topological sort. This is not a custom production SAT/MCTS/optimization engine.

**PDDL adoption decision:** A conventional STRIPS PDDL library such as pyperplan is available, but carries GPLv3+ licensing; its distribution and product embedding require separate review. No PDDL parsing or model-authored executable scripts are admitted to the current typed protocol. OR-Tools supports powerful search/constraint optimization but isn't needed to reimplement a small deterministic graph shortest-path solver already provided by NetworkX. **MCTS intentionally deferred** because the v1 domain has deterministic transitions and an exact finite-state shortest-path formulation; stochastic rollout heuristics would add complexity without a justified benefit.

## Implemented code

- `cognitum/planning_graph.py`: immutable typed `Action`, `PlanProblem`, `PlanResult`. Positive and negative action preconditions, add/delete effects, positive/negative goal facts, nonnegative bounded action risk, strictly positive integer action cost, maximum plan horizon.
- Search engines `dijkstra`, `astar`, `bfs`, `dag_dp`; exhaustive reachable-state graph includes **state, elapsed steps and accumulated risk**. Each transition requires satisfied preconditions, time horizon and total risk budget.
- `check_plan`: independent action-by-action simulator that re-evaluates every precondition and applies effects, checks final goals, horizon, cumulative risk and exact integer total cost. It does **not** trust a planner's graph edges or claimed solution path.
- `proto/cognitum/planning/v1/planning.proto`, `cognitum/proto/planning_pb2.py` and `cognitum/planning_wire.py`: strict declarative native Protobuf inputs/outputs, canonical frame checking, request SHA-256 correlation (not authentication), independent plan witness checking on decode, and result status separation. No arbitrary user/model code, filesystem effects, network actions, or Lu grants.
- Tests `test_c12_graph.py`, `test_c12_wire.py`: path optimality compared to an independent Cartesian action sequence oracle, actual shortest-path backend calls, BFS step-vs-cost distinction, incomplete/invalid plans, risk, cycles, unreachable goals, zero-step success, invalid domains, Protobuf replay/forgery and unknown field rejection.
- `tools/c12_component_benchmark.py`: fixed production/risk/unreachable scenarios with actual measured native graph timings and independent replay of found plans.
- `.github/workflows/c12-planning.yml`: actual NetworkX Windows/Linux Python 3.11/3.13, independently compiled Protobuf descriptor parity, full component tests and fixed-case runtime benchmark.

## Bounded v1 contract

| Dimension | Bound |
|---|---|
| Facts | 1–12 ASCII identifier symbols |
| Actions | 1–24 deterministic declarative transition rules |
| Horizon | 0–12 steps |
| Risk budget | 0–30 total integer risk units |
| Action costs | positive integers 1–100 |
| Action risk | integers 0–10 |
| Graph | at most 4096 distinct expanded nodes and 40000 directed edges |
| Goal | positive and prohibited fact sets |
| Solvers | NetworkX Dijkstra, A*, BFS, DAG-based DP |

**Risk measures are symbolic caller-provided bounds**, not calibrated real-world probabilities; they must never be presented as safe-world operational risk estimates.

## Result evidence

- `OPTIMAL`: NetworkX search over a **fully enumerated bounded graph** found a minimum action-cost plan. For unweighted BFS this label applies only if all action costs are equal; otherwise the solution is `FEASIBLE`, not automatically cost-optimal.
- `FEASIBLE`: independent simulator accepts every step and final state, but a truncated graph or differing-cost BFS does not establish minimum cost.
- `UNREACHABLE_EXHAUSTIVE`: complete reachable graph within the **specified horizon and risk budget** has no goal, not a universal theorem over arbitrary longer horizons.
- `UNKNOWN_LIMIT`: state/edge budget reached before proving no plan. Do not falsely call this impossible.
- `UNSUPPORTED`: optional real NetworkX library missing.
- `INVALID_SOLUTION`: action sequence failed exact independent replay. Never present as usable.

The Protobuf decoder independently verifies returned plan witnesses, but does not independently certify a remote result's `OPTIMAL` label or `UNREACHABLE_EXHAUSTIVE` claim. Those statuses are components' algorithm-reported conclusions, conditioned on bounded graph completeness. Neither user intent nor the correctness of an LLM's selected facts/actions is certified.

## Deployment and evaluation gates

- Native CI acceptance must pass on the exact branch head; until then, do not merge or call tests verified.
- Lu owner components C02/C04 must authorize/tool-scope and OS-isolate workers; this module NEVER executes planned real-world actions. A plan's output is merely a proposed sequence.
- C03 needs matched conventional planner comparisons on real goals and explicit testing of natural-language-to-domain formalization failures, latency, human acceptance and unsafe-effect prevention.
- Do not expand to stochastic MCTS, PDDL or arbitrary action scripts unless a demonstrated application needs it and licenses/security constraints are met.

## Stop rule

After successful native CI and merge, C12's bounded **deterministic planning component** can be closed, with stochastic/policy exploration identified as deferred—not incorrectly claimed as implemented. Avoid a C14-style research optimization marathon.

## Additional established-library cross-validation

The optional `planning-validation` extra installs **Unified Planning**,
an Apache-licensed maintained framework. `cognitum/planning_unified.py`
constructs its Boolean-fluent STRIPS problem strictly from already validated
typed facts, requirements and effects. It checks a `SequentialPlan` through
Unified Planning's built-in `sequential_plan_validator`, **without generating
or executing external PDDL/model scripts**.

The second library's verdict is independent of Cognitum's NetworkX
shortest-path graph and custom fact transition replay. The UP Boolean
semantics do not by themselves certify **risk budgets, horizon limits or
integer costs**, which remain enforced by C12's exact `check_plan` replay.
Therefore `VALID` requires both independent Boolean plan validation and
the original bounded risk/horizon checks. No optimality is inferred from a
`VALID` plan-validation result.

`tests/test_c12_unified.py` includes positive, negative, incorrect-action,
invalid-goal and risk-budget samples, and checks a real NetworkX-generated plan
using the independent Unified Planning engine. The cross-platform C12 native
workflow installs both optional packages; missing libraries cannot count as
positive native acceptance.
