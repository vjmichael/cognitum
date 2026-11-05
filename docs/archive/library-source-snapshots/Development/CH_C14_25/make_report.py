import json,hashlib,statistics,pathlib,datetime
P=pathlib.Path(__file__).resolve().parent
p=json.loads((P/'frozen_protocol_B.json').read_text()); CH23=P.parent/'ch_c14_23'
if not CH23.exists(): CH23=P.parent/'recovered_ch23'/'CH_C14_23'
orig=json.loads((CH23/'bounded_results.json').read_text())
first={(x['family'],x['n']):x for x in orig}
rows=[]
for c in p['cases']:
 tag=c['id']; v=json.loads((P/'verifications'/(tag+'.json')).read_text());cert=json.loads((P/'certificates'/(tag+'.json')).read_text());root_file=P/'logs'/(tag+'_root.json')
 log=json.loads((P/'logs'/(tag+'.json')).read_text()); root=json.loads(root_file.read_text()) if root_file.exists() else log.get('root_evidence',log)
 basic=root.get('root_basic_up',root.get('root_basic_upper'));curv=root.get('root_curvature_up',root.get('root_curvature_upper'))
 assert basic==curv
 rows.append({'id':tag,'family':c['family'],'n':c['n'],'index':c['index'],'seed':c['seed'],'events':c['events'],'ambiguous_CH23':c['ambiguous'],'original_digest':c['original_digest'],'input_sha256':c['exact_input_sha256'],'MPFR_root_upper':curv,'root_curvature_tightened':curv<basic,'solver_status':cert['status'],'node_count':len(cert['nodes']),'split_count':cert['split_count'],'leaf_count':cert['leaf_count'],'MPFR_solver_lower_floor':cert['lower_bound_floor_display'],'MPFR_replay_upper_ceil':v['replay_upper_ceil'],'MPFR_replay_lower_floor':v['replay_lower_floor'],'gap_upper_display':v['absolute_gap_upper_display'],'replay_status':v['result'],'baseline_CH23_250_nodes_gap':first[c['family'],c['n']]['upper_minus_incumbent'] if c['index']==0 else None})
