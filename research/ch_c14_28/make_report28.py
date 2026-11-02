"""Render CH28 engineering report from verified records, never from invented metrics."""
from pathlib import Path
import json,datetime
D=Path(__file__).resolve().parent
summary=json.loads((D/'study_summary.json').read_text())
rows63={x['case_id']:x for x in summary['case_results'] if x['budget']==63}
rows127={x['case_id']:x for x in summary['case_results'] if x['budget']==127}
a=summary['budgets']['63'];b=summary['budgets']['127']
controls={}
for bud in [63,127]:
 path=D/'baseline_equal_budget'/f'zero_balanced_n80_i00_{bud}.json'
 if path.is_file():controls[bud]=json.loads(path.read_text())
md=['# Cognitum CH-C14-28 — selective coupled-bound evaluation and cache-aware MPFR search',
'','**Date:** November 2, 2026 (America/Phoenix)  ',
'**Scope:** Standalone Cognitum C14 research; no production, G25, Lu, Windows or DLC modification.  ',
'**Disposition:** Engineering verification complete; 0/30 finite-domain 0.05-gap proofs. Scientific and production NO-GO.',
'', '## Immutable provenance and new protocol',
'','The 15 input JSONs are the original CH23 SHA-bound dataset reproductions used in CH25–CH27: 12 frozen original bounding cases and three previously ambiguous zero-event cases. No regenerated or substituted datasets were used for the present benchmark. The pinned CH27 coefficient root box is `[-10,1] × [-5,5] × [-5,5]`, 160-bit directed-rounded MPFR solve, 224-bit replay, absolute objective gap 0.05. Each case was rerun at **63** and **127** nodes. The protocol was frozen before the first run:',
'',f'`{summary["protocol_sha256"]}`','',
'CH28 does **not** rewrite CH23–CH27 certificates, and does not assert a globally unique solution over all real coefficients.',
'', '## Algorithms',
'', 'Every node receives the sound CH26 Loewner/log-likelihood MPFR upper bound. A node whose direct bound is already within the incumbent threshold skips coupled evaluation. Otherwise, CH27’s exactly-SPD coupled Fisher–likelihood dual bound is evaluated on nodes through depth 2 and each subsequent third node by insertion ID, and the tighter bound is used. This selection rule is a heuristic for *speed and search ordering*, not for certification. Other nodes retain the conservative direct upper bound.',
'', 'The solver caches each complete node’s 160-bit MPFR upper endpoint and reuses it to calculate the maximum retained leaf bound, avoiding CH27’s extra pass over the entire leaf set. The **224-bit verifier does not trust cached endpoints or binary64 display values**; it rebuilds the complete partition and any interior Newton contract proof, then recomputes each leaf’s upper bound under the recorded valid method. Unresolved proofs remain explicit refusals.',
'', '## Full original-data benchmark',
'', '| Metric | 63-node cohort | 127-node cohort |',
'|---|---:|---:|',
f'| Original cases / independent replays | {a["cases"]}/15 | {b["cases"]}/15 |',
f'| Mean upper objective gap | {a["mean_gap"]:.6f} | {b["mean_gap"]:.6f} |',
f'| Median upper objective gap | {a["median_gap"]:.6f} | {b["median_gap"]:.6f} |',
f'| Maximum upper objective gap | {a["maximum_gap"]:.6f} | {b["maximum_gap"]:.6f} |',
f'| Coupled bound calls | {a["coupled_calls"]} | {b["coupled_calls"]} |',
f'| Direct bound calls | {a["direct_calls"]} | {b["direct_calls"]} |',
f'| Cached terminal leaf values reused | {a["cached_leaf_uses"]} | {b["cached_leaf_uses"]} |',
f'| Newton contractions in global search | {a["newton_contractions"]} | {b["newton_contractions"]} |',
f'| Solver CPU seconds (sum) | {a["solve_cpu_seconds"]:.3f} | {b["solve_cpu_seconds"]:.3f} |',
f'| 224-bit replay CPU seconds (sum) | {a["replay_cpu_seconds"]:.3f} | {b["replay_cpu_seconds"]:.3f} |',
f'| Finite-box global certificates | {a["certified"]} | {b["certified"]} |',
'', '### Per-case upper objective gaps (independently replayed)',
'', '| Original CH23 case | 63 nodes | 127 nodes |', '|---|---:|---:|']
for cid in sorted(rows63):
 md.append(f'| `{cid}` | {rows63[cid]["gap"]:.6f} | {rows127[cid]["gap"]:.6f} |')
