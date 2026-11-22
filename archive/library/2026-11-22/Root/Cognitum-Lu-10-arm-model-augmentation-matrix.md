# Cognitum × Lu — preregistered paired model/weight/KV quantization benchmark v2

2026-10-27. **Protocol amendment, NOT measured model results.** This replaces the preliminary 10-arm plan. The ten *comparison groups* remain, but each group has multiple matched experimental cells.

## Objective and estimands

Estimate the paired effect of Cognitum augmentation for each **exact model source checkpoint × weight-quantization configuration × K-cache precision × V-cache precision × context-length × backend build × hardware profile**. The principal estimand is the paired change in independently scored task correctness; resource/time/cost differences are separate co-primary outcomes. Report interaction effects (including quantization-specific tool routing). This does not isolate model *size* as a causal factor across unrelated model families.

## Model size strata — NOT ten interchangeable models

| Size tier | Cognitum enabled | Cognitum disabled |
|---|---|---|
| sub-1B | paired A1 | paired B1 |
| approximately 1B | paired A2 | paired B2 |
| 7B–14B | paired A3 | paired B3 |
| approximately 16B | paired A4 | paired B4 |
| 25B–35B | paired A5 | paired B5 |

Choose at least one **fixed original, unquantized checkpoint per stratum** with recorded model revision, SHA-256 or content digest, architecture (dense vs MoE, active vs total parameters), tokenizer/chat template, licensing, training/version provenance and exact conversion tool. Additional families are *replication blocks*, not substitutes for another family's quantization. If feasible choose a coordinated family spanning multiple sizes, but do not invent a missing tier. List unsupported/missing cells explicitly; never silently fill with a different model.

## Experimental factors and explicit support gate

- **Weight precision:** supported FP16/BF16 baseline and quantized variants (e.g., Q8_0, Q6_K, Q5_K_M, Q4_K_M, Q3_K_M). These labels are examples, not equivalent across engines; record effective bits/weight, GGUF tensor mixtures, quantizer version/options, exact file digest and calibration data if used. Require a common *source model*; do not mix converted/modified/distilled model variants as ordinary quantization trials.
- **KV-cache precision:** independently record K and V types (`f16`, `q8_0`, `q4_0` where supported), Flash Attention setting, cache quantization applied in practice, maximum and realized context lengths. Validate a backend feature probe, allocation and logs. Mixed K/V configurations are separate experiments and **must not be assumed performant or supported** (GPU fallback can dominate results).
- **Cognitum:** paired enabled vs disabled on the *same exact model artifact and engine/hardware/cache settings*. Disabled must truly have no Cognitum access; the same fixed task set/scorer applies. Capture Lu's system/tool-instruction overhead and context usage, not just the numerical solver time.
- **Other confounds:** inference runtime and commit, CPU/GPU/driver, GPU layer offload, batch, cache implementation, sampler/seed/temperature, prompts, tools presented, concurrency, thread count, power/thermal settings, fixed task order seed, context truncation policy and device budget. Do not compare different execution engines without a **separate engine factor**.
- **Compatibility:** materialize only predeclared valid cells. Include an FP16/KV-F16 reference where hardware permits, otherwise state the missing control. Skip/impossible configurations with machine-readable reason rather than silently substituting. Record out-of-memory as an outcome for attempted preregistered resource cells rather than deleting those trials.

## Runs, pairing, scoring, and statistics

1. Freeze model/tensor provenance, tokenizer, prompts, tasks and gold scorers *before* trials; use held-out datasets and publish per-case records and exclusions. Avoid contamination, test-set training or selective prompts.
2. In each valid cell, pair augmentation ON/OFF at identical task IDs and configured sampling seeds. Randomize or counterbalance execution order by replicate and clear caches when comparing cold starts; perform separate warm runs. Use sufficiently many tasks and independent replicates to form cluster-aware confidence intervals; **three seeds alone is not a power calculation**.
3. Primary measures: correctness (with abstention scoring), paired effect size and uncertainty, invalid tool-call and route rates, claim verification, failure/timeout rate. Measure quality *by model and quantization cell*; avoid Simpson's paradox from pooling across family/hardware.
4. Resource measures: first-token latency, total time, tokens/s, token counts, time to launch workers, peak RAM/VRAM, disk footprint, context length, CPU/GPU utilization, measured energy only where instrumented. Account for Cognitum worker overhead and model prompt tokens. Report missing sensors as missing; do not impute watts.
5. Add separate diagnostics: **tool-oracle** run supplying the correctly selected capability, a tool-error injection run, and a matched generic-tool/control run if feasible. Oracle/control arms are diagnostics and must not be folded into the primary ON/OFF contrast. Classify model routing, tool-input formation, Lu dispatch, Cognitum algorithm, environment/isolation and scorer failures separately.
6. Predeclare equivalence/noninferiority margins for the small-device experiment; report confidence intervals and multiplicity policy for multiple comparisons. Do not declare superiority based only on a single best seed or across unmatched families.
7. Audit: record model source and quantized file hashes; K/V cache configuration **and confirmed effective runtime setting**; engine build; exact hardware, GPU offload, Lu/Cognitum versions and backend IDs; deterministic task IDs; request/outcome digests; tool traces with privacy-preserving access; and independently reproducible result exports.

## Minimal pilot and staged expansion

Start with one model at one tier and one weight quantization, comparing K/V F16 vs Q8 (when supported) with Cognitum ON/OFF. Validate the harness using an independent scorer, replayable tasks and measured memory first. Then broaden weight quantizations **within that same model**, then model-size tiers and family replication. A nominal design with five checkpoints × four weight precisions × three supported KV configurations × two Cognitum conditions contains 120 cells before repetitions, but is **not** a promise that all combinations are feasible. Prefer a balanced, predeclared subset if hardware or storage is limited.

## Release gate

No ten-arm, quantization, or small-model efficacy result is claimed as executed. Lu admission and C02 OS isolation, installed/qualified Cognitum backends, reproducible inference configurations and independent scoring must pass before model-invoked benchmarks. Experimental results are not proof of humanlike reasoning, general intelligence, or frontier-model equivalence.

## References for protocol input (not claims of our own results)

- LM Studio load config documents separate `llamaKCacheQuantizationType` and `llamaVCacheQuantizationType`, and the Flash Attention dependency for V-cache: https://lmstudio.ai/docs/typescript/api-reference/llm-load-model-config
- Existing bug reports show that mixed K/V formats can trigger backend performance fallbacks; test **actual runtime behavior**, not UI settings alone: https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/2246
