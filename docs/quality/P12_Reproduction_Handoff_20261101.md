# Cognitum P12 — local source and acceptance handoff

Includes the full P11 Cognitum development source advanced to P12, a development wheel with recalculated hashes, new `cgroup_v2_p12.py`, `cgroup_exec_gate_p12.py`, `durable_admission_p12.py`, P11-compatible modifications to the sandbox launcher, warm pool and guardian, P12 positive/negative and opted-in live-kernel tests, and local evidence. Source changes are optional and host-selected; no production defaults or Cognitum numerical algorithms changed.

Test locally: `PYTHONPATH=. pytest -q tests/test_cgroup_p12.py tests/test_durable_admission_p12.py tests/test_cgroup_p12_live.py tests/test_warm_guardian_p11.py tests/test_contained_warm_p9.py tests/test_sandbox_warm_p8.py -k 'not test_kan_warm_execution_requires_trusted_hash_and_matches_p7_cold'`.

P12 does **not** claim live kernel containment on this host: cgroup-v2 is read-only; live tests skipped. Review `Engineering_Report_P12.md` before any deployment. Do not treat simulated kernel tests as OS-enforced acceptance. No Lu changes.
