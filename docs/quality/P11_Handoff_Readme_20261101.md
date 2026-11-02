# Cognitum P11 — Contained warm admission and cleanup handoff

Package contents:

- `cognitum/` — complete locally tested Cognitum research source snapshot, including `warm_guardian_p11.py`, modified `sandbox_warm_pool.py` and `sandbox_linux.py`.
- `tests/test_warm_guardian_p11.py` — real cross-process, host-SIGKILL, guardian-SIGKILL, restart and blocked worker tests.
- `tests/test_contained_warm_p11_soak.py` — authorized 120 or 1,000 mixed-operation soak.
- `tests/test_sandbox_warm_p8.py`, `tests/test_contained_warm_p9.py` — relevant earlier regressions.
- `P11_source_changes.patch` — unified source patch validated against the recovered P10 baseline (`git apply --check`).
- `development_wheel/cognitum_core-0.1.0-py3-none-any.whl` — rebuilt **development** wheel, with PEP 427 RECORD recalculated.
- `evidence/` — verified logs, JSON outcomes, install smoke and SHA-256 manifest.
- `Engineering_Report.md` — complete acceptance/limitations.

## Reproduce on Linux with unprivileged P7 user namespace enabled

```bash
PYTHONPATH=. pytest -q tests/test_warm_guardian_p11.py
PYTHONPATH=. pytest -q tests/test_sandbox_warm_p8.py tests/test_contained_warm_p9.py tests/test_warm_guardian_p11.py tests/test_contained_warm_p11_soak.py -k 'not test_kan_warm_execution_requires_trusted_hash_and_matches_p7_cold'
COGNITUM_P10_WAVES=125 COGNITUM_P10_REPORT=soak_1000.json PYTHONPATH=. pytest -q tests/test_contained_warm_p11_soak.py
```

Run the stress test *sequentially* to avoid saturating all four shared standby slots while unit tests expect an otherwise idle host. Real P7 namespace tests require `unshare` support; writable delegated cgroup-v2 remains a separate, unverified security gate.

No Lu code changed. GitHub is a documentation/source repository, not this development environment.
