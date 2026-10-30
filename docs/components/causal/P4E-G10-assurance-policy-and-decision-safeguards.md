# C14 P4E G10 — Assurance Policy and Decision Safeguards

**Date:** 2026-10-28  
**Status:** Offline, research-only policy reference. Neither Lu host integration nor Windows worker confinement is certified.

## Scope

G10 adds `proto/cognitum/causal/v1/assurance_policy.proto` and `cognitum/causal_assurance_policy.py`. It consumes an existing typed G9 `IntervalComparisonRequest`/`Result`/`Receipt` and **replays the calculation** before issuing a typed advisory. It consults a *fixed, SHA-256-pinned* G9 calibration report and recomputes G8 binary-outcome partial-identification ranges for the same deterministic synthetic fixture. There is **no new system authority, model-facing route, host permission or external action**.

The G9 calibration report's SHA-256 is `87f66bdcdac7de9c25a1df0c951053fb8cb4922842b81542a5e9867f01eaf6f9`. Tampering, missing evidence, or a request/results mismatch produces a rejected decision. This is an integrity consistency check within a source checkpoint, **not a signature or independent attestation**.

## Explicit evidence separations

1. **Computational validity:** replay verifies that a request-bound numerical result is reproducible. This is not independent verification of the causal graph or observation quality.
2. **Synthetic calibration:** G9 coverage comes from 200 seeded trials for each scenario/sample size. It is never a guarantee of 95% coverage for a real population. The 95% Wilson interval measures empirical-coverage sampling uncertainty, not a causal credible interval.
3. **Identification validity:** G7 fixtures declare assumptions. Hidden confounding and treatment nonpositivity force abstention from a point causal interpretation. Passing the synthetic generator's assumptions does **not** validate an arbitrary empirical causal graph.
4. **Partial identification:** G8 binary treatment/outcome bounds are retained without assuming unconfoundedness. Plug-in identified-set bounds and population sampling envelopes are separately labeled; neither equals an ordinary point-effect interval.
5. **Authorization:** `authenticated_lu_host`, `may_issue_causal_claim`, `may_recommend_intervention`, and `may_trigger_external_action` are always false. The LLM cannot elevate them through prompts or result forgery.

## Versioned dispositions

| Code | Condition | Response |
|---|---|---|
| `REJECT_UNVERIFIED` | Invalid G9 receipt, mismatched result, unapproved or damaged calibration source | Fail closed |
| `ABSTAIN_CONFOUNDING` | Synthetic generator has a known hidden common cause | Bounds only, do not claim point identification |
| `ABSTAIN_POSITIVITY` | Treatment/covariate overlap absent | Bounds only |
| `ABSTAIN_METHOD` | Selected method did not compute a point interval | No numerical interval claim |
| `ABSTAIN_CALIBRATION` | Missing relevant evidence, too few completions, sample/resample mismatch, or observed synthetic coverage below policy threshold | Do not describe interval as adequately calibrated |
| `DESCRIBE_SYNTHETIC_ONLY` | Replay passes and relevant synthetic calibration meets a preliminary descriptive threshold | Qualified synthetic research summary **only**; no causal proof or action |

Thresholds are conservative *engineering defaults*, not validated clinical, safety, or scientific decision thresholds: completed trials ≥150, completion rate ≥95%, observed coverage at least 92.5% for nominal 95%. Bootstrap methods require the same 399 resamples as the pinned G9 calibration. The 95% Wilson interval is always reported, and its lower bound is **not** promoted to a proof. Other sample sizes, confidence levels, or experimental designs cannot borrow this calibration. No automatic winner-selection is implemented, avoiding selection bias from using G9's grid both to select and validate a method.

## Representative expected outcomes

- Heterogeneous 300-observation Wald: 91.5% empirical coverage → `ABSTAIN_CALIBRATION`.
- Heterogeneous 300-observation BCa using 399 resamples: 92.86% across 196 completed trials → `DESCRIBE_SYNTHETIC_ONLY`, still no confidence guarantee or intervention permission.
- The same BCa method with 199 resamples: `ABSTAIN_CALIBRATION` because the G9 reference was run at 399 resamples.
- 900-observation null-effect Wald: qualified synthetic description only.
- Known hidden confounding / no overlap: abstain and retain the broad partial-identification envelope.
- Forged G9 result, deleted report, changed request ID, or forged outcome flag: rejected or verification fails.

## Validation and security limitations

P4E G10 has **no authenticated Lu host**, no native Windows security attestation, no stable release pin certification for DoWhy main, no production effect estimator, no private-data admission policy, and no real-model benchmark. Model-use policy must be enforced by Lu's host, not by Cognitum status bits. Local source hashes do not prevent an adversary who can change the code and the hash together. Running an advisory cannot trigger an intervention or modify files.

To reproduce: `PYTHONPATH=. python -m unittest tests.test_c14_p4e_g10_assurance_policy -v`; `PYTHONPATH=. python tools/run_c14_p4e_g10_smoke.py`; `PYTHONPATH=. python tools/run_c14_p4e_g10_evidence.py`; `PYTHONPATH=. python tools/verify_protobuf_schemas.py --require`. The first uses deterministic replay; the G9 empirical summary originates in the previously verified 2,000-dataset G9 study. No new 2,000-dataset inference run is claimed in G10.

## Follow-on work

Wire policy outcomes into trusted host admission only after C02/Windows confinement and Lu's native authenticated capability envelope are actually available. Add signed and separately curated calibration evidence, domain-aware causal-identification checks, externally sourced holdout data, alpha-spending/selection controls, and rules for action consequences before permitting stronger claims. Retain synthetic-only guardrails as regression fixtures.
