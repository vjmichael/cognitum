# Cognitum CH-C14-32 — Durable, mathematically reverified proof-tree extension journal

**Date:** 2026-11-02 · **Disposition:** Research engineering acceptance only; global-optimality and scientific C14 production **NO-GO**.

## Mathematical and source boundary

Original CH23 datasets, CH29 63/127-node solver certificates, and CH31 7/15/31/95-node derived projections are preserved. Only verifier/journaling code was added. No new optimizer searches or replacement datasets were produced. The underlying 224-bit MPFR objective proof is finite-domain and shares the prior numerical implementation.

## Journal design

- A genesis frame records the verified starting certificate; each extension lists existing-terminal split promotions, new nodes, full certificate metadata, previous certificate digest, and a SHA-256-linked record digest.
- Frames are fsynced before rename and their directory is fsynced after rename; journal files are immutable by protocol and cooperative writers hold `flock`.
- On a new process, the journal is a source of *untrusted proof claims*. The original input hash, model, duals, root box, partition, parent-bound inheritance, and every MPFR bound are revalidated before verification state is established.
- A partial uncommitted pending write is ignored for reads but must be explicitly discarded before resuming; a corrupt committed frame is a hard error. A lost acknowledgement after durable rename is recovered idempotently.
- An externally anchored chain-head digest is necessary to detect malicious deletion/rewrite of an otherwise valid suffix. SHA-256 alone is not authentication.

## Frozen original-data benchmark

Protocol SHA-256: `6c064f2570874ef6fb447cc54ec45707e95b65bbf5381098f65807d6c96f7408`.

- Original source-bound datasets: **15/15**.
- Committed, hash-linked frames: **90**.
- Fresh verifier processes that independently reconstructed all 127 nodes: **15/15**, totaling **1905** independent node-bound computations.
- Three historical ambiguous zero-event cases retained: **3/3** refused.
- Global-optimality certificates: **0**.

### Timings (summed process CPU, not wall clock)

| Phase | CPU seconds |
|---|---:|
| Initial in-process four-stage append (7–63) | 309.964 |
| Fresh-process recovery and append through 127 | 576.941 |
| Additional cold replay of six committed stages | 564.411 |
| Benchmark wall time (parallel workers) | 508.036 |

### Per-case cold verification

| Original case | Crash injected | Recovery nodes rechecked | Final replay nodes | Verified final gap |
|---|---|---:|---:|---:|
| `one_event_n160_i00` | none | 63 | 127 | 3.304401 |
| `one_event_n80_i00` | before_rename | 63 | 127 | 3.162955 |
| `quasi_separated_n160_i00` | none | 63 | 127 | 7.982327 |
| `quasi_separated_n80_i00` | none | 63 | 127 | 5.347579 |
| `rare_1pct_n160_i00` | none | 63 | 127 | 4.080802 |
| `rare_1pct_n160_i13` | none | 63 | 127 | 2.275897 |
| `rare_1pct_n80_i00` | none | 63 | 127 | 3.441085 |
| `rare_5pct_n160_i00` | none | 63 | 127 | 4.192020 |
| `rare_5pct_n80_i00` | none | 63 | 127 | 4.078120 |
| `zero_balanced_n160_i00` | none | 63 | 127 | 2.582996 |
| `zero_balanced_n80_i00` | after_dir_fsync | 95 | 127 | 1.759546 |
| `zero_imbalanced_n160_i00` | none | 63 | 127 | 2.825003 |
| `zero_imbalanced_n160_i05` | none | 63 | 127 | 2.033313 |
| `zero_imbalanced_n160_i07` | none | 63 | 127 | 2.997229 |
| `zero_imbalanced_n80_i00` | none | 63 | 127 | 1.067100 |

## Adversarial tests and failure semantics

The journal suite exercises forged node mathematics even after recomputing the local frame digest, changed chain links, missing or malformed committed frames, duplicate JSON keys, truncated committed frames, mismatched source data, unauthorised false certificates, and crash-before/after-rename recovery. The cold verifier has no serialized proof-state import route. All failure decisions are fail-closed.

## Remaining work

- Durability depends on Linux filesystem rename/fsync semantics; this is not a portable Windows durable-journal guarantee.
- No multi-host Byzantine or untrusted-writer defense. Signed externally pinned chain heads and a designated security model are future work.
- Long-running worker cancellation, process-kill chaos testing, journal space quotas, compaction, and telemetry need separate hardening.
- Original mathematical interval bounds remain too loose for epsilon=0.05 in all tested cases. **This software does not establish a global or unique estimator, causal identification, or calibrated intervals.**

**Scientific release:** NO-GO. Cognitum production C14, pinned G25, Lu, and Windows are unchanged.