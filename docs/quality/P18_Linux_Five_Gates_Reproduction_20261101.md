# Cognitum P18 Linux five-gate handoff

**NOT A PRODUCTION RELEASE.** Windows/P15 fully deferred; Lu unchanged.

- Read `Engineering_Report_P18.md` for the gate-by-gate acceptance and block reasons.
- Source: `cognitum/` full recovered P17 tree plus P18 changes. Important changes: `cognitum/research/kan_optional.py`, `cognitum/durable_admission_p12.py`, new `cognitum/research/causal_bootstrap_p18.py`.
- New tests: `tests/test_kan_decoder_p18.py`, `tests/test_specialist_scale_p18.py`, `tests/test_causal_bootstrap_p18.py`, `tests/test_recovery_identity_p18.py`, `tests/test_p18_kernel_pressure_live.py`.
- Reproduce bounded Linux regression: `PYTHONPATH=.:tests python run_p18_linux_acceptance.py`, or separately run `acceptance_P8_P9.log`, `acceptance_P11_P12.log` and `acceptance_P13_P14_P16_P17_P18.log` test filenames from script. Live P13 tests require explicit operator delegation.
- Run integrated P7/P11 research workers: `PYTHONPATH=.:tests python run_p18_integration.py`.
- Fresh research C14 heldouts: `PYTHONPATH=. python run_causal_p18_holdout.py` (research only, not a causal release gate).
- KAN benchmark: `PYTHONPATH=.:tests python bench_kan_p18.py` (bundled P17 baseline reference under `evidence/`).
- Development wheel (not published): `development_wheel/cognitum_core-0.1.0-py3-none-any.whl`, built with `python build_p18_wheel.py` from locally pinned P17 wheel.
- `deploy/cognitum-p14-watchkeeper@.service.example` is not installed; requires operator review and trusted delegated cgroup before deployment.
- P13/P14 live kernel acceptance remains blocked on this environment's read-only cgroup2 mount. Never fake those tests.
