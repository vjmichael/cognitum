# COG-05-SSM-POST-NATIVE-02 — Independent external data, falsification and uncertainty

**Status:** locally qualified candidate; **38/38 newly runnable tests PASS**, **434/434 available combined local tests PASS**; **six additional genuine HDC/KAN tests STAGED, NOT EXECUTED**. The source-identical prior 391-case/4-native-target baseline remains independently PASS at c382da2e and is NOT an acceptance of these new tests. No CI triggered and no production or physical execution authorization.

## Independence and NIST source provenance (November 20, 2026)
Two real observed calibration datasets were retrieved from NIST StRD data pages and their 50 source data rows manually transcribed into strictly versioned/canonical CSV fixtures; this task did not retrieve upstream .dat files as raw bytes. **Our SHA-256s identify our own canonical transcriptions, NOT a verified byte identity to NIST's .dat.** NIST's independent certified parameters/SSE provide numerical cross-checks; they were never passed into the fitted estimators or model selection. Licensing: consulted NIST general copyright statement, but did not audit dataset-specific rights; fixture says license_scope_verified=false. These are physically observed calibration relationships, NOT longitudinal dynamical state measurements.

| Dataset | Source | Observations | Model | NIST certified parameters | NIST certified SSE | Canonical fixture SHA256 |
|---|---|---:|---|---|---:|---|
| Norris (ozone monitor calibration) | https://itl.nist.gov/div898/strd/lls/data/LINKS/DATA/Norris.dat | 36 | b0+b1*x | (-0.262323073774029, 1.00211681802045) | 26.6173985294224 | 75973a50205dadcc2876336eb7a9645128602b1463d18b8d928ed5cbf5bd59b0 |
| Misra1a (dental adsorption volume vs pressure) | https://www.itl.nist.gov/div898/strd/nls/data/LINKS/DATA/Misra1a.dat | 14 | b0*(1-exp(-b1*x)) | (238.94212918, 0.00055015643181) | 0.12455138894 | ae55d8e2a3f3d5bdc169a08cb46ef2669fd872c46657c859b3edd65f48875217 |

Reference:
- NIST certified Norris: https://www.itl.nist.gov/div898/strd/lls/data/LINKS/v-Norris.shtml
- NIST certified Misra1a: https://www.itl.nist.gov/div898/strd/nls/data/LINKS/v-misra1a.shtml
- NIST licensing policy: https://www.nist.gov/open/copyright-fair-use-and-licensing-statements-srd-data-software-and-technical-series-publications

## Actual numerical results, independently checked
- **Norris:** fitted (-0.2623230737738989, 1.0021168180204543), SSE 26.61739852942295, max relative certified-parameter discrepancy 4.96e-13.
- **Misra1a:** fitted (238.94212915238472, 0.0005501564318770761), SSE 0.12455138894440021, max relative certified-parameter discrepancy 1.22e-10. Two noncertified optimization starting points converged consistently, with analytic Jacobian.
- Model fit does not consult NIST certified coefficients; certified numbers are read-only external oracles. Three frozen splits per dataset (seeds 7/29/89) separate train, calibration and untouched test records; the same splits are rerun with preregistered weaker negative hypotheses, with a fixed 2% superiority threshold.
- **Norris held-out RMSE:** scientific linear model 0.6234 / 0.8941 / 0.5626 versus constant model 387.7056 / 329.3891 / 316.4404.
- **Misra1a held-out RMSE:** nonlinear saturation 0.1249 / 0.0902 / 0.1441 versus linear null 0.6287 / 0.6971 / 1.1523.
- **12/12 model-comparison experiments behaved as predeclared:** six supported scientific families beat weak baselines; six preregistered negative-control hypotheses were falsified. Three pressure calibration heldout groups have only 3 rows each; this is **not** broad real-domain validation.
- Canonical dataset SHA, out-of-band frozen protocol SHA, exact split indices, evidence SHA and reproducible byte-identical replay are retained. Changing protocol seed/splits, source contents or evidence results is rejected.
- Split-conformal residual radius uses finite-sample rank quantile with an **explicit, unverified exchangeability assumption**; empirical coverage is reported, not asserted as guaranteed under real physical distribution shift. Additional local 3-seed simulated IID experiments recovered approximate nominal marginal coverage; analogous shifted experiments failed coverage. No posterior coverage calibration or physical uncertainty certification.

