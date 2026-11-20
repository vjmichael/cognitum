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
