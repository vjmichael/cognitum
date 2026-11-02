# CH-C14-07 — Genuine score intervals, rare-event holdout, and false-design attestation

**2026-11-02 · Linux research engineering PASS · scientific and production release NO-GO.** No Lu, Windows, production C14, or pinned G25 changes.

## Frozen research protocol

Protocol SHA-256 `51c29874bc8cc85155b046fff182232aff48f7fde02bc807b6faff745002b40c`, written prior to this 2,000-dataset evaluation. Five new SCM families at n=300 and n=900, 200 seeds per cell; four methods each = **8,000 total attempts**.

Methods: genuine Newcombe hybrid-score difference of independent binomial proportions, Agresti–Caffo, ordinary Neyman/Wald, and the CH06-style **conservative Bonferroni–Wilson outer interval**. Newcombe is implemented and checked against `statsmodels.confint_proportions_2indep(method='newcomb')`, not mislabeled conservative Wilson differences.

Two legitimately independent randomized rare-event families were granted a bounded test-only host attestation. Stratified randomized heterogeneity (requiring design-adjusted SE), a hidden-confounded false-RCT claim, and structural-zero false-RCT claim were refused. **No scientific claim follows from a text declaration or HMAC signature.** The demonstration's fixture HMAC key is hardcoded and must never be treated as a real production credential. A genuinely mistaken or compromised trusted issuer can sign false scientific declarations; this gate only ensures message/identity/count integrity.

## Results

| Randomized study | n | Wald true-effect inclusion | Agresti–Caffo | Genuine Newcombe | Bonferroni–Wilson |
|---|---:|---:|---:|---:|---:|
| Rare events | 300 | 173/200 | 199/200 | 198/200 | 200/200 |
| Rare events | 900 | 186/200 | 192/200 | 194/200 | 200/200 |
| Very rare events | 300 | **91/200** | 200/200 | 200/200 | 200/200 |
| Very rare events | 900 | **156/200** | 200/200 | 199/200 | 200/200 |

At n=300, rare-event interval mean widths: Wald 0.04107, Agresti 0.05556, Newcombe 0.06480, Bonferroni 0.09189. For very-rare events at n=300: 0.01383, 0.04150, 0.05376, 0.07190 respectively. The very-rare n=300 series had **109/200** datasets with zero observed events in both treatment arms, producing zero-width Wald intervals although the simulated true effect is positive. These results are descriptive; they do not prove nominal coverage outside the tested families.

**3,200 issued**, **4,800 refused** (all incompatible or unsupported studies); zero causal certifications and zero promotions.

## Checks

- **12/12 fresh tests pass** on Newcombe/Agresti numerical equivalence, missing/tampered attestation, incorrect key, altered study identity/counts, unsupported design, malformed counts, tiny arms and unsigned hidden-confounded cases.
- Independent audit of all **8,000** method records, with **1,600 full interval recalculations** using separate statsmodels methods, all matching to 1e-12.
- Archive contains exact protocol, candidate implementation, source tests, full case receipts, independent audit, SHA manifest and full engineering report. Package: `Cognitum_CH_C14_07_Rare_Event_Score_Design_Gates_2026-11-02.zip`; archive SHA-256 `f8b7be6a480994b60dff4b97c5f761bd9eeb4fddcfe69620283e1c0df8107cff`; **10/10 payload hashes independently checked**.

## Scientific position and next milestone

**NO-GO:** none of the methods establishes a uniformly well-calibrated, narrow rare-event causal interval. Wrong study design cannot be detected purely statistically from observed outcomes, and cryptographic signatures cannot establish scientific validity. Robust externally verified design provenance, observational propensity adjustment, rare-event exact methods, independent R/Firth comparison, high-dimensional generalization and scientific review remain OPEN. G25N's 12/12 scientific width failures remain in force.

**CH-C14-08 candidate:** separate verified protocol/design provenance from cryptographic integrity, then investigate exact rare-event confidence construction and denominators with independent numerical validation. No retrospective relabeling of the CH07 holdout as a successful release screen.

**Strategic question outside this benchmark:** Cognitum might be more effective as a *training and evaluation curriculum system* (verified synthetic counterexamples, math/SMT checks, causal label discipline, HDC/SSM state-control and failure localization) than as a mandatory inference-time specialist on every query. This is an untested hypothesis. Require paired fine-tuning experiments on matched LLMs with separate validation and blind test sets, baseline data curation controls, per-token cost and no hidden oracle leakage before concluding it helps model training.

GitHub is only source repository and milestone record; local Linux development persists. Lu remains untouched.
