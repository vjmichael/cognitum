# Cognitum CH-C14-23 — Larger holdout and compact-box global-optimality bounds

**Date:** November 2, 2026  
**Scope:** Isolated numerical research. **Engineering PASS; global-optimality certification NOT achieved; scientific C14 NO-GO.**

## Protocol, independence, and reproducibility

The prospective study protocol was written before generating any CH23 data, with SHA-256 **`31cd3f5d01e40e496e59d48b4160a9a3a4894645509eca9eae4cdcaf3e618bde`**. A byte-for-byte frozen CH22 objective/generator reference (`ch22_pinned.py`) has SHA-256 `02de1d5bc17c5b8ea630b639b119ce2420e6cc2401dba57747bf42ff466debee`. The candidate preserves the same analytic Jeffreys score and dataset-generating rules; the seed namespace changes to `2026112323`, the six-start schedule is prescribed by CH23, and the benchmark is newly generated. No original CH22 or C14 production source was modified.

Six families × sample sizes 80 and 160 × **16 independently seeded datasets per cell**: **192 datasets**. Every dataset was attempted from six initialized starting locations via each of BFGS and L-BFGS-B: **2,304 attempts**. Local validation requires an adjusted-score infinity norm below `1e-4` and numerically negative Hessian maximum eigenvalue below `−1e-5`. Distinct maxima must disagree in coefficients and objectives by prespecified thresholds. No optimizer exit code alone is treated as certification.

## Observed local-optimum ambiguity

| Metric | Result |
|---|---:|
| Frozen datasets | 192 |
| Independent optimizer attempts | 2,304 |
| Attempts meeting local-stationarity and curvature screens | 2,298 |
| Attempts failing local screens | 6 |
| Datasets with multiple distinct validated local maxima | **3/192** |
| Datasets with only one observed local maximum | **189/192** |
| Automatically causally certified or promoted | **0** |

The three ambiguous datasets were `zero_imbalanced` n=160 seed index 5 and 7, and `rare_1pct` n=160 seed index 13; **all three had zero observed events**. Every ambiguous case remains **REFUSED**. Every other case remains **RESEARCH_only_single_observed_maximum_global_unproven**, not certified as uniquely or globally optimal. Ambiguity detection rate is specific to this synthetic grid and finite deterministic starts; absence of detected ambiguity does not establish uniqueness. For comparison, CH22 observed 4/96 on a different seed namespace and eight starts per dataset—these are not identical replicate studies, and the different start budgets affect detection.

## Stronger mathematical global bounds, without overstating them

We implemented an **upper bound on Jeffreys penalized binomial-logistic objective over a 3D parameter box**. For each observation, calculate the minimum and maximum possible linear predictor over the box. Binary log-likelihood contributions are monotone with predictor (up for event=1, down for event=0), so selecting the appropriate endpoint upper-bounds their sum. Each Fisher weight `p(1−p)` is bounded by its maximum on the predictor interval (closest-to-zero predictor). The Fisher information matrix therefore obeys the Loewner bound `I(beta) ⪯ X' diag(w_upper) X`, and monotonicity of log determinant over positive-definite matrices bounds the Jeffreys correction. Summing gives a **mathematically valid bound in exact arithmetic**, albeit generally loose.

The preregistered box is `beta_intercept ∈ [−10,1]`, each slope in `[−5,5]`. Branch-and-bound evaluated the first dataset for each family/size cell, **12 cases, 250 expanded nodes per case**. **0/12 closed the bounded-domain upper-versus-incumbent gap**. Remaining gaps ranged from **1.978 to 43.325** objective units; the quasi-separated cases had especially loose bounds. This is a reproducible demonstration of safe *bounding logic*, **not a successful optimality certificate**. More importantly, floating-point operations lacked directed outward rounding, so even if the gap became zero, it would not be a formally machine-verified interval proof. Nothing establishes optimality outside this bounded box or over all real coefficients.

## Independently checked

An auditor with its own generator and likelihood/Fisher information implementation verified all **192 dataset digests**, all **2,304 attempts and all decisions**, recomputed penalized objectives and finite-difference gradients at all **195 observed local-maximum representatives**, and checked the upper-bound formula plus 720 sampled parameter vectors across 12 boxes. Maximum independent objective discrepancy `4.89×10⁻¹⁴`; largest independent gradient infinity norm `1.01×10⁻⁷`. The sample-based upper-bound checks are tests, not proof of global validity. **10/10** new regression tests passed.

The frozen protocol preceded the holdout; there was no statistical-method adjustment after inspecting results. This report reflects completed tests, including six optimizer attempts failing the local validity screens.

## Gate decision and next science

- **Engineering scoped PASS:** larger heldout simulation, deterministic multi-start accounting, independent replay, mathematical upper-bound prototype, and explicit refusal.
- **Global proof gate BLOCKED:** upper-gap not closed for any of the 12; bound computed without directed rounding and constrained to a finite box.
- **Scientific C14 production NO-GO:** neither local convergence nor a better observed local maximum certifies a globally preferred estimator, valid causal identification, or nominal CI coverage. External `logistf` equivalence, real-world study-design provenance and independent statistical review remain incomplete.

**Proposed next experiment:** a verified interval-arithmetic branch-and-bound backend with outward rounding, interval curvature bounds and adaptive splits; start with a small predeclared bounded domain and report explicit unresolved precision and domain-coverage limits. Keep ambiguity refusal even if a heuristic global search picks a favorite local maximum. No Lu, Windows, G25, or production C14 changes.
