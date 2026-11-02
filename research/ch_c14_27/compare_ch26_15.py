"""Exploratory same-15-node comparator against original unmodified CH26 methods."""
import sys,json,hashlib,time
from pathlib import Path
D=Path(__file__).resolve().parent;ROOT=D.parent
sys.path.insert(0,str(ROOT/'CH_C14_24'))
sys.path.insert(0,str(ROOT/'CH_C14_26'))
from solver26 import solve
from verifier26 import verify
p=json.loads((ROOT/'CH_C14_26'/'frozen_protocol.json').read_text())
p['node_budget_per_case']=15
cohort=json.loads((D/'frozen_protocol.json').read_text())
id=sys.argv[1];assert id in cohort['case_input_sha256']
f=ROOT/'CH_C14_25'/'inputs'/f'{id}.json'
assert hashlib.sha256(f.read_bytes()).hexdigest()==cohort['case_input_sha256'][id]
input_=json.loads(f.read_text())
t=time.monotonic();cpu=time.process_time()
cert=solve(input_,p)
solve_wall=time.monotonic()-t;solve_cpu=time.process_time()-cpu
t=time.monotonic();cpu=time.process_time()
replay=verify(cert,input_,p,precision_bits=224)
replay_wall=time.monotonic()-t;replay_cpu=time.process_time()-cpu
out={'case_id':id,'status':replay['replay_status'],'gap':replay['gap_upper_display'],
'node_count':len(cert['nodes']),'solve_cpu_seconds':round(solve_cpu,3),
'replay_cpu_seconds':round(replay_cpu,3),'solve_wall_seconds':round(solve_wall,3),
'replay_wall_seconds':round(replay_wall,3),'input_sha256':cohort['case_input_sha256'][id],
'baseline_CH26_unmodified_source_hash':p['source_sha256_at_freeze'],
'benchmark_note':'Exploratory post-CH27 same-node comparison; not independent holdout.'}
(D/'comparator15'/f'{id}.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
print(id,'GAP',out['gap'],'NODES',out['node_count'],'CPU',round(solve_cpu+replay_cpu,2),flush=True)
