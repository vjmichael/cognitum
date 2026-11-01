# Cognitum C14 G25N — Reproducible research package

**Research-only, no Cognitum production estimator change, no Lu change.** This package evaluates a *new* DKW cumulative confidence region and a separate pointwise Monte Carlo multinomial likelihood-ratio test after the G25M hybrid-region width impossibility result. Full scientific/production acceptance has **not** been obtained.

## Contents

- `G25N_Predeclaration_2026-11-01.md` and `G25N_Frozen_{A,B}.json` — frozen source, models, thresholds, unique seeds and per-cell plans.
- `tools/g25n_core.py`, `tools/run_g25n.py` — research methods and isolated holdout driver.
- `tools/audit_g25n.py`, `tools/aggregate_g25n.py` — independent receipt audit, numerical replays, independent Monte Carlo rank recomputation, Wilson comparisons.
- `results/G25N_{A,B}_*.jsonl` — full original 14,000 dataset receipts, including all 2,000 refusals, method intervals, candidate-oracle test p-values, counts and hashes.
- `results/G25N_{A,B}_audit.json`, `results/G25N_AB_Aggregate.json`, logs — audit and acceptance evidence.
- `baseline/` — pinned G25I/J/K/L source used as existing estimators, population generators and scientific comparator.
- `tests/` — 32 new G25N method/negative/tamper tests. Additional 42 unchanged G25L/M regression tests were run using prior frozen packages; they are not duplicated in this archive.
- `G25N_Engineering_Report_2026-11-01.md`, `G25N_Acceptance_Decision.json` — conclusions, limitations and explicit no-promotion decision.
- `SHA256SUMS.json` — SHA-256 of each payload file (excluding this manifest itself).

## Environment and tests

Python 3.13 (tested with NumPy 2.3.5, SciPy 1.17.0, pytest 9.0.2). Set `OPENBLAS_NUM_THREADS=1` and `OMP_NUM_THREADS=1` for reproducible local resource use.

From the extracted root:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q tests/test_g25n.py tests/test_g25n_audit.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/audit_g25n.py A --numeric-per-cell 20
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/audit_g25n.py B --numeric-per-cell 20
python tools/aggregate_g25n.py
```

To *regenerate* receipts (copy the original ZIP first so original evidence is retained):

```bash
bash tools/run_all_g25n.sh
```

Original frozen cohort configuration hashes: A `48b85328ee371f40ca6c44e3a397b1d1f73e8ab7c0fc9bde32cd6396fef60038`, B `dd33e44798d51958f94413816f0e52e6309283eeaa2f980f2ef6a05e2e6b805b`.

## Non-promotion boundary

The Monte Carlo p-value experiment evaluates the test **at the generator-known true multinomial law**, which real inference never knows. It is not a working confidence-set inversion. The DKW sensitivity intervals are conditional on analyst-specified Γ=0.25 and necessary sampling/consistency assumptions; **neither method certifies that unmeasured confounding is absent**. The numerical LP projection is tested, but lacks an interval-arithmetic global error certificate. No code in this package authorizes a causal-confidence classification.