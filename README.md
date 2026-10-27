# Cognitum — component roadmap and initial core prototype

A separate, offline cognitive augmentation foundation based on the owner's Revision 1.4. Python standard library only at runtime. Production Lu was not changed. This is a tested prototype, not a validated cognitive system or a secure third-party plugin host.

**Active development plan:** [Component roadmap (P0 research → P1 build → P2 smoke test → P3 standardized benchmark)](docs/roadmap.md) and [dependency-ordered build path (C01–C19)](docs/build-order.md). [**Work started: C01 / P0 core runtime audit and research**](docs/components/core-runtime/P0-research.md). Each component progresses independently, with explicit research/library/hardware selection and acceptance evidence. The older project-wide phase schedules remain historical source documents; the code below is the earlier *Phase 0 starter*, not completion of all components' P0 work. HDC/KAN research is preserved for reuse, with Cognitum integration still requiring a verified archive audit.

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
