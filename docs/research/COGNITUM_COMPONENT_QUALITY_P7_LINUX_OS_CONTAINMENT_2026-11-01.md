# Cognitum P7 — Linux OS-enforced namespace worker containment

**Date:** November 1, 2026  
**Branch:** `cognitum/component-quality-p7-linux-os-containment-20261101` (from P6)  
**Status:** Linux verified **for reviewed, deterministic, effect-free built-in operations only**. **NOT production-certified arbitrary plugin isolation.**  
**Product:** ONE independent Cognitum distribution. **No Lu integration or code changes.**

## Engineering outcome

The optional `LinuxNamespaceExecutor` runs reviewed Cognitum operations in a new Linux user, PID, mount, IPC, UTS and network namespace. A private 24 MiB tmpfs root is created *after* namespace creation, with only `/usr`, `/lib`, `/lib64`, the host-selected Python runtime prefix and the current installed `cognitum` package bind-mounted **read-only**. The host user home, `/etc`, `/mnt`, `/proc`, and network stack are not mounted/exposed. `setpriv` drops effective/permitted/inheritable capabilities and sets `no_new_privs`, then `prlimit` sets strict CPU, virtual address-space, file-descriptor, core-dump, and file-size limits. A separate network namespace prevents outbound connections. Unshare's `--kill-child` with PID namespace and a parent process-group kill terminate workers and descendants on timeout/recovery, including test children in separate sessions.

The host continues to validate/authorize every Cognitum request first. This is an optional `Runtime(..., sandbox_executor=LinuxNamespaceExecutor())` mode. It uses an **exact built-in factory allowlist** (Calculator and Cognitum Specialists for HDC/KAN/SSM) and size-bounded typed JSON. Invalid scopes, unsupported factories, missing namespace support, wrong/cancelled workers, malformed/overlong frames and unauthorized KAN checkpoints **fail closed**; they never fall back to legacy uncontained execution. The trusted host must supply an approved KAN SHA-256 separately; caller input cannot self-approve a checkpoint. The existing P6 global eight-cold-worker admission budget applies to sandbox execution.

**The normal Cognitum execution path stays unchanged by default.** The existing P5/P6 1-minimum, **2-default**, 4-maximum prewarmed pool is not sandboxed. The runtime explicitly **rejects combining this legacy warm pool with the sandbox executor**, and rejects P6 batching in sandbox mode. Moving the warm workers *inside* the namespace must be separately implemented and tested.

## P7 Linux kernel acceptance

- **27/27 dedicated namespace tests passed.** Positive arithmetic, HDC, SSM, KAN with explicit trusted checkpoint pin; negative spoofed provider, omitted checkpoint pin, malformed/overlarge frame, denied user context, missing launcher, resource exhaustion, unsandboxed batch/warm bypass, timeouts, output floods, environment leakage and child-process cleanup.
- A test child in a **different process session was positively observed while running**, then proved absent after sandbox PID1 teardown. This is stronger than only checking an empty process list after a failed spawn.
- Inside-worker kernel checks confirmed **no capabilities**, `no_new_privs`, read-only code and system libraries, no visible host user home or `/etc`, and network unreachable. Unprivileged Linux namespaces were actually available on the local test host.
- Verified `RLIMIT_AS=1,073,741,824`, `RLIMIT_CPU=8s`, `RLIMIT_NOFILE=128`, `RLIMIT_FSIZE=8,388,608`, `RLIMIT_CORE=0` inside the worker.

## Regressions against the staged P6 source

| Check | Result |
|---|---:|
| P7 namespace-specific | 27 passed |
| P2–P6 worker, batching, trace, HDC/KAN/SSM and boundary regressions | 150 passed; 15 subtests |
| Selected C05/C07/C10/C11/C12/C13/C14 cross-domain suite | 187 passed; 69 subtests |
| Selected C15 spatial suite | 74 passed; 5 subtests, 1 deselected |
| **Completed selected total** | **438 passed; 89 subtests; 1 explicit deselection** |

