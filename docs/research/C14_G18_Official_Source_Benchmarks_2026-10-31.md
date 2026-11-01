# Cognitum C14 G18 — Scientific benchmark execution using uploaded official-site source archives

**Research date:** October 31, 2026 (Arizona); container execution November 1 UTC.  
**Scope:** Cognitum scientific benchmarks only; **no Lu source, configuration, or runtime changes**.  
**Disposition:** Scientific execution **PASS**, synthetic-only interpretation, production dependency release lock **NOT CLOSED**.

## Why this run was performed

The user states that the uploaded DoWhy and sparse archives came from official sites and authorizes proceeding with benchmarks while recording provenance limitations. We therefore did not block scientific execution on missing source-release metadata. Official-site origin is operator-reported; its release version cannot be independently reconstructed from the uploaded branch snapshots.

## Environment and reproducibility

- Python 3.13.5, existing scientific wheels from host shared environment, non-hermetic venv at `c14_dependency_gate/venv`.
- Uploaded archives used: Tigramite 5.2.10.1, causal-learn 0.1.4.8, EconML 0.17.0, untagged DoWhy main snapshot (`__version__ = '0.0.0'`), sparse main source locally installed as `0.0.0`, momentchi2 0.1.8.
- Exact archive SHA-256 digests in `G18_Machine_Readable_Summary.json`. `run.sh`, `run_extended.sh` and `run_g9_full.sh` reproduce the commands inside this development image.
- Test environment only: sparse `_version.py` compatibility stub exposes `0.0.0`; it is not a released version attestation. `pip check` still reports EconML requires `sparse>=0.15.4`, while locally installed sparse declares `0.0.0`. DoWhy runtime positive gates expect an installed, pinned **0.14** version; these are not spoofed.

## Actual benchmark results

### G6 — Cross-library effect comparison, one fixed synthetic dataset

- DoWhy backdoor OLS estimated ATE **0.500000**, matching exact-rational standardized reference **1/2**.
- EconML LinearDML mean effect **0.513306**, absolute DoWhy–EconML difference **0.013306**.
- DoWhy placebo-permutation diagnostic effect **-0.014870**; placebo diagnostics do **not** establish unconfoundedness.
- The development receipt was independently validated; a production DoWhy 0.14 receipt correctly remained **unverified**. One dataset cannot establish typical estimator superiority.

### G3 — Tigramite PCMCI / PCMCI+, 80 generated time-series cases

- 5 seeds, 2 sample sizes (160 and 320), 4 scenarios, 2 algorithms → **80 cases**.
- Direct-lag detection: PCMCI **10/10**, PCMCI+ **10/10** with no reported reversal; independent-series false cross-edge detection **0/10** for each.
- Hidden common-cause and time-varying structural-change cases are flagged separately; do **not** pool them into ordinary graph-recovery precision/recall.
- The PCMCI and PCMCI+ significance policies differ. Tests measure generated candidate edges, not proofs of causality.

### G7 — Observational effect estimation, 25 cases using uploaded DoWhy and EconML

5 seeds × 5 scenarios × 900 observations per case. Mean absolute errors against *known intervention-generated synthetic truth*:

| Scenario | DoWhy OLS ATE MAE | EconML DML ATE MAE | Validity note |
|---|---:|---:|---|
| Observed homogeneous | 0.03315 | 0.03134 | Synthetic assumptions specified |
| Observed heterogeneous | 0.03974 | 0.03288 | Five seeds; small sample |
| Null effect | 0.01327 | 0.01441 | Finite-sample noise |
| Hidden common cause | 0.14383 | 0.14420 | **Invalid identification** without observing confounder |
| No overlap | N/A | N/A | All **5/5** refused before estimation |

The hidden-confounder bias is an important warning: a backend can return plausible numbers yet be wrong about the true causal effect. Differences on five seeds should not be treated as universal accuracy rankings.

### G8 — DoWhy ATE / EconML CATE interval smoke, 24 cases

3 seeds × 2 sizes (300 and 900) × 4 scenarios. Of **18** assumption-eligible datasets (excluding the 6 hidden-confounder cases): DoWhy 95% ATE intervals contained the oracle ATE on **17/18**; EconML 95% subgroup CATE intervals contained their distinct subgroup targets on **18/18** at Z=0 and **15/18** at Z=1. **These are different estimands** and cannot establish method ranking or calibrated 95% coverage.

### G9 — Calibration comparison, full 1,000-case research grid

100 seeds × 2 sizes (300 and 900) × 5 scenarios, 399 bootstrap resamples for methods that use them. The original G9 numerical replay verifier returned **true**. Nominal target is **95%** empirical coverage, conditional on validity of the synthetic identification design.

| Scenario | n | Cross-fit AIPW 95% interval coverage | Population-mix Wald 95% interval coverage |
|---|---:|---:|---:|
| Null effect | 300 | 93% | 94% |
| Null effect | 900 | 97% | 97% |
| Observed heterogeneous | 300 | 95% | 95% |
| **Observed heterogeneous** | **900** | **89%** | **92%** |
| Observed homogeneous | 300 | 96% | 97% |
| Observed homogeneous | 900 | 93% | 95% |

- **Potential undercoverage:** The 89% AIPW and 92% Wald coverage in heterogeneous, n=900 is below nominal and deserves investigation; do not call these intervals calibrated across all scenarios.
- **No overlap:** All 200 datasets (100 seeds × 2 sizes) correctly refused estimation for each of 6 candidate interval methods (**1,200 method-level refusals**). These are correlated methods on 200 datasets, not 1,200 independent trials.
- **Hidden confounder:** Although algorithms computed numeric intervals, those cases were **excluded** from causal coverage scoring. Point bias remained substantial. Reporting them as valid 95% causal intervals would be misleading.
- **Bootstrap overlap failure:** One heterogeneous, n=300 case failed in each pairs-bootstrap method; it remained a denominator/status failure rather than being silently dropped.
- Wilson uncertainty bounds, bias, interval widths, and each case's status are recorded in `g9_standard_100seeds.json` and `G9_Coverage_Summary.csv`.

## Verification and still-open acceptance

The benchmark programs each exited with status 0; independent structural/provenance checks in `independent_receipt_audit.py` passed. Previously validated G17 C14 suite remained **651 passed, 4 skipped** with no Cognitum source changes between studies; this benchmark did not rerun all 651 tests.

The **three production pinned DoWhy 0.14 tests were explicitly rerun and all skipped** because this environment imports the untagged uploaded snapshot only through a development source path. This is *not* interpreted as a scientific failure; the release-pinned deployment gate remains distinct and open. The fourth historical skip was an absent-Tigramite negative that passed in a separate clean interpreter.

**Important limits:** synthetic generated data with known ground truth; not a causal conclusion about real people; no model-in-the-loop comparative gain; no future Lu authorization; no new package provenance claim; no demonstration of signed production runtime or OS isolation. Uploaded source is operator-reported official, its embedded version markers remain untagged.

## Handoff recommendation

Prioritize debugging undercoverage in G9 heterogeneous n=900, identifying whether it is nuisance-model misspecification, interval formula behavior, bootstrap behavior, or Monte Carlo variation. Use independent seed partitions and predeclared methods. The existing DoWhy/EconML G7 experiment should be extended over more seeds before drawing comparative conclusions. Continue to keep Lu convergence and Lu code untouched.
