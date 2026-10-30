# Cognitum C14 P4E G11 — Independent holdout and assurance robustness

**Date:** 2026-10-28  
**Maturity:** Reproducible offline reference; NO authorization to make real-world causal claims or trigger actions.

## Pre-registered evaluation protocol

The G10 policy **is byte-for-byte frozen** (SHA-256 `be0301129cb6060bb157a23744262dee9018b3c622e4285c546aea420d5cfd7c`). Its synthetic G9 training/calibration data used seeds 2,001–2,200. G11 evaluates exactly **new seeds 51,001–51,200**, stratified across five prespecified scenarios and sample sizes 300/900: 2,000 independent datasets. A second, prespecified experimental arm uses seeds **61,001–61,100**, three identifiable scenarios and two sample sizes with **P(Z=1)=0.80** rather than 0.50: 600 shifted datasets. There is no tuning of G10 thresholds or selection of a new method after viewing the holdout.

Six interval methods are replayed with the **same** 399 paired-row bootstrap resamples, nominal 95% confidence, two-fold cross-fitting for AIPW and fixed estimands. Each method reports attempts, completed runs, observed interval coverage against a simulator oracle, Wilson 95% intervals for coverage, mean interval width and estimation bias. The report distinguishes coverage among completed runs from failures to return an interval. Known latent confounding and no-overlap cases are not eligible for a causal point-interval interpretation. No historical or live personal data are used.

The fixed second-stage G11 gate retains G10's advisory minimum of **92.5% observed synthetic coverage**, >=150 completed trials and >=95% completion. The holdout gate **can only preserve or downgrade G10**. Its output distinguishes an *eligible, qualified synthetic description* from a real-world causal claim or any action authorization; the latter are always denied. A Wilson interval still quantifies substantial uncertainty about empirical coverage. The pass threshold is a provisional research engineering condition, **not** certification of nominal 95% coverage.

## Findings

| Heterogeneous effect | G9 calibration | G11 independent holdout | G11 advisory |
|---|---:|---:|---|
| N=300, Wald | 91.5% | 96.5% (200/200 completed) | Still abstains: frozen G10 already refused |
| N=300, BCa | ~92.9% (196/200) | ~96.4% (194/200) | Qualified synthetic description only |
| N=900, AIPW | 93.5% | 92.0% (200/200) | G11 downgrades to abstention |
| N=900, Wald | 94.5% | 94.0% (200/200) | Qualified synthetic description only, Wilson uncertainty |

The difference between G9 and G11 demonstrates why a single seed grid should not be treated as definitive calibration. The 200-trial Wilson intervals are included in `P4E-G11-holdout-evidence.json`. No unplanned method winner is declared; differences in coverage may be random, and the methods have varying noncompletion rates.

### Covariate shift and noncompletion

The deliberately shifted experiment sets the observed binary covariate frequency to **80%**, retaining specified conditional outcome and treatment mechanisms. The heterogeneous population oracle changes from **0.295** to **0.400**, so comparing unadjusted estimates against the old oracle would be invalid. In the small shifted heterogeneous case, BCa/other pairs-bootstrap intervals successfully completed only **14/100** trials; reporting their apparent coverage only on those 14 would be misleading. This domain therefore abstains even when a point interval can be computed.

A prespecified two-sided *exact binomial test* of the observed covariate mix against p=0.50 at alpha 0.01 detected the planted shift in **100/100** cases at both N=300 and N=900. Among unshifted cases, it flagged **1/200** and **4/200** respectively. This tests only a strong, known Bernoulli covariate shift. A nonsignificant result **cannot certify** that the distribution is unchanged, detect arbitrary shifts, or exclude hidden confounding. The prototype gate does not accept a model's "in distribution" assertion as real-world evidence; its only eligible inputs are deterministic, verified synthetic fixtures.

### Epistemic and authority boundaries

- A mathematical interval can be numerically reproducible yet causally unidentified.
- Hidden confounding and overlap failures still abstain. Partial-identification sets must not be relabeled as ordinary confidence intervals.
- Calibration evidence is SHA-256-pinned inside this source checkpoint, not independently signed or attested. An adversary able to alter the whole archive can change code and digests.
- In-domain holdout and shift evaluations share the same simulator family: independent *seeds*, not independent real-world populations. No clinical/safety/economic intervention is endorsed.
- A policy decision can only authorize a synthetic descriptive statement, never real-world claims, decision recommendations, actual Lu actions, or native execution.
- `declared_evaluation_domain` is **untrusted caller metadata**. The P4E research route can only replay fixtures that Cognitum itself generates; this is not a general arbitrary-dataset gate.
- Native Windows Job Objects/AppContainer, authenticated Lu supervisor and the official DoWhy v0.14 release provenance remain unverified.

## Reproduction

```sh
PYTHONPATH=. python tools/run_c14_p4e_g11_verify_report.py
PYTHONPATH=. python -m unittest tests.test_c14_p4e_g11_holdout -v
PYTHONPATH=. python tools/run_c14_p4e_g11_smoke.py
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
```

Existing G10 and older regressions should be run separately. Test receipts mean reproducibility only, not independent causal verification. Keep all scientific source/archive versions and hashes in provenance.
