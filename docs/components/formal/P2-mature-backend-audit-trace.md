# C10 P2: mature solver adapters, typed Protobuf constraints, audit and independent SAT checking

**2026-10-27, functional implementation.** Based on C10 P1, which remains the independently verifiable *bounded* Boolean/integer-difference reference. This milestone does **not** mean a native Rust/Windows Lu integration or a certified general-purpose theorem prover.

## Standards and established libraries (as of 2026-10-27)

| Technology | Standard/core coverage | Integration decision | Runtime evidence |
|---|---|---|---|
| SMT-LIB 2.7 | Common solver input semantics | Restricted, generated SMT-LIB from typed protobuf AST, not raw model-generated programs | Compiler/functional checks |
| Z3, MIT license | General-purpose SMT, many theories; mature C API and CLI | Optional pinned `z3-lib` isolated worker (C API) or `z3-cli` process adapter | **Actual Linux system Z3 lib** tested for integer, rational, BV SAT and integer UNSAT; no Z3 CLI binary available |
| cvc5, modified BSD license | Mature alternative, SMT-LIB models, cores, proofs | Optional pinned `cvc5-cli` adapter | Adapter defined and token-level checks; **cvc5 executable absent, integration not tested** |
| C10 P1 reference | Boolean + bounded integer difference logic | Retained untouched, independent exhaustive UNSAT verifier | Previous 28 focused tests retain coverage |

URLs reviewed: https://smt-lib.org/language.shtml ; https://z3prover.github.io/api/html/group__capi ; https://microsoft.github.io/z3guide/programming/Parameters/ ; https://cvc5.github.io/docs/latest/options.html ; https://github.com/Z3Prover/z3 ; https://github.com/cvc5/cvc5/blob/main/COPYING . Production redistribution requires verification of solver binary provenance, target architecture and all transitive dependencies, especially optional cvc5 GPL-linked builds.

## New implementation files and contract

- `proto/cognitum/formal/v1/backend.proto` and `cognitum/proto/formal_backend_pb2.py` are compiler-checked typed AST + backend request, result and verification receipt. Internal messages are Protobuf, not JSON or arbitrary SMT-LIB strings.
- `cognitum/formal_backend.py` type-checks a bounded AST (Bool, Int, Real, BitVector up to 64 bits), compiles SMT-LIB, dispatches only explicitly pinned backend binaries, parses bounded solver responses and independently evaluates SAT witnesses with Python exact integers/Fraction and bitvector modulus. Supported operators: Boolean AND/OR/NOT/XOR/IMPLIES, equality, ITE, +,-,*, order comparisons, bvand/bvor/bvnot/bvadd/bvult. Nonlinear multiplication can be expressed but solver may return UNKNOWN; no universal support claim. This is a typed subset, not unrestricted SMT-LIB.
- `cognitum/formal_z3_worker.py` runs optional `libz3` C API in a disposable subprocess. Z3/cvc5 CLI adapters are also defined with no shell string invocation. A two-phase call avoids requesting a model after UNSAT and enforces a shared wall-clock timeout. Native child process OS sandbox, cancellation and group/descendant reaping belong to Lu's supervisor.
- `verify_backend_frame()` independently checks returned typed SAT assignments and input hashes. UNSAT, including from Z3/cvc5, is **never counted as an independently proven theorem** in P2; it is labelled `UNSAT_NOT_PROVEN` until a separate certified proof-checker is integrated. `UNKNOWN`, rejected requests, failures and timeouts cannot carry validated evidence.
- `SolverRegistry.disable()` stops **new** backend invocations. It is not a process-wide kill switch for already running workers; production revocation/kill must be implemented by Lu.
- `BackendResult` includes bounded trace correlation ID, request/output SHA-256, pinned backend file hash, result/evidence status, elapsed wall time and sanitized reason. Hashes establish local input/result linkage, **not** trust in a malicious machine or the natural-language-to-formula mapping.

## Admission, audit and execution boundaries

- Model-supplied backend name is only a selector for a host-registered and checksum-pinned absolute file. The caller cannot supply an executable path, flags or shell commands. Never auto-download backends.
- In this reference implementation `host_authorized=True` is a testing hook, **not** a production Lu host credential. Production must authenticate the Lu caller, apply C02 native OS confinement, quotas, cancellation and revocation, and supply signed/authorized host invocation metadata before dispatch.
- User content is never sent as raw unvalidated SMT-LIB. SMT-LIB can still stress or exploit a solver; untrusted formulas and native libraries require real OS-level isolation. Python subprocess timeout is not a Windows Job Object, privilege boundary or secure sandbox.
- Research backend track is intentionally not enabled in P2; a future research backend must be explicitly configured and opt-in, separately audited, subject to the same typed schema and host kill switch, and never silently promoted.
- Full proof checking, incremental multi-session solving, assumptions, unsat cores, arrays/strings/quantifiers and Windows binary packaging remain C10 P3 or later scope. P3 subsequently implemented bounded scoped sessions and finite Bool/BV proof certificates; general proof formats remain open. No solver performance or real-world efficacy benchmark has been run.

## Focused testing

`PYTHONPATH=.:tests python -m unittest discover -q`

`PYTHONPATH=. python tools/verify_protobuf_schemas.py --require`

`PYTHONPATH=. python tools/run_c10_p2_smoke.py`

The smoke requires an actual system Z3 library. If absent, it explicitly skips; it must not be counted as a pass. Reproducible source checkpoint includes no proprietary/third-party solver binary and does not include machine-specific absolute paths or solver raw model transcript.

## Historical P2 follow-on (C10 P3 now implemented in part)

Extend the same typed contract with independently checkable proofs/unsat cores (validate core *and* its unsatisfiability, not just its listing), assumptions and incremental sessions, additional standard theories, documented experimental backend capability manifests, host-controlled cancellation, and windows x86-64 packaged solver registration. Maintain audit/benchmark hooks without launching a major benchmark campaign.

## Research-track watchlist, not deployed in P2

- **Certified SMT proof interchange:** Alethe proof generation from cvc5/veriT and the independently maintained Carcara Rust proof checker are concrete future candidates for C10 P3. cvc5 documents theory-dependent proof coverage and a separate checker workflow: https://cvc5.github.io/docs-ci/docs-main/proofs/output_alethe.html . An **ITP 2025** paper documents independent cvc5 Alethe proof reconstruction in Isabelle/HOL (DOI `10.4230/LIPIcs.ITP.2025.26`): https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.ITP.2025.26 . These are promising verified techniques, **not** already integrated proof checkers.
- **SMT theory extension and reproducible interchange:** SMT-LIB v2.7 received clarifications in March 2026; future operators/theories must be implemented under explicit opt-in and type checks, not passed through raw SMT-LIB generated by models: https://smt-lib.org/news.shtml .
- **Research solver experimentation:** Reserve an independent, disabled-by-default backend slot with a paper/commit/build-digest provenance, pinned theories and kill controls; introduce only when a candidate has a trustworthy implementation and a focused functional validation suite. No neural-guided solver improvement or claimed performance win is assumed from research announcements.

No baseline versus research solver performance comparisons or model benchmarks were conducted during P2.
