# P13: Diverse transformer failure-mode diagnostic

**2026-10-30. Research-only. Lu untouched. No fresh Qwen results collected in the development environment.**

## Purpose

The October 30 P8 Qwen/Qwen+Cognitum trial had only 12 tiny synthetic cases per arm: 11/12 answer accuracy both arms; required action-label compliance 8/12 baseline versus 4/12 augmented; mean latency 3583 versus 4328 ms. These exact P8 receipts remain frozen and separate. P12 replaced model-dependent disclosure with a synthetic policy reference and independently regraded the saved responses. P13 adds a **distinct, much harder, cross-domain Qwen diagnostic**, not a matched Cognitum ON/OFF efficacy claim.

## New 84-case plan

14 independently auto-graded families × 6 generated cases (seed `20261030`):

1. First-person/third-person false belief versus ground truth.
2. Latest-revision, tombstone, permission-revocation and equal-revision conflicts.
3. Two-hop relational joins with distractors.
4. Structural causal counterfactual interventions (not ordinary correlation).
5. Precedence-constrained tardiness optimization (exhaustive oracle).
6. Multi-operation integer-cents arithmetic with different tax and discount bases.
7. Exact tool-interface selection, including version, input type and scope.
8. Adversarial instructions inside untrusted retrieved-source notes.
9. Quantified subset/disjointness logic with YES/NO/UNKNOWN semantics.
10. Mutable aliasing, copies and reassignment in small Python snippets.
11. Longer navigation and orientation/state tracking.
12. Fundamentally unanswerable, missing-data and false-uniqueness questions.
13. Revision-aware aggregation over 146 shuffled log rows, not just needle retrieval.
14. Bayesian base-rate inversion requiring a reduced fraction.

The 14-case quick pilot selects one case from every family. The full 84-case run is repeated twice in reverse order, 168 measured local Qwen requests plus two excluded warmups. A new seed regenerates unseen synthetic parameterizations; it is not a proof of train-test independence or external benchmark authenticity.

## Safeguards and scoring

- `p13_stress_suite.py` deterministically constructs questions and gold answers. The **gold is never included in the model messages**; input contains only a narrow system instruction and synthetic question/source facts.
- Scoring strictly separates exact response correctness, required action-label compliance, abstention on unanswerable cases, over-abstention on solvable ones, malformed output, transport failure, sampled-length truncation and latency. External tool actions are not executed.
- A separate auditor recomputes the plan from the original seed and verifies prompt/response hashes and observation order from the saved raw response receipt. File hashes ensure internal integrity, not host/model authenticity; user-controlled local data can still be forged.
- All live calls are opt-in, IPv4/IPv6 loopback only, no redirects or proxies. The Windows launcher requires interactive confirmation and never silently contacts a model or cloud API.
- The output journal is append-only and an existing receipt is never overwritten. An incomplete journal is not labeled as a completed benchmark.
- `p13_fenced_reference.py` adds a fail-closed **host-held fence interface reference** for current-record release, separate from model hints. A Rust/native Lu host must enforce real source scope, record origin, current revision, deletion/authorization, revocation lease and atomic publication. These are **not** authenticated by the Python reference or its simulated tests.

## Run on Windows with LM Studio

Extract the full-source ZIP, ensure Python and Cognitum's Protobuf/security/scientific dependencies are installed (the prior P8 environment should usually work), load `qwen/qwen3.8-27b` and enable LM Studio's local server on port `1234`. Double click:

- `Run-Cognitum-Qwen-P13-Pilot.cmd` — 28 measured requests across all 14 families.
- `Run-Cognitum-Qwen-P13-Full.cmd` — 168 measured requests, 84 distinct questions.

The launchers perform a no-model dry-run and ask the operator to type `RUN` before calls begin. Receipts, independent grade and raw partial journal go to `results/`. **Only upload these files if you approve exposing the raw model responses.** No private memories or user prompts are included by design.

For other models or alternate seeds, Python CLI:

```powershell
python -m tools.run_p13_stress --dry-run --seed 41819 --limit 14
python -m tools.run_p13_stress --endpoint http://127.0.0.1:1234/v1 --model qwen/qwen3.8-27b --allow-research --capture-raw --repeats 2 --seed 41819 --limit 14 --out results/pilot_new_seed.json
python -m tools.audit_p13_stress results/pilot_new_seed.json --out results/regrade_independent.json
```

Raw receipts are an operator-approved research artifact. Actual model identity, weights, quantization, context length and effective inference settings must be verified separately. In the first party Qwen P13 run, 0-model tests are **NOT Qwen performance data**.

## Research motivation

This suite is independently written and not copied from benchmark test items. Research motivating failure categories:

- NeurIPS 2025 AbstentionBench: https://papers.nips.cc/paper_files/paper/2025/hash/fb122bfc3f0127a94ded048b5b03496f-Abstract-Datasets_and_Benchmarks_Track.html
- KaBLE belief/knowledge distinction, Nature Machine Intelligence 2025: https://www.nature.com/articles/s42256-025-01113-8
- HELMET long-context evaluation, ICLR 2025: https://proceedings.iclr.cc/paper_files/paper/2025/hash/f5332c8273d02729730a9c24dec2135e-Abstract-Conference.html
- Agent Planning Benchmark, EMNLP 2026: https://aclanthology.org/2026.findings-emnlp.1041/
- DisasterBench typed tool planning, EMNLP 2026: https://aclanthology.org/2026.findings-emnlp.1665/
- OpenAI instruction-hierarchy challenge 2026: https://openai.com/index/instruction-hierarchy-challenge/

### Boundaries / follow-up

The battery evaluates model *responses*, not Cognitum augmentation efficacy; to measure augmentation gains, preregister a separate matched ON/OFF intervention that uses actual first-party C08/C09 tools, not fabricated hints. No performance claim about Qwen should be made until the user actually runs the local model and returns an independently regraded receipt. Future tests should use held-out external data, varied context lengths, counterbalanced conditions, authenticated runtime/weights and actual (not text-simulated) tool call execution under trusted Lu policies.
