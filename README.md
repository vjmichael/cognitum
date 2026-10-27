# Cognitum — component roadmap and initial core prototype

A separate, offline cognitive augmentation foundation based on the owner's Revision 1.4. Python standard library only at runtime. Production Lu was not changed. This is a tested prototype, not a validated cognitive system or a secure third-party plugin host.

**Active development plan:** [Component roadmap (P0 research → P1 build → P2 smoke test → P3 standardized benchmark)](docs/roadmap.md) and [dependency-ordered build path (C01–C19)](docs/build-order.md). [**Work started: C01 / P0 core runtime audit and research**](docs/components/core-runtime/P0-research.md). Each component progresses independently, with explicit research/library/hardware selection and acceptance evidence. The older project-wide phase schedules remain historical source documents; the code below is the earlier *Phase 0 starter*, not completion of all components' P0 work. HDC/KAN research is preserved; the [archived K4 and optional depth overlay have now been recovered and independently unit/self-tested](docs/components/hdc-kan/P0-archive-reuse-audit.md), while Cognitum/Lu integration remains unimplemented.

**Cognitum-only development rule:** Lu and its installer, user profiles, repositories and runtime are **read-only compatibility references** in this project. Any required Lu DLC Core Extension changes are recorded as **proposed addenda** in the [Lu DLC CE Integration Addendum Register](docs/lu-dlc-ce-addenda.md) for the separate Lu team. C01 tracing hardening and the non-installable CE manifest fixture have been merged to **Cognitum `main`**; their [combined CI](https://github.com/vjmichael/cognitum/actions/runs/40444933715) passed **51/51 unit tests and 12/12 synthetic replay cases** on all four Linux/Windows Python 3.11/3.13 jobs.

**Integration principle:** Lu owns the selected/loaded transformer, model lifecycle, orchestration, tool policy and native CE/workspace environment; Cognitum supplies optional cognitive capabilities through those host interfaces. See the [Lu–Cognitum transformer collaboration contract](docs/lu-cognitum-integration.md). Component P3 evidence must measure improvements in end-to-end Lu+model tasks rather than claim that stand-alone component performance modifies a transformer's weights.

**C03 evaluation P0 started:** [Lu+loaded-transformer controlled evaluation and benchmark research](docs/components/evaluation/P0-research.md). Four test arms are specified; no model performance claim yet.

**C02 secure worker boundary in development:** [Protobuf WorkerCall/WorkerReply, closed admission and adversarial P2 tests](docs/components/security/P1-P2-protobuf-worker-boundary.md) build on [host-authority and OS confinement research](docs/components/security/P0-research.md). GitHub CI verified **136/136 units and 12/12 synthetic replay per Windows/Linux Python configuration**, plus three compiler-checked Proto schemas. **No Lu host or OS sandbox exists yet for these workers; execution remains denied.** The next [C02 native Protobuf supervisor acceptance suite](docs/components/security/P1-P2-supervisor-acceptance.md) freezes OS-level negative probes, including revocation/cancel/descendant reaping. [CI 40454579833](https://github.com/vjmichael/cognitum/actions/runs/40454579833) passed **147/147 unit tests, 12/12 replay, and four protobuf source/descriptor checks** on Windows/Linux × Python 3.11/3.13. These are offline contract tests, **not** actual OS security certification.

**Validated on `main`:** [Tracing hardening PR #1](https://github.com/vjmichael/cognitum/pull/1) and [default-off CE manifest fixture PR #2](https://github.com/vjmichael/cognitum/pull/2) are merged and the [combined full regression](https://github.com/vjmichael/cognitum/actions/runs/40444933715) is green (51 unit and 12 synthetic replay cases per Linux/Windows Python configuration). All work is **Cognitum-only**; proposed Lu integration remains unimplemented.

**Typed capability results implemented:** [C01 exact/numerical/retrieval/failure contract](docs/components/core-runtime/P1-P2-typed-results.md) was merged in [PR #3](https://github.com/vjmichael/cognitum/pull/3); [76/76 unit tests and 12/12 replay cases passed](https://github.com/vjmichael/cognitum/actions/runs/40445966151) on Linux/Windows Python 3.11/3.13. This remains a standalone typed Python/JSON representation; **native Protobuf domain wire support has since been added**, without an installed Lu extension.

**Native Protobuf implementation:** [merged PR #4](https://github.com/vjmichael/cognitum/pull/4) adds [`cognitum.v1` .proto definitions](proto/cognitum/v1/capability.proto), descriptor-backed Python classes, strict [binary codec](cognitum/protobuf_codec.py) and [contract report](docs/components/core-runtime/P1-P2-protobuf-native.md). [CI 40447933037](https://github.com/vjmichael/cognitum/actions/runs/40447933037) passed **91/91 unit tests, 12/12 replay and `protoc` schema compilation** on all four Linux/Windows Python configurations. Lu's existing `ToolCall/ToolReply` remains authoritative and **Lu has not been edited**. Install optional Python support via `pip install -e ".[proto]"`.

**Lu DLC CE discovery handoff (merged [PR #5](https://github.com/vjmichael/cognitum/pull/5)):** The newer Lu `lu/independent-branding-ce-foundation` source includes `ModuleKind::CoreExtension` and trusted CE lifecycle foundations. Cognitum's [model-facing handoff review](docs/components/core-runtime/P1-P2-lu-ce-discovery-handoff.md) defines reviewed usage guidance, strict Lu-compatible external tool parameters, real `cognitum.v1` Protobuf type URLs and explicit **not installed / not model advertised** flags. [`tools/emit_lu_ce_handoff.py`](tools/emit_lu_ce_handoff.py) exports an inert **binary Protobuf `cognitum.v1.CoreExtensionHandoff`** for Lu-team review; it cannot register/enable a tool. The optional `--model-boundary-json` flag is only for an external LLM provider preview, not native IPC. The Lu fork remains read-only.

**Current P0 evidence:** [C01 active Lu-native integration audit](docs/components/core-runtime/P0-lu-native-audit.md) and [optional schema-validator study](docs/components/core-runtime/P0-schema-study.md), with its [reproduction script](research/schema_validation_probe.py). These are research/integration studies, not shipping-code certification.

Run from this folder with Python 3.11+ (tested here on Windows, Python 3.14.6):

```powershell
python -m unittest discover -v
python -m unittest tests.test_calculator -v
python -m cognitum registry
python -m cognitum calc '1/3 + 1/6'
python -m cognitum --calculator calc '0.1 + 0.2'
python -m cognitum --calculator replay evals/smoke.json
python -m cognitum --calculator --trace trace.jsonl calc '2**-3'
```

Without `--calculator`, the core boots empty and the calculation reports unavailable (exit code 1). With it, the answer is an exact rational string. `replay` exits nonzero on a failed case. Source execution needs no installation or network. Optional package installation uses setuptools; no install/build was verified in this environment.

What is implemented:

- Immutable, versioned manifests and per-operation closed schemas, generated JSON Schema and schema hashes; a checked-in compatibility fixture.
- Explicit champion nomination; live enable/disable; atomic replacement after trusted lifecycle validation, with old entry retained on validation failure. Installed plugins start disabled.
- Deterministic policy: identity/workspace checks, exact scoped effect grants, research opt-in, replay denial and fail-closed effectful execution. Grants come from trusted host code, never model payloads.
- Disposable process per plugin call with timeout termination and cleanup; operation-specific output validation and sanitized errors.
- Separate execution status, typed result/outcome kind, arithmetic assurance and assumption-bound interpretation. Missing or failed exact capability yields no invented answer.
- Correlated metadata-only JSONL tracing; payloads, results and exception details are not logged.
- Twelve synthetic replay cases, frozen grading, suite/registry hashes and an explicit no-promotion label.
- Bounded AST calculator using exact `Fraction` arithmetic. No `eval`, symbolic parser, arbitrary code execution, function calls or variables.

See the [active component roadmap](docs/roadmap.md), [architecture](docs/architecture.md), [research agenda](docs/research.md) and [handoff/status](docs/status.md). Original design inputs are preserved under `docs/sources/` with their original date discrepancies. No license was invented for the owner's work.
