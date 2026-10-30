# C12 P3 — Stochastic decision planning, ordered HTN, and temporal precedence

**2026-10-27.** Status: *offline bounded Python reference with Protobuf-native contracts and independent result checks*. This is functional capability engineering, **not a real Lu-installed CE, unrestricted PDDL/HDDL engine, strong OS sandbox, model evaluation, or production certification**.

## Established landscape / design rationale

1. **Finite-horizon MDP planning** follows conventional Bellman backward induction and policy evaluation; the established Python MDP Toolbox supports `FiniteHorizon`, `ValueIteration`, `PolicyIteration`, and other methods: https://pymdptoolbox.readthedocs.io/en/latest/api/mdp.html . It is **not installed or runtime-tested** in the current test container. The P3 implementation is a compact exact-math reference for the supported finite known-model subset, not a replacement for all of PyMDPtoolbox. Future adapter should use identical typed models and independent rechecking.
2. **UCT MCTS** uses the standard selection/expansion/stochastic-rollout/backpropagation structure and UCB selection pioneered by Kocsis and Szepesvári. Overview: https://mcts.ai/about/index.html . UCT is a statistical search heuristic; this implementation never marks its chosen action or value estimate as proven optimal. Research candidates (learned priors, PUCT, Gumbel/other search variants) are **not** installed and remain host-opt-in backends with future empirical review.
3. **Temporal and hierarchical planning** are separate requirements. Unified Planning maintains engines including Aries for HTN and scheduling and Tamer/LPG for selected temporal planning tasks, subject to version and feature compatibility: https://unified-planning.readthedocs.io/en/stable/engines/01_available_engines.html . These engines are **not runtime-tested** in this environment. Current local temporal module handles *resource-free precedence scheduling*; the ordered HTN module handles *grounded acyclic method decomposition*. Neither represents full HDDL, durative PDDL2.1, partially ordered HTN, or continuous uncertainty.
4. **NetworkX** is used directly for temporal DAG topological scheduling, with an independent, library-free Kahn/topological validator. NetworkX graph operations are also used in C12 P1. Licensed deployment should review optional solver licensing separately from the Protobuf API.

## Implemented capability boundaries

### Stochastic finite-horizon planning

- Native `proto/cognitum/planning/v1/stochastic.proto` and `cognitum/proto/planning_stochastic_pb2.py` (compiler-verified): state/action/outcome tables, exact parts-per-million probabilities summing to 1,000,000 for each `(state,action)`, signed integer millirewards, terminal values, discount and horizon, method, seed and bounded simulation budget.
- `cognitum/planning_stochastic.py`: exact `Fraction` Bellman recursion for up to 24 states, 128 state/action entries, 8 outcomes/action, horizon <= 12; independent evaluator checks every returned stage/state policy and all Bellman inequalities. The independently checked claim is conditional on **the supplied model** and is not evidence that the real world follows its probabilities/rewards.
- UCT MCTS with seeded stochastic outcomes, exploration, rollouts and backpropagation (<= 2,000 simulations). Its estimate is **not** a proof of optimality or calibrated uncertainty. A seed-based rerun can detect record tampering, but *does not independently validate the stochastic optimization quality*. Use the final performance campaign for actual comparisons. Host authority and policy remain separate from model choices.

### Bounded ordered hierarchical planning

- Native `proto/cognitum/planning/v1/structured.proto`: alternative acyclic grounded ordered methods, root tasks, canonical P1 ClassicalPlanningRequest bytes, bounded expansions, native plan/result/receipt/audit.
- `cognitum/planning_structured.py`: enumerates alternative hierarchical decompositions, replays resulting primitive action indexes with P1's independent STRIPS replay verifier, can certify minimum cost **among the completely enumerated permitted HTN decompositions**. Bounds/cycles/unknown tasks fail closed; incomplete search yields a verified witness or `UNKNOWN`, never an impossible-world claim. A separate breadth-first enumerator and grammar witness checker validate complete certificates.
- **Does not infer hierarchical methods from natural language**; does not support resources, parallel or partial-order HTN, task preferences, sensing or effects outside P1.

### Resource-free temporal precedence planning

- Typed precedence DAG actions with integer duration, release time, optional latest finish; NetworkX finds earliest feasible starts and minimum makespan for the precedence-only problem. Infeasibility from positive-duration cycles or violated earliest deadlines can be independently certified using a separate Kahn-style checker. This does not handle resource conflicts, uncertain durations, numeric durative PDDL effects, motion constraints, or time windows requiring disjunctive reasoning. C11 scheduling handles a different resource-constrained optimization subset.

## Security, audit, and verification

- Protobuf wire schemas, canonical input frame checking, bounded dimensions and replay/rational checks; no model-supplied executable, Python source, shell command, PDDL, or direct actions.
- The `enabled` and `host_authorized` Python booleans are **test placeholders**, not Lu native grants. Native host authorization, resource fencing and Windows Job Objects remain production gates.
- SHA-256 request/result digests in receipts and data-minimized audits are *integrity linkage*, not signatures, tamperproof storage, source authentication or OS isolation.
- DP exact values and HTN complete optimality are independently checked within explicit input domains. MCTS estimate is not a proof. Finite temporal scheduling is verified for the typed restricted constraints. Time budgets are cooperative, not hard process ceilings.

## Focused functional tests (no performance campaign)

- `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=.:tests python -m unittest tests.test_c12_p3_stochastic tests.test_c12_p3_structured -q` — stochastic, HTN, temporal functional and tamper checks, including small seeded math/graph cases.
- `PYTHONPATH=.:tests python tools/run_c12_p3_smoke.py` — 5 deterministic smoke scenarios.
- `PYTHONPATH=. python tools/verify_protobuf_schemas.py --require` — `.proto` compiler versus checked-in binding validation.
- Full regression suite must pass across completed groups. Benchmark campaigns and real loaded-model results remain deferred by user decision.

## Further C12 work and honest gaps

A future C12 planning integration phase should: integrate and independently exercise actual Unified Planning temporal/HTN engines (Aries/Tamer/LPG as compatible), real Fast Downward, and PyMDPtoolbox where useful; expand to PDDL2.1/HDDL with explicit feature negotiation, partial-order planning, temporal resource and uncertainty constraints, stochastic POMDP/contingent planning, DP on larger or infinite-horizon discounted models and optional research search guidance. C12 P4 may define research-backend provenance, sandbox, default-off dispatch and Lu benchmark protocol alignment. No research improvement should be asserted without feature-matched empirical comparison after the full component portfolio is built.
