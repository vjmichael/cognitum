# Cognitum C14 G25I — Causal Identification and Sensitivity Bounds

**Date:** 2026-11-01. **Research-only. Not production-approved.**

This package adds an independent Python research harness for sharp risk-difference sensitivity bounds on the average treatment effect with one **binary observed** adjustment variable, binary treatment, and binary outcome. It reports conservative Bonferroni–Clopper-Pearson outer sampling bands conditional on an explicitly assumed sensitivity bound, including first principles no-exchangeability Manski bounds. It deliberately does **not** claim to detect hidden confounding from observational data or automatically grant causal confidence.

## Directory

- `G25I_Predeclaration.md`, `G25I_Frozen_A.json`, `G25I_Frozen_B.json`: pre-evaluation protocol and source hashes.
- `G25I_Preholdout_Development_Notes.md`: transparent changes made **before** first held-out result.
- `tools/g25i_core.py`: frozen generator, conditional sensitivity bounds, exact uncertainty band and fail-closed policy.
- `tools/g25i_independent.py`: independent SciPy linear-program calculation of the bounds.
- `tools/run_g25i.py`, `tools/audit_g25i.py`: frozen holdout and structural/exact-replay auditor.
- `tools/aggregate_g25i.py`, `tools/deep_audit_g25i.py`, `tools/write_g25i_report.py`: **post-holdout** aggregation and additional verification. These were not inputs to any held-out estimators.
- `tests/`: 17 pre-holdout method tests and 5 post-holdout tamper-check tests.
- `results/`: 24,000 full dataset receipts across cohorts A+B; 120,000 sensitivity calculations, summaries, independent audits, and 24,000 fixture-byte regenerations.
- `G25I_Engineering_Report_2026-11-01.md`, `G25I_Acceptance_Decision.json`: findings, math, limitations, no-promotion decision.
- `SHA256SUMS.json`: per-file source and evidence checksums.

## Reproduction

Python 3.13, NumPy 2.3.5, SciPy 1.17, pytest 9.0.2 and statsmodels 0.14.6 were available for this work. No R installation, Lu runtime, Cognitum production service or worker grants were used. In a shell with those dependencies available:

```sh
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=tools
python tools/run_g25i.py A
python tools/run_g25i.py B
python tools/audit_g25i.py A
python tools/audit_g25i.py B
python tools/aggregate_g25i.py
python tools/deep_audit_g25i.py
pytest -q tests
```

The two frozen runner manifests validate the SHA-256 digests of all pre-holdout source files and the research preregistration before running. The additional audit/report tools are not part of the frozen estimator and are explicitly marked post-holdout. Full experiment rebuild recomputes the receipts.

## Limitations

- Γ is an **assumed bound on counterfactual mean outcome selection**, not an observed or inferable measure of hidden confounding and not an odds ratio.
- All conclusions are conditional on the user’s causal and sampling assumptions. Attestations are not themselves proof.
- Overconservative uncertainty bands are not nominally calibrated inference.
- Binary/low-dimensional simulator only; no external independent causal package equivalence or real-world data.
- No Cognitum production estimator change, no Lu source changes, and no new tool authorization.