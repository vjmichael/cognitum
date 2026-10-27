# C05 / P0 — Exact rational calculator validation and reuse

**Date:** 2026-10-27  
**Component:** C05 exact computation  
**Lu integration:** Read-only design reference; **no Lu code or model changes**.  
**Evidence state:** Existing `calc.rational` calculator and native Protobuf request/result messages were already implemented before this C05 review. This study narrows the safety and independent correctness acceptance scope; actual loaded-transformer efficacy remains **P3 pending**.

## Task and hypothesis

**Intended Lu+model task:** Given a user-supplied mathematical problem, the loaded model may formalize the intended arithmetic as a bounded expression; Lu may offer its approved `cognitum.calc.rational` capability to evaluate *that expression* exactly. The model still must check that its formalization matches the user's intent, units and assumptions. **Exact output is not independent validation of intent.**

The falsifiable P3 question is whether Lu+selected transformer using this specialist calculator produces more correct **final user-task answers** than (A) Lu+model alone and (B) Lu+model using a competent ordinary calculator or Python/SymPy exact arithmetic, with the same task set and matched model/backend/tool-budget settings. Include (C) the Cognitum CE and, only if justified and actually available, (D) bounded composition. Measure unnecessary/missed tool calls, formalization mistakes, final-answer grading, timeouts, latency, RAM and token/cost effects. Do not equate exact math self-tests with a model benchmark.

## Existing implementation and alternatives

The shipped calculator is a **strict arithmetic AST evaluator** using Python standard-library `fractions.Fraction`: no `eval`, imports, system access, variables, I/O, vector databases, GPU, or network. Decimal lexical tokens become exact rationals (e.g., `0.1+0.2 → 3/10`), not binary floats. It supports unary `+`/`-`, `+`, `-`, `*`, `/`, parentheses and integer exponentiation. It enforces 256 input characters, 64 AST nodes, depth 16, 40-character numeric tokens, power exponent absolute value ≤16 and 1024-bit numerator/denominator result limits. The default registry still starts with the capability disabled unless explicitly nominated by the trusted caller.

**Mature alternatives and role:** `Fraction` is the exact arithmetic baseline for this rational-only domain; `decimal.Decimal` is an independent exact decimal-literal control. SymPy could extend algebra and formal manipulation but is unnecessary overhead and a different authority/complexity boundary for the current input grammar. Local LLM token math and binary floating point are not correctness oracles for exact decimal arithmetic. C05 should stay CPU-only and stdlib-first; GPU/FPGA would add complexity without a demonstrated benefit for bounded short expressions. No external package or licensing change is needed.

## P0 safety and reproducibility decisions

- **One approved operation:** `calc.rational` under C01 `cognitum.v1.CalculateRationalRequest/Result` Protobuf type URLs. The reference evaluator must **not** become a second model-advertised operation or a rival Lu agent.
- **Input grammar:** normalize nothing implicitly. Permit ASCII digit, dot, parentheses, arithmetic symbols and bounded ordinary spacing only; reject unicode lookalikes, multiline, hidden controls, comments, function calls, exponent notation, hex and numeric underscores instead of silently broadening Python's parser grammar.
- **Independent checks:** Use a bounded AST-free recursive-descent **reference parser** in C05 for deterministic differential tests. Both paths use Python `Fraction`, so agreement tests grammar/implementation consistency **but cannot prove the same underlying arithmetic primitive formally correct**. Add direct `Decimal` and `Fraction` golden controls.
- **Native byte boundary:** Exact request/result decoding rejects unknown, duplicate/shadowed and noncanonical Protobuf fields, even though ordinary Protobuf decoders allow last-value-wins. C01 result envelopes must preserve `intent_not_verified` and computation evidence; neither Protobuf nor metadata authorizes a worker.
- **Keep fail-closed launch:** C02's `start_isolated_worker` stays disabled, and this phase does not produce a Lu-native executable CE or bypass C02 and C04 host permission/trust boundaries.
- **Evaluation:** seeded fixed-corpus differential and adversarial syntax/resource tests across Windows/Linux Python 3.11/3.13, plus existing C03 10-case component smoke and 12-case legacy replay. Do not report latency gains or P3 outcomes without actual matched model trials.

## Limits

The numerical domain is exact rational arithmetic on **already formalized** inputs—not unit analysis, symbolic algebra, arbitrary-precision unrestricted computation, proofs about model reasoning, security attestation, or cognition improvement. A malicious caller cannot request additional host effects by supplying arithmetic source text. No production authorization, real OS sandbox or trained model is implied.

See the [C05 implementation and regression record](P1-P2-exact-verification.md), the [C03 benchmark contracts](../evaluation/P1-P2-host-benchmark-capture.md), and [C02 OS gate](../security/P2-host-conformance-gate.md).

## Updated P0 decision — modular scientific expansion (2026-10-27)

**Supersedes the older rational-only dependency scope above; the original research remains intact as historical baseline.** User-directed C05 now comprises six *separate* bounded reference capabilities, summarized in [P1/P2 scientific specialists](P1-P2-scientific-specialists.md): rational-polynomial symbolic expansion/derivative, mpmath transcendental approximations, user-selectable 15–256-digit Decimal arithmetic, exact small rational linear algebra, bracketed polynomial root solving and scalar harmonic-oscillator symplectic-Euler simulation. All are **first-stage restricted implementations** rather than unrestricted algebra, general optimization/ODE solving, or physics.

### Evaluated libraries and attack surface

- Python `ast` plus explicit `Fraction` coefficient operations allows a small polynomial subset without executing untrusted text. SymPy's [`parse_expr` documentation](https://docs.sympy.org/latest/modules/parsing.html) warns that it uses `eval` and should not receive unsanitized input; [`sympify`](https://docs.sympy.org/latest/tutorials/intro-tutorial/basic_operations.html) has the same warning. Do not route a model-supplied string directly to either. SymPy object APIs remain a possible optional *future* expansion only after strict AST construction and independent tests.
- [mpmath precision](https://www.mpmath.org/doc/current/basics.html) supports configurable precision, but an approximation is not a certified error interval. Clone the mathematical context for each call, cap arguments/precision, and declare approximation semantics. Install only with the optional `[scientific]` extra.
- Python `decimal.Decimal` supplies standard-library CPU decimal contexts; `Fraction` supplies exact rational small-matrix and discrete-model arithmetic. SciPy/NumPy can be studied as **external conventional comparators** for future full numerical solvers, but no separate native CE registration or dependency on them is introduced in this first slice.
- CPU is the preferred implementation for six bounded, low-dimensional operations; there is no supported evidence that FPGA/GPU acceleration would improve the user-facing Lu+model task. Future dense/sparse larger matrix workloads may require a new research and hardware baseline.

### Predeclared next security/scientific gates

Every specialist must reject unsupported syntax, unknown Protobuf types, malformed/duplicate wire tags, oversize inputs, excessive iterations/precision/degree/matrix dimensions and missing domain assumptions. Separate P2 unit tests provide limited numerical and exact reference sanity checks. Before claiming reliable scientific answers, add independent numerical error bounds or comparative library controls where possible; for physics, validate units, initial/boundary conditions, energy and convergence behavior against known solutions.

**Critical:** these are trusted in-process scientific *reference kernels*. They cannot run through the C02 production worker gate (still hard-denied), are not installed or model-advertised Lu CEs, and cannot demonstrate model-task gains without real C03 matched A/B/C/D trials.
