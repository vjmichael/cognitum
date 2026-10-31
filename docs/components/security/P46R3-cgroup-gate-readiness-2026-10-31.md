# Cognitum P46R3 — cgroup-v2 gated-worker readiness, fail-closed integration

**Recorded:** 2026-10-31
**Status:** Locally tested development fixture only. **Not** P46's original recovered archive, not a production sandbox, and **not tested inside Lu-Linux**. GitHub is source control/documentation, never a required CI development hub.

## Source reconciliation

P51's cgroup-v2 experiment was preserved in a local checkpoint but **not yet present on Cognitum main**. This branch adds the existing `cognitum/cgroup2_contract.py` and newly hardened `cognitum/cgroup2_fixed_runner.py` and `cognitum/gated_alpha_worker.py`, plus `tests/test_p46r3_containment_gate.py`. This also repairs the P46R2 test's previously untracked dependency on `cgroup2_contract` and `cgroup2_fixed_runner`.

## Behavioral changes

- **Kernel preflight:** A real Linux cgroup-v2 filesystem, delegated writable cgroup scope, `cgroup.procs`, and `cgroup.kill` are required before any fixture process may launch. Fake files, symlink aliases, read-only mounts and unprivileged scope creation fail closed. Only the fixed native alpha worker is permitted.
- **Stricter release barrier:** After cgroup attachment, the host must provide *exactly* one `G` byte and close its writer. The worker waits for EOF with a bounded timeout. Extra tokens, missing EOF, held/inherited writers or invalid tokens do **not** release execution.
- **Identity checks:** Before and after numerical-PID cgroup attachment, the host inspects a stable pidfd and `/proc/<pid>/stat` birth ticks. Missing kernel membership, dead PIDFD, PID reuse symptoms, early worker exit and unreadable process identity stop the release. **This is not an atomic PID-based kernel transfer, nor a security proof against hostile workers.**
- **Final cleanup:** After fixed worker completion, attempt `cgroup.kill`, check `cgroup.events populated=0` and empty membership; otherwise deny success. A failed cleanup cannot be mistaken for containment acceptance.

## Local verification — Python 3.13.5, Linux x86-64

**17/17 new P46R3 focused tests PASS**, including two real alpha-worker fixed-gate subprocess runs and denied fake/ro scope, stale worker, process exit and inherited-writer controls.

Additional earlier focused suites PASS in the reconstructed checkout: P46R1 (7), P46R2 (12), alpha-native (14), native fault probe (4), P51 host witness (16), P47 evidence checks (19), P49 negative process-group controls (2), P46 archive audit (6), P48 Linux reference lifecycle (4). **Total 101/101 scoped tests passed**, individually logged in the downloadable source-and-evidence archive. This is **not** one full fresh checkout test run, nor the historical original P46 764-test campaign.

The observed `cgroup2` mount is **read-only** (`/sys/fs/cgroup` reports `ro,nosuid,nodev,noexec,relatime,nsdelegate`). `preflight` reports `CGROUP2_READ_ONLY` and verified zero fixture spawns. This is a **successful denial test**. It is **not a successful kernel-enforced descendant kill test**. P46R2's actual `setsid` descendant survives process-group cancellation, and no writable delegated cgroup test is yet available.

The local working tree had P51-only host witness and archive auditor sources not previously checked in. Those P51 modules and their extra tests are in the exported P46R3 checkpoint but are **not claimed to be part of this pull request**, whose scope is strictly the three cgroup gate modules and 17 new tests.

## Security gate

**Native module admission: DENIED. Kernel-enforced hostile descendant containment: UNVERIFIED. Lu host integration: NOT TESTED. Windows worker security: NOT TESTED.**

Remaining acceptance work:
1. Use an independently configured writable, trusted **delegated cgroup-v2** test host; launch a child that calls `setsid` and a hostile child that clears parent-death protection; prove host-only cgroup `kill` eliminates and reaps the entire hierarchy.
2. Prevent workers from migrating out of the cgroup or modifying the delegated hierarchy. Introduce appropriately isolated OS identity/mount namespace and deny secret/network access. Verify resource caps and crash recovery.
3. Test the same fixed worker through an actual isolated Lu-Linux development host once the Lu build and tool bridge are available, with the *host* independently asserting task lineage/permissions. Cognitum's standalone test result cannot substitute for this.
4. Independently validate Windows Job Object/restricted-token containment and recover/reconcile the missing original P46 archive if it becomes accessible.

The fixture does not duplicate Lu's general JSON parser/repair, native orchestrator, authorization service, or Protobuf transport ownership.
