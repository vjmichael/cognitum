# C11 P2 — Domain-specific Combinatorial Workflows (2026-10-27)

## Engineering intent and maturity

**Implemented**: Protobuf-native bounded problems for assignment, 0/1 packing, minimum-cost capacitated flow, resource-constrained scheduling with precedences, and symmetric depot-based routing. These are specialized combinatorial formulations layered on mature offline libraries, **not** new solver algorithms or a production-ready Lu extension.

Established library paths:

| Domain | Mature implementation exercised here | Status and scope |
|---|---|---|
| Assignment | SciPy `scipy.optimize.linear_sum_assignment` | Rectangular worker/job cost minimization, explicitly allowed pair edges |
| 0/1 Packing | SciPy `optimize.milp` → HiGHS | Integer 0/1 knapsack with weighted capacity, maximize value |
| Minimum-cost flow | NetworkX `network_simplex` | Integer capacities and node supplies, integral minimum-cost feasible flow |
| Scheduling | SciPy `optimize.milp` → HiGHS | Bounded time-indexed integer start/finish, resource capacity, precedence, minimum makespan |
| Routing | NetworkX `greedy_tsp` | Undirected complete symmetric costs, depot node 0, heuristic candidate Hamiltonian tour |
| Scheduling (optional) | OR-Tools CP-SAT `new_interval_var`, `add_cumulative` | Adapter implemented but **not runtime-exercised** here because `ortools` is not installed |

References: [OR-Tools scheduling](https://github.com/google/or-tools/blob/stable/ortools/sat/docs/scheduling.md), [SciPy MILP](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html), [NetworkX network simplex](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.flow.network_simplex.html), [NetworkX greedy TSP](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.approximation.traveling_salesman.greedy_tsp.html). Maintain a separate experimental track for learned branching, LNS, scheduling or routing research; do not equate paper claims with practical superiority until matched future benchmark campaigns.

## Strict typed interface

- `proto/cognitum/optimization/v1/workflows.proto`, compiled descriptor-backed `cognitum/proto/workflows_pb2.py` (package `cognitum.optimization.workflow.v1` to avoid P1 package enum-name collisions).
- `WorkflowRequest` uses a Protobuf `oneof` problem; `backend_id` is a finite allowlist. No model-supplied Python, SMT source, filesystem paths, shell commands, Python imports or arbitrary payload evaluation.
- `WorkflowRegistry` defaults disabled, needs `host_authorized=True` **synthetic test gate**, and has a `disable()` switch. **This is not actual Lu host authentication, native tool permission or OS worker isolation.** Disabled registry accepts no new requests.
- Fixed limits: max 10 workers/10 jobs, 32 packing items, 16 flow nodes/64 arcs, 10 tasks/8 resources/horizon 40, or 10 routing nodes; nonnegative finite-capacity domains, at most 5,000 ms *advisory* backend time. Some library calls lack an interruption API; a host OS process kill/timeout remains a production prerequisite.
- Each result contains request-frame SHA-256 digest, backend ID, backend version, backend claim (untrusted), typed witness, exact arithmetic assurance flags, wall time, explicit unknown/rejected states and trace ID. SHA-256 digests provide integrity correlation but not authentication nor confidentiality.

## Verification and truthful proof semantics

1. Independent `verify_workflow_frame(request, result)` recomputes request digest binding, validates the exact domain-specific constraints, and recomputes each objective using integer arithmetic, without invoking SciPy, NetworkX, or OR-Tools. Rejects tampered assignments, capacity violations, duplicated choices, flow-conservation errors, precedence/resource overloads, repeated/missing tour nodes, mismatched objectives and forged host approval.
2. Up to **4,096 fully enumerated feasible-or-infeasible candidate states**, the independent `_finite_oracle` exhaustively checks the bounded domain and certifies the specific optimum or infeasibility. Larger domains produce at most `VERIFIED_FEASIBLE` for a valid witness, even if a mature solver reports OPTIMAL; unsupported or unverifiable UNSAT claims become `UNKNOWN`.
3. Routing is **heuristic** through NetworkX by default: a valid route is not necessarily optimal. Small-instance exhaustive checks can establish optimality when the candidate attains the independent minimum. No universal optimal-route claim.
4. `make_workflow_audit` creates a result/request-bound, data-minimized Protobuf record with no raw problem or solution data. It is **not a signed Lu host record**; source data may still be inferred from low-entropy hashes and must be protected by Lu.
5. Exact arithmetic receipts verify the supplied *formalized* problem, not whether the AI interpreted a natural-language task correctly.

## Functional validation and future gates

`PYTHONPATH=.:tests python -m unittest tests.test_c11_workflows -q` tests five real backends, independent random small-case oracles, forged receipts, infeasibility, backend allowlists and hard failure semantics. `PYTHONPATH=. python tools/run_c11_p2_smoke.py` runs five deterministic end-to-end workflows. `PYTHONPATH=. python tools/verify_protobuf_schemas.py --require` checks all checked-in `.proto` descriptors against actual compiler output. No broad comparative or model performance benchmark is authorized in this phase.

**Not implemented or verified:** hard OS cancellation, OS worker isolation, Lu grants, Windows x86-64 binaries/installer, OR-Tools runtime, vehicle capacities/multi-depot VRP/time windows, stochastic scheduling, geometric 2D/3D packing, generalized nonlinear integer programming, arbitrary custom solver plugins, or performance superiority over established solvers. C11 P3 can handle backend manifests, experimental extension contracts, safe subprocess lifecycle and Lu benchmark hook compatibility; C12 planning may proceed after essential C11 P2 works.