assert len(rows)==15 and all(r['node_count']==31 and r['leaf_count']==16 and r['replay_status']=='REPLAYED_BUT_UNRESOLVED' for r in rows)
protosha=hashlib.sha256((P/'frozen_protocol_B.json').read_bytes()).hexdigest()
summary={'milestone':'CH-C14-25','case_count':len(rows),'original_bounding_cases':sum(r['index']==0 for r in rows),'original_ambiguous_cases':sum(r['ambiguous_CH23'] for r in rows),'case_provenance_verified':15,'solver_runs_complete':15,'replays_complete':15,'certified_bounded_gaps':0,'unresolved':15,'curvature_root_tightenings':sum(r['root_curvature_tightened'] for r in rows),'MPFR_solver_precision_bits':160,'MPFR_replay_precision_bits':224,'root_box':p['root_box'],'objective_gap_tolerance':p['objective_absolute_tolerance'],'max_nodes_per_case':p['node_budget_per_case'],'CH23_frozen_protocol_sha256':p['CH23_protocol_sha256'],'CH25_stage_B_frozen_protocol_sha256':protosha,'all_cases':rows,'production_release':'NO_GO','unbounded_global_certifications':0}
(P/'study_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
lines=[
'# CH-C14-25 — Original CH23 datasets through the verified MPFR interval solver',
'', '**2026-11-02 | Engineering benchmark complete (15/15), global bounded gaps unresolved (0/15), production scientific release NO-GO.**',
'', '## Provenance and frozen protocol',
'',f'- Original CH23 frozen protocol SHA-256: `{p["CH23_protocol_sha256"]}`.',
f'- Original CH23 `results.jsonl` SHA-256: `{p["CH23_results_sha256"]}`.',
f'- Stage A original planned protocol SHA-256: `{p["stage_A_SHA256"]}`. Initial full-curvature 80-row run exceeded its execution cap without completing. It produced **no certificate**, and was not counted as a successful case.',
f'- Stage B frozen **before the succeeding 15-case evaluation**: `{protosha}`. Its recorded adaptation retains the CH24 solver and verifier source hashes, 160-bit directed MPFR arithmetic and 0.05 absolute objective-gap tolerance, but uses root-only full interval-curvature evaluation followed by fast directed-MPFR likelihood/determinant enclosure at every branch-and-bound node.',
'- Original binary64 predictor values are exported to **exact decimal strings** via `Decimal.from_float`; generating each dataset with the pinned CH23 code and seed reproduces the original `sha256(X.tobytes()+y.tobytes())` exactly. No replacement data, altered seeds, rounded-short input conversion, or new SCM families.',
'- Root coefficient box: intercept `[-10,1]`; slopes `[-5,5]` and `[-5,5]`; at most 31 full-tree nodes per case (15 splits/16 terminal leaves). All three ambiguous CH23 local maxima pairs were used only as **feasible search seeds** when inside the root box; not as certified global solutions.',
'- Higher-precision verifier at 224-bit MPFR independently checks exact proof-tree covering, witness feasibility and every leaf upper bound against the original signed and hashed input. The verifier still reuses the same bound implementation, so this is **proof replay, not a second formally verified implementation**.',
'', '## Full results (finite-box gaps)',
'', '| Original CH23 dataset | n | index | events | CH23 250-node float gap | CH25 31-node MPFR gap upper | Replay |',
'|---|---:|---:|---:|---:|---:|---|'
]
for r in rows:
 ch23='—' if r['baseline_CH23_250_nodes_gap'] is None else f"{r['baseline_CH23_250_nodes_gap']:.4f}"
 lines.append(f"| {r['family']}{' **(ambiguous)**' if r['ambiguous_CH23'] else ''} | {r['n']} | {r['index']} | {r['events']} | {ch23} | {r['gap_upper_display']:.4f} | unresolved / replay PASS |")
lines += ['', 'All 15 MPFR branch-and-bound computations finished and their 15 exact covering trees were replayed. **No** case met the frozen 0.05 gap threshold. The maximum of terminal upper bounds remains an outer bound; candidate feasible values are lower bounds; the difference is an **upper bound on possible suboptimality**, not a demonstrated difference from the true optimum.',
'', 'Original CH23 floating gaps and these directed-rounding gaps are **not an apples-to-apples performance comparison**: CH23 used 250 node expansions and undirected float64 bounds; CH25 used 15 splits / 31 total nodes and conservative directed MPFR. In particular, larger CH25 gaps do **not** imply worsening statistical inference.',
'', '## Root-curvature and ambiguous-candidate diagnosis',
'', '- 15/15 full interval-curvature **root evaluations executed**, but none improved the broad root objective upper bound beyond the conservative reference-minor/Hadamard method. Exhaustive interval-Hessian curvature at *every* node is presently too expensive at n=80–160; the initial uncompleted full-curvature attempt is disclosed, not silently discarded.',
'- In each of the three original ambiguous zero-event datasets, the two CH23 observed locally validated candidates were within the root box. Directed MPFR **point objective** enclosures at 224 bits strictly confirm their CH23 objective order, but this does not establish that there are only two local maxima or that the higher one is globally optimal.',
'', '| Ambiguous CH23 case | Higher local candidate J | Lower local candidate J | Rounding interval ordering |', '|---|---:|---:|---|']
local=json.loads((P/'verifications'/'ambiguous_local_candidate_MPFR_224bit.json').read_text())
for rec in local:
 hi,lo=rec['ordered_objective_intervals']; lines.append(f"| `{rec['case_id']}` | {hi['obj_lower']:.10f} | {lo['obj_lower']:.10f} | {'strict' if rec['strict_order_confirmed'] else 'not strict'} |")
lines += ['', '## Next engineering and science gates',
'', '1. Replace broad interval determinant cancellation with a stronger analytic Fisher-information enclosure (e.g., SPD-preserving interval Cholesky / expanded Cauchy–Binet lower and upper enclosures, or weighted QR), and tighten per-observation likelihood bounds. Use exact-digest-frozen inputs throughout.',
'2. Derive computationally cheaper **analytic score/Hessian bounds** (rather than second-order forward jets on all 80–160 observations), and test curvature on selective sub-boxes only where information matrices are demonstrably nonsingular over the interval.',
'3. Repeat the **same 15 original cases** with larger node budgets and explicit CPU-time accounting; do not silently change the tolerance, rounded objective, or frozen protocol. An all-`R^3` proof additionally needs rigorous exclusion of coefficients outside the compact root box.',
'4. Preserve CH23 ambiguous-case refusals. A bounded epsilon-gap certificate alone would still not prove unique maximum, calibrated causal interval, design identification, or external R equivalence.',
'', '## Reproduction from Cognitum repository',
'', '```bash', 'cd research/ch_c14_25', 'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m unittest -q audit_ch25.py', '# Run one case using the identical input, frozen stage-B thresholds and bound implementation:', 'python root_B.py zero_imbalanced_n160_i05', 'python solve_B.py zero_imbalanced_n160_i05', 'python replay_B.py zero_imbalanced_n160_i05', '```', '', 'Each case includes immutable input digest, source/model hashes, a complete 31-node partition, feasible incumbent, 224-bit replay receipt and refusal status. Local machine details and original CH24 implementation limitations remain as documented in `../ch_c14_24/README.md`.',
'', '**Scope: Cognitum C14 research only. No production estimator, G25, Lu, DLC, Windows, statistical-reporting, or causal-certification change.**', '']
(P/'Engineering_Report_CH_C14_25.md').write_text('\n'.join(lines))
print('WROTE',len(rows),'cases',len(lines),'lines',protosha)