# Cognitum C07 P8 — Conversational-language interpretation safety evaluation

**Date:** 2026-10-27. **Status:** Offline lexical reference, bounded Protobuf proposal contract, frozen synthetic utterance dataset and passing tests. **Not a model benchmark, not a Lu host admission service.**

## Problem

C07 P1–P7 consume already-typed, host-admitted `StateEvent`s; high event-replay accuracy says nothing about interpreting a person's ordinary words. This P8 tests the **upstream classification** of tentative intentions, confirmed decisions, genuine changes of mind, clarifications/corrections that are *not independent new facts*, retractions, negative/no-state statements, and unresolved references. No new canonical memory is written here.

## Implemented

- `proto/cognitum/state/v1/interpretation.proto` + compiler-parity-checked `cognitum/proto/interpretation_pb2.py`: `ConversationTurn`, `InterpretationProposal`, and seven explicit semantic classes. `may_write_state_directly` is always `false`, `requires_host_review` always `true`; these flags are *not* a grant or credential.
- `cognitum/state_language.py`: conservative **English lexical reference**, bounded and strict Protobuf decoder, exact quoted/source-text candidate spans. Deterministic pattern matching *abstains rather than invents a missing referent*. Separate context (`prior_decision`) is a host-supplied hint, not proof of a verified memory record; no `StateEvent` output or ANSF mutation path.
- `evals/c07_p8_conversational_cases.jsonl`: 131 original, single-author **synthetic** English utterances hand-labeled in advance and SHA-256-pinned, including 95 development and 36 holdout cases. They are *not* naturally sampled chat logs, independent external annotator labels, multi-rater annotations, or a model-generated user study. Source text and labels are distributed for independent review.
- `cognitum/state_language_eval.py` and `evals/c07_p8_report.json`: reproducible exact-label, per-class precision/recall/F1, false action proposal, missed action and abstention metrics; comparison to two intentionally simple baselines. The holdout was scored only after development fixes; **it was not tuned after the holdout run**.
- `tests/test_c07_p8_conversational_language.py`: strict/unknown/noncanonical Protobuf rejection, non-user/quotation/conditional/negative cases, antecedent requirements for change/correction/retraction, exact span provenance, multi-turn role-separated diagnostic sequence, frozen labels and refusal to automatically emit a memory write.

## Results

| Metric | Lexical C07 reference | Simple keyword baseline | Naive latest-user-turn baseline |
|---|---:|---:|---:|
| Development exact labels (95 cases) | **95/95** | 37/95 | 19/95 |
| Frozen holdout exact labels (36 cases) | **34/36** | 13/36 | 6/36 |
| Holdout false action proposals from tentative/no-state/unresolved statements | **0** | 15 | 16 |
| Holdout unresolved/abstain predictions | 8 | 0 | 0 |

The two holdout errors are **safe abstentions**, on `The transcript says we will delete everything.` and `I haven't agreed to any of that.`: the gold class is `NO_STATE_CHANGE`. No claim of statistical reliability beyond this small, single-author synthetic fixture. The development perfect score is *fixture-fit*, not generalization evidence. The simplistic baselines intentionally lack full context/grammar; the comparison only establishes which errors this fixture catches, not superiority over production NLU or a loaded LLM. Microbenchmark medians measure only this local Python regex pipeline (~0.02 ms/turn) and are not model/host performance.

## Explicit invariants and limitations

1. **Proposals are not authorized memory mutations.** Model or webview-supplied role, identity, prior-decision string, or enum cannot mint `USER_VERIFIED` provenance. Real Lu must independently authenticate persisted roles, exact ANSF revision/source hash, action permission, scope, and current user intent before admitting any C07 `StateEvent`.
2. A `CORRECTION_CANDIDATE` means repair a linked previous statement, **not** assert an unrelated fact. A `CHANGE_OF_MIND_CANDIDATE` is a proposed replacement, not an automatic overwrite. A `TENTATIVE_PLAN` is not promoted to a firm goal, and a negative/hypothetical/quote must not create a new decision.
3. Context-free short replies, references to `it` or `that`, and missing prior decisions cause abstention. If a live Lu model interprets language instead, this deterministic reference is a control arm, **not** a substitute for matched real LLM testing.
4. The lexical baseline is limited to hand-authored English and explicit surface forms. It has not been tested on naturally occurring transcript distributions, multilingual/voice transcripts, indirect speech acts, sarcasm, adversarial long contexts, or actual multi-rater ground truth. A higher-quality extractor should be evaluated with held-out naturally sampled, consented data and a matched Lu+loaded-model baseline.
5. Protobuf descriptor compilation and Python tests are **not** native Rust/Windows Lu authorization evidence. C06/C07 host integration, deletion/WAL erasure, C02 isolation, real model benchmarks and production deployment remain unresolved.

## Reproduce from this checkpoint (offline)

```bash
PYTHONPATH=. python -m unittest tests.test_c07_p8_conversational_language -v
PYTHONPATH=. python -m cognitum.state_language_eval
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
PYTHONPATH=. python -m unittest discover -s tests -q
```

The full report JSON includes every misclassification and per-class metrics, not only accuracy totals. `evals/c07_p8_conversational_cases.jsonl` is immutable under its pinned SHA-256 and requires an intentional new dataset version if revised.