md.extend(['','## Equal-node CH27 comparison (one original case, not general population inference)',''])
if len(controls)==2:
 md.extend(['The unchanged CH27 full coupled-evaluation solver was additionally run on the **same original** `zero_balanced_n80_i00` data at both budgets. These control runs modify only the node budget in memory. They are new exploratory controls, not modifications of CH27’s frozen 15-node results.','',
 '| Budget | CH27 full coupled gap | CH28 selective gap | CH27 solve+replay CPU s | CH28 solve+replay CPU s | CH28 CPU saved |',
 '|---|---:|---:|---:|---:|---:|'])
 for bud in [63,127]:
  c=controls[bud];z=rows63['zero_balanced_n80_i00'] if bud==63 else rows127['zero_balanced_n80_i00'];before=c['solve_cpu_seconds']+c['replay_cpu_seconds'];after=z['cpu_total_seconds'];saving=(before-after)/before*100
  md.append(f'| {bud} | {c["gap"]:.6f} | {z["gap"]:.6f} | {before:.3f} | {after:.3f} | {saving:.1f}% |')
 md.extend(['','The selective solver saves CPU on this case but returns a **looser** upper gap. Do not interpret the CPU benefit as a mathematical proof-quality improvement.'])
else:md.append('Equal-budget CH27 control data were incomplete; no quantitative control comparison is claimed.')
md.extend(['', '## Assurance and limitations',
'', '- The independent high-precision verifier accepts only a complete binary partition of the original root, valid interior-root contractions/exclusions, and sound direct or coupled MPFR bounds on all live leaves. Tampered partitions, incorrect global claims, altered root boxes and unsupported bound methods are rejected by tests.',
'- The three original zero-event ambiguous datasets retain their historical refusal status. Finding a better local maximum, or a smaller finite-domain upper gap, cannot override causal-identification or global-uniqueness gates.',
'- The cache is only a performance feature. Every terminal upper bound in each proof record was recomputed by the verifier at 224 bits. CH28 shares the underlying MPFR interval mathematics with CH24–CH27; this is not a separately formalized theorem-prover implementation.',
'- Cumulative CPU time is the sum of per-process CPU measurements. Benchmarks ran concurrently, so wall times and aggregate CPU are not interchangeable, and original CH26/127 or CH27/15 figures are not equal-node comparisons.',
'- Broader coefficient domains, unrestricted global optimization, optimality/uniqueness of the Jeffreys estimator, causal coverage/calibration and external R equivalence remain unproven. **C14 scientific and production release NO-GO.**',
'', '## Next measured engineering steps',
'', '1. Preserve the CH28 63/127 baseline and compare alternate *safe* selective gates on the exact same 15 cases using preregistered CPU/time budgets; consider dual benefit measured at parent nodes and best-first bound uncertainty.',
'2. Improve coupled scalar surrogate evaluation without heuristic precision loss; explore verified relative determinant bounds and interval-Hessian bounds that actually prune live search nodes.',
'3. Before any promotion, test larger and unseen nonzero-event cohorts, prove parameter domain tail bounds (or refuse unbounded claims), and complete the separate scientific release gates.',
''])
(D/'Engineering_Report_CH_C14_28.md').write_text('\n'.join(md))
print('WROTE',D/'Engineering_Report_CH_C14_28.md')
