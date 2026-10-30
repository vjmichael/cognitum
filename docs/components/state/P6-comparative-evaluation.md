# C07 P6 — independently labelled bitemporal evaluation

**Status:** implemented/evaluated offline on 2026-10-27. **Not** a Lu, language-model, Windows x86-64, or production host-authenticated benchmark.

## Goal and provenance

Use two deliberately limited comparison approaches to establish whether the extra time and provenance semantics provided by C07 matter on explicitly labelled cases. Do **not** treat the output of C07 as the answer key. `cognitum/state_evaluation.py` defines a small synthetic corpus with manually stated expectations, independent of calls to the reducer. `golden_corpus_sha256` fingerprints **all source Protobuf event frames and the labels**; changes must update that fingerprint and explain the change.

Nine scenarios and 44 as-of questions cover: ordinary supersession; recorded-time knowledge cutoffs; retroactive temporal correction; bounded intervals and exclusive ends; challenges and confirmed decisions; retraction and historical visibility; overlapping incompatible claims; late-recorded evidence; and explicit uncertainty promotion. These are synthetic events with synthetic hashes, not actual ANSF evidence. Only **four** of the 44 questions expect a positive conflict edge, so the positive conflict sample is too small for a generalization claim.

## Arms and fairness limits

- **Chronological register:** consumes the same events in original order, retains a latest status/value as of *recorded-time* cutoff, but does not reconstruct effective-date intervals or explicit conflict edges.
- **Effective-clock register:** consumes the same events as simple effective-time updates, ignores the *recorded-time* cutoff (future-information leakage in this model), cannot apply temporal corrections to an earlier segment, and does not emit conflict edges.
- **C07:** C07 P5 bitemporal in-memory projection using both clocks, bounded intervals, uncertainty and conflict edges. Its separate durable SQLite path is compared to the exact same manually labelled expectations **after process-local close/reopen**, under a *synthetic* host source-verification lease.

`value_status_correct` requires the entire active/inactive claim set to have correct `(claim_id, value, status)`. `full_provenance_uncertainty_correct` additionally requires matching provenance and uncertainty kinds. `exact_case_correct` additionally requires the identical explicit conflict-edge set. `incorrect_or_extra_claims` and `missed_claims` count differences in claim tuples, **not a measured security leak**. Positive-conflict recall is separately reported so correct negatives cannot hide lack of detection. No statistical confidence intervals are claimed from the small, curated sample.

The baseline registers intentionally omit authorization, durable CAS, SQLite, raw-source re-verification and some temporal operations, so the timings are **not apples-to-apples throughput**. The median timing report is a diagnostic only: single-process Python/Linux, sequential input order, tiny fixture, no controlled CPU or Windows host, no LLM. SQLite figures measure a different work envelope (commit, restart, fenced query); no claim is made that simpler registers offer equivalent safety or durability.

## Synthetic host and failure policy

`FixtureLease` is *not* a trusted identity or signed grant. It binds exact synthetic source frames to the evaluation case. `StateJournal.apply_host_batch` must accept these events through the fixture only, then after restart `publish_host_as_of` must produce the same result as the hand labels and in-memory C07. Deleting **any** retained source from the fixture lease and revoking the lease must each block historical disclosure. The callback is never run when validation fails. The real ANSF ownership, read locking and deletion policy are unimplemented here and remain Lu's responsibility.

## Reproduce

From the checkpoint root:

```bash
PYTHONPATH=.:tests python -m unittest tests.test_c07_p6_evaluation -q
PYTHONPATH=.:tests python tools/benchmark_c07_p6.py --repeats 5 --output docs/components/state/P6-evaluation-result.json
PYTHONPATH=.:tests python -m unittest discover -s tests -t . -q
PYTHONPATH=.:tests python -m cognitum --calculator replay evals/smoke.json
PYTHONPATH=.:tests python tools/run_c03_smoke.py --check
PYTHONPATH=.:tests python tools/verify_protobuf_schemas.py --require
python -m compileall -q cognitum tests tools integrations/lu
```

The JSON report records the platform, corpus checksum, per-arm correctness, restart checks, timings and sample size. The regression test pins dataset size and SHA-256, and explicitly mutates an expected answer to prove the evaluator detects an oracle failure. `P6-test-evidence.json` records which checks actually ran.

## What this does **not** establish

It does **not** show that C07 is more accurate than a full database or temporal knowledge graph; the chosen baseline implementations are intentionally less capable. It does not measure language-model response quality, real dialogue ambiguity, evidence trustworthiness, independent annotation agreement, deletion from physical SQLite/WAL/backups, or real Windows Lu performance. Results from the synthetic `FixtureLease` cannot be promoted to a production authorization claim. An unkeyed journal checksum is not tamperproof against a local writer. C06 Rust compilation and genuine Lu host integration remain open.

## Next useful tests

C07 P7 should pursue longer multi-conversation sequences with independent annotation, ontology and conflicting timeline ambiguity; include fairness-matched baseline semantics and real model-in-the-loop tests only after the native Lu host gate is available. Do not proliferate architecture frameworks solely to inflate unit-test counts.
