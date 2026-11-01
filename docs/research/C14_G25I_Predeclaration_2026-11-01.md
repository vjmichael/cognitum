# C14 G25I preregistered synthetic identification/sensitivity study

*Research-only. Frozen before first held-out result. No production or Lu modification.*

## Goal

Use a binary-stratum/binary-outcome causal model to expose the difference between observed-data overlap and **unverifiable exchangeability**. Fit no new production AIPW variance correction. Examine sharp population sensitivity identified sets under user-assumed bounded counterfactual selection contrasts, and conservative finite-sample outer bands based on **seven simultaneous Bonferroni Clopper-Pearson intervals** (observed W prevalence, two treatment propensities, and four conditional outcome risks).

## Families

`measured` (no hidden bias); `randomized_hidden_prognostic` (unobserved outcome predictor, but conditional randomization holds); `latent_confounder` (unobserved common cause); `misclassified_confounder` (observed covariate is noisy proxy); `weak_positive_overlap` (known small, nonzero treatment probabilities); `structural_zero_overlap` (genuine positivity failure).

Two independent cohorts A and B, each **1,000 distinct seeds per family × sample-size cell** with n∈{900,1800}; 12,000 datasets per cohort and 24,000 across cohorts. Five sensitivity bounds Γ∈{0,0.10,0.25,0.50,1}, giving 120,000 method attempts total. Seeds and exact source SHA-256 are frozen in JSON manifests.

## Prespecified analysis and acceptance

- Track every seed, dataset hash, numerical result, zero- or weak-arm status, and simulator-only true ATE and minimum true Gamma. No silent omission of adverse cases.
- For *simulator-known* sufficient Gamma with all observed arms nonempty, assess true ATE inclusion in the 95% conservative outer band per individual cohort cell. Require ≥95% empirical inclusion (a conservative screen, not a clinical frequentist guarantee), and report Wilson uncertainty. Reject any structurally invalid automatic causal admission (zero tolerance).
- For Γ=1, the plug-in sensitivity bounds must equal no-exchangeability Manski bounds to 1e-12 on every positive cell.
- In generated confounded cases, Γ=0 may fail despite valid numerical outcomes, and results must explicitly state conditional dependence on the untestable Gamma assumption.
- Report the rate of empty arms and separately warn when any observed (W,T) arm has fewer than 25 observations. An empty arm forbids a **conditional** interval, but the no-assumptions Manski bound remains available.
- All true DGP details, including hidden U and misclassification rate, belong only to research scoring and **must not be treated as deployable causal evidence**. Policy requires external consistency, exchangeability, and measurement-validity justification; even supplied attestations do not automatically create a verified causal label.
- Structural receipt audit, replay across all cells, independent linear-program bound solver, independent statistical-library CP comparison, tampering checks, and zero production changes required.
- Existing G25's broader acceptance gates remain in force. This narrower study cannot promote any estimator and is not a proof of identification in real observational data.