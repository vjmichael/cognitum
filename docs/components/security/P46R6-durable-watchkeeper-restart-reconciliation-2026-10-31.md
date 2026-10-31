# Cognitum P46R6 — Durable watchkeeper restart reconciliation

**Date:** 2026-10-31  
**Scope:** Cognitum fixed-worker developer harness only  
**Status:** Tested reference implementation; kernel-enforced containment and real service-manager acceptance **not achieved**

## Purpose

P46R5 proved that an out-of-cgroup watchkeeper can outlive its Python launcher and monitor its host by `pidfd`. It **did not** protect against the watchkeeper's own sudden death. P46R6 preserves enough trusted host-owned state so a separately launched recovery process can find jobs left by that failure and attempt cleanup of the exact original kernel cgroup, without allowing the model to choose a target path or invent a success receipt.

This milestone is not the historical P46 archive (which remains unavailable), does not implement Lu host permission policy or general JSON repair, and does not activate an unrestricted native worker.

## Implemented

1. `cognitum/host_recovery.py`: `record_before_worker_release` writes a complete, private (0600), immutable, fsynced pending-job record. Entries contain a strictly validated 32-hex-digit job ID, fixed-format cgroup scope basename, *device/inode* of root and scope, Linux boot ID, host and watchkeeper PIDs, and an explicit `production_authorized=false`.
2. `cognitum/cgroup2_fixed_runner.py`: when a host explicitly supplies `recovery_state_dir`, the launcher records that scope **after** arming P46R5's separate watchkeeper but **before any worker process is spawned or released**. A failed durable write aborts worker launch. The existing fixture-only API without this optional argument remains unqualified for durable recovery.
3. On normal watcher-confirmed cleanup followed by successful cgroup directory removal, the trusted host writes an immutable, fsynced `HOST_REPORTED_CLOSED_UNATTESTED` marker. Pending records are never overwritten.
4. `reconcile_pending`/`reconcile_job`: a new process can scan up to 256 fixed-format pending records, reject duplicate JSON keys and malformed records, and re-open only a caller-selected trusted delegated root. An exact matching boot ID, kernel cgroup v2 descriptor, root device/inode, and scope device/inode are required before a kernel cleanup attempt.
5. Cleanup calls P46R5 `kill_and_observe`, which writes `cgroup.kill` and checks `cgroup.events populated=0`. P46R6 independently rereads `cgroup.events` and `cgroup.procs` from the same pinned scope descriptor after the call. A write without observed emptiness is failure.
6. Every attempted reconciliation writes a create-only `p46r6-attempt-*.json` result. Contradictory or forged closure evidence fails closed; normal closure remains a **host report**, not third-party attestation.
7. `python -m cognitum.host_recovery --state-dir DIR --delegated-root CGROUP_ROOT` is inspection-only. The explicit `--execute` flag attempts **real** kernel cleanup and returns a nonzero exit on unresolved failure. The CLI exposes no mock mode or arbitrary executable path.

## Verification performed in this session

- Linux Python 3.13.5; protobuf 6.33.6.
- **23/23 P46R6 focused tests passed.** These include immutable/permission-checked journal, parent and scope identity checks, fake-kernel negative controls, mismatched boot ID, duplicate evidence, idempotent normal-completion marker, strict no-worker-on-journal-failure ordering, and a **real watchkeeper SIGKILL** followed by a **separate Python interpreter** simulating recovery.
- Focused regression suites: **154 passing tests across 15 independently completed suites**, including P46R1–P46R5, real alpha-native calculator worker, P47/P48 evidence, and P49 process-group escape controls. Exact per-suite logs and a machine-readable manifest are in the checkpoint.
- Two additional tests (`test_capability_results.py` and `test_protobuf_codec.py`) could not import `cognitum.runtime` from this **partial reconstructed checkout**; neither is counted as a pass or attributed to P46R6. A timed-out broad run was also not used as acceptance evidence.
- The local cgroup2 hierarchy is mounted **read-only**. **No live `cgroup.kill` descendant-containment acceptance, no service-manager recovery, and no isolated Lu-Linux integration occurred.**

## Explicitly unverified / required before real worker admission

1. A *writable, delegated cgroup v2* test environment, with actual escaped grandchild termination observed through cgroup events and independent process handles. `cgroup.kill` must work under the precise authority and delegation model proposed for deployment.
2. A trusted service manager (systemd or equivalent) must own watchkeeper restart and invoke the reconciliation command after halting/quiescing new launches. This Python script **is not itself a service manager**. PID 1 here is `supervisord`, not systemd. **Do not run recovery against active jobs from an unrelated service without an explicit shutdown/revocation policy; it intentionally targets all pending scopes for termination.**
3. Recovery on watchkeeper death must be durably initiated independent of the Python launching host, with retries on failed cleanup and persistence across service restart/power loss. The current CLI is one-shot; an external manager must provide scheduling and retry behavior.
4. Unprivileged workers must be prevented by OS policy from leaving their delegated cgroup, altering cgroup files, reading or forging host records, accessing private credentials/network, or interfering with the watchkeeper. The cgroup is only **process containment**, not a full sandbox.
5. Proper authentication/signing/attestation of host evidence; current record integrity is host-owned file permissions and fsync, **not cryptographic independent attestation**. Exact source and library provenance must be recorded.
6. Windows restricted-token/Job Object breakaway containment, Lu conversation-bound grants, and real Lu-Linux developer host integration are separate gates.

**Security disposition: DEVELOPMENT-ONLY / NO PRODUCTION ADMISSION.** A simulated successful cleanup never counts toward actual OS containment acceptance.
