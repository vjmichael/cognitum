"""Report only after every frozen original case has completed replay and hash checks."""
from pathlib import Path
import hashlib,json,statistics,math
D=Path(__file__).resolve().parent;P=json.loads((D/'frozen_protocol.json').read_text());C=D.parent/'CH_C14_25'
if not C.exists():C=D.parent/'ch_c14_25'
protocol_digest=hashlib.sha256((D/'frozen_protocol.json').read_bytes()).hexdigest()
if protocol_digest!=(D/'frozen_protocol.sha256').read_text().split()[0]:raise RuntimeError('Protocol was changed')
old={x['id']:x for x in json.loads((C/'study_summary.json').read_text())['all_cases']}
records=[]
for case in P['cases']:
 name=case['id']
 raw=(C/'inputs'/f'{name}.json').read_bytes()
 assert hashlib.sha256(raw).hexdigest()==case['exact_input_sha256']
 cpath=D/'certificates'/f'{name}.json';vpath=D/'verifications'/f'{name}.json';lpath=D/'logs'/f'{name}.json'
 if not cpath.exists() or not vpath.exists() or not lpath.exists():raise RuntimeError('Missing finished case '+name)
 cert=json.loads(cpath.read_bytes()); ver=json.loads(vpath.read_bytes());perf=json.loads(lpath.read_bytes())
 assert cert['original_data_identity']['data_digest']==case['original_digest']
 assert cert['frozen_case_input_sha256']==case['exact_input_sha256']
 assert cert['frozen_protocol_sha256']==protocol_digest
 assert ver['certificate_sha256']==hashlib.sha256(cpath.read_bytes()).hexdigest()
 assert ver['replay_status'] in ('VERIFIED_BOUNDED_GAP','REPLAYED_BUT_UNRESOLVED')
 assert ver['partition_verified'] and ver['objective_bounds_recomputed'] and ver['incumbent_verified']
 assert ver['frozen_case_input_sha256']==case['exact_input_sha256']
 assert perf['nodes']==127
 o=old[name]
 record={**case,
         'status':ver['replay_status'],'model_sha256':ver['model_sha256'],
         'CH25_gap':o['gap_upper_display'],
         'CH26_gap':ver['gap_upper_display'],
         'CH25_root_upper':o['MPFR_root_upper'],
         'CH26_root_upper':cert['nodes'][0]['upper_display'],
         'absolute_gap_reduction':o['gap_upper_display']-ver['gap_upper_display'],
         'relative_gap_reduction_percent':100*(o['gap_upper_display']-ver['gap_upper_display'])/o['gap_upper_display'],
         'nodes':perf['nodes'],'splits':cert['split_count'],'leaves':ver['leaf_count'],
         'solver_wall_seconds':perf['solver_wall_seconds'],'solver_cpu_seconds':perf['solver_cpu_seconds'],
         'verification_wall_seconds':perf['verifier_wall_seconds'],'verification_cpu_seconds':perf['verifier_cpu_seconds'],
         'hessian_calls':cert['hessian_evaluations'],'hessian_bound_tightenings':sum(z['method']=='analytic_hessian_taylor' for z in cert['nodes']),'hessian_leaf_methods':cert['leaf_methods'],
         'certificate_sha256':ver['certificate_sha256']}
 records.append(record)
