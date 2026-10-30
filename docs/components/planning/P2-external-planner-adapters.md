# Cognitum C12 P2 — optional mature planning-engine adapters

**Status:** functional offline host-configured Protobuf subprocess adapter; **not** a live Fast Downward/Unified Planning integration test; **not** installed in Lu. The reference environment does not have `fast-downward.py`, `unified_planning`, or a Unified Planning plugin. Synthetic drivers exercise the execution/verification boundary, not the external engines' actual PDDL support. The real NetworkX planner from P1 remains the tested baseline.

## Standards and established implementations

- Fast Downward 26.6: grounded classical planning, PDDL to SAS+ translation; supports action costs, negative preconditions, delete effects and many other classical constructs. [Usage](https://www.fast-downward.org/latest/documentation/planner-usage/); [2026 release](https://www.fast-downward.org/latest/releases/26.6/); [PDDL support](https://www.fast-downward.org/24.06/documentation/pddl-support/). `lama-first` is *satisficing* and must not be treated as an optimality proof. `seq-opt-lmcut` is an optional host-reviewed optimizer configuration. Fast Downward GPL-3.0-or-later must undergo a redistribution/license review before shipping a Windows package.
- Unified Planning provides PDDLReader, OneShotPlanner, planner discovery and the `up-fast-downward` plugin. [Official UP documentation](https://unified-planning.readthedocs.io/en/stable/getting_started/quickstart.html); [Fast Downward integration](https://unified-planning.readthedocs.io/en/v1.0.0/engines/3-fast_downward.html). UP framework Apache-2.0, external engine licenses separate. UP `pyperplan` is **not a compatible default** for this interface: it lacks action costs (and standalone Pyperplan supports a narrower positive STRIPS fragment). [Pyperplan capabilities](https://pypi.org/project/pyperplan/). P2 UP wrapper therefore permits only the reviewed `fast-downward` plugin until another backend is proven cost-compatible.
- PDDL: generated exclusively from the P1 validated `ClassicalTask`, with predictable generated action and predicate identifiers. No model-authored PDDL, arbitrary program, shell command, solver alias, path or plugin is accepted in the Protobuf request.

## Native contracts and files

- `proto/cognitum/planning/v1/engines.proto`, independently compiled descriptor-matched `cognitum/proto/planning_engines_pb2.py`: `EngineRequest`, `EngineResult`, `EngineReceipt`, `EngineAudit`, `EngineManifest`.
- `cognitum/planning_engines.py`: `EnginePolicy`/`pinned_policy`, default-disabled `ExternalPlannerRuntime`, SHA-256 host-pinned driver, trusted config allowlist, plan text parser, bounded worker deadline, cancellation/disable, temp-file PDDL, independent plan replay, separate complete finite-state optimality check, audit and manifest.
- `tools/c12_unified_worker.py`: host-pinned optional UP wrapper (requires installed local UP and `up-fast-downward` engine; not runtime-tested here). Drivers execute only under separate subprocess boundaries; **not** yet OS hardened on Windows.

### Security and proof invariants

1. Host authorizes and selects an enabled, **SHA-256-pinned executable** and a reviewed engine config. Requests only name a supported backend, carry canonical Protobuf planning requests, and set a bounded deadline; no execution path or command from the model is accepted. A fake boolean host authorization in this Python reference is **not** Lu's authenticated capability grant.
2. Verify *every* supplied action index, each precondition, transition and final goal, and recompute total cost from the typed task. Invalid plans, malformed textual output and missing plans are never represented as valid or as proofs of impossibility.
3. Check optimality only by a separate bounded **complete** reachable-state enumeration; the engine's own `SOLVED_OPTIMALLY`, `UNSOLVABLE` or exit code never confers a proof. Resource exhaustion leaves a valid witness `VERIFIED_PLAN`, or `UNKNOWN` without one.
4. Every result carries the request SHA-256, classical request SHA-256, checked worker hash, PDDL-export digest, backend ID, wall time, result status and reason code. Receipts independently recompute witness validity/cost and any claimed finite optimality. An optional trusted host worker SHA-256 input gates provenance consistency; a self-reported worker hash alone is not proof of source integrity. The driver hash alone does not attest the interpreter or the solver's transitive library/binary dependencies, which must be pinned and audited by the host. Data-minimized audit records omit original facts/actions. Hashes provide integrity linkage, **not** authenticated provenance, persistent signed audit storage, or tamper resistance against a compromised host.
5. In Linux Python, subprocess process groups allow cancellation/deadline termination. On Windows, descendant process containment and native resource limits require Lu Job Objects; the Python layer is **not an OS security sandbox**. There is no hard CPU/memory quota, signed binary provenance or native Lu host-authority integration.
6. Manifest marks both optional engines **unavailable and not runtime-tested**, regardless of the test-shim success. Only the full real engine tests should change those flags.

## How to test or integrate a real engine later

Install a reviewed release of Fast Downward (or UP with `up-fast-downward`) **outside** Cognitum; inspect its license, hash and dependencies. Host constructs `pinned_policy('fast-downward', path_to_fast_downward_driver, enabled=True)` or `pinned_policy('unified-planning', reviewed_c12_unified_worker, enabled=True, search_configuration='fast-downward')`, with a separately authenticated `host_authorized=True` provided only by Lu. This policy is not controllable from a model. The typed PDDL exporter is the only input boundary. A real runtime verification should confirm its version, plan file conventions, syntax, feature compatibility, cancellation, and OS containment on Windows x86-64 before declaring availability.

## Focused development tests, no benchmarks

- `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=.:tests python -m unittest tests.test_c12_p2_engines -q` — synthetic drivers with real subprocess lifecycle and independent replay, tamper, deadline, cancellation and digest-gating tests.
- `PYTHONPATH=.:tests python tools/run_c12_p2_smoke.py` — five synthetic adapter smoke scenarios.
- `PYTHONPATH=. python tools/verify_protobuf_schemas.py --require` — compiler-level Protobuf wire check.
- Legacy C12, C11 and remaining component suites still must pass; timeout of a combined runner is not a test pass.

## Follow-up P3/P4, not claimed implemented

Integrate real Fast Downward/UP on target Windows, PDDL parser roundtrips and richer action modeling (conditional effects, quantified preconditions, parameterized grounded schemas), typed temporal/numeric/HTN/contingent planning, graph search/DP/MCTS specialist APIs, and optional independently vetted research heuristics. Keep full model-vs-baseline benchmarking deferred until the component portfolio is built.
