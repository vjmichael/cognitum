# C05 expansion — six Protobuf-native scientific mathematics specialists (P0/P1/P2)

**Scope:** Cognitum-owned C05 experimental math kernels. **Lu was not modified.** These functions run only as trusted in-process reference tests, are **not installed**, **not enabled**, **not model-advertised**, and are **not OS-isolated**. Lu alone may authorize their future Core Extension registration and worker execution after C02 security proof.

## Task and platform decisions

The user's requested C05 expansion includes symbolic algebra, scientific functions, arbitrary-precision arithmetic, linear algebra, advanced solvers and scientific simulation. To avoid treating a code-evaluating math interpreter as a safe general calculator, version 1 provides six deliberately **restricted operations**, each with its own typed `cognitum.math.v1` Protobuf messages and negative tests. It is a meaningful starting implementation, **not a general-purpose CAS, SciPy replacement or physics engine**.

| Specialist / experimental operation | Implemented scope | Output semantics and main limit |
|---|---|---|
| `cognitum.math.symbolic` | Expand/derivative of rational polynomials through degree 6; exact rational-root factorization of degree ≤2 only; ≤48 AST nodes and bounded coefficients | Exact polynomial for expansion/derivative, or an equivalent factor expression in the existing `polynomial` field; irreducible rational quadratics remain expanded; **not** general factorization, integration or equation reasoning |
| `cognitum.math.scientific` | mpmath real `sin`, `cos`, `exp`, `log`, `sqrt`; 15–80 significant digits; finite canonical decimal input; absolute argument ≤100; trig in **radians** | Numerical approximation, **no certified error interval**. Precision context cloned per call so global `mp.dps` is unaffected |
| `cognitum.math.precision` | Decimal context add/subtract/multiply/divide/sqrt at 15–256 significant decimal digits | Finite-precision rounded decimal result, **not exact rational provenance**; core stdlib `decimal` |
| `cognitum.math.linear` | Exact determinant, matrix multiplication, and nonsingular linear solve; 1–4 rows/columns; `Fraction` inputs and outputs | Exact small rational matrix arithmetic; rejects invalid shapes, singular systems and unbounded values |
| `cognitum.math.root` | Bisection on real degree-≤6 polynomial with supplied sign-changing rational bracket and ≤128 iterations | Exact rational root enclosure via continuity, **not unique-root proof or arbitrary nonlinear solve** |
| `cognitum.math.simulation` | Bounded scalar harmonic oscillator `x'' = -ω²x`, discrete symplectic Euler, 1–256 steps, bounded step/stability input | Exact rational evaluation **of a discretized numerical model**; unquantified discretization error, no units or physical validation |

## Internal interface and limits

[`proto/cognitum/math/v1/specialists.proto`](../../../proto/cognitum/math/v1/specialists.proto) defines **separate** request/result messages for every operation. [`cognitum/proto/specialists_pb2.py`](../../../cognitum/proto/specialists_pb2.py) supplies real descriptor-backed Protobuf classes, compiler-verified as the **eighth** source schema. The [math kernel](../../../cognitum/scientific_math.py) accepts only bounded canonical binary Protobuf, validates each domain, and returns only its matching typed binary result. The response cannot give model permissions, run arbitrary Python, read/write files, launch a subprocess or use network access.

Every domain is hard-bounded by finite input lengths and allowed mathematical syntax. The symbolic grammar walks a **restricted Python AST**, manually permitting only `x`, numeric literals, bounded polynomial operators and degree/bit-size ceilings. It **never passes untrusted expressions to `eval`, `exec`, `sympy.sympify` or `parse_expr`**. SymPy documentation explicitly warns that its parsers use eval for some cases, so raw external expressions must not be passed to them. The first version deliberately avoids loading SymPy into the runtime.

Scientific functions use optional **mpmath 1.3+**, with a cloned precision context rather than mutable global precision; the approximate output has explicit limitations. Decimal precision (15–256 digits) and linear algebra use standard Python `decimal` and `Fraction`, respectively. Heavy SciPy solvers, unrestricted ODEs, arbitrary symbolic algebra and complex-valued numerics are **out of scope until independently reviewed and benchmarked**, and should remain additional optional specialists.

[`cognitum/math_catalog.py`](../../../cognitum/math_catalog.py) exports a **strict Protobuf-only inert catalog** containing six fixed developer-authored `use_when`/`avoid_when` descriptions and matching `type.googleapis.com/cognitum.math.v1...` type URLs. Its `registered`, `model_advertised` and `host_approved` flags must all be **false**; attempted activation or changed descriptions are rejected. It cannot be used as an installer, worker authorization, or Lu host ABI by itself. The original C01 CE handoff remains the single reviewed inert calculator, until Lu formally approves extending that handoff format. No JSON is introduced as internal protocol.

## Security and verification discipline

- **Zero new native privileges:** The existing `calc.rational` remains the only installed/trusted diagnostic plugin; six specialists are plain optional in-process **reference functions**, not registered capabilities. The C02 `start_isolated_worker(...)` gate still **unconditionally raises `PermissionError`**. Production execution must not bypass Lu's separate host signature/permission/effect/OS-isolation check.
- **No LLM or benchmarking claim:** Component tests do not verify that the selected transformer knew when to call a function, interpreted units properly, formalized the intended equation or improved on a conventional tool. C03 A/B/C/D matched Lu+model trials remain **not executed**.
- **Precision is not truth:** Exact coefficients, matrix solves and rational interval endpoints can be precise for the *entered model* without verifying the user's real problem. mpmath/Decimal answers are approximations; numerical uncertainty is not calibrated here. Symplectic Euler is exact rational arithmetic performed on a discretized physical assumption, **not an exact continuous trajectory**.
- **Hard bounds versus sandbox:** Input length, degree, bit-size, matrix size, iteration count, and scientific argument/precision bounds limit tested computational workloads. They are **not equivalent to resource isolation or robust denial-of-service protection** against adversarial native code.

