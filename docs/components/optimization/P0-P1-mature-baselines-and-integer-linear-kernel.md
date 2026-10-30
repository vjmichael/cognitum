# C11 P0/P1 — Standards-first combinatorial optimization and first integer-linear kernel

**Date:** 2026-10-27. **Owner priorities:** established library first, optional bleeding-edge research track, offline-first Lu, Protobuf-native, auditable, benchmark hooks now / actual benchmarks later. **Status:** executable reference integration; NOT Lu production integration.

## Component inventory and reference technology

C11 is larger than integer programming: target capability inventory includes CP-SAT and constraint programming, LP/MIP and QP, scheduling/interval constraints, packing/knapsack, graph matching/flow/assignment, vehicle routing, resource allocation, and exact/approximate combinatorial search. Maintain distinct typed specialist interfaces where theory or validation differs. Avoid calling one MILP adapter a full optimization suite.

| Candidate | Standard features / usage | License / deployment | C11 treatment |
|---|---|---|---|
| Google OR-Tools / CP-SAT | Integral domain CP-SAT, resource scheduling, routing, networks | Apache 2.0; Windows/Linux native libraries | Optional `ortools-cpsat` MILP-compatible adapter coded, **not runtime-tested** because OR-Tools is absent locally; native specializations later |
| HiGHS through SciPy `optimize.milp` | Established MILP solver, plus LP/QP elsewhere in HiGHS | HiGHS MIT; SciPy BSD-3-Clause; bundled SciPy/HiGHS currently running on Linux | **Real backend tested** through SciPy 1.17.0; no network or standalone solver installer |
| SCIP (future) | Advanced MIP/CP solver | Check compatible licenses for chosen distribution | Candidate, not a required dependency |
| Conventional exact oracle | Exhaustive enumeration of small finite domains | Cognitum reference code | Check small optimality/infeasibility, **not** a replacement backend for industrial instances |

Primary references (accessed 2026-10-27): [HiGHS official site](https://highs.dev/), [OR-Tools repository](https://github.com/google/or-tools), [OR-Tools CP-SAT docs](https://developers.google.com/optimization/cp/cp_solver/), [SciPy MILP docs](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html). Check current licenses again when actually bundling binaries for Windows.

## P1 implemented surface

- `proto/cognitum/optimization/v1/optimize.proto` and matching checked-in, compiler-verified `cognitum/proto/optimization_pb2.py`. Only typed integer-variable domains, linear constraints (≤, ≥, =), min/max objectives, status/receipt/audit messages. No user-supplied solver scripts, CLI paths, shell commands, arbitrary callbacks or unbounded domains.
- `cognitum/optimization.py`: two registered backend adapters: real SciPy/HiGHS MILP and optional OR-Tools CP-SAT. Registry defaults disabled and requires explicit **synthetic** host-authorized flag on each invocation. This is NOT a real Lu host grant; a model cannot obtain C02 worker privileges through these records.
- Independent exact-integer witness checking **after** solver numeric conversion. Full finite-domain proof through exhaustive enumeration only when product of domain sizes is ≤ 4,096. A valid solver assignment in a larger domain is `VERIFIED_FEASIBLE` even if the solver says `OPTIMAL`; larger-domain `INFEASIBLE` solver claims become `UNKNOWN` unless separately proved. Contradictory / forged witness is rejected or downgraded. Solver status is audit information, **never equivalent to independent proof**.
- `verify_optimization_frame()` independently rechecks request/result binding, exact constraints, objective, assignment and any bounded proof claim, without invoking the backend. `make_optimization_audit()` emits a data-minimized Protobuf record bound to hashed request/result frames, trace and backend version. Audit digests are **not cryptographic host attestations**; keep separate from Lu's canonical provenance and security.
- Wall-time in result, digest, backend ID/version, status and reason make later benchmark collection possible. No benchmark campaign performed.

## Strict limits and caveats

- 1–24 integer variables, up to 128 linear constraints, up to 512 terms; bounded integral domains [-1,000,000, 1,000,000], coefficients/RHS ≤ 1,000,000. Max 5 seconds advisory solver time; max independent 4,096 domain states. No fractional/continuous variables, nonlinear objectives, scheduling/flow/routing protocol, negative bound sentinel, or native proof certificates in P1.
- SciPy/HiGHS is called **inside the current Python process**. Its advisory solver time limit is not a hostile-code containment mechanism or a guaranteed wall-clock kill. **C02 OS-isolated worker, hard cancellation, memory ceilings, host admission, native Lu integration and Windows x86-64 package are open.** Ordinary Lu users should eventually receive bundled native dependencies (no pip/command-line prerequisite).
- A finite enumeration verifies the integer problem as typed; it does NOT verify that conversational natural-language requirements were correctly formalized. Printed backend version is descriptive rather than measured binary attestation. Input hashes must not be treated as de-identification guarantees for low-entropy user datasets.
- This C11 P1 is **one technology slice**, not component-wide completion or an efficacy claim.

## Experimental research track (candidate; not implemented)

2026 results offer plausible, **task- and baseline-dependent** research hypotheses. Keep experimental backends optional, disabled by default, with provenance, research-paper revisions and matched future controls:

1. [Hou et al., *LLM4Branch*, ICML 2026](https://proceedings.mlr.press/v306/hou26d.html): automatically discovered MILP branching policies, published CPU/GPU comparative claims. Compare versus conventional solver with same instance, resource and version controls later.
2. [Chen et al., *Probabilistic Multi-variable Branching*, ICML 2026](https://proceedings.mlr.press/v306/chen26ah.html): learned multi-variable branching. Do not infer improvement to our instances without evaluation.
3. [Yuan et al., *BTBS-LNS*, ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/7eca17ef54789b0663cab421f2e9dbf5-Abstract-Conference.html): learned large-neighborhood search for mixed-integer programs. May fit a future optional heuristic backend.

## Future build order

- **C11 P2:** native CP-SAT runtime checks, typed scheduling/packing, assignment/flow and routing specialists, extensible backend capability manifests and hard resource controls. Use established library implementations.
- **C11 P3:** research adapters isolated from the mature default, advanced audit/benchmark bridge to Lu's existing collector and reproducibility contract; no model/hardware benchmark until the overall component portfolio is built.
- Production release requires actual Windows x86-64 execution, Lu host authorization and an OS-enforced kill path. Nothing in P1 clears those gates.

## Tests and reproducibility

`PYTHONPATH=.:tests python -m unittest tests.test_c11_optimization -q` exercises 30 focused cases, including real HiGHS and seeded small problem oracle checks. `PYTHONPATH=. python tools/run_c11_smoke.py` performs five observable scenarios; `PYTHONPATH=. python tools/verify_protobuf_schemas.py --require` ensures `.proto` matches descriptor bindings. Full tests should use `PYTHONPATH=.:tests` to support older C06 sibling imports.
