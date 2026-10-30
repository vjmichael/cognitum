# C10 P3 — Native incremental SMT sessions and independently checked finite UNSAT

**Implementation date:** 2026-10-27. **Status:** Functional Python reference on Linux using a *real host-pinned Z3 shared library*. Focused tests only. Native Lu Rust and Windows x86-64 integration remain untested.

## Established standard and research assessment

- [SMT-LIB 2.7](https://smt-lib.org/papers/smt-lib-reference-v2.7-r2025-07-07.pdf) standardizes `push`, `pop`, `check-sat-assuming`, named assertions, unsat cores and proof inspection. P3 uses `push/pop` and *scoped temporary assertions* with equivalent checking semantics for arbitrary well-typed Boolean assumption expressions, not native `check-sat-assuming` or `get-unsat-core` calls. The distinction matters for proof/metadata provenance.
- [Z3 C API](https://z3prover.github.io/api/html/group__capi) exposes `Z3_eval_smtlib2_string`, which evaluates incremental commands in the same retained solver context. P3 executes one generated SMT-LIB script through the isolated Z3 worker and receives all CHECK statuses from that same process. A separate per-check invocation obtains independently rechecked SAT witnesses and tests backend agreement.
- [cvc5 Alethe proof format](https://cvc5.github.io/docs-ci/docs-main/proofs/output_alethe.html) and the independent Carcara Rust checker support a richer proof-certificate path; **they are not integrated or tested in P3**. For general arithmetic UNSAT, solver claims are not treated as independently proven.
- Experimental theorem-proving approaches may be added behind optional, common Protobuf capability contracts, with versioned evidence and unchanged host authority. No research superiority claims were evaluated here.

## Implemented features

1. `proto/cognitum/formal/v1/advanced.proto` defines a bounded `SessionPlan` of `PUSH`, `POP`, `ASSERT`, `CHECK` steps; checkpoint results carry exact per-check request digests, status, model, optional finite certificate, and independently checked unsat core indices. `SessionReceipt` re-verifies every statement-bound outcome. Checked-in `formal_advanced_pb2.py` has a descriptor independently compared to the real `.proto` source by `protoc`.
2. `cognitum/formal_session.py` compiles a *typed* Protobuf request into generated SMT-LIB, enforces balanced scope stacks and limits, executes every CHECK through the same local solver process, and uses separately validated P2 SAT model checks for each SAT checkpoint.
3. `cognitum/formal_finite.py` implements a distinct exhaustive interpretation of Boolean and bitvector logic. For up to **12 total Boolean/BV bits** (at most 4096 valuations), it enumerates **all** assignments, emits a digest-bound certificate, and recomputes the entire proof at verification. Unsupported theories and excessive domains **never become proofs**.
4. On finite UNSAT, `cognitum/formal_session.py` obtains a **deletion-minimal** core from the input assertions and temporary assumptions (bounded to 12 candidate assertions) using repeated exact finite UNSAT checks. It is **not guaranteed to be a globally smallest core**. All core indexes and their original scopes are independently recomputed by the receipt checker.
5. Calls are denied by default; a synthetic `host_authorized` flag is the P2 reference boundary. Only a Lu-native authenticated broker can establish actual production authority. The host-owned registry can disable new work, but cancellation of in-flight processes and OS sandboxing remain Lu's responsibility. Solver paths are host-pinned with digest verification.
6. The result includes backend metadata and execution time from P2. Session sequence, traces and all input/output digests are available for future audit and benchmark pipelines; **no performance benchmarks were conducted**.

## Strict limits and invariants

- Maximum 48 operations, 8 checks, 8 additional active push levels, 12 assumptions per CHECK, 64 assertions in any snapshot; global SMT-LIB input and output ceilings. Per-check bounded worker timeouts, not an OS-complete resource ceiling.
- The session is an **atomic logical batch of steps** in a fresh worker, not a durable interactive solver that persists after return. For each SAT status, P3 launches a fresh per-snapshot SAT model query; disagreement yields inconclusive rather than proof. This gives correct incremental semantics, **not a claim of fastest incremental performance**.
- The independent verifier only certifies finite Bool/BV UNSAT within the domain bound. It uses different evaluation logic than the backend and does not accept solver `unsat` as a proof. Unsupported integer, rational, quantifier, string, array and general-theory proofs are explicitly withheld.
- `UNKNOWN`, timeout, malformed solver responses, unbalanced scopes, stale/different binaries, tampered models, forged core indices or false host/semantic approval flags fail closed.
- Mathematical proof of a *formalized input* does not establish that an LLM's translation from ordinary language is correct. Only the Lu host can admit a genuine source of authority.

## Functional test and follow-on

`PYTHONPATH=.:tests python -m unittest tests.test_c10_p3_advanced -q` exercises independent certificate checking, 2-bit modular wrap, native Z3 incremental scope rollback, ephemeral assumptions, finite unsat cores, integrity checks and negative cases. `PYTHONPATH=. python tools/run_c10_p3_smoke.py` covers the narrow native-Z3 flow. `PYTHONPATH=. python tools/verify_protobuf_schemas.py --require` independently checks all schema descriptors.

**Next:** C11 combinatorial optimization should start from established CP-SAT/OR-Tools and HiGHS libraries, plus research adapters. General SMT unsat proof checking through cvc5/Alethe+Carcara remains a separate optional C10 follow-up—not a prerequisite for C11. Benchmark A/B runs are deliberately deferred.
