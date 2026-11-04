# ADR — Established Libraries First for Every Cognitum Component

**Approved:** November 4, 2026. **Scope:** All C01–C19 components, future modules, and DLC-adjacent scientific capabilities.

## Binding engineering rule

Before writing a custom algorithm, inspect the component design and inventory existing maintained libraries, libraries already supplied by the user, standard-library facilities, conventional tools and reference implementations. **Adopt established implementations whenever they satisfy the required semantics, resource limits, platform support, security isolation, license, and reproducibility requirements.**

Do not reinvent SMT solving, causal inference, numerical optimization, scientific computing, geometry, probability distributions, scheduling or analogous mature disciplines merely because a local prototype is convenient. Existing modules are not automatically replaced: inspect their conformance, maturity and dependency footprint first.

Our first-party responsibilities remain: strict typed schemas/Protobuf interfaces; host authorization and worker lifecycle; constrained adapter invocation; trusted inputs; independent witness/result checking; provenance, limits and uncertainty; failure-status handling; package pinning; comparative evaluation and distribution compliance.

## Required pre-implementation library review

For each Cxx work item, record:
1. **Capability and incumbent:** what solver/library actually implements the required method (not a name-only list).
2. **Licensing and supply chain:** compatible license and distribution conditions; pinned version, provenance, hashes and transitive dependencies. Do not bundle unreviewed third-party code.
3. **Cross-platform fitness:** Windows and Linux runtime and CPU/GPU behavior; optional native extensions and memory/runtime pressure.
4. **Safety boundary:** model-generated code or raw parsing prohibited; typed whitelists, input budgets, timeouts, OS isolation, and no model-supplied grants.
5. **Correctness checks:** independent checkable SAT witnesses, numerical residuals, conservation identities, cryptographic/proof certificates where available; do not claim UNSAT proofs without an accepted checker.
6. **Benchmarks:** compare against a competent conventional incumbent; measure correct task completion, latency, memory and operational failures, not just algorithm microbenchmarks.
7. **Build-vs-adopt decision:** explicit reason if custom code is justified, with a bounded scope and maintenance owner.

Prefer optional adapters and separate dependency extras where scientific packages are not core requirements. **Library discovery and code import never grant Lu tool authorization.**

## Component-specific initial portfolio decisions

| Component family | First established options to evaluate |
|---|---|
| C05 mathematical computation | Python Fraction/Decimal, SymPy, mpmath, NumPy/SciPy, FLINT/Arb, HiGHS |
| C06/C07 data, retrieval and state | SQLite/FTS, appropriate vector-index libraries, typed schemas |
| C08 HDC and C09 KAN | Existing user-provided TorchHD/pykan packages, their dependencies and maintained alternatives |
| C10 formal logic / proof | Z3 and cvc5; proof checking only with authenticated, format-compatible independent verifier |
| C11 optimization / scheduling | Google OR-Tools CP-SAT, SciPy/HiGHS, CVXPY where formulation calls for it |
| C12 planning | OR-Tools/graph libraries and established planners appropriate to the search domain |
| C13 probability | SciPy/statistics and established probabilistic inference libraries |
| C14 causal inference | DoWhy, EconML, causal-learn, Tigramite; component separately CLOSED |
| C15 tracking/vision | Established detector/tracker/geometry libraries; avoid invented CV primitives |
| C16 physical simulation | SciPy integrators and domain-specific physics engines |
| C17 temporal | Existing SSM packages and conventional time-series models |
| C18/C19 | Mature learning and topological-analysis libraries after a concrete task is scoped |

This is an **inventory and adoption directive**, not a claim every listed library has passed review or is installed. Individual module reviews must examine exact versions, license, availability and genuine test evidence.

## C10 application

The original C10 Boolean exhaustive solver is retained as a small independent verification oracle only; it is **not** the principal solver. New typed linear-integer SMT adapters delegate solving to optional Z3 and cvc5. The adapter rechecks SAT assignments independently and only upgrades solver-reported UNSAT to verified exhaustive UNSAT when the finite integer domain can actually be enumerated under the cap. Larger UNSAT reports remain unverified until a compatible independent proof checker is implemented. No raw SMT-LIB supplied by an LLM is executed.