One inherited historical test (`test_c15_scene_reference.py::SpatialSceneReferenceTests::test_defers_current_llm_gate_not_faked`) checks for `docs/decisions/2026-10-28-C14-G15-real-LLM-gate-deferred.md`, **missing from the staged historical snapshot**. An unqualified initial spatial run correctly FAILED that assertion. The source does not supply that document, so the test was **not faked**; the second run deselected precisely that test and passed 74/74 remaining. The combined long-running pool regression was interrupted by the execution limit; only independently completed suites count above.

**This is a selected reconstructed P6 source acceptance; not a complete clean checkout of the newest canonical branch and not an independent Windows run.**

## Linux request latency (matched local arithmetic, n=12 each)

| Backend | Median | Nearest-rank p95 (small n) |
|---|---:|---:|
| Legacy `multiprocessing.spawn` disposable Python worker | 560.0815 ms | 607.986 ms |
| P7 fresh Linux namespace process | 72.9435 ms | 76.653 ms |

The **~7.68×** local speedup primarily compares different worker-launch implementations. It does **not** prove that namespaces make Python intrinsically faster. The previously measured ~5 ms ready-standby latency is not maintained in sandbox mode yet; P7 workers are intentionally cold/one-shot. Model inference, LLM tool selection, queueing, Windows and real science workloads are outside this timing profile.

## Single-wheel packaging

One `cognitum_core-0.1.0-py3-none-any.whl` is built using the existing packaging configuration and a new included `sandbox_entry_linux.sh` package resource. Clean installation into a fresh prefix completed arithmetic, SSM and HDC through the Linux namespace backend and confirmed KAN remains unavailable without the host pin. This is **not** a separately distributed Cognitum edition. The Linux package requires reviewed `unshare`, `mount`, `chroot`, `setpriv`, `prlimit` and a namespace-capable kernel; missing prerequisites fail closed rather than invoking an unsandboxed worker.

## Open production/security gates

1. **cgroup-v2 enforcement OPEN:** the developer host mounts `/sys/fs/cgroup` read-only. PIDs and memory cgroup quotas, reliable process-count anti-fork-bomb protection and external-worker resource hierarchy are not proven. RLIMIT_AS is a virtual-memory limit, not a complete cgroup memory controller replacement.
2. **Seccomp/Landlock review OPEN:** namespaces + mount permissions + dropped capabilities improve confinement but are not a general-purpose hostile-code sandbox. No arbitrary third-party Python/plugin code is approved.
3. **Windows OPEN:** independent restricted-token/AppContainer + Job Object `KILL_ON_JOB_CLOSE` and descendant tests must be implemented and observed on installed Windows; Linux namespace success cannot be carried over.
4. **Sandbox-native warm pool OPEN:** honor the accepted 1-minimum, 2-default, 4-maximum process-wide policy *inside the containment boundary*, with readiness handshakes, recovery, measured idle RSS and uncontained bypass prevention.
5. **Full canonical checkout OPEN:** build/qualify the complete most recent unified Cognitum source at one reviewed SHA. Current 438-pass figure is a carefully selected reconstructed P6 source run.
6. **Real scientific and LLM trials OPEN:** unseen HDC/KAN/SSM effectiveness and C14 causal-interval calibration require their own scientific benchmarks; operating-system containment does not certify their outputs.
7. **Supply-chain/runtime portability OPEN:** runtime path is host-selected rather than hard-coded, but host-installed interpreter/binaries and import dependency trees need pinned/hash-audited packaging and tested Linux distributions. No production installation promise.

## Files

- `cognitum/sandbox_linux.py`: parent restricted launcher and bounded JSON IPC.
- `cognitum/sandbox_child.py`: allowlisted one-shot child and kernel negative-test probes.
- `cognitum/sandbox_entry_linux.sh`: namespace-private readonly mounts, capability and resource limits.
- `cognitum/runtime.py`: explicit opt-in containment, no warm/batch bypass.
- `tests/test_linux_namespace_p7.py`: real Linux kernel adversarial and functional suite.
- `tools/benchmark_linux_namespace_p7.py`: matched worker latency profile.
- `pyproject.toml`: one package includes shell launcher.

## Release decision

**P7 Linux built-in isolated-worker research gate: PASS on this host.**  
**General OS containment, warm worker containment, Windows, cgroups and production promotion: OPEN.**
