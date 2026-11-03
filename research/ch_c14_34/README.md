# Cognitum CH-C14-34 — Independently pinned proof anchors and quota-failure tests

**Research engineering only.** Original CH23 inputs and CH29–CH33 proofs are
unchanged. No new optimization runs or synthetic numerical substitutions.
Global-optimality/scientific/production admission: **NO-GO**.

## What is new

* `anchor34.py`: immutable per-generation ledger revisions, SHA-256-linked
  predecessors, canonical duplicate-key-rejecting JSON, an fsynced revision
  before atomic HEAD replacement, local exclusive `flock`, schema checks,
  quota preflight, orphan/pending detection, and explicitly requested cleanup.
* An independent caller-supplied **external tip SHA-256** is compulsory for
  reads. Changing on-disk HEAD does not change that tip. Stale-pin recovery
  refuses to proceed unless an actual CH33 MPFR replay demonstrates a direct,
  ancestry-preserving successor. Reconciliation returns a *proposal*, never
  silently repins the external trust store.
* `publish_verified_ch33()` demands a previously cold-replayed CH33 checkpoint
  and invokes `verify_archived_history()` for complete independent MPFR replay
  of all historical frames. It rejects pending writes and covered remnants.
  New anchor generations must directly extend the prior anchored checkpoint.
* A ledger quota is a conservative *software preflight*. Genuine Linux
  `RLIMIT_FSIZE` write-failure testing separately demonstrates kernel rejection
  and retained old HEAD. Injected ENOSPC-like faults at write/rename boundaries
  are **not** actual full-disk/power-cut evidence.

**Important security limit:** Storing the ledger in a sibling folder alone is
not cryptographic independence. To defend against whole-store rollback, the
caller must durably pin the returned anchor SHA-256 in a different trusted
security domain (e.g. an independent signer or append-only witness). The CH34
research tests exercise externally supplied pins; they do **not** establish an
operational trusted witness service or hostile-writer resistance.

## Reproduction

Use the exact CH33 full reproduction bundle with sibling `CH_C14_23` through
`CH_C14_33`; add this directory as `CH_C14_34`. The original 15 CH32 head
hashes and 15 CH33 checkpoint hashes are loaded from the frozen input package.
MPFR/ctypes and all other CH29–CH33 prerequisites must be installed.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m unittest discover -s CH_C14_34/tests -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python CH_C14_34/audit34.py --workers 3
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python CH_C14_34/test_original_forward.py
```

The audit requires a **fresh** `CH_C14_34/anchor_storage` destination. It
refuses to reuse existing anchor tips; this prevents a repeat run from
silently overwriting historical witnesses. Each original case independently
replays all 127 checkpoint nodes and all six historical archived frames,
compares the CH29 original display gap, and writes a proposed tip SHA-256.
Run `test_original_forward.py` separately to exercise the original 63 → 127
checkpoint sequence, interrupted HEAD publication, and mathematical
reconciliation without automatic re-anchoring.

## Known limitations and release gates

* Verified Linux local-filesystem metadata and replay only; no NTFS, Windows
  locking, network filesystem, actual hardware power-cut or malicious-writer
  test is claimed.
* `RLIMIT_FSIZE` produces kernel **EFBIG**, not ENOSPC; logical quota is not
  a real filesystem capacity reservation. `os.fsync` success is not proof
  of survival across arbitrary storage-controller failures.
* Full historical archive remains necessary and may grow without bound.
  Pin records must be retained by an independent authority; the generated
  evidence report itself is not a trusted external witness.
* No CH34 change modifies Lu, Cognitum production C14/G25, or the verified
  interval BnB mathematical algorithm. The objective-gap threshold of 0.05
  remains unmet on the original frozen cases. This is not a global-optimality
  certification.
