# C18 — Practical consent-scoped adaptation P0–P3

**Date:** 2026-11-04. **Status:** standalone bounded implementation on PR branch; exact-head CI, merge and real-source Lu acceptance pending.

## Goal and required boundaries

C18 asks whether **explicitly permitted adaptation improves future tasks** without leaking data, degrading existing tasks, or silently updating Lu's selected transformer. It is a **candidate-producing evaluation component**, not an automatic learner or conversation-trace recorder.

All training requests originate outside Lu and accept only typed, numeric, host-sanitized features. Source digests, claimed consent receipts, workspace IDs and timestamps provide explicit caller-declared lineage; SHA-256 does **not** authenticate source or actual permission. The Lu host must separately validate the user grant, training budget, retention, per-turn isolation and allowed target. No C18 path may load prompts, user files, tools, private traces, arbitrary Python expressions or model weights.

## P0 — Explicit proposal, provenance and retention

`cognitum/adaptation_policy.py` implements `AdaptationProposal` with allowed target, version, workspace scope, source digest, privacy class, consent receipt, allowed task families, retention deadline, train/heldout cutoff, frozen incumbent and rollback digests, row cap and training wall-time limit. `Trace` includes timestamp, source ID, retention, consent, task family, expected route and bounded numeric features (never raw transcript text or prompt tokens). Candidates are serialized as digest-bound immutable policy records. All changes to Lu core weights are explicitly **out of scope**.

`cognitum/adaptation_traces.py` provides opt-in **in-memory reference** trace collection, compare-and-swap revision checks, source/receipt consistency, pause/resume, expiry removal, irreversible revoked state and tombstone hashes. These remove samples from the **next in-memory state**; they cannot erase previously copied immutable objects, filesystem files or actual user records. Physical erasure, durable user consent, OS process control and retention have to be implemented and tested by the trusted Lu host.

## P1 — Established classical adaptation, not novel meta-learning research

`adaptation_policy.py` trains a genuine scikit-learn multinomial logistic regression router using bounded, labeled numeric features for three outputs: `direct`, `specialist`, and `abstain`. The sklearn model is a **candidate** only; without separately passed trusted-host approval no training occurs. The trained coefficients, intercepts and feature normalizers are frozen in a versioned source-bound SHA-256 checkpoint.

`adaptation_retrieval.py` independently trains a binary relevance scorer with scikit-learn logistic regression on numeric retrieval signals, never raw source documents or uncontrolled embeddings. It splits by **whole query and timestamp**; reports held-out hit@1 and mean reciprocal rank against the existing first-feature deterministic score. Checkpoints are candidates only, with explicit consent/source and tamper refusal. This provides a meaningful conventional retrieval-tuning reference without building neural retrievers, MAML, LoRA, or modifying the transformer.

`cognitum/adaptation_calibration.py` adds a bounded SciPy temperature-scale calibrator. It fits solely on an independently permitted **middle chronological calibration window** after training and before the final future holdout. It stores a checksum-bound calibrator artifact, refuses training/final-test overlap, and compares raw versus calibrated future log-loss and multiclass Brier score. Optimization against final acceptance labels is prohibited. A smaller calibration loss is never automatically interpreted as real-world calibrated probability or approval to activate a policy. `tests/test_c18_calibration.py` uses the real SciPy optimizer on three disjoint synthetic windows.

`cognitum/adaptation_wire.py`, `cognitum/proto/adaptation_pb2.py` and `proto/cognitum/adaptation/v1/adaptation.proto` expose a **read-only** canonical typed candidate-vs-incumbent comparison. It rejects unknown/noncanonical/oversized requests, recomputes frozen policy/holdout results independently, and returns SHA-256-correlated evaluation. **No train or policy-activation command is present in the model-visible Protobuf.**

## P2 — Poisoning, revocation, recovery and fail-closed behavior

Training refuses missing host admission, unrecognized target, unknown task family, duplicate event or query/document ID, malformed timestamp order, NaN, out-of-bounds feature, source/consent mismatch, expired retention, contaminated training/holdout split, excessive rows and unsupported checkpoint. The reader never interpolates malicious text into a code path. Training does not directly update user policy. `adaptation_lifecycle.py` uses immutable CAS receipts for `prepared → active → paused/resumed → rolled_back/revoked`. Revoked states cannot resume. A rollback always resolves to the original pinned incumbent; replayed mutation IDs or stale revisions fail.

`evaluate_promotion` compares the candidate to the pinned incumbent **on the same future observations**; checks accuracy improvement, log-loss regression, worst-task-family loss, abstention and sufficient held-out sample size. A passing gate yields `READY_FOR_HOST_APPROVAL`, **not automatic deployment**. Real user approval and OS-isolated writing are separate.

Limitations: The in-process wall-clock check cannot hard-kill malicious or hung external code. The only trained external operation is trusted maintained scikit-learn with bounded inputs. True resource limits and cancellation require an OS-isolated host supervisor. Policy-checkpoint SHA-256 without trusted host signatures also cannot resist an attacker who controls both the checkpoint and hash.

## P3 — Strict future evaluation and negative transfer

`tools/c18_adaptation_benchmark.py` runs actual sklearn on **synthetic** numeric routing examples, compares future-only accuracy, log loss, worst-family and independent calibration results to the incumbent, measures CPU/wall training cost, and runs a separate full-query heldout retrieval ranking against original scores. `tests/test_c18_adaptation.py`, `tests/test_c18_retrieval.py`, `tests/test_c18_calibration.py` and `tests/test_c18_wire.py` exercise real training, promotion refusal, rollback, revocation, expiry, train/eval leakage, malformed source, checkpoint corruption, forbidden raw code/grants and forged Protobuf results.

`.github/workflows/c18-adaptation.yml` requires real NumPy/scikit-learn on Windows/Linux Python 3.11/3.13, independent `protoc` source/binding comparison, adversarial tests and measured synthetic held-out benchmarks.

**No real permitted user dataset has been used here.** Synthetic success cannot establish a Lu model A/B uplift, memory quality, correct agent tool choice, user task completion, zero forgetting, real calibrated prediction, or suitability for default-on adaptation. Real data ingestion, consent/revocation receipts, durable deletion and time-ordered independently replicated task-level studies are future deployment acceptance, **not permission to start automatic learning**.

## Practical closeout criteria

1. Current-head CI must pass all 4 native platforms plus relevant repository regression; correct failures, then merge the source.
2. Approved Lu host scopes and OS-isolated worker are needed before users can train or adopt a policy. Keep Observe & Learn OFF by default.
3. A trained policy must clear true future heldout and previous-family regression, memory/energy/latency budget, and rollback test, before a user can explicitly choose to activate it.
4. MAML, LoRA and neural meta-learners are optional challengers only when the classical references fail a real task. No speculative training of Lu's base LLM by Cognitum.
