# Cognitum CH-C14-36 engineering report

**Date:** November 2, 2026 (America/Phoenix)

**Disposition:** Scoped Linux evidence-integrity milestone accepted; scientific
production and global-optimality certification remain **NO-GO**.

## Objective and immutable baseline

Complete independent signer verification of the remaining 14 frozen CH23
cases after CH35's one-case acceptance. Simultaneously strengthen storage
fault testing beyond simulated Python exceptions while preserving the
original CH23–CH35 numerical input, protocol, journal heads, checkpoint
identity and archive history. No synthetic replacement numerical datasets,
optimizer re-runs or changed objective-gap thresholds.

The CH35 signer key is different from the CH36 signer key because CH36 is
an independent fresh-run research authority. All 15 CH36 original cases
were signed into one ledger under one CH36 key and final tip.

## Isolated signing and full original coverage

1. The test harness creates signer-owned source, Ed25519 key, immutable
   15-case source pins and protected journal evidence under Linux UID 65534.
2. The journal writer runs under UID 1000; OS permissions deny it access
   to the private key and frozen source, and only permit case-only AF_UNIX
   requests. Extra caller-supplied proof fields are refused.
3. The signer dispatches up to four independent processes for fresh 224-bit
   MPFR replay of the complete 127-node final CH33 checkpoint and all six
   CH32 historical archived frames, checking original CH29 objective caps.
4. Under a single publication mutex, the signer rechecks its protected
   head, rejects duplicates or rollback, writes an immutable Ed25519-signed
   revision, atomically replaces HEAD, and advances the protected tip.
5. Public receipts were independently reconstructed and checked against
   original CH32 source-head hashes and CH33 checkpoint SHA-256 pins, with
   exact signed generation sequence 0–14 and final externally recorded tip.

The original run produced all **15** committed witness records; its optional
post-batch duplicate probe mistakenly repeated MPFR and hit a 10-second
harness timeout *after signing was finished*. The handler now checks duplicate
signatures before submitting proof work and again at publication; a restarted
live signer refused a duplicate without changing the chain. Since original
witnesses were fully persisted, read-only `recover36.py` exported and audited
the pre-existing 15 records; it did not perform or claim a second MPFR run.

| Verification | Result |
|---|---:|
| Frozen original CH23 cases signed | **15/15** |
| Newly signed cases relative to CH35 | **14** |
| Signed 127-node checkpoint coverage | **1,905 nodes** |
| Historical CH32 frame replay coverage | **90 frames** |
| Cryptographic signatures/source pins independently audited | **15/15** |
| Separate journal/signer UID admission | **PASS** |
| Writer reading private key or protected source | **DENIED** |
| Duplicate after signer restart | **REFUSED**, no new signature |
| Global-optimality certifications | **0/15** |

## Storage-failure verification

15 pytest test methods passed; the suite executed 54 adversarial subtests
counting prior CH35 fault injection and hard process exits. CH36 adds:

- **15 libc `fsync` interception tests**: `ENOSPC`, `EIO`, and `EDQUOT` at
  record-file, revision-directory, HEAD-file, HEAD-directory, and protected
  tip-file durability fences. These are test-only intercepted syscalls, not
  physical media faults.
- **3 genuine kernel ENOSPC tests** in an isolated **256 KiB Linux tmpfs**
  mounted inside a private user and mount namespace. The tests measure and
  intentionally constrain free capacity to 0, 4 KiB and 8 KiB. Filesystem
  write allocation returned actual kernel `errno=28` in each case.
- In the 8 KiB case, holding the previous HEAD inode open prevented space
  reclamation through replacement, triggering ENOSPC **after the new HEAD
  was committed but before trusted-tip advancement**. It remained
  quarantined; no automatic adoption or new attestation was allowed.
- Existing CH35 `RLIMIT_FSIZE` kernel EFBIG and nine actual hard exits
  stayed passing. An operator must still reconcile orphan/pending files.

| Tested failure | Expected post-failure behavior | Result |
|---|---|---|
| 0 bytes left before revision | Preserve previously trusted tip | PASS |
| 4 KiB left before subsequent HEAD write | Preserve previous HEAD; deny orphan/pending retry | PASS |
| 8 KiB left with old HEAD held open | Quarantine new signed HEAD; no tip adoption | PASS |
| `fsync` EIO/ENOSPC/EDQUOT injected | No silent partial-success acceptance | 15/15 |
| CH35 baseline safety + new tests | All assertions pass | 15 methods, 54 subtests |

## Trust and safety limits

A separate signer UID protects against ordinary writer filesystem tampering;
this does not protect against a compromised signer process or verifier worker
sharing its UID. The private key is **not** included in distribution.
Externally pinned public-key fingerprint and signed tip are necessary for
an auditor to detect simultaneous replacement/rollback of the signer store.
Current signer-only `trusted_tip.json` is not a truly off-host anchor, and
there is not yet an independent co-signing authority.

The signed records prove the signer performed its specified scoped
verification; the public auditor rechecks signatures/pins, **not** MPFR
mathematics. Every original CH23 case remains scientifically unresolved
under the frozen 0.05 objective-gap threshold; nothing is certified beyond
the original bounded coefficient box, let alone unrestricted global
optimality. Real disk-full was checked on a disposable tmpfs mount, not a
power cut, a production filesystem, or actual quota-based EDQUOT. Windows
and NTFS tests remain deferred as directed. No production algorithm or Lu
integration changes were made.

## Next gate

CH37 should isolate the mathematical verifier from the signer key with a
separate UID/one-way authenticated attestation channel, require a second
independently operated signature or monotonic off-host append-only witness
pin, and perform source-preserving crash/power-failure and genuine quota
EDQUOT tests on suitable disposable Linux infrastructure.