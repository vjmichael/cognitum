# Cognitum C14 G25E — Sparse-event nuisance fitting (isolated research)

**Status:** two held-out synthetic cohorts complete, independently audited; **G25 overall scientific acceptance failed / remains open**. No production Cognitum algorithm, Lu source, DLC, privilege, or authorization change.

## Included

- `G25E_Cohort_{A,B}_Frozen_Protocol.json`: locally frozen cohort configs, separate seeds, unchanged candidate methods, exact source hashes embedded in receipts.
- `tools/g25e_core.py`: independent two-covariate data generation, ordinary/ridge/Firth/FLIC logistic nuisance fitting, AIPW scoring, refusal classifications and oracle nondeployable diagnostic.
- `tools/run_g25e.py`: full primary/replication runners, 1,000 attempt records per scenario/sample-size/cohort.
- `tools/audit_g25e.py`: verifies 8,000 distinct fixture IDs, 40,000 method receipts, source/config/receipt hashes, 160 complete same-code case replays, and refusal/CI invariants.
- `tools/independent_validation.py`, `tools/check_firth_numeric.py`: independent `statsmodels` ML/ridge comparisons and finite-difference-optimizer reference for the Firth likelihood (not an independent Firth package).
- `tools/summarize_g25e.py`: complete and paired comparison summaries; `tools/write_report.py` renders full report.
- `tests/`: 13 focused tests including false-covered and missing-method tampering detection.
- `results/`: full compressed JSONL receipts for A/B, per-method summaries, independent validation, audit, test log, and paired comparisons.
- `G25E_Engineering_Report_2026-11-01.md`: design, findings, failures, limitations and next research tasks.

## Important limitations

- Synthetic generating truth is available only to the heldout *oracle* and offline scoring. It does not authorize production use.
- Zero-event outcome arms are refused by design; finite penalized predictions do not override causal admission. Low-event arms (1–3 events) can receive penalized exploratory fits, whose confidence intervals still require validation.
- Confidence-interval coverage is **conditional on successful fit** and has selection bias. `≥99%` completion was not reached in every positive cell, and overall G25 acceptance is not met.
- Independent validation against an external Firth implementation and direct Cognitum G9 production comparator has **not** been completed.
- No claim of externally timestamped preregistration; frozen hashes, detailed receipts and exact replay are included.

## Local reproduction

Run in this directory with Python 3.13 and NumPy, SciPy, statsmodels installed:

```bash
python -m unittest discover -s tests -v
PYTHONPATH=tools python tools/independent_validation.py
PYTHONPATH=tools python tools/check_firth_numeric.py
PYTHONPATH=tools python tools/audit_g25e.py
PYTHONPATH=tools python tools/summarize_g25e.py
```

To recompute both full heldout cohorts (will overwrite only research results):

```bash
OPENBLAS_NUM_THREADS=1 python tools/run_g25e.py G25E_Cohort_A_Frozen_Protocol.json
OPENBLAS_NUM_THREADS=1 python tools/run_g25e.py G25E_Cohort_B_Frozen_Protocol.json
```

GitHub is a source/documentation repository, not the development environment. No Docker or CI required.