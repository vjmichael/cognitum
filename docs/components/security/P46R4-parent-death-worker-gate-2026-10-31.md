# Cognitum P46R4 — Parent-death guard integrated with cgroup release barrier

**Date:** 2026-10-31  
**Scope:** Cognitum isolated Linux test checkout, **not the Lu-Linux desktop development build**. No Lu code changed. GitHub is source control/documentation only.

## Defect and fix

P46R3 required exact `G` + EOF release and a membership/identity check before launching the fixed `cognitum.alpha_native_worker`, but the gated worker lacked Linux parent-death signaling. A supervisor could die after release while an independent process retained the worker's input-pipe writer, leaving the real worker blocked and alive.

P46R4 adds `PR_SET_PDEATHSIG=SIGKILL` to `cognitum/gated_alpha_worker.py` **before** the release-barrier read. It takes an explicit `expected_parent_pid`, rechecks `getppid()` immediately after registering the signal and again immediately before the fixed executable `execv`. Missing PID, wrong parent, failed registration and malformed release fail without executing the worker.

The fixed `cognitum/cgroup2_fixed_runner.py` launcher now provides its own PID to the guard. Existing P46R3 test callsites were updated to the two-argument interface. The separate P51 host-witness tests in the *local reconstruction* were also updated, but those P51 witness files are **not part of this PR** and may still be absent from repository `main`.

## Direct local OS observations

- Killing a supervisor before token release terminates or prevents its fixed child from executing.
- Killing the supervisor after `exec`, with a real Protobuf worker deliberately blocked on incomplete input, terminates it by SIGKILL and it is reaped.
- A second process that inherits and retains a copy of the input-pipe writer survives the supervisor death, yet the guarded real worker **still dies by SIGKILL**, demonstrating this protection does not depend on stdin EOF. The extra holder is explicitly terminated/reaped using a stable `pidfd`.
- Wrong expected parent PID is rejected before worker execution.
- Actual kernel cgroup v2 preflight reports `CGROUP2_READ_ONLY` here and refuses to launch any worker. **No successful cgroup-enforced descendant containment was performed.**

## Tested evidence

Python 3.13.5 Linux x86-64:

- **7/7 new P46R4 tests passed**, and the seven-test suite passed again in **three independent repeats**.
- **17/17 P46R3 tests, 7/7 P46R1, 12/12 P46R2, 14/14 alpha-native, 4/4 actual worker fault probes** passed.
- **16/16 P51 host witness (local-only files), 6/6 P46 archive audit, 19/19 P47 evidence, 2/2 P49 breakaway, 4/4 P48 reference** passed.
- Total: **108/108 targeted tests in 11 named suites**; this is **not** a complete fresh-checkout repository-wide test run. All 5 locally changed Python files compiled. The original P46 764-test checkpoint remains unrecovered.
- Tested source SHA-256: guard `b47acbd12d0c25e49cd3bafd1b961df1c971160213ad6029971b94b9b1b00772`, runner `dca75d09970e930d0d346677eba1a143fbcd6310e6ca6a064e1eb2730279259a`, P46R3 tests `8c61459446cdc47bbe803b23623b62fdd207fe99516c2650345d905cbd5c1a40`, new P46R4 tests `2570eb3fe52d6e1059b320af672264e2333ef4cb0938decf3a94706da2f151e2`.
- Full detailed local test logs, source, hashes, and reproducibility caveats are in the P46R4 checkpoint ZIP.

## Explicit security nonacceptance

Linux parent-death signaling is a *cooperative process-lifetime safety mechanism*, not a security boundary against a hostile worker that can clear the signal, spawn `setsid` breakaway descendants, change its execution credentials, or migrate from an insufficiently protected cgroup.

Even a writable cgroup will not self-kill its members when an unrelated supervisor crashes: a **separately surviving trusted cleanup owner/service** must trigger and verify `cgroup.kill`, or a kernel/service-manager lifecycle mechanism must provide the equivalent. Kernel containment, trusted Lu conversation authorization, Windows restricted tokens/Job Objects, network/file confinement and independent attestation remain unverified. Untrusted worker admission remains **DENIED**.

## Next gate

Run the actual cgroup attach-before-release + `setsid` breakaway descendant + cgroup kill/reap sequence in an appropriately delegated, writable Linux cgroup hierarchy, with independently owned cleanup and host evidence. Only after independent kernel verification should isolated Lu-Linux integration be tested.