## Tests and next gate

[`tests/test_c05_scientific_math.py`](../../../tests/test_c05_scientific_math.py) contains separate groups for every specialist: polynomial expansion/derivative and syntax denial; high-precision transcendental checks; precise decimal add/divide/sqrt; matrix determinant/product/solve and singularity/dimension denial; polynomial root interval; bounded oscillator energy drift; canonical Protobuf duplication/unknown-field rejection; and catalog default-off integrity. Existing C05 exact rational reference tests and C01–C04 regressions must stay green.

CI runs the same four Windows/Linux × Python 3.11/3.13 combinations with optional `[scientific]` dependencies, seven prior Protobuf schema compiler comparisons plus the new math schema and the 12-case synthetic replay. [C05 implementation CI 40465416831](https://github.com/vjmichael/cognitum/actions/runs/40465416831) passed **232/232 unit tests, 12/12 replay, 10/10 calculator smoke and all eight Protobuf compiler/schema checks per Windows/Linux × Python configuration**. Each specialist is separately testable using `python -m unittest discover -s tests -p test_c05_scientific_math.py -v`. This is P2 **bounded component behavior**, not a secure Lu Core Extension or real model efficacy.

**Future incremental expansion:** independent symbolic algebra checks and factorization/integration with safe AST-to-SymPy object construction (never eval-based string parsing); numerical error-bound witnesses and special functions; larger/structured/sparse linear algebra; bounded multidimensional root/optimization solvers with convergence certificates; explicit units, dimensions, integrators, conservation tests and reference systems for ODE/scientific simulations. Each has its own provisional Protobuf schema/version and OS sandbox/benchmark gate.


## P2.1 follow-on checkpoint (November 4, 2026)

C14 is closed independently; this C05 work does not reopen causal research.
The existing typed `PrecisionRequest.action` accepts two additional bounded operations:
`subtract` and `multiply`. They use the same finite canonical-decimal input
checks, local Decimal precision context (15–256 digits), typed Protobuf response,
and default-off host authorization policy as the prior three operations.

`tests/test_c05_independent_invariants.py` adds an independent Leibniz
permutation determinant comparison, exact `Ax=b` residual checks,
polynomial root-enclosure sign/nesting/width witnesses using independent Horner
evaluation, and singular-system rejection. Existing specialist tests now cover
new Decimal operations and rounding behavior.

**Admission remains unchanged:** no model-visible tool or Lu registration,
no OS-isolated scientific worker, no general CAS claim. CI and independent
on-host validation must pass before this checkpoint can be called verified.

## P2.2 rational quadratic factorization (November 4, 2026)

The typed `SymbolicRequest.action` now accepts `factor` for polynomials of degree **at most two** over the rational numbers. Discriminants are computed exactly, and `math.isqrt` checks whether numerator and denominator are perfect squares; there are **no floating-point square-root guesses**. If two rational roots exist (including repeated roots), the result is an expression of exact linear factors with the leading rational coefficient. Linear and constant cases are supported. Irreducible rational quadratics return their expanded polynomial with `irreducible_over_rationals` in limitations. Degree three and higher is rejected for this operation, not silently called fully factored.

The current `SymbolicResult.polynomial` Protobuf field is reused for the equivalent factor **expression**, rather than introducing a wire-incompatible result. The response includes `polynomial_field_contains_factor_expression`, `factor_degree_le_2`, and the relevant status limitation so consumers do not misinterpret representation. Every returned factor expression must pass the existing bounded AST parser and re-expand exactly to the original rational polynomial. This is not a completeness proof for general symbolic algebra. Existing negative tests remain in force; new tests require exact equivalence across integer/rational, repeated-root, zero-root, negative-leading, constant and rational-irreducible cases.

All six specialist entries remain inert and unavailable to models. Lu authorization, worker isolation, and controlled benchmark evidence remain separate future gates.

## P2.3 exact polynomial integration (November 4, 2026)

The inert Protobuf `SymbolicRequest.action` supports `integrate` for single-variable rational polynomials of input degree at most **five**, producing exact antiderivatives of degree at most six. This is an **indefinite integral with the integration constant normalized to zero**: other antiderivatives differ by an arbitrary additive constant. The existing `SymbolicResult.polynomial` field contains the canonical zero-constant antiderivative (not a numerical definite integral).

The input retains the existing strict, non-evaluating AST and all size, degree and rational coefficient bounds. The producer reparses the result through the same bounded grammar and differentiates it to assert exact coefficient identity before returning the response. The response includes `antiderivative_constant_zero`, `integrand_degree_le_5`, `indefinite_polynomial_integral`, `derivative_identity_checked`, and `intent_not_verified`. This is an internal invariant, not an independent verifier or user-intent certification.

The regression suite exercises zero/constant, rational, negative, sparse, degree-five, and disallowed degree-six inputs. It checks typed Protobuf responses and performs 60 seeded rational-polynomial cases with **independent exact rational sample-point derivative identities**. Cases exceeding existing 160-character expression grammar are excluded by the same bounded input policy.

C05 remains unregistered, unadvertised, and unavailable to models. CI/on-host validation is a separate gate; no Lu/C02 capability or OS privilege is granted.
