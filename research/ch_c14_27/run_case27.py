"""Research runner for all recorded CH23 source-bound cases; fail closed."""
import sys,time,json,hashlib,os
from pathlib import Path
D=Path(__file__).resolve().parent;ROOT=D.parent;CH25=ROOT/'CH_C14_25'
sys.path.insert(0,str(D))
from solver27 import solve
from verifier27 import verify
case_id=sys.argv[1] if len(sys.argv)>1 else 'zero_balanced_n80_i00'
proto=json.loads((D/'frozen_protocol.json').read_text())
from hashlib import sha256
assert sha256((D/'frozen_duals.json').read_bytes()).hexdigest()==proto['dual_matrices_sha256']
for file,hash_ in proto['source_sha256'].items():assert sha256((D/file).read_bytes()).hexdigest()==hash_,file
for file,hash_ in proto['dependency_sha256'].items():assert sha256((ROOT/file).read_bytes()).hexdigest()==hash_,file
f=CH25/'inputs'/f'{case_id}.json'
if case_id not in proto['case_input_sha256']:raise ValueError('Unfrozen case')
assert sha256(f.read_bytes()).hexdigest()==proto['case_input_sha256'][case_id]
reference=json.loads(f.read_text())
Q=json.loads((D/'frozen_duals.json').read_text())[case_id]
t=time.monotonic();cpu=time.process_time()
result=solve(reference,proto,Q)
result['research_case_id']=case_id
result['frozen_protocol_sha256']=sha256((D/'frozen_protocol.json').read_bytes()).hexdigest()
result['frozen_case_sha256']=proto['case_input_sha256'][case_id]
solver_time=time.monotonic()-t;solver_cpu=time.process_time()-cpu
certpath=D/'certificates'/f'{case_id}.json'
certpath.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print('SOLVED',case_id,round(solver_time,2),'sec gap',result['gap_upper_display'],'nodes',len(result['nodes']),'newton',result['newton_calls'],flush=True)
t=time.monotonic();cpu=time.process_time()
verified=verify(result,reference,proto,Q)
verified['case_id']=case_id
verified['frozen_protocol_sha256']=result['frozen_protocol_sha256']
verified['certificate_sha256']=sha256(certpath.read_bytes()).hexdigest()
verified['replay_seconds']=round(time.monotonic()-t,3)
verified['replay_cpu_seconds']=round(time.process_time()-cpu,3)
(D/'verifications'/f'{case_id}.json').write_text(json.dumps(verified,indent=2,allow_nan=False)+'\n')
record={'case_id':case_id,'input_digest':reference['original_CH23_identity']['data_digest'],
        'node_count':len(result['nodes']),'solver_wall_seconds':round(solver_time,3),
        'solver_cpu_seconds':round(solver_cpu,3),'replay_wall_seconds':verified['replay_seconds'],
        'replay_cpu_seconds':verified['replay_cpu_seconds'],
        'newton_calls':result['newton_calls'],'newton_exclusions':result['newton_exclusions'],
        'newton_contractions':result['newton_contractions'],
        'verified_gap':verified['gap_upper_display'],'status':verified['replay_status']}
(D/'logs'/f'{case_id}.json').write_text(json.dumps(record,indent=2,allow_nan=False)+'\n')
print('VERIFIED',case_id,round(verified['replay_seconds'],2),'sec',verified['replay_status'],'gap',verified['gap_upper_display'],flush=True)
