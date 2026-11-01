# Cognitum C14 G25G — Reproducible standalone research package

**Version:** November 1, 2026. **Production acceptance:** NOT MET.

## Purpose

Test a two-fold, parametric nuisance-score sandwich adjustment against the score-only AIPW interval, and compare pair resampling against positive-exponential-weight full-refit bootstrap on sparse event models. Data are synthetic, with deterministic SHA-256 fixture identifiers and preregistered seeds. Nothing touches Cognitum production algorithms or Lu.

## Research results

- Primary: A/B 1,600 datasets (200 per cell and cohort). C 4,000 **separately frozen post-pilot** confirmation datasets (1,000 per cell); all three methods accepted all 5,600 cases.
- Sparse bootstrap: 64 method/dataset attempts, 62 accepted baseline, 49 resamples per method per accepted dataset (3,038 pair and 3,038 weighted). Strict no-interval if any resample invalid.
- Verification: G25G 18/18 tests, G25F parent 30/30 tests, 240 primary exact replays, 64 full bootstrap method/dataset exact replays, and 32 independent QR Firth checks. **External R Firth equivalence unverified.**

## Files and source integrity

- `G25G_Engineering_Report_2026-11-01.md` — full findings, tables, statistical caveats, literature links, admission decision, G25H handoff.
- `G25G_Frozen_A.json`, `G25G_Frozen_B.json`, `G25G_Confirmation_C_Frozen.json` and `G25G_Freeze_Record.md` — frozen sources, seeds and policies.
- `tools/g25g_sandwich.py`, `tools/g25g_bootstrap.py`, `tools/g25g_firth_check.py`, `tools/run_g25g.py`, `tools/run_g25g_confirmation.py`, `tools/audit_g25g.py`, `tools/audit_g25g_confirmation.py`, `tools/replay_g25g_bootstrap.py`, `tools/g25g_paired.py` — standalone source and verification.
- `tools/g25e_core.py`, `tools/g25f_core.py` — copied byte-for-byte from the G25F standalone research package.
- `tests/` — test modules. `results/` — primary and bootstrap receipts, summary JSON, exact replay receipts and audits.
- `SHA256SUMS.json` — expected file hashes (excluding itself and the ZIP container).

## Reproduce (developer/scientific CLI only)

Python 3.13 with NumPy, SciPy and pytest. On Linux, set `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1` to avoid excess BLAS thread oversubscription. All the study runners verify frozen source hashes for A/B or C. From this package root:

```bash
python -m pytest -q tests
python tools/run_g25g.py --cohort A --mode primary
python tools/run_g25g.py --cohort B --mode primary
python tools/run_g25g.py --cohort A --mode bootstrap
python tools/run_g25g.py --cohort B --mode bootstrap
python tools/run_g25g_confirmation.py
python tools/audit_g25g_confirmation.py
python tools/replay_g25g_bootstrap.py --cohort A
python tools/replay_g25g_bootstrap.py --cohort B
```

The independent accountancy auditor can also be run from `tools/audit_g25g.py`; if the container imposes strict timeouts, use its structural check with `audit(replay_bootstrap=False)` and the two bounded replay commands above. Each run overwrites only local research output files. `tests` and scientific scripts use CLI because they are developer-facing, not end-user Lu tools.

## Interpretation

The positive-weight resampling preserves source event support by construction, but its resampling validity for sparse binary causal inference has not been established. The sandwich correction only targets smooth parametric M-estimation and is not a general solver for every Cognitum inference task. **Do not treat pilot results or conditional-on-success coverage as production authorization.**