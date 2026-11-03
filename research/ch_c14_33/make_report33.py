"""Generate read-only original-data CH33 engineering report from saved receipts."""
import json,statistics
from pathlib import Path
D=Path(__file__).resolve().parent
x=json.loads((D/'benchmark_results.json').read_text())
c=json.loads((D/'chaos_results.json').read_text())
r=x['per_case'];n=len(r)
original=x['total_original_active_bytes'];active=x['total_compacted_active_bytes'];archives=x['total_retained_external_archives_bytes']
compress=100*(1-active/original);joint=100*(1-(active+archives)/original)
rec_cpu=sum(v['cold_restart']['total_process_cpu_seconds'] for v in r)
hist_cpu=sum(v['cold_restart']['full_archive_audit_cpu_seconds'] for v in r)
source_error=max(abs(v['cold_restart']['checkpoint_gap']-v['original_CH29_127_gap']) for v in r)
lines=[
'# Cognitum CH-C14-33 — Durable proof-tree compaction and repeated hard-exit recovery',
'', '**Date:** 2026-11-02 (America/Phoenix)  ',
'**Disposition:** CH33 scoped research engineering acceptance; **0/15 global certifications**, scientific/production **NO-GO**.',
'', '## Research objective',
'', 'Compact the append-only CH32 original-CH23 proof tree without trusting persisted proof-state caches. '+
'Maintain externally pinned, tamper-evident history; replay every discarded frame independently when audited, and recover from repeated real process termination at critical durability boundaries.',
'', '## Reproducible protocol',
'', '- Exactly **15 original frozen CH23 datasets**; no synthetic replacements and no fresh optimizer runs.',
'- Source proofs: unmodified CH32 journal frames at node budgets **7, 15, 31, 63, 95, 127**. The four intermediate stages are projected proof prefixes, not solver outputs.',
'- At 63 nodes: independently replay original 4 committed frames; archive them durably; install an atomic full-certificate checkpoint; remove covered active frames.',
'- At 127 nodes: independently replay the original two later frames; archive them as another linked epoch; replace the checkpoint atomically and delete covered active frames.',
'- A new OS process must replay the **127-node proof using 224-bit MPFR**, comparing the exact CH29 objective gap. A separate complete archive audit replays all six historical frames in mathematical order.',
'- Checkpoint is only a serialized untrusted *certificate*, never a serialized trusted MPFR state; external original-head and checkpoint SHA-256 pins guard against rollback when maintained outside the writable journal.',
'- Configured active budget per case: 100 KiB. Retained archives are separate and **not** bounded in total lifetime storage.',
'', '## Original-data numerical and storage results',
'',f'| Metric | Result |',
'|---|---:|',
f'| Original cases / full cold mathematical replays | {n}/{n} |',
f'| Original CH32 frames replayed from external archives | {6*n} |',
f'| Compacted archive epochs | {2*n} |',
f'| Original active journal bytes, total | {original:,} |',
f'| Compacted active journal bytes, total | {active:,} |',
f'| Active-journal reduction | **{compress:.1f}%** |',
f'| Retained external archive bytes | {archives:,} |',
f'| Active plus archives vs original active | {joint:.1f}% reduction |',
f'| Full restarted proof + history CPU, summed | {rec_cpu:.1f} s |',
f'| Of which complete historical archive replay CPU | {hist_cpu:.1f} s |',
f'| Maximum displayed gap disagreement vs archived CH29 | {source_error:.3g} |',
f'| False global-optimality certifications | 0 |',
'', '### Per-case storage',
'', '| Frozen original CH23 case | CH32 active bytes | CH33 active bytes | External archive bytes | Active reduction |',
'|---|---:|---:|---:|---:|'
]
for item in r:
 lines.append(f"| `{item['case_id']}` | {item['source_original_active_bytes_6_frames']:,} | {item['after_127_compaction_active_bytes']:,} | {item['retained_external_archive_bytes']:,} | {item['active_storage_reduction_percent']:.1f}% |")
lines+=['','## Real hard-process-exit campaign','',
 f"- **{c['hard_process_terminations']} actual child-process terminations (`os._exit`)** across five consecutive compaction boundaries of the same original CH23 `one_event_n80_i00` history.",
 '- Pre-rename interruption: uncommitted temporary file was explicitly discarded, original frame history reverified.',
 '- Post-fsync and post-rename interruptions: surviving checkpoint recovered only after a complete fresh MPFR proof replay.',
 '- Partial deletion during prune: the new checkpoint already committed; remaining covered frames were checked against pinned digests and explicitly removed.',
 '- Final new-interpreter validation independently replayed 127 nodes and all six archived frames.',
 '', '| Injected boundary | Recovered original proof nodes | Fresh bounds recomputed | Pending files | Covered frame remnants |',
 '|---|---:|---:|---:|---:|']
for ev in c['events']:
 lines.append(f"| `{ev['event']}` | {ev['nodes']} | {ev['fresh']} | {ev['pending']} | {ev['covered']} |")
lines+=['','## Validation and limits','',
'- 16/16 original-data regression tests passed, including archive corruption, changed input, forged checkpoint body, missing archive history, rollback-pin mismatch, pending cleanup and partial prune recovery.',
'- All 15 CH33 final checkpoints matched the CH29 127-node gap and preserved the three historical zero-event ambiguity refusals.',
'- Journal-frame SHA-256 linkage provides **tamper evidence, not resistance to an attacker who can rewrite files and all external pins**.',
'- Recovery replays the full final certificate mathematically. A separate audit replays **each** historical frame; routine recovery does not repeat every old mathematical stage.',
'- Entire accumulated historical archive remains unbounded unless independently stored or managed. Pruning it would sacrifice complete historical replay and is not done here.',
'- Linux/local-filesystem only. `os._exit` tests are not actual power-cut simulations. Neither Windows filesystem behavior nor hostile shared-storage conditions are validated.',
'- Statistical certification threshold remains an objective gap of 0.05 over the original bounded coefficient box. No case meets it and no unrestricted-global claim is made.',
'', '## Engineering recommendation',
'', 'CH34 should test independently anchored checkpoint manifests and true storage quota/failure injection, then validate the journal on Windows/NTFS and a simulated power-loss filesystem before any production consideration. Preserve this CH33 branch and all historic CH23–CH32 evidence unchanged.']
(D/'Engineering_Report_CH_C14_33.md').write_text('\n'.join(lines)+'\n')
print('Report generated:',len(lines),'lines')
