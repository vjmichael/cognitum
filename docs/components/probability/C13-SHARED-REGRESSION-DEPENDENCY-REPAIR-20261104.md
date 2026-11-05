# C13 shared regression dependency repair — 2026-11-04

## Observed CI results
At PR #70 head `a5486987df1e34324f1a7e1c1ce0ac825bcfe9a2`:
- The dedicated `C13 real SciPy Bayesian inference and calibration acceptance`
  job passed, with actual SciPy numerical operations and typed Protobuf on
  Windows and Linux (Python 3.11/3.13).
- The broader `Cognitum Python regression` matrix failed. Its setup installed
  `.[security,scientific]` but **not** `.[probability-stats]`, despite
  discovering and running all C13 tests. Consequently, C13's optional
  `scipy.special.logsumexp` and `scipy.stats.beta` adapters reported
  `UNSUPPORTED`. C13 tests appropriately require `OK` when the numerical
  backend is part of the acceptance environment.
- The Windows generic matrix also reported host-recovery failures in
  `tests/test_host_recovery.py`, distinct from C13; do not alter Windows
  host-isolation tests or weaken fail-closed behavior as a workaround.

## Implemented repair
In `.github/workflows/python-tests.yml`, install
`.[security,scientific,probability-stats]` in the full regression, and add
`pip check` and explicit `scipy.special.logsumexp` /
`scipy.stats.beta` import checks before the suite.

C13 remains an optional-extra **component**, not an unconditionally imported
dependency of `cognitum-core`. A full test job that deliberately tests the
real optional backend must provision that backend. The dedicated C13 workflow
already did this correctly.

## Remaining acceptance
- Recheck all real C13 and shared regression jobs at the **new exact head SHA**.
- Triage unrelated Windows host-recovery errors separately with platform
  ownership maintained. No synthetic/mocked status can substitute for real
  Bayesian and calibration numerical tests.
- Only close/merge PR #70 when the agreed required checks pass.

No new Bayesian research or numerical optimization is authorized by this fix.
