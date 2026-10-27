# Cognitum — component roadmap and initial core prototype

A separate, offline cognitive augmentation foundation based on the owner's Revision 1.4. Python standard library only at runtime. Production Lu was not changed. This is a tested prototype, not a validated cognitive system or a secure third-party plugin host.

**Active development plan:** [Component roadmap (P0 research → P1 build → P2 smoke test → P3 standardized benchmark)](docs/roadmap.md) and [dependency-ordered build path (C01–C19)](docs/build-order.md). [**Work started: C01 / P0 core runtime audit and research**](docs/components/core-runtime/P0-research.md). Each component progresses independently, with explicit research/library/hardware selection and acceptance evidence. The older project-wide phase schedules remain historical source documents; the code below is the earlier *Phase 0 starter*, not completion of all components' P0 work. HDC/KAN research is preserved; the [archived K4 and optional depth overlay have now been recovered and independently unit/self-tested](docs/components/hdc-kan/P0-archive-reuse-audit.md), while Cognitum/Lu integration remains unimplemented.

**Cognitum-only development rule:** Lu and its installer, user profiles, repositories and runtime are **read-only compatibility references** in this project. Any required Lu DLC Core Extension changes are recorded as **proposed addenda** in the [Lu DLC CE Integration Addendum Register](docs/lu-dlc-ce-addenda.md) for the separate Lu team. A [C01 tracing hardening patch is under isolated review](https://github.com/vjmichael/cognitum/blob/cognitum/c01-tracing-guard/docs/components/core-runtime/P1-P2-tracing-hardening.md); it is **not merged to main** and only its focused tests have been executed.

**Integration principle:** Lu owns the selected/loaded transformer, model lifecycle, orchestration, tool policy and native CE/workspace environment; Cognitum supplies optional cognitive capabilities through those host interfaces. See the [Lu–Cognitum transformer collaboration contract](docs/lu-cognitum-integration.md). Component P3 evidence must measure improvements in end-to-end Lu+model tasks rather than claim that stand-alone component performance modifies a transformer's weights.

**C02 security P0 started:** [Host authority and OS worker confinement research](docs/components/security/P0-research.md). No effectful/untrusted worker is enabled.

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
