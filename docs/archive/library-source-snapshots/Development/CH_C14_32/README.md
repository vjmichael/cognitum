# Cognitum CH-C14-32 — Durable proof-tree extension journaling

**Status:** isolated numerical research. **No global certification or scientific/production promotion.** This code never changes Cognitum production C14, pinned G25, Lu, or the Windows application.

## What this adds

`journal32.py` provides an **append-only, SHA-256-linked sequence of atomic, fsynced JSON frames**. The genesis record carries an original CH29 proof certificate; each extension carries newly introduced nodes, promotions of existing leaves to split nodes, and the updated certificate metadata. Prior node bodies and earlier partitions cannot be modified through the extension format. The reader rejects duplicate JSON keys, unknown files, sequence gaps, missing or changed hashes, noncanonical bytes, wrong input/protocol bindings, and invalid proof partitions.

A writer fsyncs a fresh `*.pending` file, atomically renames it to a numbered `0000NN.json` record, and fsyncs its directory. Its exclusive Linux `flock` limits concurrent cooperative writers. After a crash:

- **Before rename:** uncommitted pending file is *not* a proof or committed extension. Recovery may verify all existing complete frames but must explicitly discard the orphan before appending another frame.
- **After rename and directory fsync, before acknowledgement:** a valid committed extension is found by its sequence number, reverified from disk, and accepted. Re-appending the identical certificate is idempotent, not a second journal entry.
- **Corruption:** a corrupted *committed* frame is never silently truncated or skipped. The journal fails closed and requires intervention. A missing last frame may be undetectable without an **externally pinned head digest**; the API supports `expected_head_sha256` for this purpose.

**Important security boundary:** SHA-256 chaining is *tamper-evident*, not tamper-proof when an adversary can rewrite every local file and the pin. For adversarial provenance, pin the final journal heads externally (e.g., a reviewed signed release manifest or protected repository history). The existing implementation assumes trusted Python code and operating system. It does not prevent malicious concurrent filesystem writes outside its lock or claim power-failure proof on every filesystem.

## How restart verification works

`restart32.py` always loads CH23’s original 15 input hashes and CH29 frozen solver certificates, then independently recomputes all committed numerical upper bounds using 224-bit MPFR through CH30/CH31's verifier. **No persisted MPFR objects, saved certificates' release flags, or journal receipts are treated as trusted proof.** Any later increments are verified only after their original prefix is re-established in that process.

### Reproduction

Requires the source directories `CH_C14_24` through `CH_C14_32`, the original frozen inputs, the research Python dependencies including MPFR 4.2.x, and a Linux filesystem that supports `flock`, atomic same-directory rename, and fsync.

```sh
cd CH_C14_32
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q tests/test_journal.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python chaos32.py   # hard child process exits at both commit boundaries
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python benchmark32.py --workers 3
python audit32.py
python restart32.py --case zero_balanced_n80_i00 --journal journals/zero_balanced_n80_i00 --verify-only --expected-head '<pin from heads.json>'
```

Run the full benchmark in a clean `journals/` directory; it refuses existing journal frames instead of rewriting old results. Additionally, `chaos32.py` verifies real hard process exits on an original CH23 case. The benchmark injects a **before-rename crash on `one_event_n80_i00`**, and a **post-fsync, pre-ack crash on `zero_balanced_n80_i00`**, before completing all 15 journals. The final additional cold process checks every 127-node proof, with the external head pin read from the previous verified stage's receipt. Saved replay receipts are only diagnostics.

Proof checkpoint sizes: 7 → 15 → 31 → 63 → 95 → 127. The 7/15/31/95 intermediate checkpoints are projections of CH29's archived proof trees, **not new optimizer searches**. The 63/127 source checkpoints retain their original hashes. The fifteen cases and the three historical ambiguous zero-event refusals are unchanged.

## Disposition

This is a *durable research proof journal*, not an estimator. These tests address crash recovery, partition integrity, proof continuity, and restart verification for **finite coefficient boxes**, not the unrestricted global maximum, unique stationary solutions, causal identifiability, calibration, or coverage of confidence intervals. C14 scientific release remains **NO-GO**.