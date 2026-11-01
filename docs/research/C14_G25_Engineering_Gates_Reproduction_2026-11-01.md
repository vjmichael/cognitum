# Cognitum C14 G25 — Engineering gate closure, batch 1

**Research and release-gate verification only. Not deployed. No production causal algorithm changes. No Lu changes.**

This package converts the known G25I conservative binary W/T/Y sensitivity calculation into a strictly validated **research reporting interface**. It does not revive the failed G25J–N confidence-interval candidates or claim that hidden confounding can be diagnosed from observational data.

## Local reproduction

Python 3.13, NumPy 2.3.5, SciPy 1.17.0, pytest 9.0.2 and statsmodels (installed for independent binomial interval comparisons).

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q tests/test_g25_release_guard.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/audit_archived_g25n_gate.py
```

The second command expects the original `Cognitum_C14_G25N_2026-11-01/` archive to be extracted at `/mnt/data/`; this package includes its original G25I baseline source, not 14,000 duplicate dataset receipts. The resulting archived-gate audit JSON is included for independent review. To replay the full archived-data audit, extract the G25N companion archive separately.

## Safety contract

- Data must be exactly an eight-cell nonnegative integer table for binary `(W,T,Y)`, with no silent float-to-integer conversion.
- Gamma must be explicitly supplied in [0,1]; no fitted Gamma selection or hidden-confounding inference.
- Observed empty treatment arms and arms with fewer than 25 observations block numerical reporting (a **policy** threshold, not proof of population positivity).
- Conditional numerical intervals require explicit sampling, consistency, measurement and Gamma-assumption documentation, plus exchangeability justification when Gamma=0. Such documentation is only an analyst claim; it is not empirically verified by the guard.
- Every result has `automatic_causal_certification=false`, `production_estimator_promotion=false`, and `identification_verified_from_data=false`.
- Deterministic receipt replay recomputes semantics and rejects rehashed forged flags; a SHA-256 receipt alone is not an authenticity guarantee.

## Gates

See `C14_G25_Release_Gate_Status.json` and `C14_G25_Gate_Closure_Report.md`. Batch 1 closes input, refusal, receipt provenance and scoped math cross-check gates; the global scientific calibration and production integration gates remain OPEN or FAILED.