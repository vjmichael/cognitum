# C12 P4 — Host-pinned experimental guidance for classical planning

**2026-10-27 · Offline functional engineering milestone.** This is *not* a trained neural planner, verified research performance gain, trusted model execution, Fast Downward runtime test, or native Lu integration. Full comparative benchmarking is deferred.

## Established baseline and what P4 actually adds

The established classical-planning baseline remains P1's typed STRIPS-style problem, conventional cost-aware A*/Dijkstra, exhaustive bounded graph checker, and P2's *optional* Fast Downward/Unified Planning adapters. The P3 stochastic/HTN/temporal planners are separate algorithms. **P4 implements a hybrid, research-guided A***: it keeps P1's admissible `h_max` primary A* priority, using only precomputed and bounded per-(state,action) research guidance to break **equal-`f`** ties. Advice can mark an action preferred, disfavored, or *predicted* dead end. It **never prunes**, never changes cost or h_max, and can never approve an action or certify a theorem. A false predicted-dead-end hint cannot suppress a viable route.

This is useful as a concrete, executable research seam: data from an offline learned transition classifier, a relational graph heuristic, or a language-model-generated heuristic can later be converted by trusted import tooling to the same **bounded, typed, non-executable** hint table. There is **no such learned model** or source-code execution in P4, and no untrusted arbitrary callback, model weights, imports, shell, or executable string can be supplied in a request. The `offline-*` source identifiers denote **claimed origin/maturity**, not installed model implementations.

## Research assessment (specific, reproducible leads)

- Musayev et al., *Combining Heuristics and Transition Classifiers in Classical Planning*, ECAI 2025 proceedings, online 2026-08-25, DOI [10.3233/FAIA251375](https://doi.org/10.3233/FAIA251375): learned transition classification combined with traditional heuristics, lookahead and unsolvability guidance. Paper's reported performance is **not** a Cognitum P4 result; our no-pruning tie-break is deliberately narrower.
- Aichmüller, Hesse and Geffner, *Learning to Search and Searching to Learn for Generalization in Planning*, ICML 2026 [PMLR 306](https://proceedings.mlr.press/v306/aichmuller26a.html): self-improving weighted A* and relational GNN guidance. This architecture is a future experimental track, **not executed** in P4.
- Corrêa, Pereira and Seipp, *Classical Planning with LLM-Generated Heuristics*, NeurIPS 2025 [proceedings](https://proceedings.nips.cc/paper_files/paper/2025/hash/3bf4b55960aaa23553cd2a6bdc6e1b57-Abstract-Conference.html): an offline heuristic-generation path. **Generated executable code must never enter a Lu-hosted Cognitum request or worker without separate provenance, review, and OS sandbox.** P4 accepts numbers/enums, not executable heuristics.
- Futuhi and Sturtevant, *Learning Admissible Heuristics for A*: Theory and Practice*, ICLR 2026 [proceedings](https://proceedings.iclr.cc/paper_files/paper/2026/hash/7f3b25e39e0f0330435d1ffc1d6fa193-Abstract-Conference.html): an admissibility-oriented future candidate; P4 makes **no claim** that any supplied learned heuristic is admissible.

**No comparative accuracy, speed, coverage, sample-efficiency, or solver superiority is claimed.** Future feature-matched baselines require same problems/theories, process ceilings, training/test isolation, seeds, source versions, and machine configuration.

## Implemented source/contract

- `proto/cognitum/planning/v1/guidance.proto` and compiler-confirmed `cognitum/proto/planning_guidance_pb2.py`: typed `GuidanceArtifact`, `TransitionHint`, nested classical request, result, receipt, audit, bounded enums and explicit status/assurance. Source reference and model digest are *claimed metadata*, not verified model file integrity.
- `cognitum/planning_guidance.py`: `GuidanceRegistry` defaults **disabled**. The host owns an approved set of exact content SHA-256s. Enabling is insufficient without explicit host approval for the exact hint table, `host_authorized` and valid typed data. Missing/mismatched pins fail closed. The request cannot choose an executable path or grant itself approval.
- The artifact's `content_sha256` covers its deterministic Protobuf bytes with the digest field cleared. Host approval must be passed **outside the request**. SHA-256 is integrity linkage **not a signature, user/source authentication, proof of model weight authenticity, or complete protection against a compromised host**.
- Exactly supported mode: standard optimal A* `f=g+h_max`, with hint-based secondary priority. No dynamic learning, state generation, source data extraction or action execution. Limits: <=24 facts, <=96 actions, <=256 hints, <=1024 bounded states/expansions, max 3000ms cooperative search, with inherited P1 frame and plan-length limits.
- `verify_guided_frame` independently replays all claimed plans, verifies exact cost, and invokes P1's separate finite reachable-graph checker for `VERIFIED_OPTIMAL`/`VERIFIED_UNREACHABLE`. `UNKNOWN` and rejection never create positive evidence receipts. If independent enumeration cannot finish within its bounds, a verified feasible plan stays `VERIFIED_PLAN` without an optimality claim.
- `make_guided_audit` emits only request/result/artifact digests, backend/version, trace, elapsed time, counters, status and limited evidence decision. No raw task facts, model weights, or hints. Receipt and audit are **not signed or persisted in an append-only journal**. Lu collector compatibility has **not** been proved.

## Focused verification and limitations

- `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=.:tests python -m unittest tests.test_c12_p4_guidance -q`: 24 dedicated tests, including 36 tiny seed-varied comparison cases against established NetworkX Dijkstra **as a correctness oracle** (not benchmark timings), forged proofs, forged provenance, unsupported hints, scope mismatches, host disable and unsafe claims.
- `PYTHONPATH=. python tools/run_c12_p4_smoke.py`: five safety/functional scenarios.
- `PYTHONPATH=. python tools/verify_protobuf_schemas.py --require`: all 22 actual `.proto` source files match checked-in descriptor-backed bindings.
- Full Python tests pass in completed per-component groups, with single-threaded numeric libraries. Legacy monolithic tests can exceed the command runner ceiling.

**Important production gates**: host authorization booleans are synthetic; no worker OS sandbox, Windows hard kill/Job Object, authenticated Lu backend approval, real learned-model weights, trained classifier, model evaluator, real external planner runtime, or peer-reviewed benefit established. Research source IDs are assertions in the artifact; upstream paper/licensing/model supply-chain verification is separate. C08/C09 remain deferred; comprehensive benchmarks wait until components are built.

## Recommended next engineering phase

Continue to **C13 Bayesian/probabilistic inference** under the standards-first + experimental-backend engineering standard. Revisit C12 for real Fast Downward / Unified Planning / PyMDPtoolbox runtime integration, proven source-artifact model adapters, expanded temporal/HTN languages, and Lu native worker/collector wiring after the portfolio's essential capabilities are present. Do not portray those gates as complete.
