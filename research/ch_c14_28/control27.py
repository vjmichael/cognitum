"""Exploratory *equal-budget* CH27 baseline on original CH23 case(s).
CH27 source and original 15-node receipts unchanged. This is a new run.
"""
import sys,os,json,time,pathlib
D=pathlib.Path(__file__).resolve().parent;BASE=D.parent
sys.path.insert(0,str(BASE/'CH_C14_27'))
from solver27 import solve
from verifier27 import verify
ids=['zero_balanced_n80_i00']
for budget in (63,127):
 for cid in ids:
  p=json.loads((BASE/'CH_C14_27'/'frozen_protocol.json').read_text());p['node_budget_per_case']=budget
  inp=json.loads((BASE/'CH_C14_25'/'inputs'/f'{cid}.json').read_text())
  Q=json.loads((BASE/'CH_C14_27'/'frozen_duals.json').read_text())[cid]
  t=time.monotonic();cpu=time.process_time();c=solve(inp,p,Q)
  elapsed=time.monotonic()-t;solve_cpu=time.process_time()-cpu
  print('CH27 CONTROL SOLVED',cid,budget,'gap',c['gap_upper_display'],'cpu',solve_cpu,flush=True)
  t=time.monotonic();cpu=time.process_time();v=verify(c,inp,p,Q)
  rcpu=time.process_time()-cpu
  obj={'original_case':cid,'node_budget':budget,'original_CH27_solver_source':'unchanged','solve_cpu_seconds':solve_cpu,'replay_cpu_seconds':rcpu,'gap':v['gap_upper_display'],'status':v['replay_status'],'nodes':len(c['nodes'])}
  path=D/'baseline_equal_budget';path.mkdir(exist_ok=True)
  (path/f'{cid}_{budget}.json').write_text(json.dumps(obj,indent=2)+'\n')
  print('CH27 CONTROL VERIFIED',cid,budget,'gap',v['gap_upper_display'],'cpu',rcpu,flush=True)
