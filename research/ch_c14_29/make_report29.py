"""Report only from verified original-data study summary; never rewrite frozen receipts."""
import json,statistics
from pathlib import Path
D=Path(__file__).resolve().parent
s=json.loads((D/'study_summary.json').read_text())
fixed=s['modes']['fixed'];cpu=s['modes']['equal_cpu'];ids=sorted(s['original_input_sha256'])
fmt=lambda x:f'{x:.4f}'
lines=[
'# Cognitum CH-C14-29 — Verified inherited upper bounds and paired fixed-node/equal-CPU benchmarks',
'', '**Date:** November 2, 2026 (America/Phoenix). **Scope:** Original CH23 research cases only. **Scientific release: NO-GO.**',
'', '## Mathematical safety',
'', r'For nested coefficient boxes \(B_c\subseteq B_p\), the true objective maximum over the child cannot exceed the maximum over its parent. CH29 therefore computes \(U_c=\min(U_p,U_{c,local})\) with 160-bit directed-rounding MPFR. The bound may be inherited repeatedly through arbitrary ancestor depth.',
'', 'Independent verification at 224 bits rebuilds the exact partition and any interior interval-Newton contractions, recomputes *every* local node bound and recursively reconstructs the ancestor minimum, and rejects any false finite-box certification. Neither displayed floats nor cached endpoints carry proof authority.',
'', 'The finite coefficient domain is `[-10,1] × [-5,5] × [-5,5]`; `epsilon=0.05`. The method does **not** establish unrestricted global maximization, uniqueness, causal identification, or interval calibration.',
'', '## Frozen cohort and measurement protocols',
'', 'All 15 original CH23 inputs are hash-bound in the preregistered `frozen_protocol.json` (12 original bounding cases and three original zero-event ambiguities). The paired tests used 63 and 127 nodes per case. Equal-CPU controls used the independently recorded CH28 *solve process CPU* per case as a hard target checked between node expansions; a final expansion can overshoot. They allowed up to 127/255 nodes to avoid conflating node and CPU budgets. Verification CPU was measured independently, not added to the solve cap.',
'', 'Results from different search policies cannot be compared as if their nodes followed the same partitions. CPU comparisons use historical CH28 single-process measurements from the same environment; machine load and finite node-step granularity remain limitations.',
'', '## Aggregate results',
'', '| Mode | Reference CH28 nodes | CH28 mean gap | CH29 mean gap | Better / tied / worse | CH29 solve CPU (s) | CH28 solve CPU (s) | 224-bit replay CPU (s) | Within ±10% CPU target |',
'|---|---:|---:|---:|---:|---:|---:|---:|---:|'
]
for mode in ('fixed','equal_cpu'):
 for b in ('63','127'):
  x=s['modes'][mode][b]
  lines.append(f'| {mode} | {b} | {fmt(x["baseline_CH28_mean_gap"])} | **{fmt(x["mean_gap"])}** | {x["improved"]}/{x["tied"]}/{x["worsened"]} | {fmt(x["solve_cpu_total_seconds"])} | {fmt(x["baseline_CH28_solve_cpu_total_seconds"])} | {fmt(x["replay_cpu_total_seconds"])} | {x["matched_within_10pct"]}/15 |')
lines+=['','## Original-case paired comparisons','', '| CH23 input | CH28/63 | CH29/63 | CH28/127 | CH29/127 | CH29 CPU/63 | CH29 CPU/127 |','|---|---:|---:|---:|---:|---:|---:|']
for cid in ids:
 by=lambda mode,b:next(x for x in s['modes'][mode][b]['case_results'] if x['case_id']==cid)
 a=by('fixed','63');b=by('fixed','127');ac=by('equal_cpu','63');bc=by('equal_cpu','127')
 lines.append(f'| `{cid}` | {fmt(a["CH28_reference_gap"])} | **{fmt(a["gap"])}** | {fmt(b["CH28_reference_gap"])} | **{fmt(b["gap"])}** | {fmt(ac["gap"])} | {fmt(bc["gap"])} |')
lines+=['','## Monotonicity and unproven claims','']
monotone=[]
for cid in ids:
 a=next(x for x in fixed['63']['case_results'] if x['case_id']==cid)
 b=next(x for x in fixed['127']['case_results'] if x['case_id']==cid)
 monotone.append(b['gap']<=a['gap']+1e-9)
lines.append(f'- CH29 127-node gaps no greater than its own 63-node gaps: **{sum(monotone)}/15**. This comparison tests search-budget monotonicity; it is distinct from CH29-versus-CH28 improvement.')
for mode in ('fixed','equal_cpu'):
 for budget in ('63','127'):
  x=s['modes'][mode][budget]
  lines.append(f'- `{mode}/{budget}`: {x["parent_tighter_events"]} inherited caps strictly tighter; {x["globally_certified"]}/15 finite-box gap certificates; {x["newton_contractions"]} Newton contractions.')
lines+=['','All three original CH23 ambiguous zero-event cases retain **REFUSED** scientific status. Every numerical bound-gap claim is confined to the *finite root box*. A held-out detection rate or near-optimal objective bound alone cannot validate a causal estimator.',
'', '## CPU caveats',
'', 'The equal-CPU controls match **solving process CPU only**. Independent replay CPU is not constrained; it is deliberately measured and included separately in the engineering-cost comparison. CH29 replay recomputes upper bounds at every internal ancestor, whereas CH28 primarily replayed terminal leaves. This additional cost must not be disguised as an end-to-end equal-CPU win.',
'', '## Verification and reproducibility',
'', 'The original CH23 per-case inputs, CH27 dual matrices, CH28 baseline controls, solver sources, and 160-bit/224-bit directed MPFR primitives have SHA-256 entries in the frozen protocol and package manifest. All case receipts contain a full split tree, parent references, upper-bound modes, feasible incumbents, and verifier outcomes. Adversarial tests reject forged parent references, false certification, bogus partitions, unknown ancestor methods, and infeasible incumbents; display-only cap tampering does not affect replay.',
'', 'Independent replay uses the same mathematical bounding algorithms at higher MPFR precision, not an external formally verified proof assistant. The wider precision and recomputation reduce rounding and cache risk but are not a proof of zero software defects.',
'', '## Next engineering gate',
'', 'Profile the cost of recomputing internal ancestor bounds during independent replay, retain a cryptographically bound partition-replay cache only for efficiency, and add a priority-neutral controlled search comparison. Do not relax the fail-closed scientific gates or promote C14/G25 to production.']
(D/'Engineering_Report_CH_C14_29.md').write_text('\n'.join(lines)+'\n')
print('wrote report',len(lines),'lines')
