# C03 / P1–P2 — Protobuf-native synthetic evaluation contract

**Date:** 2026-10-26 (user-local)  
**Owner:** Cognitum only. Lu repository and its selected transformer remain untouched and uninvoked.  
**Status:** P1 component-only Protobuf evaluation code committed; P2 regression/CI verification recorded after successful run. **Not P3 host-model efficacy evidence.**  
**Depends on:** C01 typed exact arithmetic and native Protobuf, C02 no-worker-launch gate, [C03 P0 baseline design](P0-research.md).

## Scientific boundary

The evaluation question remains **whether Lu with its selected transformer completes real tasks better with Cognitum** compared with the *same* Lu+model and established conventional tools. That comparison is impossible today: the experimental native CE is not installed/approved and C02 real OS worker isolation is not verified. A local correct arithmetic answer cannot establish better task interpretation, model tool routing, end-to-end quality, speed, or energy usage.

This milestone freezes a **deterministic component correctness check**, distinct from the existing 12-case JSON replay. It deliberately does **not** record any model/provider latencies, guessed GPU counters, implied permissions or synthetic data as customer prompts.

## Canonical native messages

[**`proto/cognitum/eval/v1/evaluation.proto`**](../../../proto/cognitum/eval/v1/evaluation.proto) defines `cognitum.eval.v1` messages and closed enums:

- `EvaluationSuite` — v1, `COMPONENT_SYNTHETIC` tier, pinned `synthetic_calc_v1` suite identity, ten public literal arithmetic inputs and expected statuses; `contains_real_user_data=false`.
- `EvaluationCase` — stable identifier, bounded **synthetic** arithmetic expression, expected exact canonical rational or expected rejection. It is not a general-purpose prompt or private conversation field.
- `HostArm` — A `HOST_ONLY`, B `CONVENTIONAL_TOOL`, C `COGNITUM_SINGLE`, D `COGNITUM_COMPOSITION`. All four are preregistered as **planned only**, with no fabricated result, tool-selection evidence or baseline comparison.
- `EvaluationCaseResult` — derived `EXACT_MATCH`, `EXPECTED_REJECTION`, `INCORRECT_RESULT`, `UNEXPECTED_REJECTION`; only bounded rational output or sanitized `invalid_expression`, never arbitrary exception text.
- `EvaluationReport` — SHA-256 of the canonical binary suite, counts and results, explicit `model_arms_executed=false`, `promotion_evidence=false`, and all four `unexecuted_host_arms`. Its scope is `trusted_component_smoke_only`.

Messages use generated/descriptor-backed Google Protobuf classes, with the compiler source↔binding identity checked in CI. **No internal JSON transport or new MCP server** is introduced. [`cognitum/eval_protobuf.py`](../../../cognitum/eval_protobuf.py) rejects oversized/malformed/unknown-field or duplicate-scalar-tag frames, and accepts only the exact frozen fixture in this intentionally narrow v1 implementation. Its report decoder **recomputes** the reference calculator result before accepting a frame, so simply modifying counts or adding a positive model-arm claim fails closed.

### Reproducibility controls

- Fixed input expressions, expected rational strings, rejection behavior and case order in checked-in source; canonical deterministic Protobuf and suite SHA-256.
- No ambient randomness, timestamps, wall-clock latency, external network, GPU, model-selection calls, private files, permissions or worker launch.
- Tested with exact `fractions.Fraction`-based calculator and explicit rejection on unsupported syntax. The oracle is preregistered in source and checked for canonical exact-rational formatting, **not independently blinded/held out**.
- Runner is a **trusted in-process arithmetic check** and **does not exercise** C02's isolated worker or the Lu CoreExtensionHost. The existing `start_isolated_worker()` must still reject all launch attempts.

`python tools/run_c03_smoke.py` writes **binary Protobuf** to stdout. `python tools/run_c03_smoke.py --check` prints a concise operator-readable status and exits nonzero on an incorrect reference run. Human-readable output is a CLI boundary, not an alternate native wire format.

## Honest next-stage experimental protocol

Real P3 requires a *separate, reviewed* `LU_MODEL_TASK` variant/schema and a host-granted evaluation bridge that can genuinely observe all available A/B/C/D arms with:

1. Immutable Lu build, selected model identifier/hash, inference and sampling settings, tool catalog, workspace/host grant set, task instructions, seeds, declared dataset split and environment/hardware version.
2. Matched task runs (with actual reruns or repeat trials) and strong maintained conventional-tool comparators, not an artificial disabled baseline. Randomization/counterbalancing and explicit invalid or missing data treatment.
3. Tool-call appropriateness, validated final task outcomes, abstention/leakage rates, timeouts/failures, wall-clock response latency and peak memory usage **actually measured** by trusted host/OS instrumentation.
4. Local-only consented provenance/telemetry (no default raw user prompts, transcript exports, external collector or model-weight modifications).
5. Predeclared promotion thresholds, confidence/uncertainty calculations where defensible, per-model hardware strata, negative/regression reporting and reproducibility bundles.

Never promote a component based on a passing calculator smoke suite or rely on Cognitum's denied C02 worker execution to create host performance figures.

## Verification evidence

New [`tests/test_eval_protobuf.py`](../../../tests/test_eval_protobuf.py) checks deterministic binary frames, exact and invalid arithmetic cases, frozen A/B/C/D non-execution, no fabricated promotions, forged/wrong data, version changes, unknown Protobuf tags, duplicate scalar tags, CLI output and continued C02 launch denial.

The whole-repository CI matrix must compile **five** Protobuf sources including this one, test `python tools/run_c03_smoke.py --check`, preserve all existing 162 C01/C02 unit tests, and replay the 12 existing `evals/smoke.json` cases on Windows/Linux Python 3.11/3.13. A passing result will qualify C03 for **P2 synthetic component verification only**.
