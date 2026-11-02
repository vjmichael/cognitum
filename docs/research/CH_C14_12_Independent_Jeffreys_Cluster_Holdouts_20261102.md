# CH-C14-12 — Independent Jeffreys score and cluster/rare-event holdouts
**2026-11-02 | Engineering scoped PASS; external R equivalence BLOCKED; C14 scientific NO-GO.** Research only; no production estimator, Lu, or Windows changes.

## Frozen science and source
Frozen CH11 estimator SHA-256: `6d06d3f34f7305aeb8f609b3877c67281edcc563895cc6674ec4682201eddef8`. Initial CH12 protocol SHA-256: `779dfb0d24a5efa3069370737af0f6b423b492a0362f4fb1283e8561476eb545`. Confirmation protocol was independently frozen before running the larger new-seed cohort; its digest is in the `frozen_sha256.txt` archive. Seven model families, two sample sizes, ridge vs Firth-like nuisance cross-fitting. Initial 24 seeds/cell yielded **336 datasets / 672 attempts**; separate 120-seed/cell confirmation **1,680 datasets / 3,360 attempts**. Combined **2,016 datasets / 4,032 attempts**.

Families stress cluster sizes 5 and 25, rare events, nonlinear observed-outcome relationships, extreme propensity overlap and hidden cluster confounding. True effects are approximated using separate 350,000-draw SCM Monte Carlo integration.

## New issue identified: low-cluster silent IID fallback
CH11's original `estimate()` sets `clustered = G<n and G>=25`. If a clustered dataset has **fewer than 25 clusters**, CH11 switches to individual-level stratified folds and reports `iid_IF` variance; that is an unsafe silent downgrade, not an explicit refusal. CH12 added an outer research **fail-closed check** to reject these cases, without changing frozen CH11 bytes. A new regression test reproduces the old behavior. **Permanent source-level fix remains OPEN**; no production integration.

## Holdout accounting
| Cohort | Attempts | Issued | Refused: <25 clusters | Refused: weak overlap | Refused: single-class outcome fold | Unexpected failures |
|---|---:|---:|---:|---:|---:|---:|
| Initial | 672 | 465 | 96 | 96 | 15 | 0 |
| Independent-seed confirmation | 3,360 | 2,334 | 480 | 480 | 66 | 0 |
| **Combined** | **4,032** | **2,799** | **576** | **576** | **81** | **0** |

Examples in confirmation (120 attempted per method per cell):
- Rare outcomes, cluster size 5, n=500: ridge **70/120 issued** vs Firth-like **120/120 issued**; their truth-inclusion counts were 70 and 116.
- Rare outcomes, cluster size 25, n=1000: ridge **114/120 issued** vs Firth-like **120/120 issued**; truth inclusion 112 and 118.
- Cluster size 25, n=500: **all 240 attempts refused** due to 20 clusters.
- Severe weak overlap, n=1000: **all 240 attempts refused**.
- Hidden confounding, n=1000: both methods issued 120 intervals, but only **1/120 per method** contained the simulator truth. Firth regularization **does not** solve causal identification.

## Independent numerical validation
No local `Rscript`, `logistf` or `brglm2` was available, so **actual external R/Firth numerical equivalence was not run and remains BLOCKED**. A separately written Jeffreys adjusted-score root equation matched frozen CH11 coefficients for **46/48** fixtures (maximum delta `4.1765e-05`). The two original independent-start root failures (cases 7 and 19) were preserved; a separately labeled **post-hoc** least-squares score check initialized from the CH11 candidate resolved both with beta delta under `1e-6`. This is not fully independent-start or R equivalence.

**10/10** new regression tests and **12/12** unchanged CH11 tests passed. The independent receipt auditor checked **all 4,032** records for unique IDs, refusal completeness, correct interval arithmetic, ≥25 clusters for issued results, zero shared train/test clusters, cluster-CR1 variance and no causal certification. Not every nuisance model was independently refit in the audit.

## Deliverables and disposition
Full reproducibility ZIP `Cognitum_CH_C14_12_Independent_Jeffreys_Cluster_Holdouts_2026-11-02.zip` SHA-256 `44af9e627e5ea0171f476cfffda4418b5391ec53b25b42c40d8159ee5a8a2464`. Contains preserved CH11 estimator source, protocols, scripts, original and confirmation data receipts, verification, tests and complete engineering report. **24 CH12 payload hashes plus pinned CH11 source hash validated in the archive.**

**SCIENTIFIC NO-GO** unchanged. Required next steps: real independent R `logistf`/`brglm2` equivalence; permanent few-cluster fail-closed fix; broader independent cluster-size and rare-event sweeps, confidence-interval calibration with refusal denominators and independent scientific review. G25N's existing width/calibration failures remain unresolved. GitHub serves only as repository and milestone record; all execution occurred locally.
