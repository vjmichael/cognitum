# ADR — Standard libraries first across Cognitum C01–C19

**Adopted:** 2026-11-03  
**Decision:** Established, maintained mathematical/scientific/engineering libraries are the default execution engines. Cognitum owns strict typed interfaces, Lu-host authority boundaries, safe adapters, provenance, independent checks, measured model-facing orchestration, and reproducible evaluation—not wholesale replacements for mature algorithms.

## Binding rules

1. Before introducing a nontrivial numerical, statistical, symbolic, constraint, search, spatial, tracking or ML algorithm, complete a **reuse review**: candidate libraries, versions, maintenance, actual functions, input domain, license and distribution obligations, platform packaging, security, provenance, accuracy/assurance and failure behavior. "Stdlib-only core" is a deployment boundary, **not** an instruction to reimplement math; use optional feature extras and separately isolated workers.
2. Identify a **competent conventional baseline** before custom development. Compare a mature library's native capability with any Cognitum wrapper and with the current custom implementation using fixed representative and held-out data.
3. Keep custom algorithms only for a demonstrated functional gap, an independently measured and reproduced practical advantage, a tighter independently verified mathematical guarantee, or a necessary safety/integration requirement unavailable upstream. Write an explicit exception ADR including costs, benchmarks and reevaluation date. A one-case win or faster unchecked answer is insufficient.
4. A library does **not** by itself certify a causal assumption, an unrestricted global optimum, security isolation, or performance of Lu plus transformer. Preserve distinct evidence labels: approximate/interval-certified/proven, host verified/not, model effect measured/not.
5. For mathematically rigorous tasks, the producer and auditor must have independent failure modes where feasible. A repeated invocation of the same implementation is not independent mathematical verification. An established arithmetic library may replace a custom kernel; define independent reference/oracle/cross-library checks.
6. No deletion of CH23/CH40 frozen source, signatures or historical scientific reports; use immutable archive and compare adapters on exactly pinned cases. Scientific release stays NO_GO unless its original proof gates are satisfied.
7. Do not add dependencies silently to base runtime. Evaluate Python ABI and Windows/Linux packaging, native DLL/shared-library loading, supported versions, licenses (especially GPL/LGPL conditions), supply chain/pinning, platform-specific binaries, resource ceilings and Lu worker confinement.
8. C03 owns prospective evaluation with false-positive controls, resource use, latency, correctness and full model-task metrics. Publish regressions and ties. Do not infer production adoption from an isolated solver benchmark.
9. Standard-library preference applies to **all C01–C19**, including memory and spatial systems, not only C14. Adapter replacement must not circumvent C02's fail-closed worker gate or C04's host-owned permissions.

## Component reuse register (candidates, NOT installed or approved)

| Component | First library/reference candidates | Primary reuse decision |
|---|---|---|
| C01 contracts | Protobuf, schema-validation libraries | Reuse codecs and schemas; preserve Cognitum semantics |
| C02 security | OS primitives, cryptography | Do not invent cryptographic algorithms or sandbox substitutes |
| C03 evaluation | NumPy/SciPy, standard stats/scoring tooling | Keep provenance and evaluation contracts |
| C04 Lu extension | Lu's native ToolCall/ToolReply and CE registry | Adapt, do not fork host runtime |
| C05 exact/scientific | SymPy, SciPy, NumPy, FLINT/Arb, mpmath | Use external CAS and verified arithmetic |
| C06 retrieval/memory | SQLite FTS5/BM25; FAISS or similar when justified | Lu/ANSF remains canonical owner |
| C07 temporal beliefs | SQLite transactional/event tooling | Keep domain-specific revisions and authorization |
| C08 HDC/vector symbolic | torchhd and NumPy | Compare against exact/BM25/embedding controls |
| C09 KAN | pykan and PyTorch | Challenger only; compare MLP/spline alternatives |
| C10 SMT/proofs | Z3, cvc5 | Trust actual proof/result modes and exact solver capabilities |
| C11 combinatorial | OR-Tools CP-SAT, HiGHS, SCIP | Native optimization baseline first |
| C12 planning | NetworkX, OR-Tools, established planning libraries | Reuse search/graph; custom policy only with evidence |
| C13 Bayesian/stats | SciPy, statsmodels, PyMC, ArviZ | Preserve calibrated uncertainty checks |
| C14 causality | Tigramite, DoWhy, causal-learn, EconML, statsmodels, brglm2/logistf; FLINT/Arb, IBEX, Ipopt, SCIP | Separate identification, estimation, verified global numerical certification |
| C15 spatial/tracking | OpenCV, Open3D, scipy.spatial, ByteTrack/BoT-SORT/OC-SORT/DeepSORT where licensed | Stable identity and custody remain Cognitum's |
| C16 physics | SciPy integrators, SUNDIALS, established physics engines | Independent conservation tests |
| C17 SSM | PyTorch and maintained SSM/reference implementations | Compare simpler RNN/filters and temporal baselines |
| C18 adaptation | scikit-learn, PyTorch, established continual-learning toolkits | Consent and retention are custom policy |
| C19 TDA | GUDHI, Ripser, giotto-tda where maintained | Require practical benefit over non-TDA baselines |

The register is a research starting point, not a claim of installation, compatibility, licensing approval, active maintenance verification or numerical superiority. Check exact APIs and distribution conditions prior to selection.

## Adoption gates

- **R0:** existing component and frozen-evidence inventory
- **R1:** public-source library/function/license/platform survey and selection rationale
- **R2:** smoke/test adapters on fixed golden, negative, ill-conditioned and sparse cases
- **R3:** paired custom-vs-library comparison with independently correct outcomes and CPU/RAM metrics
- **R4:** Lu/model-facing whole-task P3 evaluation under C02/C04 approvals
- **R5:** measured promotion, retention of fallback, or retire custom kernel; document rejection reasons

**Immediate engineering priority: C14/CH40-M**. No additional custom interval, determinant or solver machinery before testing established libraries against the 15 frozen original datasets, while keeping CH40 signatures immutable. Next inspect C05, C10, C11, C13 and C15 for high-duplication risks, followed by every remaining component.

## Source references

- Cognitum component portfolio and development roadmap in this repository.
- FLINT ball arithmetic and verified linear algebra: https://flintlib.org/doc/algorithms/ball-arithmetic/index.html
- FLINT Arb enclosure semantics: https://flintlib.org/doc/arb.html
- Follow-up library documentation/compatibility verification is required for IBEX, Ipopt, SCIP, and other candidates.
