# C10 — P0/P1 Bounded Protobuf SMT and Formal Property Checking

**Status (2026-10-27): Implemented offline Python reference; no Lu host/tool registration, no unrestricted SMT solver integration.** C08/C09 remain deferred. Full comparative benchmarks are postponed by user direction; only focused synthetic functionality tests are run during development.

## Exact supported fragment

`proto/cognitum/formal/v1/solve.proto` defines versioned `SolveRequest`, `SolveResult`, `CheckRequest`, `CheckResult`, `PropertyRequest`, and `PropertyResult`. Internal transport is typed Protobuf. No executable solver-language scripts, arbitrary Python text, model-generated authorizations or network access. The formula fragment is:

- A conjunction of propositional clauses over **at most 10 atomic predicates**; signed one-based literal indices (CNF).
- Atomic predicates are independently declared Boolean variables or **integer difference bounds** `x - y <= c`, where `x`/`y` may be `$ZERO`. Negative difference literals are exact integer complements: `y - x <= -c - 1`.
- At most 8 declared integer variables, 48 clauses, 8 literals per clause, integer bound magnitude ≤ 1,000,000, 8 KiB request and 128 KiB result; exhaustive search limited to at most 1,024 atom assignments, optionally less per request.
- **SAT:** returns exact per-atom Boolean values plus a normalized integer model. Independent checker checks every clause and every theory atom against model values.
- **UNSAT:** must have one independently validated leaf per exhaustive atom assignment. A leaf either references an actual falsified clause or supplies a directed negative-cycle witness in the difference-constraints graph. Checker independently checks all leaves; it does **not** trust the solver's `UNSAT` assertion or invoke the solver.
- **UNKNOWN:** a budget or proof-size cap prevented a conclusive certificate; it has no witness and is **never** accepted as a proof.

This is a deliberately small, complete SMT fragment implemented with exact integer difference-constraints theory and bounded exhaustive Boolean assignment search. It is not a general Z3/cvc5 replacement: no bitvectors, quantifiers, arrays, nonlinear polynomials, real arithmetic, uninterpreted functions, SMT-LIB parser, general unsat cores or unbounded optimization. SAT/UNSAT are sound only for the **supplied typed constraints**; solver success never establishes that an LLM's natural-language translation was correct.

## Formal property verification

For explicit `PropertyRequest(assumptions, required_literal)`, the solver examines the original assumptions and the counterexample formula `(assumptions AND NOT required_literal)`.

- `PROVEN`: assumptions have a checked satisfying model **and** the negated claim has a checked exhaustive UNSAT certificate.
- `COUNTEREXAMPLE`: a checked model for the negated claim exists; this is a falsification of the proposed entailment.
- `INCONSISTENT_ASSUMPTIONS`: the original assumptions themselves have a checked UNSAT certificate. This is a **vacuous** implication, never promoted to an ordinary proof.
- `INCONCLUSIVE`: budgets or limits prevent required evidence. No fake proof.

The `verify_property_frame` verifier checks both exact bound request fingerprints and all relevant underlying witnesses/certificates. It does not call the solver. Proof outputs always have `formalization_verified=false`, `host_approved=false`. Separate Lu C02/C04 authorization and an audited problem-formalization stage are prerequisites for any model-facing CE.

## Implementation and testing

- Implementation: `cognitum/formal_solver.py` and `cognitum/proto/formal_pb2.py`.
- Tests: `tests/test_c10_formal.py` validates SAT/UNSAT/UNKNOWN, signed Boolean clauses, strict integer negation, negative cycles, tampering, bounds, conflicting assumption vacuity, request hashes, malformed/duplicate/unknown Protobuf, 160 additional seeded random small formulas checked against an independent exact finite-model oracle.
- Smoke: `PYTHONPATH=. python tools/run_c10_smoke.py` (five deterministic scenarios).
- Full Python regression: `PYTHONPATH=. python -m unittest discover -q`.
- Independent Protobuf source/binding compilation: `PYTHONPATH=. python tools/verify_protobuf_schemas.py --require`; uses actual vendored `protoc` when available.

No SMT solver executable, third-party SMT binding, production Lu ABI, real-world correctness benchmark or native Windows host tests are represented as passed by these offline results. End-to-end host permissions, true OS sandboxing and C06/C07 Lu authentication remain unresolved.

## Next functional implementation (C10 P2)

Add an **optional** local Z3/cvc5 backend only after availability and source integrity are established, retaining the present exact fragment verifier and fail-closed `UNKNOWN` behavior; introduce domain-specific certificate checking for new supported theories rather than accepting a remote/black-box UNSAT answer. Add constraint composition and host-scoped tool catalog once C04 has a trusted no-side-effect native-tool contract. Keep comprehensive A/B performance benchmarks for final component integration.