### Two-system genuine HDC/KAN/SSM tests (native-only; not counted as passed)
The new suite stages six tests using the actual MEL elliptic checkpoint fixture, not mock KAN evaluations. Two genuinely distinct normalized 2D candidate vector fields (cooperative vs antagonistic second component) are tested at two initial states against an independently integrated analytical polynomial ODE. The wrong-sign alternative must fail a preregistered end-state tolerance. One test rejects a mismatched checkpoint digest and one uses actual HDC Spec/Cleanup for source-bound regime-candidate retrieval, future-step exclusion and ambiguity abstention. A KAN-represented field is a mathematical fixture, **not a scientifically established physical law**; HDC similarities are candidates, not verified explanations. No automated model training, cross-domain physical law claim or external action.

### Actual local test results
- **38/38** new executable NIST and uncertainty tests PASS (31 external measurement/falsification + 7 exchangeability/refusal tests), no new local failures after repairing a duplicate safety-flag keyword in the new replay receipt.
- **434/434** locally available combined tests PASS (377 earlier isolated base + 19 post-native-01 + 38 new); genuine repository-only MEL/KAN/HDC tests are excluded as unavailable in this isolated container.
- Source/test/CSV Git blobs matched exactly to the locally tested file bytes. Windows checkout is forced to preserve LF on the two external CSV snapshots.
- Environment: Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0, pytest 9.0.2, single-thread BLAS/OpenMP.
- Dedicated JUnit SHA256: e3e8a5c360749233075e20bec4d96ad8c76327c595023424e113465b8e6a3fa9.
- Combined JUnit SHA256: d28ba62464ae0df2e11724235439725f8c5a170afa0f89c9f2db9d8460688e06.
- Detailed 12-trial numerical audit and frozen protocol SHA registry: [POST_NATIVE02_LOCAL_RESULTS.json](POST_NATIVE02_LOCAL_RESULTS.json).

## Acceptance and residual classification
**NEW 44-case native gate staged** after previous 19-case POST-NATIVE-01 same-head gate and SSM-09B 391-case receipt, with all source pins, source/checkpoint data files, previous receipts and digests required unchanged. The gate requires 44 dedicated and 63 combined post-native tests. This gate has **NOT** been executed, and therefore neither six KAN/HDC cases nor 38 external-data cases have new cross-platform native acceptance yet. The original 391-case acceptance is not reopened/reclassified.

Priority residuals:
- DS69/70/72 (P0A): externally certified numerical cross-checks and reproducible falsification now have local coverage; authentic raw-upstream-byte verification, specific rights audit, larger datasets and production-grade independent provenance/security still open.
- DS36/60/67/68 (P0B): two novel KAN field families and HDC retrieval scenarios staged for native, not locally passed; no independent physical system measurements or learned scientific discovery.
- DS40/45/63 (P0C): IID split-conformal coverage and changed-distribution negative controls locally verified; conditional distribution shift, general risk and real regime forecasting open.
- ALL 72 research capabilities remain PARTIAL. P0A=5, P0B=4, P0C=5, P1=42, P2=16. Test-case coverage does not equal full mathematical acceptance.

## Next independent closeout
**COG-05-SSM-POST-NATIVE-02-NATIVE-01 — Execute same-SHA cross-platform gate for 44 new external-science/HDC-KAN tests and 63 combined post-native tests, repair any genuine fixture regressions, and reconcile dataset rights/provenance without changing the already qualified source tree.**

## Native addendum — POST-NATIVE-02-NATIVE-01 complete

The earlier wording `NEW 44-case native gate staged` describes the **historical local candidate**, superseded by [the source-locked native closeout](POST_NATIVE02_NATIVE01.md). Native run [#44832908788](https://github.com/vjmichael/cognitum/actions/runs/44832908788) **completed SUCCESS**, all four hosted Ubuntu/Windows Python 3.11/3.13 environments at fixed SHA `bd2b332a`, 44/44 dedicated and 63/63 combined post-native, 81 cumulative source pins, independently checked receipts and JUnit artifacts. First native attempt failed four KAN result-receipt tests due duplicate authorization-flag keyword; minimal fix and explicit non-authorizing default confirmed. A first corrected run passed three platforms but Windows/Python3.11 exceeded a 12-minute job timeout; workflow-only 30-minute limit allowed all four to pass on final SHA. Neither the mathematical assumptions nor test counts were relaxed. **All 72 broad mathematical capability rows remain PARTIAL.** NIST public StRD data are SRD 140; all 50 displayed data values match frozen transcriptions but original .dat source-byte authentication and dataset-specific licensing/reuse rights remain unresolved. Empirical split-conformal coverage is not guaranteed under non-exchangeable shift. Checkpoint fixtures do not establish real-world dynamical model discovery. No deployment or external actuation authority.
