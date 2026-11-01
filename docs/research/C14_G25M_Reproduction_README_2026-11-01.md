# Cognitum C14 G25M — Frozen negative-width research milestone

**Status: G25M research and local verification complete; scientific promotion FAILED.**

The package preserves the complete 14,000-fixture preregistered study, all original per-case attainable-width witnesses, the unmodified G25I/J/K/L baseline inference code required to reproduce the comparisons, and an independent auditor that validates each witness from its original eight-cell confidence-polytope constraints. A mathematically valid **attainable-width lower bound** exceeds the preregistered maximum for *every positive cell*. This is a method-specific impossibility result for the frozen G25M hybrid confidence region, not a claim that globally optimized causal inference is impossible in general.

## Key artifacts

- `G25M_Engineering_Report_2026-11-01.md` — full statistical analysis, gate-by-gate decisions and remaining blockers.
- `G25M_Predeclaration.md`, `G25M_Frozen_A.json`, `G25M_Frozen_B.json` — preregistration, immutable seeds and source hashes.
- `docs/G25M_Mathematical_NoGo_and_Gate_Contract.md` — proof that certified attainable witness span is a lower bound on the interval width from the confidence region.
- `tools/g25m_core.py` — exact four-arm-mass reduction, full witness verification, capped globally outward branch-and-bound, and independent exact Gamma=1 LP.
- `tools/run_g25m_witness.py` — frozen receipt generator; `tools/execute_g25m_cohorts.py` — execution-only concurrent dispatcher.
- `tools/audit_g25m.py` — independently regenerate and audit all 14,000 datasets and 12 adversarial alterations.
- `tools/g25m_independent_numerical.py` — independent closed-form/LP/functional checks on entirely different seeds; `tools/run_regression_gates.py` — 130 tests across G25I-M.
- `results/G25M_*.jsonl` — 29 immutable original receipt chunks (2 cohorts, six positive families plus one structural-zero family, two sample sizes; the first Cohort A exact-kink n=900 cell is split into 50 and 450 fixtures).
- `results/G25M_Independent_Audit.json`, `results/G25M_Independent_Numerical.json`, `results/G25M_Regression_Gates.json`, `G25M_Acceptance_Decision.json` — machine-readable gate evidence.
- `SHA256SUMS.json` — SHA-256 integrity manifest of all companion files.

## Reproduction (local-first)

Requirements: Python 3.13, NumPy 2.3.5, SciPy 1.17.0, pytest 9.0.2. Set `OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=1`, and `MKL_NUM_THREADS=1` before any scientific execution.

From the package's top-level directory:

```bash
python -m pytest -q tests/test_g25m.py
python tools/g25m_independent_numerical.py
python tools/audit_g25m.py
python tools/run_regression_gates.py
```

The complete held-out study regeneration requires substantial compute:

```bash
python -u tools/execute_g25m_cohorts.py
```

**Preserve the original `results/` folder before rerunning.** The runner intentionally refuses if a frozen source hash differs and overwrites the matching receipt chunks in the working copy. Audit the original archived receipts first. No network or GitHub CI is required for local reproduction.

## Research boundary

This package **does not implement or authorize a production confidence-interval replacement**, a Lu integration, a causal identification oracle, or a verified inference procedure for general continuous covariates. The G25M numerical global branch search reports nonzero sharpness gaps where unsolved. Γ is an externally supplied sensitivity assumption; its adequacy and exchangeability remain unverified. Independent external scientific review and distinct production authorization are outstanding.