profiles=json.loads((D/'hessian_profile.json').read_text())
assert len(records)==15 and sum(x['ambiguous'] for x in records)==3
assert all(x['CH26_gap']>=0 for x in records)
summary={
 'milestone':'CH-C14-26','scope':'finite root box only; no unbounded-R3 claim, no scientific release',
 'frozen_protocol_sha256':protocol_digest,'cases':len(records),'original_cases_verified':15,
 'original_ambiguous_cases':3,'solver_nodes_per_case':P['node_budget_per_case'],
 'solver_bits':P['precision_bits'],'replay_bits':P['replay_precision_bits'],
 'objective_gap_tol':P['objective_absolute_tolerance'],
 'certified_bounded_gaps':sum(x['status']=='VERIFIED_BOUNDED_GAP' for x in records),
 'unresolved':sum(x['status']!='VERIFIED_BOUNDED_GAP' for x in records),
 'improved_cases':sum(x['CH26_gap']<x['CH25_gap'] for x in records),
 'hessian_bound_tightenings':sum(x['hessian_bound_tightenings'] for x in records),
 'worsened_cases':sum(x['CH26_gap']>x['CH25_gap'] for x in records),
 'CH25_gap_mean':statistics.mean(x['CH25_gap'] for x in records),
 'CH26_gap_mean':statistics.mean(x['CH26_gap'] for x in records),
 'CH25_gap_median':statistics.median(x['CH25_gap'] for x in records),
 'CH26_gap_median':statistics.median(x['CH26_gap'] for x in records),
 'absolute_gap_reduction_mean':statistics.mean(x['absolute_gap_reduction'] for x in records),
 'median_relative_gap_reduction_percent':statistics.median(x['relative_gap_reduction_percent'] for x in records),
 'solver_cpu_seconds_sum':sum(x['solver_cpu_seconds'] for x in records),
 'verification_cpu_seconds_sum':sum(x['verification_cpu_seconds'] for x in records),
 'solver_wall_seconds_sum_not_concurrent_elapsed':sum(x['solver_wall_seconds'] for x in records),
 'verification_wall_seconds_sum_not_concurrent_elapsed':sum(x['verification_wall_seconds'] for x in records),
 'all_cases':records,'hessian_profile':profiles,'release':'NO_GO'
}
(D/'study_summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
oldlist=[x for x in records if x['index']==0];ambs=[x for x in records if x['ambiguous']]
def fmt(n):return f'{n:.4f}'
lines=[
 '# Cognitum CH-C14-26 — Loewner determinant and analytic-curvature frozen CH23 replay',
 '',
 '**Date:** 2026-11-02 (America/Phoenix) | **Engineering:** verified search replay | **Global/R³ and C14 scientific release:** NO-GO.',
 '',
 '## Scope, frozen inputs and resource plan',
 '',
 'This is research-only development on the original 15 CH23 datasets from CH25: 12 predetermined index-0 bounding cases and three independently recorded zero-event ambiguity cases. No regenerated replacement examples, altered outcome tables, modified CH25 evidence or production Lu/Cognitum/G25 changes. The original CH23 dataset hashes are inherited from CH25 provenance audit; each CH26 input is matched byte for byte to its frozen CH25 input SHA-256 and original CH23 identifier.',
 '',
 f'- Frozen protocol SHA-256: `{protocol_digest}`; protocol was written before any full-cohort solver execution.',
 f'- Root box: `[-10,1] × [-5,5] × [-5,5]`; objective tolerance `{P["objective_absolute_tolerance"]}`.',
 f'- Search nodes/case: CH25 `31` → CH26 `{P["node_budget_per_case"]}` (~{P["node_budget_per_case"]/31:.2f}×); MPFR solving/replay: `{P["precision_bits"]}` / `{P["replay_precision_bits"]}` bits.',
 f'- Max Hessian-assisted node calculations/case: {P["max_hessian_calls_per_case"]}; only narrow boxes with maximum width ≤ {P["hessian_max_root_side_width"]}. The Hessian attempts are optional conservative upper-bound tightenings, independently recomputed on the leaves as needed.',
 '',
 '## Mathematical improvements',
 '',
 'Let each distinct predictor `x_i` represent `n_i` observations, with `w_i(β)=σ(x_iᵀβ)(1−σ(x_iᵀβ))`. On every parameter box B, directed MPFR supplies `0 < w_i(β) ≤ u_i`. Construct `U_B=Σ n_i u_i x_i x_iᵀ`. Then `I(β) ⪯ U_B`; since the information matrices are positive definite, `det I(β) ≤ det U_B`. The MPFR outward-rounded interval determinant of `U_B` is intersected with the old termwise Fisher/Leibniz and Hadamard determinant bounds. The positive Cauchy–Binet reference minor certifies a strictly positive determinant lower bound, even when naïve interval expansion crosses zero.',
 '',
 'The ordinary logistic log-likelihood `ℓ(β)` is globally concave. Therefore each frozen anchor `c` gives a valid tangent upper bound `ℓ(β) ≤ ℓ(c)+∇ℓ(c)ᵀ(β−c)` over the root and every descendant box. Intersecting this with per-observation scalar binomial maxima reduces interval dependence without assuming concavity of Jeffreys-penalized **J** itself.',
 '',
 'For interval curvature, analytic identities are `I_a=Σ n_i w_i(1−2p_i)x_ia x_i x_iᵀ`, `I_ab=Σ n_i w_i[(1−2p_i)^2−2w_i]x_ia x_ib x_i x_iᵀ`; hence `∂_a J = ∂_a ℓ + ½tr(I⁻¹I_a)` and `∂²_ab J = −I[a,b] + ½[tr(I⁻¹ ∂²_ab I)−tr(I⁻¹(∂_b I) I⁻¹(∂_a I))]`. The first term is ordinary logistic information, the traced terms are the Jeffreys correction. This code evaluates the terms using directed MPFR interval sums, interval adjugate, and a positive determinant enclosure. It is more efficient than the CH24 2nd-order interval-jet path but its wide-box curvature enclosures remain loose.',
 '',
 '## Complete frozen-cohort results',
 '',
 f'**{summary["cases"]}/15 cases replayed**; {summary["certified_bounded_gaps"]} finite-box `0.05` global gaps certified; {summary["unresolved"]} remain `REPLAYED_BUT_UNRESOLVED`. The first-order and determinant improvements must not be misread as unbounded-global optimization or causal identification.',
 '',
 '| Original CH23 case | CH25 gap, 31 nodes | CH26 gap, 127 nodes | Gap reduction | Solver CPU (s) | Replay CPU (s) |',
 '|---|---:|---:|---:|---:|---:|'
]
for x in records:
 lines.append(f'| `{x["id"]}` | {fmt(x["CH25_gap"])} | {fmt(x["CH26_gap"])} | {x["relative_gap_reduction_percent"]:.1f}% | {x["solver_cpu_seconds"]:.1f} | {x["verification_cpu_seconds"]:.1f} |')
lines+=['',
 f'- Mean gap: {fmt(summary["CH25_gap_mean"])} → {fmt(summary["CH26_gap_mean"])}; median: {fmt(summary["CH25_gap_median"])} → {fmt(summary["CH26_gap_median"])}.',
 f'- Improvement: {summary["improved_cases"]}/15 smaller than CH25, {summary["worsened_cases"]}/15 larger. Median relative gap reduction: {summary["median_relative_gap_reduction_percent"]:.1f}%.',
 f'- Total cumulative solver CPU seconds (sum across processes): {summary["solver_cpu_seconds_sum"]:.1f}; higher-precision replay CPU seconds: {summary["verification_cpu_seconds_sum"]:.1f}. Because searches ran concurrently, summed wall times are **not** elapsed cohort clock time.',
 '',
 f'- Curvature probes: {sum(x["hessian_calls"] for x in records)} node-level analytic Hessian evaluations; {summary["hessian_bound_tightenings"]} selected as tighter than the direct objective enclosure. Determinant and likelihood bounds drive improvements if this count is zero.',
 '',
 '## Analytic interval curvature timing',
 '',
 'Same original CH23 zero-balanced n=80/160 predictor arrays, 160-bit MPFR, narrow test box `[-4.5,-4.49]×[0,0.01]²`. Both analytic derivative enclosures contain the CH24 jet derivative enclosures at the box midpoint. Measured values are for this single local execution, not a general performance guarantee.',
 '',
 '| Original dataset | CH24 2nd-order jet (s) | CH26 analytic (s) | Speed ratio |',
 '|---|---:|---:|---:|']
for x in profiles:lines.append(f'| `{x["case"]}` | {x["old_seconds"]:.3f} | {x["new_seconds"]:.3f} | {x["speedup"]:.2f}× |')
lines+=['','## Verification and limitations','',
 '- Each original CH25 input SHA-256 and CH23 dataset identity was checked before evaluation. The prior CH25 independent data-reconstruction audit also passed unchanged.',
 '- Solver uses `max_nodes=127`, directed 160-bit MPFR; verifier reads each of the 64 terminal leaves and recomputes all upper bounds at 224-bit MPFR, checks the partition, data/model digest, fixed anchor, feasible lower incumbent, frozen tolerance and source protocol, then independently decides the bound gap. The verifier uses the same mathematical bounding method, so this is reproducible MPFR replay, not a separate formal-verification proof assistant.',
 '- The numerical gap table uses outward double approximations for *display*; only exact MPFR endpoint comparisons determine certification. No time/energy scaling or bound tightening is extrapolated beyond this finite cohort.',
 '- Historical CH23 refusal remains mandatory on all three ambiguous zero-event datasets, irrespective of within-pair objective ranking. No result proves uniqueness or global optimality outside the finite box. Release status stays **NO-GO**.',
 '- Full source, frozen protocol, 15 original-input references, proof partitions, replays, case CPU/wall receipts, adversarial tests and hashes are bundled. Research branch only; main production untouched.',
 '',
 '## Next research gate','',
 'Tighten **likelihood–information coupled bounds** and use affine-Taylor/interval Newton contraction selectively near the strongest leaves. Consider independently established tail bounds on the unbounded coefficient domain. Reuse this exact frozen cohort for comparisons; any new acceptance gate or study cohort must be prospectively frozen before running.',
 '']
(D/'Engineering_Report_CH_C14_26.md').write_text('\n'.join(lines))
(D/'README.md').write_text('''# Cognitum CH-C14-26 — Verified MPFR determinant/Hessian improvement on original CH23 data

Research-only Linux implementation. No changes to CH23/CH24/CH25, production C14/G25 or Lu.

The **same 15 CH23 datasets** are sourced from `../CH_C14_25/inputs/*.json` (immutable) and tied to their original CH23 SHA-256s by `frozen_protocol.json`. No synthetic replacement fixtures used in the benchmark.

## Commands

```bash
cd research/ch_c14_26
OPENBLAS_NUM_THREADS=1 python -m unittest discover -s tests -v
OPENBLAS_NUM_THREADS=1 python run_case.py zero_imbalanced_n160_i05
python compile_results.py
```

Requirements: Python 3.13, `libmpfr.so.6`, NumPy/SciPy needed only to rerun the historical CH23 generator audit. `solver26.py` and `verifier26.py` import the exact CH24 MPFR interval primitives; the original CH25 dataset files are taken from the CH25 archive. The run is bounded to `[-10,1]×[-5,5]×[-5,5]`; certificate replay at 224 bits never promotes an unresolved gap.

- `improved_bounds.py`: Loewner Gram determinant + logistic concave tangent + analytic interval Hessian.
- `solver26.py`, `verifier26.py`: interval branch-and-bound and exact partition/high-precision replay.
- `frozen_protocol.json`: SHA-256 frozen 15 cases, source hashes, precise budget/claim parameters.
- `certificates/`, `verifications/`, `logs/`: saved proof trees and CPU/wall timing receipts (in evidence ZIP).
- `Engineering_Report_CH_C14_26.md`, `study_summary.json`: full held-out baseline comparison and remaining limitations.

**All scientific and unrestricted-global certification remains NO-GO.**
''')
print('REPORT COMPILED:',len(records),'CASES',summary['certified_bounded_gaps'],'GAPS CERTIFIED',summary['improved_cases'],'IMPROVED')
