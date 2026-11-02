# Cognitum P10 Linux worker tests

This package preserves the tested P9 Cognitum source tree and contains **P10 test harnesses, probes, logs and evidence**. No production source modifications are required for this test milestone. See `Engineering_Report.md` for verified results and security caveats.

From a Linux host with working unprivileged user/PID/network/mount namespaces, execute:

```bash
PYTHONPATH=. pytest -q tests/test_contained_warm_p9.py tests/test_sandbox_warm_p8.py tests/test_contained_warm_p10_soak.py -k 'not kan_warm_execution_requires_trusted_hash_and_matches_p7_cold'
COGNITUM_P10_WAVES=125 COGNITUM_P10_REPORT=evidence/soak_1000_repeated.json PYTHONPATH=. pytest -q tests/test_contained_warm_p10_soak.py
PYTHONPATH=. python tools/host_sigkill_probe.py
PYTHONPATH=. python tools/multi_host_cap_probe.py
```

The KAN test is excluded only because the upstream `test_research_optional.py` fixture is absent from this handoff, not because its algorithm is known to fail. The multi-host probe **intentionally confirms an unresolved cap violation**. Do not interpret these tests as arbitrary-code sandbox security acceptance, or run SIGKILL fault probes in an unmanaged production host.
