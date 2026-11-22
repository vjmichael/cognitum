# Cognitum P23 FULL — Independent P25 Evidence Report

**Run:** P23_Full_9577_20890 · 12 synthetic problems, each with Cognitum OFF/ON · locally executed Qwen runtime as reported by receipt (model identity and runtime settings not independently attested).

## Verification

- P25 independent receipt/journal audit **passed**. Both SHA-256 hashes match the originals.
- All 24 trial arms and all 12 pairs verified; no source changes or inference calls were made during analysis.
- Benchmark uses no Cognitum-imposed generation-token cap. Raw original P23 grades remain unchanged.

## Results

| Metric | OFF | ON |
|---|---:|---:|
| Strict protocol + exact answer | 0/12 | 5/12 |
| Exact mathematical answer after removing *only* an enclosing JSON Markdown fence | 10/12 | 10/12 |
| Authorized solver invocations | 0 | 11 |
| LM Studio requests | 12 | 23 |
| Recorded completion tokens | 114,127 | 128,573 |
| Sum of recorded inference latency | 1,917.619 s | 2,227.028 s |

**Interpretation:** No mathematical-accuracy gain over these 12 matched problems (one assisted gain, one assisted loss); all tool invocations were authorized and 10/11 tool-assisted problems returned an exact mathematical optimum. The strict advantage (5 vs 0) reflects primarily bare-JSON formatting, not general mathematical superiority. Recorded ON inference latency is 16.1% higher and completion-token usage is 12.7% higher.

**Exploratory paired exact two-sided tests:** strict p = 0.0625, format-tolerant mathematical p = 1.0. These are descriptive in a small synthetic, single-run study, not an efficacy proof.

## Per-problem details

| Case | OFF mathematical | ON mathematical | ON authorized tool |
|---|---|---|---|
| p22_s01 | Correct | Correct | Yes |
| p22_s02 | Correct | Correct | Yes |
| p22_s03 | Correct | Correct | Yes |
| p22_s04 | Correct | Correct | Yes |
| p22_s05 | Correct | Correct | Yes |
| p22_s06 | Correct | Correct | Yes |
| p22_s07 | Correct | Correct | Yes |
| p22_s08 | Correct | Correct | Yes |
| p22_s09 | Not correct | Not correct | Yes |
| p22_s10 | Correct | Correct | Yes |
| p22_s11 | Not correct | Correct | Yes |
| p22_s12 | Correct | Not correct | No |

## Notable failure modes

- `p22_s09`: ON requested and received the authorized scheduling tool result but produced no final answer; OFF provided an incorrect order.
- `p22_s11`: OFF returned an invalid answer string with embedded whitespace and a different order; ON returned the exact optimum after tool execution.
- `p22_s12`: OFF returned the exact optimum within a Markdown JSON fence; ON neither called the tool nor produced a final answer.
- Ten of twelve OFF outputs are mathematically correct, but all twelve OFF outputs violate strict bare-JSON formatting (mostly fenced).

## Methodological cautions

- The 12-case full run includes 3 previously used pilot cases, and is a single unblinded synthetic benchmark with no independent model identity attestation.
- ON includes a longer tool instruction and usually a second model call. The observed latency difference is not isolated solver compute overhead.
- The P25 semantic score strips only a single enclosing Markdown JSON fence. It does not repair strings, infer missing jobs, or fabricate an answer.
- No claim of a statistically significant gain, production Lu integration, or general Cognitum efficacy is warranted.

**Files:** P23_Full_9577_20890.json, P23_Full_9577_20890.json.partial.jsonl, Cognitum_P25_P23_Full_Paired_Evidence_2026-10-30.json.
