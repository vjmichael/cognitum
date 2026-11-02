"""CH29 original CH23 case runner; exact input hashes, separate fixed and measured-CPU budgets."""
from __future__ import annotations
import argparse,hashlib,json,sys,time
from pathlib import Path
D=Path(__file__).resolve().parent;BASE=D.parent
sys.path.insert(0,str(D))
from solver29 import solve
from verifier29 import verify
sha=lambda data:hashlib.sha256(data).hexdigest()
p=argparse.ArgumentParser()
p.add_argument('case_id');p.add_argument('--budget',type=int,choices=(63,127),required=True)
p.add_argument('--mode',choices=('fixed','equal_cpu'),default='fixed')
p.add_argument('--solver-only',action='store_true')
a=p.parse_args()
proto=json.loads((D/'frozen_protocol.json').read_text())
if sha((D/'frozen_protocol.json').read_bytes())!=(D/'frozen_protocol.sha256').read_text().split()[0]:raise ValueError('Protocol hash mismatch')
for path,h in proto['solver_source_sha256'].items():
 if sha((D/path).read_bytes())!=h:raise ValueError(f'Source integrity mismatch: {path}')
for path,h in proto['dependency_source_sha256'].items():
 if sha((BASE/path).read_bytes())!=h:raise ValueError(f'Dependency mismatch: {path}')
if a.case_id not in proto['original_case_sha256']:raise ValueError('Unregistered original CH23 dataset')
inpath=BASE/'CH_C14_25'/'inputs'/(a.case_id+'.json')
if sha(inpath.read_bytes())!=proto['original_case_sha256'][a.case_id]:raise ValueError('Original CH23 input changed')
qpath=BASE/'CH_C14_27'/'frozen_duals.json'
if sha(qpath.read_bytes())!=proto['original_dual_sha256']:raise ValueError('Dual matrix changed')
inp=json.loads(inpath.read_text());duals=json.loads(qpath.read_text())[a.case_id]
if inp['bounds']!=proto['original_root_box']:raise ValueError('Root domain changed')
ref=proto['CH28_control'][str(a.budget)][a.case_id]
# Equal CPU comparison uses the *original CH28 solving CPU measurement* as the
# precommitted target. Replay CPU is separately recorded, not charged to solving.
if a.mode=='equal_cpu':
 budget=2*a.budget+1
 cfg={**proto,'node_budget_per_case':budget,'cpu_budget_seconds':ref['solve_cpu_seconds']}
else:
 budget=a.budget;cfg={**proto,'node_budget_per_case':budget}
base=D/'runs'/a.mode/str(a.budget)
for sub in ('certificates','verifications','logs'):(base/sub).mkdir(parents=True,exist_ok=True)
t=time.perf_counter();cpu=time.process_time();cert=solve(inp,cfg,duals)
solve_wall=time.perf_counter()-t;solve_cpu=time.process_time()-cpu
cert['research_case_id']=a.case_id;cert['CH28_comparison_budget']=a.budget;cert['benchmark_mode']=a.mode
cert['frozen_protocol_sha256']=sha((D/'frozen_protocol.json').read_bytes())
cert['original_case_sha256']=proto['original_case_sha256'][a.case_id]
cp=base/'certificates'/(a.case_id+'.json');cp.write_text(json.dumps(cert,indent=2,allow_nan=False)+'\n')
print('SOLVED',a.mode,a.budget,a.case_id,'nodes',len(cert['nodes']),'CPU',round(solve_cpu,3),'gap',round(cert['gap_upper_display'],6),flush=True)
if a.solver_only:sys.exit(0)
t=time.perf_counter();cpu=time.process_time();v=verify(cert,inp,cfg,duals)
replay_wall=time.perf_counter()-t;replay_cpu=time.process_time()-cpu
v.update({'certificate_sha256':sha(cp.read_bytes()),'frozen_protocol_sha256':cert['frozen_protocol_sha256']})
(base/'verifications'/(a.case_id+'.json')).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
rec={'case_id':a.case_id,'mode':a.mode,'budget':a.budget,'target_CPU_seconds_CH28':ref['solve_cpu_seconds'],
     'CH28_reference_gap':ref['gap'],'CH28_reference_status':ref['status'],
     'original_sha256':proto['original_case_sha256'][a.case_id],
     'CH23_digest':inp['original_CH23_identity']['data_digest'],
     'nodes':len(cert['nodes']),'leaves':cert['leaf_count'],'solve_cpu_seconds':round(solve_cpu,4),
     'replay_cpu_seconds':round(replay_cpu,4),'solve_wall_seconds':round(solve_wall,4),
     'replay_wall_seconds':round(replay_wall,4),'gap':v['gap_upper_display'],
     'status':v['replay_status'],'counters':cert['counters'],
     'replay_verified_ancestor_nodes':v['ancestor_caps_recomputed']}
(base/'logs'/(a.case_id+'.json')).write_text(json.dumps(rec,indent=2,allow_nan=False)+'\n')
print('VERIFIED',a.mode,a.budget,a.case_id,'gap',round(v['gap_upper_display'],6),'CPU',round(replay_cpu,3),flush=True)
