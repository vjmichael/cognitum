# C07 P7 — Long-form cross-conversation belief-revision evaluation

**Status:** Offline implementation and evaluation (2026-10-27). **Not production Lu authorization, native Rust execution, real-model reasoning, or an externally annotated study.** The canonical user-memory owner remains Lu ANSF; C07's SQLite log is a derived/rebuildable cache.

## What was implemented

- `cognitum/state_longform_eval.py`: 4 multi-conversation scenarios, **126 typed Protobuf events** (30 target events and 96 unrelated background events), **six synthetic conversation IDs**, and **67 explicitly written historical answer labels**. The cases cover goal changes, unresolved hypothetical alternatives, conflicting verified sources, delayed recording, disputed vs confirmed status, imported evidence with uncertainty, retraction, retroactive corrections and inclusive/exclusive interval boundaries.
- `tests/test_c07_p7_longform.py`: 18 tests for corpus pinning, independent oracle corruption, all 67 SQLite restart-and-replay case answers, scope/source admission, cross-chat source deletion, revocation, deletion mid-verification, proposed unverified supersessions, historical provenance, retractions and stale revision CAS.
- `tools/benchmark_c07_p7.py`: repeatable 2-repetition, post-reopen SQLite validation and deliberately diagnostic Python timing report. A host fixture verifies the *exact canonical event frame associated with a synthetic source*, rather than accepting any event that merely names a known source.

**Important scoring boundary:** The hand-written gold labels cover a *declared target subject/predicate* inside each full multi-subject projection, not the entire state of all 126 source events. Filtering is done **after** offline projection exclusively for scoring; it is not a production query filter or access control. The full host-held publication still checks *all* retained sources, including background claims unrelated to the target answer. Synthetic positive numeric ANSF-like source row IDs are unique within their claimed session, but they are not actual canonical ANSF records or credentials.

## Observed results (synthetic, no model)

| Arm | Exact target answer sets out of 67 | Positive-conflict expected cases |
|---|---:|---:|
| C07 bitemporal reducer | **67** | **26** |
| Chronological last-known register | **22** | Not implemented |
| Simple effective-time register | **26** | Not implemented |

The chronological and effective-time registers intentionally lack bitemporal correction, evidence authorization and conflict semantics; **this is not a matched-capability comparison and does not establish real-world accuracy superiority**. The labels were written by the assistant as a fixed synthetic oracle, **not independently annotated by multiple human raters**; they are independent of the reducer's *computed output* only. Test code pins the complete event+answer-key SHA-256 `687d1c8cca705b3113ecd5de633743150d14c8df34501a39c8253b59e5a4bc59`. Tampering with one expected answer is detected.

Two repeated SQLite restart passes matched **134/134** independently specified historical target answer sets, with 8 synthetic deleted-background-source denials and 8 revoked-lease denials. Retained evidence is checked inside the publication lease and the callback is not invoked when any source fails verification. Median diagnostic timings and environment are recorded in `P7-evaluation-result.json`, with caveats about non-comparability, synthetic source IDs and one Linux process.

## Reproduce

From the checkpoint's root:

```sh
PYTHONPATH=.:tests python -m unittest tests.test_c07_p7_longform -q
PYTHONPATH=.:tests python tools/benchmark_c07_p7.py --repeats 2 --output docs/components/state/P7-evaluation-result.json
PYTHONPATH=.:tests python -m unittest discover -s tests -t . -q
PYTHONPATH=.:tests python -m cognitum --calculator replay evals/smoke.json
PYTHONPATH=.:tests python tools/run_c03_smoke.py --check
PYTHONPATH=.:tests python tools/verify_protobuf_schemas.py --require
python -m compileall -q cognitum tests tools integrations/lu
```

## Still blocked / next engineering dependency

P7 validates **pre-labeled structured events**. It does not parse ambiguous natural language or prove that a model correctly determines whether a person changed their mind; asserting `USER_VERIFIED` in a Protobuf event is not proof the user actually said so. A real Lu host must authenticate turns and memory provenance, enforce action-specific writes, manage source deletion/revocation and hold the authorization lock through publication. The candidate C06 Rust adapter remains uncompiled and unused. C07 SQLite history cleanup does not physically purge WAL/free pages or backups.

**Next genuine quality gate:** use externally annotated, multi-rater natural-language conversations with uncertain intent/no-change examples, measure event-extraction and end-to-end Lu+model correctness against a reasonably matched baseline; run only after the Lu host's native Rust memory boundary is proven. Avoid passing repeated synthetic unit tests off as model-quality evidence.
