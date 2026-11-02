import hashlib,json,sys,time,traceback
from pathlib import Path
D=Path(__file__).resolve().parent;C=D.parent/'CH_C14_25'
if not C.exists():C=D.parent/'ch_c14_25'
P=json.loads((D/'frozen_protocol.json').read_bytes())
assert hashlib.sha256((D/'frozen_protocol.json').read_bytes()).hexdigest()==(D/'frozen_protocol.sha256').read_text().split()[0]
assert hashlib.sha256((C/'frozen_protocol_B.json').read_bytes()).hexdigest()==P['CH25_frozen_protocol_B_sha256']
for n,sha in P['source_sha256_at_freeze'].items():assert hashlib.sha256((D/n).read_bytes()).hexdigest()==sha,n
if len(sys.argv)!=2:raise SystemExit('Usage run_case.py case_id')
case=next((x for x in P['cases'] if x['id']==sys.argv[1]),None)
if case is None:raise ValueError('Case not in frozen cohort')
blob=(C/'inputs'/f'{case["id"]}.json').read_bytes()
assert hashlib.sha256(blob).hexdigest()==case['exact_input_sha256']
inp=json.loads(blob)
assert inp['original_CH23_identity']['data_digest']==case['original_digest']
assert inp['original_CH23_identity']['seed']==case['seed']
assert inp['bounds']==P['root_box']
from solver26 import solve
from verifier26 import verify
output=D/'certificates'/f'{case["id"]}.json';resultfile=D/'verifications'/f'{case["id"]}.json';logfile=D/'logs'/f'{case["id"]}.json'
t=time.monotonic();cpu=time.process_time()
cert=solve(inp,P)
swall=time.monotonic()-t;scpu=time.process_time()-cpu
cert['research_case_id']=case['id'];cert['frozen_protocol_sha256']=hashlib.sha256((D/'frozen_protocol.json').read_bytes()).hexdigest();cert['frozen_case_input_sha256']=case['exact_input_sha256']
output.write_text(json.dumps(cert,indent=2,allow_nan=False)+'\n')
print('SOLVE',case['id'],round(swall,2),'sec gap',round(cert['gap_upper_display'],6),'nodes',len(cert['nodes']),'hess',cert['hessian_evaluations'],flush=True)
t=time.monotonic();cpu=time.process_time()
v=verify(cert,inp,P,precision_bits=P['replay_precision_bits'])
vwall=time.monotonic()-t;vcpu=time.process_time()-cpu
v['case_id']=case['id'];v['frozen_protocol_sha256']=cert['frozen_protocol_sha256'];v['frozen_case_input_sha256']=case['exact_input_sha256'];v['certificate_sha256']=hashlib.sha256(output.read_bytes()).hexdigest();v['elapsed_seconds']=round(vwall,3);v['cpu_seconds']=round(vcpu,3)
resultfile.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
ref=next(c['gap_upper_display'] for c in json.loads((C/'study_summary.json').read_text())['all_cases'] if c['id']==case['id'])
record={'case_id':case['id'],'status':v['replay_status'],'original_digest':case['original_digest'],'max_nodes':P['node_budget_per_case'],'nodes':len(cert['nodes']),'hessian_evaluations':cert['hessian_evaluations'],'solver_wall_seconds':round(swall,3),'solver_cpu_seconds':round(scpu,3),'verifier_wall_seconds':round(vwall,3),'verifier_cpu_seconds':round(vcpu,3),'gap':v['gap_upper_display'],'CH25_gap':ref}
logfile.write_text(json.dumps(record,indent=2,allow_nan=False)+'\n')
print('REPLAY',case['id'],round(vwall,2),'sec',v['replay_status'],'gap',round(v['gap_upper_display'],6),flush=True)
