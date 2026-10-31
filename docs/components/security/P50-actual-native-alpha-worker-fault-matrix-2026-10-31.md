# Cognitum P50 — Actual alpha-native worker fault matrix

**Date:** October 31, 2026  
**Development:** Local first; GitHub is only the repository and documentation ledger. No Lu source changes.

## Scope and provenance

P47-P49 exercised structural receipts and fixed reference subprocesses. P50 exercises the **existing `cognitum.alpha_native_worker` executable** with its real installed Protobuf and rational-calculator dependencies, directly in fresh local subprocesses. It does not reconstruct or import the separately missing P46 checkpoint. Cognitum remains an independent cognitive component; no general JSON repair or Lu authority services are duplicated here.

The exact existing worker on current Cognitum GitHub `main` has Git blob SHA-1 `9c6eb70dcc2f39a77e6f6b9143189e8d727df8b5` and SHA-256 `f547294522d0b4416bdce76010ca273571ff4820f53f2e2d377ca1fcb1f9c507`. P50 measures and reports both values. SHA-1 Git identity is for cross-checking source revisions, **not** a signed-code certificate.

## Observations from real worker executable

1. `actual-valid-protobuf`: a bounded Protobuf `calc.rational` call computes exactly `1/2`, with `lu_integrated=false` and `os_isolation_verified=false`.
2. `actual-oversize-frame`: worker rejects a frame declared above `MAX_FRAME` with exit code 2.
3. `actual-truncated-frame`: worker rejects an incomplete body with exit code 2.
4. `actual-extra-byte`: worker rejects a frame with an extra trailing byte with exit code 2.
5. `actual-disallowed-operation`: direct worker rejects unsupported `shell.run` with exit code 2.
6. `actual-blocked-input-cancel`: worker is observed waiting for a partially transmitted frame, receives SIGKILL to its private test process group, and is reaped with signal-exit code -9.
7. `actual-supervisor-death-eof`: an experimental parent sends an incomplete frame; when parent is SIGKILLed, its last pipe write handle closes. The **actual worker exits due to EOF with code 2** and is adopted/reaped by a Linux child subreaper. Stable PID file descriptors are used in abnormal cleanup paths.

No test sends model-produced commands to a production host. The runner explicitly reports **no authenticated Lu admission**. Direct worker execution does not bypass Lu approval in a real deployment, nor is it a trusted supervisor by itself.

## Local verification and accounting

- Linux Python 3.13.5, `google.protobuf` 6.33.6.
- Existing actual alpha-native tests: **14 passed**.
- P50 new tests: **4 passed** (all seven cases; exact worker source; fail-closed exception injection; typed assurances stay false).
- P47/P48/P49 prior lifecycle suite: **25 passed** in a separate full focused run against reconstructed local files.
- Combined P50 + existing alpha-native tests: **18 passed** in one run.
- A broad `unittest discover` over a **partial reconstructed checkout** did not complete and reported missing unrelated modules (`cognitum.runtime` etc.). This was not a valid full-repository run and must not be recorded as a passing global suite. It does not override the individually completed P50 and lifecycle focused runs.
- The original P46 archive remains unavailable in this active environment; its previously reported 764 passes/1 skip were *not* reproduced here.

Run from a complete checked-out Cognitum repository:

```shell
python -m unittest discover -s tests -p 'test_alpha_native_fault_probe.py' -v
python -m unittest discover -s tests -p 'test_alpha_native.py' -v
python -m cognitum.alpha_native_fault_probe > p50-local-observations.json
```

## Limits and next gate

This checks the fixed-function calculator worker's protocol, EOF, signal cancellation and reaping. It does **not** establish process-tree containment for arbitrary descendants, cgroup/namespace isolation, Windows AppContainer/Job Objects, network/credential denial, adversarial Python code execution, trusted host identity, cryptographic evidence or full Lu integration.

The worker has no explicit Linux parent-death signal: the observed parent-crash recovery depends on closure of the input pipe. Inherited/duplicated writer handles could change the observation, and the worker cannot rely on EOF as an unrestricted execution sandbox.

Next: recover P46's full source checkpoint and rerun it against the real worker; separately develop a trusted, OS-enforced process-tree supervisor in an isolated host fixture, with breakaway negative tests and independently authenticated evidence. Keep native CE admission default denied until all relevant host, OS, Windows and Lu security gates have been verified.
