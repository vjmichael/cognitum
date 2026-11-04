# C10 — Formal Reasoning: bounded Boolean reference closeout

**Date:** November 4, 2026.
**Disposition:** **Bounded P1/P2 Boolean reference implementation completed for review; C10 full SMT design is NOT closed.** Native Protobuf host integration and solver-theory expansion are deferred. This document must not be interpreted as production readiness.

## Implemented in this branch

- `cognitum/formal_boolean.py`: developer-owned frozen dataclasses `CNF` and `Decision`, no parser for arbitrary Python/model code, no external solver dependency.
- Boolean CNF as integer signed literals, up to 12 variables / 64 clauses / 256 literals, and at most 4096 exhaustive assignments.
- Distinct statuses: `SAT` with a complete Boolean witness, `UNSAT_EXHAUSTIVE` only after all assignments are examined, and `UNKNOWN_BUDGET` where an assignment budget runs out.
- An independent replay verifier checks SAT witnesses and independently enumerates all assignments for an UNSAT claim. An UNKNOWN result proves nothing about satisfiability. The verification is for a *tiny finite fragment*, **not a general SMT proof certificate**.
- `tests/test_c10_boolean.py`: SAT witness tamper rejection, exhaustive UNSAT replay, budget cutoffs, no clauses / empty clause, all 512 subsets of 9 two-variable clauses checked against an independent Cartesian-product oracle, invalid literals/types/bounds, assurance spoofing, and unchanged calculator plugin registration.

## Deliberately unsupported

No integers/reals/arrays/bitvectors, quantifiers, temporal logic, unit-aware formulas, uninterpreted functions, nonlinear arithmetic, SMT-LIB scripts, general Z3/cvc5 integration, Lean proofs, general UNSAT certificates, native Protobuf C10 schema, OS sandbox, or model-visible Lu registration. The previous portfolio's C10 design target remains intact but *unimplemented outside this finite Boolean slice*. No benchmark or real-model formalization accuracy claim is made.

## Verification and release boundaries

The small reference is CPU-only, stdlib-first, and has no authority to launch workers, install tools, or claim Lu permissions. The typed Python inputs are trusted developer structures, **not a safe LLM-to-C10 protocol**. Calling a Boolean instance correctly is distinct from translating the user's intent into formulas. The whole-Lu A/B gate (C03), OS isolation and authorization (C02/C04), and native protocol admission must be tested separately.

**Closeout rule:** Stop expanding the bounded reference component for now after CI passes. Keep the broader C10 SMT/full-proof portfolio **open in design**, and reopen implementation only when a concrete application requires it. Do not describe the full C10 component as completely implemented or independently certified.
