# MEL-06A-R1 — intent binding and verified answer grounding

## Scope and status

Unpublished local reference implementation on published MEL-05C parent `e0b680acd9d5cfb1f42b6c83d7021a2190793c8d`. The prior MEL-06A overlay is included byte-for-byte (11 files). The 119 inherited source identities match the pinned manifest. The predecessor GitHub run 44558654551 completed 18/18 successfully, with all four native MEL-05C gates passed on the unchanged parent; MEL-06A/R1 itself has not been published, and is not native Lu acceptance. No changes were made remotely in this task.

## Changes

- `intent_reference.Intent` is an immutable independently provided scoped contract: exact canonical represented JSON arguments, operation, checkpoint identity when applicable, threshold and result component. It distinguishes booleans from numeric values, ordered lists, and unit labels, and the original codecs produce the expected Protobuf request. The genuine model request must match both the host-typed inputs and exact wire before dispatch. A mismatch cannot consume a worker call. No argument rewriting, hidden tool selection, new grants or retries. It is not a general natural-language intent extractor; the diagnostic fixture is a trusted input, not an inference result.
- `BoundTurn` uses the original `ReferenceTurn`, live schemas, scoped admission, receipt and independent mathematical verifier. Retained immutable evidence binds intent, operation via intent, request/result identities, answer and conservative projection. Publication independently replays the retained result; user/model JSON supplies only an answer, not feedback, scope, grant, evidence, match flag or threshold. Single dispatch/publication, invalid component rejected before dispatch, inventory and checkpoint mismatches refused, revocation/expiry checked before publication. Process-local reference, no production security or durable host guarantees. Digests prove identity, not authentication.
- Numeric interpretation uses the outward binary64 interval and the exact comparison flags for >= and <, never rounded worker observation. HDC retains all ties and exact bit claims only relative to submitted inputs. No unknown-target error, semantic probability or calibration claims. With trusted fallback enabled, a failed model answer may be replaced by the independently derived mathematical answer, explicitly labeled `host_verified_fallback`; otherwise refuse. Unmatched or unverified intent never receives a fallback. This is not proof of transformer reasoning. Intent is fixed by the trusted fixture; future general intent extraction and host authorization are separate tasks.

## Matched diagnostics — real llama.cpp CPU, greedy decoding

Two already available Qwen2.5 Instruct GGUF files, Q2_K 0.5B and Q4_K_M 1.5B, twelve model/case pairs. For each model compare same question and answer-shape grammar in both arms; assisted selection uses the live schema projection with every route offered and one attempt, followed by verification and an answer-only interpretation prompt. The answer grammar permits all candidate index lists, binary strings and three threshold classifications; it does not force the correct answer. No cloud inference or synthetic model output. Baseline and assisted task are matched, but assistance includes differing prompts, schema constraints, additional compute and host verification/fallback; not a controlled estimate of parameter scaling or efficacy. Models differ in quantization as well as parameter count. Three original diagnostic cases were reused or adapted, so no holdout claim. Concurrency and model reload overhead also make elapsed times unsuitable as performance comparisons.

| Model | Baseline correct | Verified intent/calls | Model answers correct | Host fallbacks | Correct published | Refused |
|---|---:|---:|---:|---:|---:|---:|
| Qwen2.5-0.5B-Instruct-Q2_K | 2/6 | 3/6 | 1/6 | 2 | 3/6 | 3 |
| Qwen2.5-1.5B-Instruct-Q4_K_M | 2/6 | 6/6 | 3/6 | 3 | 6/6 | 0 |

| Model | Case | Baseline | Intent match | Model answer | Published source / answer |
|---|---|---|---|---|---|
| Qwen2.5-0.5B-Instruct-Q2_K | hdc-tie | [1, 0, 2] | True | [1, 0, 1] | host_verified_fallback / [0, 1] |
| Qwen2.5-0.5B-Instruct-Q2_K | hdc-xor | "01000001" | True | "11011010" | model_verified / "11011010" |
| Qwen2.5-0.5B-Instruct-Q2_K | kan-above | "above" | False | null | refused / null |
| Qwen2.5-0.5B-Instruct-Q2_K | kan-below | "above" | True | "uncertain" | host_verified_fallback / "below" |
| Qwen2.5-0.5B-Instruct-Q2_K | vfa-ambiguous | "above" | False | null | refused / null |
| Qwen2.5-0.5B-Instruct-Q2_K | vfa-above | "above" | False | null | refused / null |
| Qwen2.5-1.5B-Instruct-Q4_K_M | hdc-tie | [0, 1, 2, 3, 4, 5, 6, 7] | True | [0, 1, 4] | host_verified_fallback / [0, 1] |
| Qwen2.5-1.5B-Instruct-Q4_K_M | hdc-xor | "11011010" | True | "11011010" | model_verified / "11011010" |
| Qwen2.5-1.5B-Instruct-Q4_K_M | kan-above | "uncertain" | True | "uncertain" | host_verified_fallback / "above" |
| Qwen2.5-1.5B-Instruct-Q4_K_M | kan-below | "uncertain" | True | "below" | model_verified / "below" |
| Qwen2.5-1.5B-Instruct-Q4_K_M | vfa-ambiguous | "uncertain" | True | "uncertain" | model_verified / "uncertain" |
| Qwen2.5-1.5B-Instruct-Q4_K_M | vfa-above | "uncertain" | True | "uncertain" | host_verified_fallback / "above" |

The 1.5B model matched all six independently specified intents, executed HDC bind/query, KAN and VFA, and correctly interpreted the previously problematic ambiguous VFA result. Three other interpretations needed a host fallback. The 0.5B failed by adding the threshold to the KAN coordinates, choosing KAN instead of VFA, or exhausting 256 generation tokens before a complete VFA request; all three were refused without worker dispatch. It missed a tie and a KAN threshold even with valid feedback, corrected by host fallbacks. Model-only improvements were not uniform: 0.5B 2 -> 1 correct, 1.5B 2 -> 3; aggregate model-only 4 -> 4. With deterministic verified host fallback, 9/12 correct and 3 refusals, no incorrect publication in these cases. This measures a bounded assisted system, not an increase in intrinsic transformer capability.

## Acceptance

Local Linux Python 3.13: 102/102 reference tests (46 MEL-06A inherited, 56 new). Zero failures/errors/skips. All nine actual admitted requests independently re-executed and replayed on the hardened typed-input boundary with exact receipt and witness comparison; all transcript publication outcomes matched. Four actual model-generated negative controls (two per model) refused without dispatch. Genuine inference ran on the initial R1 guard; the final hardening adds typed-wire comparison, pre-dispatch component validation and single-use locking. The final hardened guard was independently replayed on all recorded generations; it has not been re-inferred using fresh model generation. Source tests include wrong route and input, bool/int and binary32 rounding substitution, signed zero wire drift, revoked authority/checkpoint, tampered result, feedback/audit display mutation, incorrect answer, publication order, and a competing dispatch. Retained logs include original EOG status and partial text of exhausted call. No fabricated results. Changes are local only; native matrix and model runner integration into Lu are not done.

## Next engineering step

Consolidate MEL-06A and MEL-06A-R1 publication on the existing branch once the ledger and exact parent are reconciled. Add a scoped reference CI gate without bundling GGUF weights or claiming hosted genuine inference. Separately qualify user-approved live intent capture and model tool integration through Lu's native host; future broader matched specialist/ordinary-model comparisons require independent held-out tasks and comparable quantization. No research promotion.
