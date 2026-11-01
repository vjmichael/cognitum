# C14 G25K — Reproduction and acceptance ledger (2026-11-01)

**Scope:** Cognitum-only research. No production estimator changes; Lu untouched. GitHub is the repository ledger, not the test runtime.

## Reproducible local artifact

The companion `Cognitum_C14_G25K_Kink_Aware_Inference_2026-11-01.zip` contains frozen G25I/G25J baselines, G25K source, both frozen protocol JSONs, seven synthetic causal families, 14,000 complete primary dataset receipts, full A/B auditors, LP cross-checks, tests, hashes, and the complete engineering report. Each ZIP member was SHA-256 checked.

Run from the extracted directory with Python 3.13, NumPy 2.3.5 and SciPy 1.17.0, BLAS capped to one thread:

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python -m pytest -q tests/test_g25k.py
python tools/run_g25k.py A
python tools/run_g25k.py B
python tools/audit_g25k.py A
python tools/audit_g25k.py B
python tools/g25k_independent_numerical.py
python tools/g25k_postholdout_adversarial.py
python tools/aggregate_g25k.py
```

The audit CLI checks every record but by default numerically replays 168 cases/cohort; the archived full audits were run with `audit('A',replay_per_cell=500)` and `audit('B',replay_per_cell=500)`, totaling 14,000 exact case replays. Use a fresh extracted copy before rerunning to retain original receipt hashes.

## Headline acceptance

- 14,000 datasets, 210,000 interval-method/Gamma attempts and all 14,000 exact numerical replays passed integrity verification.
- G25K exploratory subsampling: 41/60 preregistered positive-support cells passed the narrow research screen, 19/60 failed. At Gamma=0.25, local-kink n=1,800 and rare-binary n=900 both covered only 92.9% of full identified sets.
- G25I exact CP reference: 60,000 supported-band attempts, 60,000 observed population-set containments, with substantially wider intervals.
- 2,160 independent LP endpoint comparisons, 720 G25I equivalence checks, 23 G25K tests, 43 unchanged G25J regressions and 10 adversarial receipt mutations passed/rejected as appropriate.
- All 2,000 structural-zero datasets were refused for conditional inference. No automatic causal certification.
- **NO PRODUCTION PROMOTION**. The experimental m-out-of-n procedure lacks validated uniform coverage at kinks.

## Verification and next work

The full report and original predeclaration are separate files on this branch. The next candidate, G25L, should project a simultaneous confidence region for the observed multinomial distribution through the nonsmooth identified-set map, with separately verified region coverage, projection optimization and fresh independent SCMs. Do not use G25K holdout seeds for tuning.

External R or specialist inference-package equivalence was not performed. All tests ran locally; the GitHub branch records results and provenance only.
