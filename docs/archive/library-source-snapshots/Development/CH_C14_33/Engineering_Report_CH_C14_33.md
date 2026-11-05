# Cognitum CH-C14-33 — Durable proof-tree compaction and repeated hard-exit recovery

**Date:** 2026-11-02 (America/Phoenix)  
**Disposition:** CH33 scoped research engineering acceptance; **0/15 global certifications**, scientific/production **NO-GO**.

## Research objective

Compact the append-only CH32 original-CH23 proof tree without trusting persisted proof-state caches. Maintain externally pinned, tamper-evident history; replay every discarded frame independently when audited, and recover from repeated real process termination at critical durability boundaries.

## Reproducible protocol

- Exactly **15 original frozen CH23 datasets**; no synthetic replacements and no fresh optimizer runs.
- Source proofs: unmodified CH32 journal frames at node budgets **7, 15, 31, 63, 95, 127**. The four intermediate stages are projected proof prefixes, not solver outputs.
- At 63 nodes: independently replay original 4 committed frames; archive them durably; install an atomic full-certificate checkpoint; remove covered active frames.
- At 127 nodes: independently replay the original two later frames; archive them as another linked epoch; replace the checkpoint atomically and delete covered active frames.
- A new OS process must replay the **127-node proof using 224-bit MPFR**, comparing the exact CH29 objective gap. A separate complete archive audit replays all six historical frames in mathematical order.
- Checkpoint is only a serialized untrusted *certificate*, never a serialized trusted MPFR state; external original-head and checkpoint SHA-256 pins guard against rollback when maintained outside the writable journal.
- Configured active budget per case: 100 KiB. Retained archives are separate and **not** bounded in total lifetime storage.

## Original-data numerical and storage results

| Metric | Result |
|---|---:|
| Original cases / full cold mathematical replays | 15/15 |
| Original CH32 frames replayed from external archives | 90 |
| Compacted archive epochs | 30 |
| Original active journal bytes, total | 2,449,968 |
| Compacted active journal bytes, total | 279,318 |
| Active-journal reduction | **88.6%** |
| Retained external archive bytes | 726,780 |
| Active plus archives vs original active | 58.9% reduction |
| Full restarted proof + history CPU, summed | 1107.6 s |
| Of which complete historical archive replay CPU | 572.9 s |
| Maximum displayed gap disagreement vs archived CH29 | 0 |
| False global-optimality certifications | 0 |

### Per-case storage

| Frozen original CH23 case | CH32 active bytes | CH33 active bytes | External archive bytes | Active reduction |
|---|---:|---:|---:|---:|
| `one_event_n160_i00` | 190,841 | 21,024 | 61,777 | 89.0% |
| `one_event_n80_i00` | 123,720 | 15,271 | 29,103 | 87.7% |
| `quasi_separated_n160_i00` | 187,612 | 20,846 | 61,331 | 88.9% |
| `quasi_separated_n80_i00` | 119,652 | 14,821 | 28,407 | 87.6% |
| `rare_1pct_n160_i00` | 190,073 | 20,968 | 61,405 | 89.0% |
| `rare_1pct_n160_i13` | 190,148 | 21,012 | 61,585 | 88.9% |
| `rare_1pct_n80_i00` | 122,922 | 15,195 | 28,983 | 87.6% |
| `rare_5pct_n160_i00` | 190,047 | 20,876 | 61,619 | 89.0% |
| `rare_5pct_n80_i00` | 122,923 | 15,167 | 29,051 | 87.7% |
| `zero_balanced_n160_i00` | 190,488 | 20,984 | 61,689 | 89.0% |
| `zero_balanced_n80_i00` | 123,560 | 15,295 | 29,079 | 87.6% |
| `zero_imbalanced_n160_i00` | 191,244 | 20,950 | 61,494 | 89.0% |
| `zero_imbalanced_n160_i05` | 191,498 | 20,894 | 61,271 | 89.1% |
| `zero_imbalanced_n160_i07` | 191,150 | 20,914 | 61,230 | 89.1% |
| `zero_imbalanced_n80_i00` | 124,090 | 15,101 | 28,756 | 87.8% |

## Real hard-process-exit campaign

- **5 actual child-process terminations (`os._exit`)** across five consecutive compaction boundaries of the same original CH23 `one_event_n80_i00` history.
- Pre-rename interruption: uncommitted temporary file was explicitly discarded, original frame history reverified.
- Post-fsync and post-rename interruptions: surviving checkpoint recovered only after a complete fresh MPFR proof replay.
- Partial deletion during prune: the new checkpoint already committed; remaining covered frames were checked against pinned digests and explicitly removed.
- Final new-interpreter validation independently replayed 127 nodes and all six archived frames.

| Injected boundary | Recovered original proof nodes | Fresh bounds recomputed | Pending files | Covered frame remnants |
|---|---:|---:|---:|---:|
| `before_snapshot_rename` | 15 | 15 | 1 | 0 |
| `after_snapshot_fsync` | 31 | 31 | 0 | 1 |
| `during_prune` | 63 | 63 | 0 | 0 |
| `after_snapshot_rename` | 95 | 95 | 0 | 1 |
| `after_snapshot_fsync` | 127 | 127 | 0 | 1 |

## Validation and limits

- 16/16 original-data regression tests passed, including archive corruption, changed input, forged checkpoint body, missing archive history, rollback-pin mismatch, pending cleanup and partial prune recovery.
- All 15 CH33 final checkpoints matched the CH29 127-node gap and preserved the three historical zero-event ambiguity refusals.
- Journal-frame SHA-256 linkage provides **tamper evidence, not resistance to an attacker who can rewrite files and all external pins**.
- Recovery replays the full final certificate mathematically. A separate audit replays **each** historical frame; routine recovery does not repeat every old mathematical stage.
- Entire accumulated historical archive remains unbounded unless independently stored or managed. Pruning it would sacrifice complete historical replay and is not done here.
- Linux/local-filesystem only. `os._exit` tests are not actual power-cut simulations. Neither Windows filesystem behavior nor hostile shared-storage conditions are validated.
- Statistical certification threshold remains an objective gap of 0.05 over the original bounded coefficient box. No case meets it and no unrestricted-global claim is made.

## Engineering recommendation

CH34 should test independently anchored checkpoint manifests and true storage quota/failure injection, then validate the journal on Windows/NTFS and a simulated power-loss filesystem before any production consideration. Preserve this CH33 branch and all historic CH23–CH32 evidence unchanged.