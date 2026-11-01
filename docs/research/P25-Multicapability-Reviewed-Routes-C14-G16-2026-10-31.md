# Cognitum research checkpoint — P25 multi-capability, reviewed routing, C14 independent oracle

**Date:** 2026-10-31 (Arizona local; Linux UTC crossed to 2026-11-01)  
**Scope:** Cognitum research only. No Lu source, binaries, branches, IPC, DLC registration, or model-tool permissions changed. This branch is a repository/evidence record, not a development execution environment.

## P25 live model experiment

Ran a separate localhost CPU llama.cpp process with a real Qwen2.5 0.5B Instruct Q2_K GGUF; weights SHA-256: `9ee36184e616dfc76df4f5dd66f908dbde6979524ae36e6cefb67f532f798cb8`.

16 distinct problems, 4 each for C05 matrix determinant, symbolic polynomial expansion, exact decimal addition, and C10 finite Boolean constraints. Each was run twice with and without backend context, with paired identical **user** text, randomized trial order (seed 251102), model temperature zero, 96 maximum output tokens. All 64 actual model calls completed.

- **OFF**: model alone.
- **CONTEXT**: the same question, with an independently verified **actual Cognitum backend output** included as separate trusted context. C05 used typed Protobuf specialists. C10 used the finite-certificate backend and a separate Boolean truth-table oracle.
- **Important:** The context was inserted by the benchmark; it was **not** an actual authorized Lu tool call, an automatic Cognitum route, or a claim of model-initiated execution.

| Capability | OFF semantically correct | With context semantically correct |
|---|---:|---:|
| C05 linear | 0/8 | 4/8 |
| C05 symbolic | 2/8 | 6/8 |
| C05 precision | 2/8 | 4/8 |
| C10 finite constraints | 4/8 | 4/8 |
| **Total** | **8/32** | **18/32** |

Paired semantic outcomes: 10 gains, 0 losses, 8 correct in both arms, 14 wrong in both. However, there are only **16 unique items** repeated twice—not 32 independent questions. The independent auditor also distinguished **strict output format** (0/32 OFF, 6/32 CONTEXT) from semantically correct responses, so format compliance cannot masquerade as mathematical success. Median *direct model response time* was 184.45ms OFF versus 303.35ms CONTEXT; not a production Lu latency measure.

**Scientific limits:** one heavily quantized sub-1B model, synthetic tasks, no evidence of efficacy for untested larger-model tiers. The historical operator-reported 27B P23 scheduling receipts were 10/12 correct in both arms under tolerant grading, and cannot be pooled with these results. The unchanged C10 4/8 score underlines the importance of assessing the model's use of evidence, not merely backend correctness.

## Cognitum-only reviewed capability-route proposals

New locally tested source: `cognitum/capability_route_proposal.py`, with tests in `tests/test_cognitum_capability_route_proposal.py` (included in the downloadable source/evidence bundle).

The inert metadata catalog covers C05 linear, C05 symbolic, C05 decimal precision, and C10 finite Boolean. Reviewed identifiers, compiled Protobuf input/output type URLs, and descriptor digests are checked; conservative relevance cues return either one proposal or none.

The module **cannot register, enable, advertise, authorize, or execute** anything in Lu. Effect escalation, forged descriptors, ambiguous requests, overlong messages, and user refusal of tools are rejected. Any later Lu integration would require separate explicit owner approval and host-side permissions; there is **no** such approval currently.

Router and nearby mathematical suites: **42 tests passed, 69 subtests**. The final combined new-work suite (routing, independent P25 auditor, and C14 G16): **33 tests passed**.

## C14 assumed-structural-causal-model experiment

New locally tested independent-oracle regression: `tests/test_c14_p4e_g16_independent_scm_oracle.py`. It generated 96 seeded binary SCMs with shared latent cause U and noise E; compared C14 observational, interventional, and counterfactual outputs to **separately implemented exact-rational enumeration** rather than merely replaying C14's evaluator.

- 257 supported probabilities exactly matched the oracle.
- 31 queries correctly reported unsupported/impossible factual evidence.
- 55 of the 96 models had differing observational and interventional probabilities.
- Cross-request provenance substitution and missing host authorization were rejected.
- New test: 3/3 passed.
- Full C14 regression: **618 passed, 37 skipped, 37 subtests passed**. Skipped runtime tests require optional real DoWhy, Tigramite, causal-learn, or EconML dependencies/source fixtures; skips are *not* passes.

These are correctness checks **conditional on specified SCM assumptions**. They do not establish causal identification from observational real-world data, authorize interventions, or certify Lu-host execution.

## Artifacts, provenance, and open gates

The full verified local ZIP `Cognitum_P25_Routing_C14_2026-10-31.zip` contains:
- Cognitum-only Python source and tests for routing, P25 benchmark/auditing, and C14 G16;
- 64 individual real-model responses, partial journal, independent grading, raw hashes, compiler/test logs;
- extended engineering report and SHA-256 manifest.

The ZIP is made available as a conversation artifact; source was developed/tested locally and has **not been merged into Cognitum main or Lu**. The source files in the ZIP should not be misrepresented as committed code in this documentation-only repository branch.

**Remaining:** additional model-size tiers, repeated controlled sampling, C05/C10 real model-tool integration (requires new Lu owner authorization), HDC/KAN ablations, optional C14 mature-library positive runtime tests, more external causal ground-truth cases and calibrated uncertainty research.

**Lu modification status: prohibited by explicit user instruction; none performed in this work.**
