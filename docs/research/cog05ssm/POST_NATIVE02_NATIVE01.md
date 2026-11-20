# COG-05-SSM-POST-NATIVE-02-NATIVE-01 — Native qualification and residual reconciliation

## Qualification scope
Target branch: `cognitum/ssm-postnative02-native-r1-20261120`. First attempted source-locked GitHub Actions run [44828561298](https://github.com/vjmichael/cognitum/actions/runs/44828561298), SHA `4a33cbec2d1103eabd13d704c8f7d3eb9de68eef`, exercises the inherited 391-scope SSM-09B acceptance, 19-case post-native-01 and new 44-case post-native-02, including 63-case combined post-native check, on Ubuntu/Windows with Python 3.11 and 3.13.

### Original native failure — explicit evidence
The first Ubuntu 3.11 native `research_tests/ssm_postnative02` run returned **40 PASS / 4 FAIL**. Four test variants of `test_two_distinct_checkpoint_dynamical_families_against_independent_ivp` reached the `kan_hypotheses()` result-construction boundary after computing finite independent-KAN-reference errors. The failure was `TypeError: dict() got multiple values for keyword argument 'execution_authorized'`. The shared `ssm_stochastic.receipt()` helper already inserts `execution_authorized=False`; the new `kan_hypotheses()` passed a redundant second value. No numerical-algorithm change, test tolerance change, or authority-policy weakening was indicated by this trace. The failing candidate is **not accepted**. A ZIP of the original failed dedicated XML and log is retained as evidence.

### Minimal integration repair
On research branch `research/ssm-postnative02-20261120`, remove only the redundant explicit `execution_authorized=False` keyword at the `kan_hypotheses()` receipt call; retain the original helper default so the emitted value stays false. Locally tested corrected Git blob: `5c15058ce70e9b6cd71c5bbb48cfa1839ce3dc72` (old blob `f79018fdade8c0194c743afb41c6bffdc389b562`). Source-lock gate `tools/ssm_postnative02/acceptance.py` re-pinned to the new exact blob. Remaining fixture and mathematical test files, model references, safety values, acceptance counts **44/63**, and predecessor source receipts are unchanged.

Available local post-native 01+02 tests passed 57/57 after repair. Entire available isolated suite passed **434/434**; 6 new and 14 older repository-dependent MEL/KAN/HDC cases remain native-only in this local environment. An isolated stub that exercises the receipt metadata path also confirms `execution_authorized=False` and the expected accepted/rejected values. Do not infer this passes the complete native gate.

### Independently sourced data, evidence and rights
[Provenance audit](POST_NATIVE02_PROVENANCE_AUDIT.md): read all **50** publicly rendered NIST numeric observation pairs — Norris **36**, Misra1a **14** — and compare in exact row order against frozen local CSV values, with **zero numeric disagreements**. Local canonical transcription digests are documented; original NIST .dat byte origin/hashes are **not independently authenticated**.
NIST explicitly lists its Statistical Reference Datasets as **Standard Reference Database 140**. Under NIST's SRD distinction, do not claim unrestricted public-domain redistribution from public webpage access. Confirm individual dataset rights/terms and required attribution separately; retain `license_scope_verified=False`.
NIST certified regression parameter/SSE comparisons are numerical-reference validation of the software, *not* physical dynamics confirmation. Nonlinear KAN fixtures are represented mathematical functions, not experimental discovery. The existing split-conformal empirical IID coverage is not guaranteed under shift, dependence, tiny calibration samples or unknown observation models.


### First corrected run: mathematical gates pass, Windows 3.11 hosted-timeout limitation
[Run 44831037543](https://github.com/vjmichael/cognitum/actions/runs/44831037543), corrected SHA `ba348f888bfc5b205696dfdc9fe8f2c5cf2be8b5`, passed **44/44 dedicated and 63/63 combined** with valid 81-pin receipts on Ubuntu 3.11, Ubuntu 3.13 and Windows 3.13. Windows 3.11 was **CANCELLED**, not passed, during a prior SSM-07-R1 step. The job's GitHub logs record `The operation was canceled`, not a POST-NATIVE-02 regression; workflow setting `timeout-minutes: 12` did not allow that longer hosted Windows path to finish. Earlier POST-NATIVE gates on that Windows job were skipped, therefore no fourth native acceptance receipt exists for this SHA.

### Next fixed-SHA qualification with bounded time repair
Changed only `.github/workflows/python-tests.yml` job `timeout-minutes` **12 → 30** in the research candidate, preserving all mathematical source/test bytes and acceptance contracts. A new single exact-tree qualification run [44832908788](https://github.com/vjmichael/cognitum/actions/runs/44832908788) at SHA `bd2b332a06291f005adf5ab8183c56c8d36ba81f` is in progress, on the same four hosted OS/Python targets. Do not promote the new run until each required receipt passes and artifact integrity is independently checked. No overlapping corrected runs were launched.

### Pending closeout requirements
- Obtain the corrected 44 dedicated / 63 combined native receipts from a **single new fixed SHA** and verify 391-case inherited SSM scope, 19-case prior, 80+ cumulative blob pins, predecessor source SHA, JUnit inventories, artifact digests and job conclusions on all four OS/Python targets.
- Reconcile additional verified scoped results against the DS36/40/45/60/63/67/68/69/70/72 register without promoting broad DS capabilities to full acceptance.
- Preserve native [first-run evidence](https://github.com/vjmichael/cognitum/actions/runs/44828561298) and local reproducibility separately. Do not stack additional CI runs or permit external system actuation.

**Current status: repaired candidate prepared, cross-platform acceptance pending.**

## Final closeout — bounded native qualification PASS

### Authoritative final acceptance — 44832908788
[GitHub Actions run 44832908788](https://github.com/vjmichael/cognitum/actions/runs/44832908788) **completed SUCCESS**, four GitHub-hosted native OS/Python jobs, all at the **single source SHA** `bd2b332a06291f005adf5ab8183c56c8d36ba81f`. A longer **30-minute per-job timeout** resolved the Windows 3.11 hosted execution cancellation. The only difference from the three-pass mathematical candidate is workflow timeout plus documentation; **no mathematical code, test, fixture, data, source pin or acceptance threshold changed**. This is a source-locked candidate, not the earlier failed SHA.

| Native environment | POST-NATIVE-02 dedicated | POST-NATIVE-01+02 combined | Pinned source blobs | GitHub artifact |
|---|---:|---:|---:|---|
| Ubuntu / Python 3.11 | 44/44 | 63/63 | 81/81 | [14676992246](https://github.com/vjmichael/cognitum/actions/runs/44832908788/artifacts/14676992246) |
| Ubuntu / Python 3.13 | 44/44 | 63/63 | 81/81 | [14676762615](https://github.com/vjmichael/cognitum/actions/runs/44832908788/artifacts/14676762615) |
| Windows / Python 3.11 | 44/44 | 63/63 | 81/81 | [14678185798](https://github.com/vjmichael/cognitum/actions/runs/44832908788/artifacts/14678185798) |
| Windows / Python 3.13 | 44/44 | 63/63 | 81/81 | [14677408577](https://github.com/vjmichael/cognitum/actions/runs/44832908788/artifacts/14677408577) |

Downloaded and independently audited all four artifact ZIPs. Every receipt asserts `status=PASS`, matching `source_sha`, `source_pins` count 81, `dedicated.tests=44` and `combined.tests=63`, zero failures/errors/skips; every included JUnit testcase was counted and each receipt artifact SHA-256 recomputed. Prior POST-NATIVE-01 receipt hashes differ correctly across the four platform jobs and are enforced by the same-head gate. All four jobs finished with `conclusion=success`. This gives **176 dedicated** and **252 combined post-native** test executions across platforms; those counts are repeated scoped tests, not independent scientific discoveries. The inherited 391-case accepted baseline is enforced upstream in the same-head chain; it is not a fresh set of 391 distinct post-native tests.

Original failed [run 44828561298](https://github.com/vjmichael/cognitum/actions/runs/44828561298): three native variants failed a shared duplicate result-key bug, one Windows run cancelled before reaching the gate. First corrected [run 44831037543](https://github.com/vjmichael/cognitum/actions/runs/44831037543): 3/4 environments passed, Windows 3.11 cancelled due too-short 12-minute job timeout during earlier SSM stage. Final run above resolved both blockers **without relaxing mathematical acceptance**. Retain both earlier runs in the audit trail.

### Scientific evidence and rights: residuals deliberately NOT closed
- **NIST reference consistency verified:** all publicly rendered response/predictor numeric pairs checked against frozen transcriptions (Norris 36, Misra1a 14) with zero mismatches, and certified numerical regressions independently matched by existing tests. The original upstream `.dat` bytes and historical acquisition chain are **not** cryptographically authenticated by a canonical CSV digest.
- **Source classification confirmed:** NIST Statistical Reference Datasets are **SRD 140**, and NIST distinguishes SRD licensing from other government works. These two dataset-specific redistribution/derivative rights and attribution/permission requirements remain **unresolved**. Public access and certified output are not a license grant. See [provenance audit](POST_NATIVE02_PROVENANCE_AUDIT.md), [NIST StRD home](https://www.itl.nist.gov/div898/strd/), [NIST SRD catalog](https://www.nist.gov/srd/srd-catalog) and [NIST licensing policy](https://www.nist.gov/open/copyright-fair-use-and-licensing-statements-srd-data-software-and-technical-series-publications).
- **Uncertainty remains conditional:** split-conformal marginal coverage assumes exchangeability; the small and shifted datasets do not establish general/conditional calibration or out-of-distribution reliability. Deliberate shift counterexamples do not qualify a universal detector.
- **KAN/HDC/SSM functional scope:** six repository-dependent tests now pass across four native targets, exercising two genuine checkpoint-represented mathematical vector fields, HDC candidates and falsification. They are **not** independent validation of a discovered physical law, generalized KAN training, physical state estimation or guaranteed model-uncertainty propagation.
- **Governance:** every one of the 72 DS broad capabilities remains `PARTIAL`, none promoted to complete by this suite; `execution_authorized=False`, no Maj Vaj/physical/control authority, no production acceptance or physical Radeon/FPGA workstation qualification.

**Final task disposition: PASS for bounded source-locked 44/63 post-native tests on all four native matrix targets, with previously verified 391-case baseline preserved. No outstanding numerical regression in the executed scope. Broader research/dataset/rights/physical validation remain open.**
