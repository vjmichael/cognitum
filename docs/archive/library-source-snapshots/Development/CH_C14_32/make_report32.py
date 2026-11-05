"""Generate final CH32 report from frozen results without editing raw receipts."""
import json
from pathlib import Path
D=Path(__file__).resolve().parent
s=json.loads((D/'benchmark_results.json').read_text())
cases=s['per_case'];assert len(cases)==15
lines=[
'# Cognitum CH-C14-32 — Durable, mathematically reverified proof-tree extension journal',
'', '**Date:** 2026-11-02 · **Disposition:** Research engineering acceptance only; global-optimality and scientific C14 production **NO-GO**.',
'', '## Mathematical and source boundary',
'', 'Original CH23 datasets, CH29 63/127-node solver certificates, and CH31 7/15/31/95-node derived projections are preserved. Only verifier/journaling code was added. No new optimizer searches or replacement datasets were produced. The underlying 224-bit MPFR objective proof is finite-domain and shares the prior numerical implementation.',
'', '## Journal design',
'', '- A genesis frame records the verified starting certificate; each extension lists existing-terminal split promotions, new nodes, full certificate metadata, previous certificate digest, and a SHA-256-linked record digest.',
'- Frames are fsynced before rename and their directory is fsynced after rename; journal files are immutable by protocol and cooperative writers hold `flock`.',
'- On a new process, the journal is a source of *untrusted proof claims*. The original input hash, model, duals, root box, partition, parent-bound inheritance, and every MPFR bound are revalidated before verification state is established.',
'- A partial uncommitted pending write is ignored for reads but must be explicitly discarded before resuming; a corrupt committed frame is a hard error. A lost acknowledgement after durable rename is recovered idempotently.',
'- An externally anchored chain-head digest is necessary to detect malicious deletion/rewrite of an otherwise valid suffix. SHA-256 alone is not authentication.',
'', '## Frozen original-data benchmark',
'', f'Protocol SHA-256: `{s["frozen_protocol_sha256"]}`.',
'', f'- Original source-bound datasets: **{s["cases"]}/15**.',
 f'- Committed, hash-linked frames: **{s["journal_frames"]}**.',
 f'- Fresh verifier processes that independently reconstructed all 127 nodes: **{s["cases"]}/15**, totaling **{s["total_fresh_final_replay_bounds"]}** independent node-bound computations.',
 f'- Three historical ambiguous zero-event cases retained: **{s["original_ambiguous_case_refusals"]}/3** refused.',
 f'- Global-optimality certificates: **{s["global_certificates"]}**.',
'', '### Timings (summed process CPU, not wall clock)',
'', '| Phase | CPU seconds |', '|---|---:|',
 f'| Initial in-process four-stage append (7–63) | {s["total_writer_cpu_seconds"]:.3f} |',
 f'| Fresh-process recovery and append through 127 | {s["total_resume_cpu_seconds"]:.3f} |',
 f'| Additional cold replay of six committed stages | {s["total_cold_final_replay_cpu_seconds"]:.3f} |',
 f'| Benchmark wall time (parallel workers) | {s["elapsed_wall_seconds"]:.3f} |',
 '', '### Per-case cold verification',
 '', '| Original case | Crash injected | Recovery nodes rechecked | Final replay nodes | Verified final gap |', '|---|---|---:|---:|---:|',
]
for x in cases:
 lines.append(f'| `{x["case_id"]}` | {x["crash_injection"]} | {x["fresh_restart"]["cold_recomputed_bounds"]} | {x["cold_final_replay"]["cold_recomputed_bounds"]} | {x["original_127_gap"]:.6f} |')
lines += [
'', '## Adversarial tests and failure semantics',
'', 'The journal suite exercises forged node mathematics even after recomputing the local frame digest, changed chain links, missing or malformed committed frames, duplicate JSON keys, truncated committed frames, mismatched source data, unauthorised false certificates, and crash-before/after-rename recovery. The cold verifier has no serialized proof-state import route. All failure decisions are fail-closed.',
'', '## Remaining work',
'', '- Durability depends on Linux filesystem rename/fsync semantics; this is not a portable Windows durable-journal guarantee.',
'- No multi-host Byzantine or untrusted-writer defense. Signed externally pinned chain heads and a designated security model are future work.',
'- Long-running worker cancellation, process-kill chaos testing, journal space quotas, compaction, and telemetry need separate hardening.',
'- Original mathematical interval bounds remain too loose for epsilon=0.05 in all tested cases. **This software does not establish a global or unique estimator, causal identification, or calibrated intervals.**',
'', '**Scientific release:** NO-GO. Cognitum production C14, pinned G25, Lu, and Windows are unchanged.',
]
(D/'Engineering_Report_CH_C14_32.md').write_text('\n'.join(lines)+'\n')
print('REPORT WRITTEN',len(lines),'lines')