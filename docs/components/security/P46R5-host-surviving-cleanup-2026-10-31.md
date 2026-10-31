# Cognitum P46R5 — Host-surviving fixed-worker cgroup cleanup (experimental)

**Date:** 2026-10-31  
**Implementation:** Linux-only, fixed-function Cognitum alpha-native worker  
**Production admission:** DENIED. Neither Cognitum nor Lu is allowed to treat these tests as arbitrary-tool sandbox certification.

## Goal and observed gap

P46R4 arms Linux `PR_SET_PDEATHSIG` on the direct fixed worker. This is useful but cannot kill malicious descendants that clear the signal, escape process groups, or retain a pipe writer. If the launching host is killed, its `finally` block cannot call `cgroup.kill`. P46R5 introduces a separate out-of-worker-cgroup **watchkeeper** which does not depend on the host remaining alive to perform cleanup.

The Linux kernel documents `cgroup.kill` as killing members of a cgroup and all descendant cgroups, including concurrent forks; `cgroup.events` `populated=0` describes an empty subtree. This requires a writable, delegated cgroup v2 hierarchy and privileges preventing a worker from migrating itself out. References: https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html and https://github.com/systemd/systemd/blob/main/docs/CGROUP_DELEGATION.md.

## Implementation details

- `cognitum/host_surviving_watchkeeper.py`: fixed watchkeeper entrypoint, separate process session, Linux `pidfd_open(parent)` tracking, bounded lease time, inherited **directory FDs** for the kernel cgroup and private evidence directory, `fstatfs` verification of genuine cgroup2, test that watchkeeper is not a direct member of the worker cgroup, pre-open check that `cgroup.kill` can be written, recursive `cgroup.kill` after host death/lease closure, poll `cgroup.events` `populated=0`, and write an atomic, non-overwriting `0600` receipt with `fsync`.
- `cognitum/host_survivor_arm.py`: trusted host-only bootstrap. Starts watchkeeper **before** any worker exists, sends it only previously opened FDs, waits for its ready byte, and returns an armed lease handle only on success. Verifies JSON receipts with duplicate-key rejection, strict status and flag checks, exact job ID, OS PID, parent PID, kernel cgroup device/inode identity, and false production-attestation fields.
- `cognitum/cgroup2_fixed_runner.py`: experimental fixed-worker runner now requires a watchkeeper before launch, releases its worker only after attachment/identity checks, and cannot report success until the watchkeeper has both written `cgroup.kill` and observed an empty subtree. It rejects a watchkeeper that has exited after READY but before fixed-worker release. On errors the trusted host closes the lease, waits for watchdog cleanup, then attempts direct emergency cleanup if necessary. A missing watchkeeper or receipt remains a denial.
- There is no general JSON repair, dynamic executable, model-selected path, MCP server, Lu conversation permission, external workspace admission, or user-admin elevation.

## Local verification — exact accounting

Environment: Linux, Python 3.13.5, `/sys/fs/cgroup` cgroup v2 mounted **read-only**. It **cannot** run a real writable delegated cgroup cleanup proof.

**New P46R5 focused suites: 17/17 tests passed** (13 watchkeeper tests + 4 gate-integration tests). A Linux subprocess acting as a trusted watchkeeper outlived a supervisor killed with `SIGKILL` **while a separate helper retained the lease writer**. The watcher detected `HOST_PIDFD_EXITED`, performed a *simulated* cgroup.kill write in a disposable file fixture, and the test explicitly reaped its processes. Both the process survivability and kernel-pidfd detection are real; the cgroup kill in that test is **simulated**. Four additional repeated runs of the final 13-test suite passed.

**Existing focused regressions separately completed: 114/114**:

| Suite | Passed |
|---|---:|
| P46R4 parent-death guard | 7 |
| P46R3 cgroup admission | 17 |
| P46R1 reconstructed guard | 7 |
| P46R2 negative matrix | 12 |
| Native alpha Protobuf worker | 14 |
| Actual native worker fault probe | 4 |
| P51 host observation | 16 |
| P46 archive auditor | 6 |
| P47 lifecycle evidence | 19 |
| P49 breakaway negative controls | 2 |
| P48 native reference lifecycle | 4 |
| Calculator unit tests | 6 |
| **Total** | **114** |

**Total scoped passing assertions: 131/131 across separate completed suites.** Do not represent this as a fresh complete repository-wide run or a reprise of the lost historical P46 campaign.

The partial reconstructed checkout cannot import `cognitum.runtime` in the unrelated `test_protobuf_codec.py` and `test_capability_results.py` modules. Those two import errors are recorded separately, not scored as P46R5 containment failures. One earlier batched test command timed out; all suites involved in the 130 total were rerun successfully in independently completed commands.

## Security disposition and next acceptance gates

**What passed:** watchdog process survives killing its Python launching parent in this local test; pidfd catches parent death even when the pipe cannot close; kernel cgroup filesystem validation rejects plain directories; read-only cgroup is rejected **before worker spawn**; mock-verified sequencing and strict host receipt rejection work; P46R1–R4 and older evidence tests stay green.

**What remains unverified:** actual `cgroup.kill` of a live escaped descendant under a writable delegated kernel cgroup; watchkeeper isolation against malicious same-UID workers or cgroup migration; systemd service/desktop session killing an entire app unit (the watchdog must live in a **separately managed unit** for that case); watchdog **itself** crashing or being killed; reboot recovery; multiple scopes/parallel loads; durable authenticated out-of-process receipts; Windows Job Objects/AppContainer; Lu host authorization, cancellation, and effect journaling. A new process session alone does NOT escape a systemd service cgroup.

The local watchkeeper has a **60-second fixed-fixture lifetime** and is not suitable for a long-running production cognitive task. A future trusted host must provide durable private state, an independent service manager owning the reaper, and restricted worker credentials/mounts. Restart reconciliation must detect any nonempty scope abandoned by the watchkeeper, and native CE admission remains default denied until those gates pass.

The original P46 source archive remains missing. This checkpoint is **P46R5**, newly developed behavior, not recovered P46 source or the historical 764-pass campaign.
