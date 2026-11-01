# Cognitum C14 G25J — calibrated sensitivity-bound research

**Status: completed research, FAIL production promotion.** November 1, 2026.

G25J studies an experimental **asymptotic simultaneous confidence outer set** for the *population identified set* under fixed bounded counterfactual outcome-risk difference Γ. It compares this method with the more conservative, finite-sample G25I seven-Clopper–Pearson reference. It does **not** estimate Γ from data, prove absence of hidden confounding, implement an Imbens–Manski parameter-point confidence interval, or authorize a production estimator change. The G25I core is included unchanged under `baseline/`.

## Contents

- `G25J_Predeclaration.md`, `G25J_Frozen_A.json`, `G25J_Frozen_B.json`: frozen preregistration, thresholds, seeds and source digests.
- `tools/g25j_core.py`: partial-ID bounds, analytic multinomial gradients and experimental joint-normal set interval.
- `tools/independent_g25j.py`: SciPy LP and bivariate-normal independent numerical references.
- `tools/run_g25j.py`: original frozen runner; completes all datasets but has a **summary-stage `numpy.int64` serialization error** afterward. It was intentionally NOT modified after freeze.
- `G25J_Operational_Deviation.md` and `tools/g25j_postfreeze_summary_serialization.py`: reporting-only correction preserving original raw receipts and source hashes.
- `tools/audit_g25j.py`, `tools/aggregate_g25j.py`: deterministic full-data replay of all datasets, numerical method and refusal verification; pooled summaries.
- `tools/g25j_additional_independent_validation.py`, `tests/`: numerical and adversarial checks; nine adversarial tests added after primary evaluation without tuning the frozen method.
- `results/`: both 12,000-dataset JSONL receipts; audit/summary/replay reports; original runner logs and exit-code evidence; pooled results.
- `G25J_Engineering_Report_2026-11-01.md`, `G25J_Acceptance_Decision.json`, `SHA256SUMS.json`: scientific results, decision, reproducibility hashes.

## Verification (without rerunning the frozen holdout)

Prerequisites: Python 3.13 with NumPy, SciPy, pytest (statsmodels for the unchanged G25I suite). No R or additional HTP download required for the G25J numerical checks.

```sh
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH=tools:baseline
pytest -q tests
python tools/audit_g25j.py A
python tools/audit_g25j.py B
python tools/aggregate_g25j.py
python tools/g25j_additional_independent_validation.py
```

To reproduce a *fresh* full G25J evaluation, use the original runner with frozen seeds and preserve its receipts despite the reporting-only exception, then run:

```sh
python tools/g25j_postfreeze_summary_serialization.py A
python tools/g25j_postfreeze_summary_serialization.py B
```

The exact 24,000 datasets and 240,000 interval attempts were already generated and are bundled; users do not need to rerun them to inspect the results. Original runner nonzero exits are explicitly documented, not concealed.

## Limitations and safety

- Γ is an analyst's unverified risk-difference assumption, not an identified upper bound. An observed-confounder association benchmark is **never** used to choose Γ automatically.
- Set coverage and effect coverage are different targets; selected-case conditional coverage does not imply 95% unconditional frequentist coverage.
- Empirical failures at Γ=.25 and lack of uniformity around kinks preclude production use.
- Hidden confounding may evade all observed-data checks. **No automatic causal certification.**
- Exact G25I reference is conservative and remains unchanged. No Lu modifications or Cognitum C14 production changes.

GitHub is the repository/documentation record, not the development environment. All tests and cohorts were developed and executed locally.