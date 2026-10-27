# C05 / P1–P2 — Verified exact arithmetic and strict native input

**Component:** C05 exact calculator  
**Implementation scope:** Cognitum only. Lu's selected transformer, code, tool registry, profiles, install state and runtime are **unchanged**.  
**P0 basis:** [Exact arithmetic research](P0-research.md)  
**Status:** The existing `calc.rational` operation has improved admission and verification tests. Still **not** a Lu-installed CE, OS-confined worker, automated model-intent verifier or P3 efficacy benchmark.

## P1 changes

1. [`cognitum/plugins/calculator.py`](../../../cognitum/plugins/calculator.py) checks the **deliberately narrow ASCII arithmetic alphabet** before the existing Python AST path. Digits, operators `+`/`-`/`*`/`/`/`**`, periods, parentheses and bounded ordinary spacing are supported. Unicode lookalikes, newline/control bytes, comments and code-bearing source remain unsupported. Existing node/depth/length/power/bit-size bounds remain in force.
2. [`cognitum/exact_reference.py`](../../../cognitum/exact_reference.py) implements a separately structured **tokenizer and recursive-descent arithmetic grammar**, not another advertised CE. Its precedence handles signed unary operations and right-associated integer exponentiation. This checks the production AST evaluator against a different parsing algorithm but shares `fractions.Fraction` as the arithmetic primitive; it is **not a mathematical proof or an independent library comparison**.
3. [`cognitum/protobuf_codec.py`](../../../cognitum/protobuf_codec.py) now refuses **duplicate known scalar tags, field shadowing, unknown nested tags and noncanonical deterministic bytes** when parsing Cognitum's existing native `cognitum.v1` request/result messages. Ordinary Protobuf permissive last-value-wins behavior is not acceptable at this strict tool boundary. Native type URLs and Lu-owned ToolCall/ToolReply envelopes are not changed.
4. No new Protobuf schema, developer signing identity, model-visible tool, sandbox bypass or independent agent loop is introduced. The native `CalculateRationalRequest` and `CalculateRationalResult` remain canonical and are still compiler-verified.

## P2 tests and reproducibility

The [C05 tests](../../../tests/test_c05_exact_verification.py) exercise:

- Decimal-literal exactness against `Decimal → Fraction`, leading-dot decimals, unary/power precedence, denominator and signed expression handling;
- **600 deterministic pseudorandom expressions**, generated with a fixed `random.Random(0xC0505)` seed, compared between production AST and AST-free reference parser when valid; rejected/resource-bound cases are checked for denial;
- Unicode confusables, multiline/control bytes, imports, attributes, comments, code-looking expressions and unsupported grammar;
- huge exponent/magnitude attacks, divide-by-zero and invalid exponent cases;
- forged native Protobuf request/result known-field shadowing and unknown nested evidence fields;
- exact result roundtrip retaining computation provenance and the required `intent_not_verified` limitation;
- continued C02 production worker-launch denial, no new calculator operation.

**Observed branch CI:** [40462149387](https://github.com/vjmichael/cognitum/actions/runs/40462149387) passed **216/216 Python unit tests**, **12/12 legacy synthetic replay**, **10/10 C03 component evaluation** and **seven Protobuf compiler/descriptor matches** in *each* of Ubuntu and Windows × Python 3.11 and 3.13. A later documentation-only run and pull-request CI must also be green before merge.

The seeded samples are deterministic **test fixtures**, not held-out Lu+model user tasks; passing them cannot establish that an LLM selected the right tool or formalized the user's request correctly. No measured latency, memory, GPU, energy or end-to-end accuracy claims were generated.

## C05 remaining gates

- **P3:** matched Lu+model A/B/C/D testing with a properly pinned conventional exact-calculator competitor and actual trusted telemetry, once native host tool visibility/invocation and C02 security are approved.
- **Formal verification:** a second parser sharing `Fraction` is a differential check, not a formal algebraic certificate. Any future proof system requires independently checked witnesses and scoped formalization.
- **Output trust:** Protobuf wire canonicalization prevents certain ambiguity classes but is not publisher authentication, process isolation or consent.
- **Lu-side compatibility:** Existing `ToolDescriptor.effect` lacks a genuine pure/no-effect variant on the inspected Lu branch. Installation/approval, model visibility and the host collector remain the separate Lu team's decision; no Lu modification is made here.

See [C03 benchmark plan/capture](../evaluation/P1-P2-host-benchmark-capture.md) and [C04 collector claim verifier](../integration/P0-P2-host-collector-receipt.md) for the still-pending end-to-end performance gate.
