# CH-C14-35 — Linux separate-UID proof trust authority

**Research-only. Production Cognitum C14/G25 and Lu unchanged. Windows deferred by user.**

## Trust separation

The journal writer and the authority are **different Linux UIDs** (test: writer
UID 1000, signer UID 65534). The signing key, immutable frozen 15-case CH23
source material, compiled/loaded verifier source, authority case policy,
externally held tip and signed ledger live in a signer-owned 0700 directory.
The journal writer can edit its journal copy, but not the signer store.

The authority serves an AF_UNIX socket with `SO_PEERCRED`-based UID admission,
accepting only `{"op":"verify","case_id":"<frozen CH23 ID>"}`. It does not
accept writer-generated attestations, fingerprints, paths, checkpoints,
receipts, signatures, private keys, or revised trust policy. For each admitted
new case it copies the checkpoint and compressed archives into a signer-owned
temporary working directory, checks the independently frozen content SHA,
loads the original case from the protected source, recomputes the 127-node
MPFR certificate and all six original archived mathematical frames, compares
the CH29 objective gap, and signs **only** `scientific_release: NO_GO`.

Ed25519 signs a canonical, domain-separated witness body. Public verification
requires a **pretrusted public-key fingerprint and externally retained latest
signed tip**. The client must not obtain these initial trusts from the
writable journal or a mutable response alone. The signer maintains its own
protected tip in `trusted_tip.json` independently of the ledger HEAD. A crash
between those two updates quarantines the store until an authorized operator
independently replays mathematics and explicitly repins the successor. There
is **no automatic re-pin API**.

The signing account itself is a trust root: if it is compromised, the private
key/source/config/tip can be changed. This is not an HSM, TPM, remote witness,
or immutable transparency log. UIDs are isolation evidence on the tested Linux
host, not a claim of resistance to root/admin. The protocol currently signs
one frozen 127-node CH33 proof per case; it deliberately forbids signing
later extensions without a new separately approved protocol. Do not deploy
with shared writable directories, reused keys or mutable source files.

## Scope and acceptance

- 12 local witness-store tests and 27 ENOSPC/EIO/EDQUOT injection subcases passed.
- 9 **actual `os._exit(79)` subprocess crashes** across record/head write,
  fsync, rename, and dirsync boundaries passed (not power-cycle tests).
- One **real kernel `RLIMIT_FSIZE`** write rejection passed (EFBIG).
- One independent Linux signer-versus-writer UID case passed, including rejected
  journal tampering, OS-blocked signing-key access, independent original CH23
  127-node MPFR replay plus six historical frames, signature validation, signed
  tip validation, and duplicate-signing refusal.
- **14 other original frozen cases not rerun under the new UID-separated signer**;
  they were verified under CH34, not CH35. No false global certificates claimed.
- Genuine `ENOSPC` from a full filesystem, hardware power-cut simulation,
  multi-host trust replication, Unix-socket hostile-client fuzzing, and
  Windows/NTFS tests are **not done**.

## Reproduce

Extract the CH35 full reproduction ZIP to a directory with sibling directories
`CH_C14_23` through `CH_C14_35` and the original source files. On Linux with
`cryptography`, `pytest`, pinned CH24–CH29 mathematical dependencies, `setpriv`,
and permissions to invoke it as root:

```bash
python -m pytest -q CH_C14_35/tests/test_store.py CH_C14_35/tests/test_hard_exit.py
python CH_C14_35/audit35.py
python CH_C14_35/tests/live_15_protocol.py
```

The last test copies source and proof into a newly provisioned **private signer
trust domain** under `/tmp`, launches separate UIDs, and may require around a
minute of MPFR CPU time. It creates a fresh *ephemeral* signing key and a fresh
signed tip, so don't compare the resulting key fingerprint and signature to
prior runs; compare mathematical input pins and signed body semantics. It does
not delete the signer directory, allowing manual inspection. Never put the
private key into an evidence ZIP or GitHub.

**Result:** CH35 trust boundary validated on one original case; no scientific
release, zero certified global optima, three historical ambiguous zero-event
refusals retained unchanged. Windows explicitly deferred.