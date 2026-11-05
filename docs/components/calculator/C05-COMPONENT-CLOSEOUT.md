# C05 — Scientific Mathematics Component Closeout

**Decision date:** 2026-11-04. **Status:** C05 *component implementation complete for the bounded v1 scope*, subject to branch CI verification and merge. This is **not** a Lu-deployed capability, a general-purpose computer algebra system, or proof of model-level mathematical efficacy.

## Implemented capabilities

- Exact bounded rational arithmetic and independent expression-parser differential tests from the original C05 checkpoints.
- Six Protobuf-native inert specialists: single-variable polynomial symbolic operations, real scientific approximations, 15–256-digit Decimal operations, exact 1–4 dimensional rational linear algebra, sign-bracketed polynomial roots, and bounded oscillator simulation.
- Symbolic expansion and derivative through degree six.
- **P2.2:** exact rational-root factorization through degree two, including repeated roots and reducible/irreducible reporting; no floating-point root guessing. Every factor expression is re-expanded and compared exactly.
- **P2.3:** exact rational-polynomial indefinite integration through input degree five; antiderivative constant normalized to zero; exact differentiation identity checked before return.
- **P2.1:** Decimal subtraction and multiplication added to existing add/divide/sqrt with existing precision bounds; independent Leibniz determinant identities, linear-equation residuals, and polynomial root bracketing witnesses.

All operations retain strict bounded Protobuf serialization, type separation, rejection of unknown fields, and fail-closed mathematical input validation. No model-supplied Python is evaluated. The symbolic `polynomial` result field contains a polynomial for integration, but a factor **expression** for factorization; explicit limitations distinguish these cases.

## Verification and honest limits

Unit suites include deterministic rational examples, unsafe grammar rejection, independent identities, roundtrip witnesses, singular-system rejection and randomized bounded input checks. **Merge is gated on fresh branch CI**, not on historical passing baseline reports. The early P2.3 CI caught a fixture generator that exceeded the existing AST node bound; this was fixed by generating only admissible inputs, not by weakening parser limits.

These checks establish *bounded component behavior only*. They do not attest:
- User-intent formalization or model tool selection and efficacy.
- Authenticated OS confinement, native worker launch permission, or scoped host grants.
- Arbitrary symbolic mathematics, high-degree factorization, general nonlinear optimization, verified numerical error intervals or physical simulation correctness.
- Certified observational/causal inference (C14 is separately closed).

## Deferred acceptance (not new C05 research)

1. **C02/C04 Lu host security and integration:** code signing, process confinement, cancellation/revocation, permission grants, and receipts must be proven using the actual host.
2. **C03:** matched real-model A/B benchmarks, pinned conventional-tool comparisons, and authentic latency/memory/VRAM measurements.
3. **Before Lu 2.0:** revisit mathematical expansion only if end-to-end evidence identifies a concrete missing operation. General-purpose numerical solver/ODE/CAS expansion is explicitly not part of this closed bounded v1 scope.

**Development policy:** Do not reopen C05 for speculative mathematical research; track integration gates with C02/C03/C04. C14 remains closed. Lu source and permissions are unchanged by this checkpoint.
