# Cognitum CH-C14-36 — All-original independent witnesses and real Linux ENOSPC

**2026-11-02 · Research-only · Windows deferred · Scientific NO-GO**

CH36 extends CH35's **separate Linux signer account** (UID 65534) and
writer UID 1000 with up to four separate, signer-owned proof verifier
processes. A bounded AF_UNIX request contains only a frozen original CH23
case ID. Every requested case is independently replayed at 224-bit MPFR,
including all six CH32 archived proof frames, before the single signing
authority serializes an Ed25519 witness record and its protected tip.

## Results

- **15/15 ORIGINAL CH23 cases** signed in one signer-owned append-only ledger;
  this adds 14 live cases to CH35's previous one-case acceptance.
- 15 signed 127-node checkpoint verifications = **1,905** accepted proof nodes;
  6 archived historical frames per case = **90** replayed frames.
- 15/15 signatures, previous-hash links, source heads, CH33 checkpoint pins,
  generation numbers and final tip independently checked by `audit36.py`.
- Old CH35 storage tests plus new Linux tests: **15 pytest methods and 54
  adversarial subtests passing**; 15 new libc `fsync` faults and 3 true
  kernel ENOSPC failures on a private, user-namespaced 256 KiB `tmpfs`.
- A corrected duplicate-request admission path rejects an already-witnessed
  case **before** expensive MPFR and again under a publication mutex afterward.
  Verified by restarting the signer on the completed 15-record ledger and
  observing a sub-2-second refusal with no new signature.
- A research harness's *optional* duplicate request timed out after the 15
  actual authority ledger commits had completed. `recover36.py` performed
  **read-only** reconstruction of the existing receipts. No new signature,
  tip update, replacement case, or unverified mathematics was introduced.
- No scientific global-optimality certificate (**0/15**) and no production
  changes to Cognitum C14/G25 or Lu.

## Security boundary and limits

Signer files, frozen original source and private key belong to UID 65534;
the writer UID 1000 cannot read/modify them. Proof workers are independent
processes but share the signer UID: a compromised proof worker is **not yet**
isolated from the authority key. The signing ledger's protected tip is local
signer storage; a key fingerprint and latest tip must be independently pinned
outside that storage to detect rollback or replacement of the entire signer
root. No external multi-host co-signing or hardware key store is claimed.

The `LD_PRELOAD` C shim returns real OS-facing `fsync` errors for target
record/head/tip file descriptors but the errnos are *injected*, not from a
failing physical disk. Separately, the temporary `tmpfs` tests create an
actual full 256 KiB filesystem in a **private user+mount namespace**;
`os.posix_fallocate` fills it and the Linux kernel genuinely returns ENOSPC.
EDQUOT and EIO remain injected. No real power-cut, network filesystem,
quota-enforced EDQUOT, cross-host trust anchor, or Windows/NTFS test has
been completed.

## Local reproduction

Unzip this research package with sibling folders `CH_C14_23` through
`CH_C14_36`, install the CH24–CH35 pinned dependencies, and on suitable
Linux with `setpriv`, user namespaces, and permission to mount private
`tmpfs` inside the namespace:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q \
  CH_C14_35/tests/test_store.py CH_C14_35/tests/test_hard_exit.py \
  CH_C14_36/tests/test_syscall_fsync.py CH_C14_36/tests/test_real_enospc.py

# Root-only two-UID signer acceptance (research, several minutes):
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python CH_C14_36/batch36.py --root . --workers 4

# The fingerprint and signed tip must come from an independently retained
# operator record; do not discover/re-pin them from a potentially rewritten
# signer directory during an anti-rollback audit.
python CH_C14_36/audit36.py --original-root . \
  --expected-fingerprint '<separately pinned fingerprint>' \
  --expected-tip '<separately pinned tip>'
```

`audit36.py` verifies **public signatures, chain structure and frozen source
pins only**. It never claims to re-run the numerical proof itself. CH36's
signed proof generation is done by `witness_original_ch33()` inside the
signer-controlled separate processes, and any failures deny publication.

## Files

- `service36.py` — bounded parallel, process-separated mathematical verification,
  serialized signed commit, and early+late duplicate/rollback checks.
- `batch36.py` — two-UID Linux integration and actual case-only AF_UNIX requests.
- `audit36.py`, `recover36.py` — public artifact audit and strictly read-only
  signed-ledger recovery.
- `tests/test_syscall_fsync.py`, `fsync_fault36.c` — 15 syscall-level failure
  cases; the `.so` is compiled locally during tests, not shipped as trusted code.
- `tests/test_real_enospc.py`, `tests/real_enospc_worker36.py` — three *real*
  ENOSPC boundaries on a private mount.
- `tests/test_restarted_duplicate36.py` — optional live signer restart check;
  requires `--state` and `--expected-tip` from a completed local run.
- `original15_results.json`, `public_witness/` — authenticated public receipt
  artifacts; **no private signing key is distributed**.
- `syscall_fsync_results.json`, `real_enospc_results.json`,
  `duplicate_restart_results.json`, `SOURCE_SHA256.json`, `frozen_protocol.json`,
  and engineering report — scoped evidence and provenance.

**Next proposed CH37:** additional signer/verification UID separation,
independent remotely anchored or co-signed witness tips, realistic hardware
crash and quota EDQUOT testing. Windows remains explicitly deferred.
