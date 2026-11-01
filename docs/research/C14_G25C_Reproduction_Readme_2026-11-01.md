# Cognitum C14 G25C — 2026-11-01 isolated research package

**Research only. C14 G25 acceptance is NOT MET. No production estimator or Lu changes.**

This package follows the G25 A/B evidence with fresh generator seeds and one fixed propensity-fit regularization comparison while **preserving** the originally required estimated-propensity lower bound of 0.015. It also includes a strict all-resamples-successful full-pipeline pairs bootstrap diagnostic, independent numerical GLM/OLS checks through `statsmodels`, reproducible receipts, and two independent structural auditors.

Important provenance: The first 6,000-case run omitted the preregistered oracle known-nuisance diagnostic. The original raw receipts and hashes are retained; the subsequent corrected re-run added that oracle and reproduced all 12,000 original baseline/ridge receipts **exactly**. The rerun is not independent replication. See `G25C_Protocol_Deviations.md`.

## Start here

- `G25C_Engineering_Report_2026-11-01.md`: decision, complete results, failures, next gates.
- `G25C_Predeclaration.json`: protocol frozen before the first primary runs.
- `G25C_Protocol_Deviations.md`: transparent post-first-run correction and nonclaim.
- `tools/g25_inference.py`: bit-identical copy of prior G25 A/B source.
- `tools/g25c_methods.py`: baseline + fixed L2=1 propensity + oracle diagnostic.
- `tools/run_g25c.py`: frozen-seed primary experiment.
- `tools/run_g25c_bootstrap.py`: exploratory 99-resample full-refit experiment.
- `tools/run_g25c_library_crosscheck.py`: independent `statsmodels` comparisons.
- `tools/analyze_g25c.py`: paired refusal/coverage comparisons.
- `tools/audit_g25c.py` and `tools/audit_g25c_bootstrap.py`: structure and refusal integrity.
- `tools/g25c_numeric_spot_replay.py`: exact source numerical replay.
- `results/`: full compressed JSON receipts, summaries, audits, provenance hashes, and quarantined smoke results.
- `tests/`: 13 unit tests including deliberately corrupted records.

## Run locally

Python 3.13 with NumPy, SciPy and statsmodels is sufficient. No Docker, installer, network connection, Lu or elevated privileges required.

```sh
python -m unittest discover -v -s tests
python tools/audit_g25c.py
python tools/audit_g25c_bootstrap.py
python tools/g25c_numeric_spot_replay.py
python tools/run_g25c_library_crosscheck.py
```

Optional reproducibility reruns overwrite the local research outputs:

```sh
python tools/run_g25c.py
python tools/run_g25c_bootstrap.py
```

Do **not** treat the oracle or bootstrap-selected results as deployable causal-confidence procedures. Review the acceptance matrix in the engineering report before proposing any changes to production C14/G9.