# Cognitum P46R1 — Reconstructed Linux fixed-worker parent-lifetime protection

**Date:** 2026-10-31  
**Status:** Newly rebuilt P46 behavior, **not the original lost P46 source/archive**.  
**Scope:** Cognitum only; local-first development. GitHub is a repository and documentation record. No Lu source changes.

## Recovery result

The original archive was called `Cognitum_P46_Parent_Lifetime_Fault_Testing_Full_Source.zip`, previously written under `/workspace/scratch/f4c001a94ade/`. It was not found in the accessible local runtime, user Library, or Cognitum GitHub repository. Historical P46 reported 764 passed, one skipped, 43 worker tests and three native Rust policy tests. **None of those original P46 totals can currently be reproduced or attributed to P46R1.**

P45 covered process-group cleanup and nonblocking I/O; P47–P51 later added independent safety tests, witnessed worker fault checks, cgroup2 admission contracts and archive auditing. Process groups and parent-death signals do not prevent all descendant breakaway. P51's cgroup v2 containment could not be executed here because the kernel hierarchy is read-only.

## New P46R1 behavior

`cognitum/fixed_parent_lifetime.py` is a fixed Linux-only experimental wrapper targeting **only** `cognitum.alpha_native_worker`.

1. It receives an expected supervising PID and two inherited descriptors (one readiness and one release).
2. It installs Linux `prctl(PR_SET_PDEATHSIG, SIGKILL)` before signaling readiness.
3. It verifies the actual parent PID immediately after registration, denying a supervisor-death race before `prctl` can take effect.
4. It signals readiness with `R`, then requires an exact `G` release token.
5. It checks its parent again, and only then invokes `execv` with a fixed native worker module. No model-provided path, command or authorization is accepted.
6. On ordinary Linux non-setuid `exec`, the parent-death signal remains active; the worker is killed if its parent dies.

**Security limitations:** this is not PID-authenticated host authority, malicious Python isolation, descendant containment, cgroup enforcement, Windows Job Objects, Lu conversation authorization or production-ready admission. A hostile worker could clear its parent-death setting or create independent descendants. Keep native CE admission default denied.

## Locally reproduced test evidence

Linux Python 3.13.5, fixed alpha worker and existing Protobuf requests:

- **7/7 new P46R1 tests passed:** real typed calculator execution, invalid identity, invalid release token, wrong parent ID, supervisor death before readiness, after guard registration/before release, and during a blocked real-worker input frame.
- **14/14 existing alpha-native tests passed** independently.
- **4/4 existing actual-worker fault-matrix tests passed** independently.
- Source SHA-256: `56e4c819890223f7a064e95af8a57afe2f1dac749c4d056d22451e25c675d52e`.
- Test SHA-256: `2e58e46bda620707857d1b84ebc1064c65c2f2ceb6ae108789b34b21b66a6591`.

A broader test-discovery attempt against the partial reconstructed checkout had unrelated missing imports and timed out during an older reference fixture. It was stopped and is **not** a passing full-suite result. The original P46 archive and its historical 764-test source are unrecovered.

Run from the full Cognitum checkout:

```bash
python -m unittest discover -s tests -p 'test_fixed_parent_lifetime.py' -v
python -m unittest discover -s tests -p 'test_alpha_native.py' -v
python -m unittest discover -s tests -p 'test_alpha_native_fault_probe.py' -v
```

## Next gates

Rebuild P46's remaining independent worker/fault tests, including hostile descendants, signal clearing and inherited handles. Combine with the P51 cgroup-before-release gate and test against a **writable, correctly delegated** kernel cgroup2 hierarchy; absent OS enforcement must still fail closed. Independently measure source and process status; validate Windows process-tree containment and Lu trusted host permissions separately. Recover the original archive if possible and reconcile it by hash rather than assuming equivalent source.

**Disposition:** P46 parent-lifetime *behavior partially recreated and tested*. Historical P46 restoration, full worker qualification, independent OS containment, Windows, and production authorization remain open.
