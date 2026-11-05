# Cognitum CH-C14-35 engineering report — independent proof witness and storage-fault recovery

**Dated:** 2026-11-02 (America/Phoenix)  
**Disposition:** Scoped Linux trust-authority acceptance; no production release.

## Goal and baseline

Build a genuinely separate Linux process/UID trust authority above CH34,
without adopting a journal-owned SHA as independent authentication. Original
CH23/CH29 input, dual, protocol, CH32 head and CH33 checkpoint proof identity
remain frozen. The 15-case CH34 audit is preserved and not misrepresented as a
CH35 15-case independent service evaluation.

## Implementation

1. `trust35.py` protects a private signer root (0700 owner UID and no shared
   keys), signs frozen original-CH23 receipt bodies with Ed25519 using domain
   separation, and commits immutable chained revisions before atomically
   replacing HEAD and fsyncing its parent directory.
2. `service35.py` is a single-process AF_UNIX service admitting only an exact
   frozen case identifier, with `SO_PEERCRED` OS account filtering. The writer
   cannot provide a proof, path or attestation to sign. A private, separate
   `trusted_tip.json` must match the ledger on every operation.
3. The authority copies the untrusted journal and archive into private scratch,
   compares the checkpoint to a signer-pinned byte-level digest, loads original
   input/dual/protocol data under the signer-owned tree, runs full independent
   224-bit MPFR CH33 cold checkpoint recovery and archived-history replay, and
   compares the CH29 objective-gap proof receipt before signing an **unresolved**
   `NO_GO` witness. No signed global-optimality claims are possible in this v1.
4. Public signature verification requires an externally pinned key fingerprint
   **and** the last accepted signed tip to detect signature substitution or
   HEAD rollback. Interrupted HEAD advancement is quarantined, not silently
   recovered or adopted. No helper repins a candidate automatically.

## Measured evidence

| Test/gate | Result |
|---|---|
| Local signing/storage test methods | **12/12 passed** |
| ENOSPC, EIO, EDQUOT injection combinations | **27/27 passed** |
| Actual hard-exit injection points | **9/9 passed** |
| Real Linux kernel file-write rejection (`RLIMIT_FSIZE`) | **Passed, EFBIG** |
| Separate signer UID 65534 vs writer UID 1000 | **Passed** |
| Journal writer denied signer key reads and edits | **Passed** |
| Journal checkpoint tampering blocked before signing | **Passed** |
| Fresh MPFR verification of original `one_event_n80_i00` | **Passed, 127 nodes** |
| Independently replayed original historical frames | **6/6** |
| Ed25519 signed tip and public-key fingerprint audit | **Passed** |
| Duplicate signing of same case | **Refused** |
| Original CH23 objective-gap scientific release | **NO-GO** |
| Original cases rerun with CH35 signer | **1/15** |
| Hardware power loss, real disk-full ENOSPC, Windows | **Not tested** |

Original test case: `one_event_n80_i00`; pinned CH32 head
`ce92be481fcd868ea18d10eea2f4f54b018a5a107b912019c98e71fea8f92ada`;
CH33 checkpoint
`84429dae20d0315bda2f48a4e82908d515469863a70832ee8d56fc87746232b2`.
The tested new key fingerprint and public signature are recorded in
`independent_process_results.json`; `witness_public_key.pem` is **public**
verification material, never the secret. The 127-node MPFR replay and six
historical frames took 52.85 seconds wall time on the tested Linux host.

## Failure semantics

- Before a file mutation: no pending file, retry against unchanged trusted pin.
- After record temp/write/fsync, rename, or head temp/write/fsync: deny new
  signatures until incomplete/pending state is explicitly reconciled.
- After HEAD rename and before durable trusted-tip advance: the old externally
  trusted tip cannot validate the changed HEAD, and the candidate must remain
  quarantined until an independent fresh mathematical replay and authorized
  external re-pin. `recover()` reports the candidate but **does not adopt it**.
- All nine actual `os._exit(79)` injections intentionally leave artifacts on
  the filesystem as evidence. They do not simulate sudden power removal.

## Remaining gates

1. Run the signer against all remaining 14 original CH23 cases, including the
   three historically ambiguous zero-event cases, with independently frozen
   output hashes and signed receipts.
2. Enforce actual filesystem ENOSPC/EDQUOT with a disposable quota-limited
   filesystem, plus fsync failures returned by a storage fault shim.
3. Test independent witness replication/witness co-signing and an external
   append-only public trust anchor. Current signer account compromise or
   rollback of all independent pins is out of scope.
4. Fuzz AF_UNIX protocol and investigate shared storage, mount boundaries,
   and crash power-loss. Windows/NTFS **deferred at the user's direction**.

Nothing in this work changes Cognitum's production causal algorithms, G25,
Lu, or the original CH23–CH34 mathematical certificates. Global mathematical
optimality certifications remain **0/15**.