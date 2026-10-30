# Cognitum C12 P0–P1 — classical planning, bounded graph search, audit and research interfaces

**Checkpoint:** 2026-10-27. **Maturity:** Linux Python reference with real NetworkX backend; not native Lu, not production hardened.

## Standards-first inventory

- **PDDL / STRIPS / action costs:** established symbolic planning interchange. Fast Downward translates PDDL to SAS+ and supports PDDL 2.2 level 1 with action costs; it is not a temporal or unrestricted numerical planner. Docs: https://www.fast-downward.org/latest/documentation/planner-usage/ and https://www.fast-downward.org/24.06/documentation/pddl-support/ . Upstream license GPL-3.0-or-later: https://github.com/aibasel/downward . Review separate executable distribution and GPL obligations before bundling.
- **Unified Planning:** maintained, planner-neutral Python framework; supports problem models, PDDL/ANML import/export and integrations with Fast Downward, ENHSP, LPG and others depending on backend and requirements. Apache-2.0 (review bundled solver licenses independently). Docs: https://unified-planning.readthedocs.io/en/latest/ and https://unified-planning.readthedocs.io/en/stable/engines/01_available_engines.html . Not installed or tested here.
- **NetworkX:** mature, BSD-3-Clause graph library used *directly* for Dijkstra/BFS and independently checking finite reachable-state paths (https://networkx.org/documentation/stable/). Available and executed in P1.
- **Conventional heuristic planning:** A* with delete-relaxation h_max (admissible lower bound from positive goals only, ignoring delete effects/negative requirements), plus explicitly satisficing weighted A*. P1 uses a bounded local reference implementation; these are not claims to compete with Fast Downward's LM-cut, landmarks or causal-graph heuristics.

## Implemented P1 contracts and capability set

- Native `proto/cognitum/planning/v1/classical.proto` with generated and independently compiler-matched `cognitum/proto/planning_pb2.py`.
- Typed grounded facts, positive and negative preconditions, add and delete effects, positive and negative conjunctive goals, explicit nonnegative integer action cost **strictly >=1**, cost minimization, zero-step plans, deterministic transitions, and globally validated domain constraints.
- Host-disabled-by-default `PlanningRegistry` (synthetic host_authorized boolean is **not** a production credential). Supports `NETWORKX_DIJKSTRA`, `NETWORKX_BFS` (unit-cost only), `ASTAR_HMAX`, `WEIGHTED_ASTAR_HMAX`.
- Independent plan replay verifies every precondition, transition and terminal goal, and recomputes the total integer cost. Independently enumerated complete bounded reachable graph + NetworkX Dijkstra may certify optimality or finite unreachable result; otherwise `VERIFIED_PLAN` or `UNKNOWN` only. Exhaustion of a search budget **never proves unreachable**. Weighted A* never self-certifies optimality.
- Bounded resources: <=24 facts, <=96 actions, <=1024 states/expansions, <=3000 ms cooperative time limit, <=512 action plan, <=64 KiB inbound frame. Resource limits are NOT OS hard memory ceilings or process cancellation.
- Request-bound result, receipt and data-minimized audit Protobufs; no source task content in audit records; SHA-256 is an integrity digest, NOT an authenticated signature.
- **PDDL export:** host-gated, deterministic PDDL 2.2 STRIPS+negative-precondition+action-cost text as an **interoperability boundary** (not arbitrary model-written PDDL and not an executable backend). Action and fact names are generated from indices, not interpolated untrusted identifiers. External Fast Downward/parser roundtrip still untested.
- Capability manifest separates *actually tested* NetworkX, local A* reference, *unavailable* Fast Downward/Unified Planning adapters and disabled experimental research candidates.

## Research watchlist — proposals, not implemented advances

- Musayev et al., ECAI 2025 (published August 2026), **Combining Heuristics and Transition Classifiers in Classical Planning**: integrating learned transition classifiers with established heuristics; promising domain-specific gains but not universal replacement. https://journals.sagepub.com/doi/10.3233/FAIA251375
- Aichmüller, Hesse & Geffner, ICML 2026, **Learning to Search and Searching to Learn for Generalization in Planning**: weighted A* and relational GNN/value-learning feedback; research-backend candidate, not installed. https://proceedings.mlr.press/v306/aichmuller26a.html
- Corrêa, Pereira & Seipp, NeurIPS 2025, **Classical Planning with LLM-Generated Heuristics**: selected heuristic code improves several tasks. Never execute AI-generated code in the Lu host; any future plugin requires reviewed, pinned, OS-isolated offline worker with reproducibility controls. https://proceedings.neurips.cc/paper_files/paper/2025/hash/3bf4b55960aaa23553cd2a6bdc6e1b57-Abstract-Conference.html

## Focused functional checks and intentionally untested areas

- `PYTHONPATH=.:tests python -m unittest tests.test_c12_planning -q` (36 tests, 48 seeded small-world cases inside one test, independent shortest-path oracle).
- `PYTHONPATH=. python tools/run_c12_smoke.py` (five scenarios).
- `PYTHONPATH=. python tools/verify_protobuf_schemas.py --require` (all 18 .proto descriptors).
- Full regression as separate module groups; report only completed runs.

**Open P2–P4:** real pinned optional Fast Downward and/or Unified Planning adapter with external process control; PDDL import/parser roundtrip and richer ADL/quantified/conditional effects; temporal, numerical, hierarchical and contingent planning; graph-search utilities, dynamic programming, MCTS and uncertainty-aware planning as distinct typed capability contracts. Research heuristics remain opt-in and unexecuted. No model benchmarks until portfolio completion; no Linux/Windows Lu-native security claims. Every plan remains a proposal, not authorization to perform tool effects.
