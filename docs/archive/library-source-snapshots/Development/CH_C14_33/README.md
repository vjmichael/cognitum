# CH-C14-33 — Compacted durable proof history with restart and archive replay

**Research-only; production C14, G25 and Lu unchanged; scientific NO-GO.**

This branch adds `compaction33.py` on top of CH32's append-only MPFR proof
journal. The 15 original CH23 datasets, 90 original CH32 committed frames,
CH29 63/127-node proof trees, and their source SHA-256 digests are unchanged.
No synthetic replacement datasets or fresh optimizer solutions are introduced.

## Integrity and durability model

1. An exclusive Linux writer lock protects commit/compaction. The original
   journal can append new CH32 extension records normally.
2. Compaction writes a *separately stored, immutable, compressed archive* of
   each covered journal frame and fsyncs both the archive and its directory.
3. A new checkpoint stores a zlib-compressed full final proof certificate,
   the source journal head hash, archive digest, all covered frame hashes,
   and the previous checkpoint envelope. It is installed by atomic replacement
   with fsync. Only **after that commit** are old active frames removed.
4. If a crash occurs, any still-present covered frames must match the
   checkpoint's recorded hashes. Interrupted temporary files and incomplete
   cleanup require explicit recovery actions, not silent repair.
5. Every process restart decompresses an **untrusted** checkpoint certificate,
   independently verifies all its 224-bit MPFR bounds, validates new tail
   extensions and verifies the entire archived hash-chain metadata.
6. `verify_archived_history()` is deliberately more costly: it reconstructs
   every archived original CH32 frame and independently replays the complete
   mathematical sequence. It never trusts a saved verifier receipt or a
   hash-only assertion as proof.
7. The caller can bind an external expected *original journal head hash* and
   a separate *checkpoint SHA-256*. Without a trusted external pin, a
   malicious party capable of rewriting all files could rewrite history.

The optional `max_active_bytes` setting preflights journal-extension sizes
and compacts before adding an extension that would exceed the active budget.
**Only active journal storage is bounded.** Retaining complete historical
archives consumes additional, eventually unbounded storage unless the owner
moves them to an independent archive store. Deleting archives breaks full
history auditability and is not an accepted recovery shortcut.

This research implementation targets Linux, `fcntl.flock`, same-filesystem
atomic rename and fsync semantics. Hard `os._exit` tests **do not simulate
hardware power loss**. Windows and network-filesystem durability are not
claimed or supported by this milestone.

## Reproduction

Extract the full reproduction ZIP to a working directory containing sibling
`CH_C14_23` through `CH_C14_33` directories. Install the MPFR dependencies
specified by CH24 and the Python dependencies required by CH29–CH32.

```
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q CH_C14_33/tests/test_compaction.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python CH_C14_33/benchmark33.py --workers 3
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python CH_C14_33/chaos33.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python CH_C14_33/audit33.py
```

The benchmark refuses to overwrite pre-existing active journals/archives.
Run in a fresh extraction for a full repeat. The intermediate 7-, 15-, 31-,
and 95-node original CH29 prefixes are research proof-tree projections, not
new optimizer searches. The 0.05 global-gap requirement remains unmet.

## CH33 files

- `compaction33.py`: compact/restart logic and full archived-history replay
- `restart33.py`: independent fresh-process mathematical verification
- `benchmark33.py`: original 15-case two-epoch compaction and disk measurements
- `chaos33.py`: five repeated *actual* hard process exits and recovery
- `finalize_chaos33.py`: reconcile surviving crash logs and immutable archives after a failed harness acknowledgement
- `tests/test_compaction.py`: original-data fail-closed and tamper tests
- `freeze33.py`, `frozen_protocol.json`: input and method identity
- `audit33.py`, `benchmark_results.json`, `chaos_results.json`: read-only evidence
- `Engineering_Report_CH_C14_33.md`: final measured engineering disposition

Any certificate that cannot be verified remains REFUSED/UNRESOLVED. There are
**zero bounded-global and zero unrestricted-global scientific certifications**.