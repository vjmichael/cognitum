"""Frozen CH28 original-case runner: one budget+case pair, with independent replay."""
from __future__ import annotations
import hashlib,json,sys,time,os,argparse
from pathlib import Path
D=Path(__file__).resolve().parent;BASE=D.parent
sys.path.insert(0,str(D))
from solver28 import solve
from verifier28 import verify
p=argparse.ArgumentParser();p.add_argument('case_id');p.add_argument('--budget',type=int,choices=(63,127),required=True);p.add_argument('--solver-only',action='store_true');args=p.parse_args()
proto=json.loads((D/'frozen_protocol.json').read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()
if sha((D/'frozen_protocol.json').read_bytes())!=(D/'frozen_protocol.sha256').read_text().split()[0]:raise ValueError('Protocol corrupted')
for file,h in proto['solver_source_sha256'].items():
 if sha((D/file).read_bytes())!=h:raise ValueError('Source altered '+file)
for file,h in proto['dependency_source_sha256'].items():
 if sha((BASE/file).read_bytes())!=h:raise ValueError('Dependency altered '+file)
if sha((BASE/'CH_C14_27'/'frozen_protocol.json').read_bytes())!=proto['cohort_CH27_sha256']:raise ValueError('CH27 origin altered')
if args.case_id not in proto['original_case_sha256']:raise ValueError('Unknown original case')
inpath=BASE/'CH_C14_25'/'inputs'/f'{args.case_id}.json'
if sha(inpath.read_bytes())!=proto['original_case_sha256'][args.case_id]:raise ValueError('Original dataset hash mismatch')
qpath=BASE/'CH_C14_27'/'frozen_duals.json'
if sha(qpath.read_bytes())!=proto['original_dual_sha256']:raise ValueError('Original duals altered')
reference=json.loads(inpath.read_text());duals=json.loads(qpath.read_text())[args.case_id]
if reference['bounds']!=proto['original_root_box']:raise ValueError('Coefficient box altered')
run_proto={**proto,'node_budget_per_case':args.budget}
outdir=D/'runs'/str(args.budget);outdir.mkdir(parents=True,exist_ok=True)
for sub in ('certificates','verifications','logs'):(outdir/sub).mkdir(exist_ok=True)
t=time.monotonic();cpu=time.process_time();cert=solve(reference,run_proto,duals)
solved=time.monotonic()-t;solve_cpu=time.process_time()-cpu
cert['research_case_id']=args.case_id;cert['node_budget_used']=args.budget
cert['frozen_protocol_sha256']=sha((D/'frozen_protocol.json').read_bytes())
cert['original_case_sha256']=proto['original_case_sha256'][args.case_id]
cert_path=outdir/'certificates'/f'{args.case_id}.json';cert_path.write_text(json.dumps(cert,indent=2,allow_nan=False)+'\n')
print('SOLVED',args.budget,args.case_id,len(cert['nodes']),f'{solved:.3f}s',f'CPU={solve_cpu:.3f}',f"gap={cert['gap_upper_display']:.6f}",flush=True)
if args.solver_only:sys.exit(0)
t=time.monotonic();cpu=time.process_time();v=verify(cert,reference,run_proto,duals)
replay=time.monotonic()-t;replay_cpu=time.process_time()-cpu
v['certificate_sha256']=sha(cert_path.read_bytes());v['frozen_protocol_sha256']=cert['frozen_protocol_sha256']
(outdir/'verifications'/f'{args.case_id}.json').write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
rec={'case_id':args.case_id,'budget':args.budget,'input_sha256':cert['original_case_sha256'],
     'data_digest':reference['original_CH23_identity']['data_digest'],
     'nodes':len(cert['nodes']),'leaves':len([n for n in cert['nodes'] if 'children' not in n]),
     'solve_wall_seconds':round(solved,4),'solve_cpu_seconds':round(solve_cpu,4),
     'replay_wall_seconds':round(replay,4),'replay_cpu_seconds':round(replay_cpu,4),
     'gap':v['gap_upper_display'],'status':v['replay_status'],'counter':cert['counters'],
     'newton_exclusions':cert['newton_exclusions'],'newton_contractions':cert['newton_contractions']}
(outdir/'logs'/f'{args.case_id}.json').write_text(json.dumps(rec,indent=2,allow_nan=False)+'\n')
print('VERIFIED',args.budget,args.case_id,v['replay_status'],f'gap={v["gap_upper_display"]:.6f}',f'CPU={replay_cpu:.3f}',flush=True)
