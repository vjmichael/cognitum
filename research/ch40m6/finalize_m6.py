"""Combine already completed original-case research results; no re-generation."""
import json, hashlib
from pathlib import Path
from fractions import Fraction as F
ROOT=Path(__file__).resolve().parent
PARENT=ROOT.parent
OUT=ROOT/'accepted'
OUT.mkdir(exist_ok=True)
pins=json.loads((PARENT/'CH40K/CH40K_ACCEPTANCE.json').read_text())
orig=json.loads((PARENT/'CH40L/CH40L_FRONTIER.json').read_text())
index={x['case']:x for x in orig['cases']}
rows=[]
for p in pins['cases']:
 case=p['case']; candidates=[ROOT/d/(case+'.json') for d in ['full15_v2','missing_batch_a','missing_batch_b']]
 available=[x for x in candidates if x.exists()]
 if len(available)!=1:raise ValueError('duplicate/missing accepted source '+case)
 data=json.loads(available[0].read_text())
 if data['trace_sha256']!=p['trace_sha256']:raise ValueError('original pin mismatch')
 for key in ['flint','legacy']:
  arm=data[key]
  if arm['audit']['status']!='PASS_INDEPENDENT_FULL_CHILD_BOUND_RECOMPUTATION' or arm['cpu_budget_requested']!=.25 or arm['split_count']>12 or arm['scientific_release']!='NO_GO':raise ValueError('inadmissible result '+case)
  if arm['audit']['verified_children']!=2*arm['split_count']:raise ValueError('partial proof')
 if data['legacy']['initial_upper']!=data['flint']['initial_upper']:raise ValueError('different starting state')
 lower=F(index[case]['feasible_lower_outward55']); gaps={a:float(F(data[a]['new_upper'])-lower) for a in ('legacy','flint')}
 if min(gaps.values())<=.05:raise ValueError('unreviewed global tolerance closure')
 row={'case':case,'file_sha256':hashlib.sha256(available[0].read_bytes()).hexdigest(),
      'trace_sha256':p['trace_sha256'],
      'mpfr_splits':data['legacy']['split_count'],'flint_splits':data['flint']['split_count'],
      'mpfr_new_child_checks':data['legacy']['audit']['verified_children'],'flint_new_child_checks':data['flint']['audit']['verified_children'],
      'mpfr_search_cpu':data['legacy']['cpu_seconds'],'flint_search_cpu':data['flint']['cpu_seconds'],
      'mpfr_upper_drop':data['mpfr_upper_decrease_float'],'flint_upper_drop':data['flint_upper_decrease_float'],
      'mpfr_remaining_gap':gaps['legacy'],'flint_remaining_gap':gaps['flint'],
      'flint_strictly_more_progress':data['flint_upper_decrease_float']>data['mpfr_upper_decrease_float']+1e-10,
      'tied_at_precision':abs(data['flint_upper_decrease_float']-data['mpfr_upper_decrease_float'])<=1e-10}
 rows.append(row); (OUT/(case+'.json')).write_bytes(available[0].read_bytes())
result={'protocol':'CH40-M6-COMPARATIVE-SEARCH-CPU-BUDGET-15-FROZEN-V1',
        'input_case_count':len(rows),'expected_original_case_count':15,
        'starting_frontier':'same independently recorded signed CH40J terminal 64 per case; stored source SHA pins',
        'search_cpu_budget_requested_per_case_per_arm_seconds':.25,'max_splits_per_arm':12,
        'total_flint_splits':sum(x['flint_splits'] for x in rows),
        'total_mpfr_splits':sum(x['mpfr_splits'] for x in rows),
        'total_reverified_children':sum(x['mpfr_new_child_checks']+x['flint_new_child_checks'] for x in rows),
        'total_flint_search_cpu_seconds':sum(x['flint_search_cpu'] for x in rows),
        'total_mpfr_search_cpu_seconds':sum(x['mpfr_search_cpu'] for x in rows),
        'strict_flint_progress_wins':sum(x['flint_strictly_more_progress'] for x in rows),
        'ties_at_1e_minus10':sum(x['tied_at_precision'] for x in rows),
        'any_finite_root_gap_closed':False,'all_origins_pinned':True,
        'important_caveat':'Distinct bound mathematics: FLINT Gram PSD vs MPFR direct Hadamard; not an isolated library speed A/B. Per-arm CPU ceiling can be overshot by last complete split; FLINT max12 splits is sometimes reached early. Independent audits consume additional CPU outside search budget. Whole-process CPU is not matched. Test cases original but not held-out.',
        'claim_scope':'research-only improvement of frozen finite-root proof frontier using separately rationally checked child bounds; no unrestricted global optimum',
        'scientific_release':'NO_GO','rows':rows}
(OUT/'CH40M6_ALL15_SEARCH_COMPARISON.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
