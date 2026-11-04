# C10 — Practical SMT Implementation Closeout

**Decision:** 2026-11-04.
**Status:** CODE SCOPE FROZEN FOR REVIEW; CI and merge NOT YET VERIFIED. The previous Boolean-only closeout is superseded.

## Purpose and chosen implementation

C10 supports formal *checking of already typed constraints*, not a guarantee that an LLM correctly translates a natural-language request into mathematics. Following the project-wide established-libraries-first decision, **Z3 and cvc5 are the production-intended solver backends**. Cognitum does not reimplement their SMT algorithms.

The previous small Boolean exhaustive solver is kept only as a reference oracle.

## Implemented in PR #67

- Two optional maintained backend adapters (`formal-z3`, `formal-cvc5`) behind a strict, bounded linear-integer constraint model. Current fragment is QF_LIA with finite integer domains: <=8 variables, maximum 33 values per variable, <=64 constraints, <=128 linear terms, <=10,000 ms solver logical timeout, and capped coefficients.
- Backend result handling distinguishes SAT, independent finite-domain UNSAT_EXHAUSTIVE, solver-reported UNSAT_UNVERIFIED, UNKNOWN, and UNSUPPORTED.
- SAT witnesses are independently re-evaluated with Python exact integer arithmetic against **all original constraints**. No model or solver-originated code is evaluated.
- UNSAT is independently marked exhaustive only when <=4096 finite assignments can be replayed independently. Larger UNSAT claims remain **UNSAT_UNVERIFIED** and must not be presented as an independently certified theorem.
- Typed `cognitum.formal.v1` Protobuf schema, descriptor-backed bindings, strict canonical frame validation, bounded result decoding, request correlation hashes, and explicit model-assurance tamper rejection.
- Tests for invalid types/limits, wrong assignments, forged status/assurance, constraint contradictions, unsupported backends, negative integer witnesses and finite exhaustive comparison.
- Dedicated GitHub Actions workflow installs actual optional Z3/cvc5 on Windows and Linux with Python 3.11/3.13, executes native tests, and independently compiles/compares the Protobuf descriptor.

## Not implemented / deliberately non-claims

This is not a general first-party SMT engine. Quantifiers, unrestricted nonlinear arithmetic, mixed real-number and bitvector reasoning, arrays, uninterpreted sorts, SMT-LIB scripts, Lean integration, independently checkable native Z3/cvc5 UNSAT certificates, and unbounded proofs are outside the implemented typed fragment. The mature solvers may support these theories internally; **the Cognitum interface does not yet expose them**.

Logical solver timeouts are not OS process termination. No hostile native solver process isolation, Lu host authorization, model registration, signed execution receipts, real-model A/B evaluation, or proof-of-user-intent formalization is claimed. Those require C02/C03/C04 and Lu interface acceptance.

## Validation requirements before merge

- Latest Python regression tests across supported operating systems and Python versions must pass.
- Each optional solver/backend must actually install and run its positive and negative tests; missing optional backend is not allowed to be counted as an acceptance pass for that backend.
- The compiled Protobuf schema must match the checked-in descriptor.
- Security/assurance regression tests must pass.
- Any failure requires a targeted fix and new validation; no papering over failures as skipped scientific cases.

## Engineering closure policy

Do not open a C14-style optimization program for C10. Freeze this *practical implementation scope* and defer extensions until actual tasks require a specific SMT theory or checker. Do not label the entire original full-theory/formal-proof research design implemented. Future model-facing privileges and production acceptance remain host-owned integration gates. C14 remains closed.

The engineering work can be closed after verification and merge; until then, the correct state is **implementation committed, validation pending**.
