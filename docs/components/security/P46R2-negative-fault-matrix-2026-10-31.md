# Cognitum P46R2 — Reconstructed remaining Linux lifetime fault cases

**Date:** 2026-10-31
**Disposition:** Negative controls reproduced locally; production native containment remains **DENIED**.
**Source lineage:** Fresh reconstruction, not the missing original P46 checkpoint or its historical 764-test suite.

## What was implemented

New test-only Cognitum module: cognitum/p46r2_fault_matrix.py.
New regression suite: tests/test_p46r2_fault_matrix.py.

Fixed disposable Linux fixtures demonstrate three real failure modes:

1. **Cleared parent-death signal.** A guard installs SIGKILL as its Linux parent-death signal, then deliberately clears it and checks the setting. When the supervisor is killed, the child survives.
2. **New-session descendant.** The parent-death-protected guard spawns a new-session descendant. Supervisor death kills the guard but not the escaped descendant.
3. **Retained input pipe writer.** The actual fixed Protobuf worker is blocked on an incomplete frame, and a second process keeps a writer handle open. Supervisor death does not deliver EOF; the worker survives.

For each case, the local test observer obtains Linux pidfds before supervisor termination, reads process start ticks from /proc, makes observations, explicitly kills survivors through their existing pidfds, and reaps every observed child as a child subreaper. Unknown fixture names do not spawn anything. No general model-created commands, paths or workloads are accepted.

A strict structural receipt verifier rejects false sandbox/authorization claims, wrong source hashes, duplicate JSON keys, omitted/reordered cases, mismatched observations and absent cleanup. The only favorable verdict is OBSERVED_NEGATIVE_CONTROLS_UNATTESTED: these *failures of containment* were observed and cleaned up, **not** that OS containment is secure. The host observer is not cryptographically attested.

## Local verification

Linux / Python 3.13.5:
- New P46R2 fault and evidence suite: **12/12 passed**
- P46R1 parent-death guard: **7/7 passed**
- Existing alpha native worker: **14/14 passed**
- P50 actual worker fault probe: **4/4 passed**
- P51 host evidence/cgroup gate: **16/16 passed**
- P51 archive audit: **6/6 passed**
- P47 structural evidence: **19/19 passed**
- P49 breakaway controls: **2/2 passed**
- P48 reference lifecycle: **4/4 passed**
- Calculator: **6/6 passed**

**Total: 90 completed, passing targeted tests.** Three additional direct full P46R2 matrix runs each reproduced all three expected survival failures with cleanup. Python compileall succeeded.

The optional broader reconstructed-checkout modules test_protobuf_codec and test_capability_results could not import cognitum.runtime, which is missing from this partial local checkout. These attempted modules are *not* counted as passing or as P46R2 regressions. This was not a full-repository test pass. The full dated local report, repeat receipts, test logs and SHA-256 file manifest are in the downloadable P46R2 checkpoint.

## Not accepted

- Original P46 source or historical 764-test campaign: NOT RECOVERED.
- Linux kernel cgroup v2 kill and descendant containment: NOT VERIFIED in this environment; /sys/fs/cgroup is read-only and the existing P51 cgroup gate correctly refuses launch.
- OS isolation against malicious plugins, Lu conversation authority, Windows Job Objects/AppContainer/LPAC, cryptographic evidence attestation: NOT VERIFIED.
- Native Cognitum CE admission: DENIED.

PDEATHSIG, killpg and EOF alone must never be treated as a security boundary. Next gate: fixed worker test under correctly delegated **writable** cgroup v2 with launch barrier, guarded cgroup mount, cgroup.kill, kernel-verified emptiness, and actual breakaway and cleared-signal descendant tests. Native host evidence signing/verification and Windows containment require independent gates. GitHub remains the repository and documentation ledger, not the development environment.

## Reproduce

Run from a full Cognitum checkout containing P46R1 and P51 contracts:

    python -m unittest discover -s tests -p 'test_p46r2_fault_matrix.py' -v
    python -m cognitum.p46r2_fault_matrix
