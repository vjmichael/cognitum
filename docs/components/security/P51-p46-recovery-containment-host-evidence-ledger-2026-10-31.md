# Cognitum P51 — P46 recovery ledger, cgroup v2 gate, host evidence

**Date:** 2026-10-31  
**Engineering policy:** Local development/testing first. GitHub is a repository and milestone record, **not** the development hub. No Lu source or general JSON repair tools were modified.

## P46 recovery status: NOT RECOVERED

Earlier Cognitum conversation identified the original archive as `Cognitum_P46_Parent_Lifetime_Fault_Testing_Full_Source.zip`, formerly under the ephemeral `/workspace/scratch/f4c001a94ade/` working directory. That path is not mounted in the current runtime. Searches of the current local workspace, accessible Library/Checkpoints, exact archive names, and Cognitum repo/PR/branches did **not** locate its original bytes. No original SHA-256 or manifest is available to authenticate. Historical P46 figures (764 passed, 1 skipped, plus three native policy tests) **were not reproduced**.

The current, separately committed P50 `cognitum.alpha_native_worker` source is verified against Git blob `9c6eb70dcc2f39a77e6f6b9143189e8d727df8b5` and SHA-256 `f547294522d0b4416bdce76010ca273571ff4820f53f2e2d377ca1fcb1f9c507`. That is **not** the P46 full source checkpoint.

## P51 local source checkpoint and reproducible tests

P51 local source comprises five Cognitum modules (`cgroup2_contract.py`, `cgroup2_fixed_runner.py`, `gated_alpha_worker.py`, `host_native_witness.py`, `p46_archive_audit.py`), three CLI tools, two regression suites, and a detailed local report. The source-only archive is a staged, unmerged local artifact with SHA-256:

`97a55faa20c066701e45e2d5e472292330d8aafbb9e768e39ce168bd283db841`

The local evidence ZIP has SHA-256:

`c396920e7b2bef5f2a30d788dc243ec99b66b7b51a736eb8bafcb0c410cb8a77`

These are handoff hashes, **not** cryptographic identity or signing attestations. The P51 implementation remains in the local checkpoint package until its full source is reconciled into the repository. This GitHub entry records the tested status rather than claiming source files were already merged.

- On Linux Python 3.13.5: **61/61** selected native/P47–P51 tests passed (including P51 witness, cgroup denials, and archive auditor).
- Separately: **4/4** P48 native reference tests passed. Total **65/65 focused tests**; not a full-repository count.
- Broad test discovery on the partial reconstructed checkout **did not complete** and encountered missing unrelated modules. No full-repo pass is claimed.

## Descendant containment: gate built, actual cgroup enforcement NOT VERIFIED

P49 previously demonstrated that `setsid()` can escape a POSIX process-group `killpg`. P51 therefore provides an experimental **host-owned cgroup v2 fixture** for a hard-coded alpha calculator worker. It verifies the actual mount and delegation, attaches a bootstrap PID to the scope **before** an explicit one-byte launch release, and uses kernel `cgroup.kill` plus `cgroup.events populated=0` and reaping for cleanup.

**Actual environment result:** cgroup2 exists, but `/sys/fs/cgroup` is read-only; preflight returns `CGROUP2_READ_ONLY` and refuses to spawn. Fake writable directories, symlink aliases, invalid frames, and failed handshake tests are likewise rejected. No live writable-cgroup, breakaway-survival prevention, or hostile-child containment has been demonstrated by P51.

The launch release byte is only synchronization, **not authorization**. Even a writable cgroup test would not by itself establish a complete untrusted-code sandbox; worker UID, cgroup migration denial, mount/network namespace restrictions, seccomp, credentials, and host-granted effects remain separate requirements.

## Host-generated observation, not host attestation

The separate native witness runs the **actual fixed P50 worker** with (1) valid typed-Protobuf rational output of 1/2 and (2) malformed-frame rejection. It measures independent host PID fds, `/proc` PID start ticks, wait/reaping, source SHA-256 and input/output digests. The structured bounded verifier rejects tampering, duplicate fields, missing events and forged isolation claims.

Local verdict: `OBSERVED_UNATTESTED`. Its record marks `security_admission=DENIED` and `native_containment_verified=false`. A compromised or malicious host could fabricate and rehash a receipt, so this is **not independently authenticated evidence** or authority for Lu worker execution.

## Next required acceptance

Recover P46 original archive from the prior scratch/download or an independently verifiable original copy; audit paths, independently verify a source manifest/hash, reconcile changes and reproduce P46 tests. On a separate Linux host with **writable, properly delegated cgroup v2**, run the actual kernel attachment and hostile descendant breakaway test, then verify host observations and cleanup independently. Windows Job Object/AppContainer and Lu authority remain separate hard gates.

**Current security disposition: DEFAULT DENY for untrusted Cognitum CE workers.** No Lu integration or production certification is implied.
