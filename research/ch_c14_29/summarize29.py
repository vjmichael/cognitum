"""Compute paired CH28/CH29 numbers from original per-case measured receipts."""
from __future__ import annotations
import json,statistics
from pathlib import Path
D=Path(__file__).resolve().parent
p=json.loads((D/'frozen_protocol.json').read_text())
ids=sorted(p['original_case_sha256'])
res={'milestone':'CH-C14-29','cohort_count':15,'original_input_sha256':p['original_case_sha256'],
     'protocol_sha256':(D/'frozen_protocol.sha256').read_text().split()[0],
     'comparison':'CH28 archived frozen CPU and proof receipts; same original 15 CH23 datasets', 'modes':{}}
for mode in ('fixed','equal_cpu'):
 res['modes'][mode]={}
 for b in (63,127):
  records=[json.loads((D/'runs'/mode/str(b)/'logs'/(cid+'.json')).read_text()) for cid in ids]
  gaps=[x['gap'] for x in records]
  compare=[p['CH28_control'][str(b)][cid]['gap'] for cid in ids]
  ratios=[x['solve_cpu_seconds']/x['target_CPU_seconds_CH28'] for x in records]
  fixed_tests=[x['gap']<=base+1e-9 for x,base in zip(records,compare)]
  result={'n_cases':len(records),'node_budget_reference_CH28':b,
    'mean_gap':statistics.mean(gaps),'median_gap':statistics.median(gaps),'max_gap':max(gaps),
    'baseline_CH28_mean_gap':statistics.mean(compare),
    'improved':sum(x<y-1e-9 for x,y in zip(gaps,compare)),'tied':sum(abs(x-y)<=1e-9 for x,y in zip(gaps,compare)),
    'worsened':sum(x>y+1e-9 for x,y in zip(gaps,compare)),
    'solve_cpu_total_seconds':round(sum(x['solve_cpu_seconds'] for x in records),3),
    'replay_cpu_total_seconds':round(sum(x['replay_cpu_seconds'] for x in records),3),
    'baseline_CH28_solve_cpu_total_seconds':round(sum(x['target_CPU_seconds_CH28'] for x in records),3),
    'matched_within_10pct':sum(abs(v-1)<=0.1 for v in ratios),'max_cpu_overshoot_ratio':max(ratios),
    'nodes_executed':sum(x['nodes'] for x in records),
    'parent_tighter_events':sum(x['counters']['parent_cap_tighter'] for x in records),
    'newton_contractions':sum(x['counters']['contractions'] for x in records),
    'globally_certified':sum(x['status']=='VERIFIED_BOUNDED_GAP' for x in records),
    'case_results':records}
  res['modes'][mode][str(b)]=result
  print(mode,b,'gaps',round(result['mean_gap'],5),'CH28',round(result['baseline_CH28_mean_gap'],5),
   'improved/tied/worse',result['improved'],result['tied'],result['worsened'],
   'cpu',round(result['solve_cpu_total_seconds'],2),'matched',result['matched_within_10pct'],'inherit',result['parent_tighter_events'])
(D/'study_summary.json').write_text(json.dumps(res,indent=2,sort_keys=True,allow_nan=False)+'\n')
