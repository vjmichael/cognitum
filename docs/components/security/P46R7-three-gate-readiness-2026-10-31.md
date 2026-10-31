# Cognitum P46R7: three-gate engineering outcome

**October 31, 2026 — development-only.** All production worker admissions remain off.

## Gate 1: real kernel descendant containment

**BLOCKED / FAIL CLOSED.** `/sys/fs/cgroup` is a cgroup2 filesystem but has the `ro` mount flag. Attempting to create a private test cgroup produces `Read-only file system`. Tests cannot verify `cgroup.kill` against real escaped descendants. No fake cgroup cleanup is treated as kernel acceptance. This gate requires a trusted delegated writable hierarchy and a separate integration run against an escaped descendant.

## Gate 2: independent supervisor restart and crash reconciliation

`cognitum/recovery_service.py` adds a system-service entrypoint around the existing P46R6 ledger and kernel reconciliation. It is exclusive per private state directory via a nonblocking OS lock. It never starts workers, never grants an extension, rechecks root cgroup mount writability and kernel identity before execution, rejects unverified host-closed markers, and does not assert independent attestation. It exits nonzero on cleanup failure, allowing the independent service manager to restart/escalate.

A local external `supervisord` fixture validates actual service restart after two independent `SIGKILL` events, using **inspection-only** execution against a fake cgroup. This proves service restart and ledger inspection, not kernel cleanup. `deployment/systemd/cognitum-p46r7-recovery.service.example` is a deployment template only: **not installed or activated** in this container. Actual systemd PID 1 is absent.

## Gate 3: Lu-Linux isolated development-host integration

**BLOCKED / NOT INTEGRATED.** The isolated Lu branch `lu/linux-native-test-host` documents a native Unix-socket test-host P0 overlay, but its branch status explicitly says it is not source-synchronized and the real enabled Tauri server has not been compiled or launched. No authenticated Lu host socket or matching L16 overlay is mounted in this container. Cognitum does not substitute a mock Lu host or claim successful UI/model/native-worker integration. No Lu main/Windows changes were made.

### Required next acceptance evidence

1. Real delegated-cgroup test: worker enters exact cgroup *before release*, `setsid()` breakaway remains attached, supervisor and watchkeeper crash, independent service invokes `cgroup.kill`, and the kernel reports `populated 0` for the same `(st_dev,st_ino)` scope; capture kernel and process evidence.
2. System-service deployment: service manager with restart policy installed on a disposable Linux host, repeated watchkeeper termination, durable reconciliation and clean removal measured against real cgroups. Tests should also cover manager restart limits, filesystem denial, ledger tampering and boot ID drift.
3. Lu development host: synchronize L16, compile/launch native test host with owner-only socket and host-derived authorized USER turn, then route one fixed Cognitum Protobuf capability through Lu's native worker manager and capture host-originated typed feedback. Distinguish component tests from full alpha.

**No general JSON repair or Lu-native execution policy is moved into Cognitum.**

## Measured local regression accounting

- P46R7 recovery service: **11/11**, repeated three additional independent times, including real `supervisord` restarts after two consecutive service `SIGKILL` events; on each generation the same durable pending job was inspected.
- P46R7 Lu readiness: **5/5** strict no-auth/no-execution preflight tests.
- Prior P46R6 recovery: 23; P46R5 watchkeeper: 13; P46R5 handoff: 4; P46R4 gate: 7; P46R3 containment: 17; P46R2 matrix: 12; P46R1 fixed-parent: 7; alpha-native: 14; alpha-native fault: 4; host witness: 16; archive auditor: 6; P47 evidence: 19; P49 escape: 2.
- **160/160 tests passed across 15 completed focused suites** (each run separately). This is not a full repository test. The older P48 `test_reference_lifecycle.py` did **not** complete within its bounded run and is excluded; a partial batch that later stalled is also excluded.
- The actual Lu branch `lu/linux-native-test-host` at `236a3e7f87d5538ba2c04ed71bcba04a04e607e2` lacks the `lu-native-test-host` feature in `src-tauri/Cargo.toml` and the `src-tauri/src/core/lu_native_test_host.rs` server module. The branch's own `P0_BRANCH_STATUS.md` says source synchronization and full server launch are unverified. The local development container has no corresponding running Unix socket.
- Linux kernel: 6.18.57, container PID 1 `supervisord`; `systemctl is-system-running` reports `offline`. Cgroup2 is mounted `ro` and a disposable cgroup `mkdir` returns `Read-only file system`.

The systemd unit is **illustrative and uninstalled**. Its `Restart=on-failure` setting requires a real service-manager deployment test; the verified independent restart used `supervisord` with **inspection-only** execution. Any future full accepted result must come from a writable delegated cgroup with independent kernel evidence and a live authenticated Lu host turn.
