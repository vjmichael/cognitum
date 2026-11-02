import pathlib,json,hashlib,sys,time
HERE=pathlib.Path(__file__).resolve().parent;CH24=HERE.parent/'ch_c14_24'
if not CH24.exists():CH24=pathlib.Path('/mnt/data/CH_C14_24');sys.path.insert(0,str(CH24))
from verified_bnb import solve
pbytes=(HERE/'frozen_protocol_B.json').read_bytes();p=json.loads(pbytes)
assert hashlib.sha256(pbytes).hexdigest()==(HERE/'frozen_protocol_B.sha256').read_text().split()[0]
tag=sys.argv[1];case=next(c for c in p['cases'] if c['id']==tag)
blob=(HERE/'inputs'/f'{tag}.json').read_bytes();assert hashlib.sha256(blob).hexdigest()==case['exact_input_sha256']
inp=json.loads(blob);start=time.monotonic()
cert=solve(inp['rows'],inp['bounds'],tol=p['objective_absolute_tolerance'],max_nodes=p['node_budget_per_case'],precision_bits=p['precision_bits'],seeds=inp['seeds'],use_curvature=False)
cert['CH25_original_case']={'case_id':tag,'original_digest':case['original_digest'],'frozen_input_sha256':case['exact_input_sha256'],'protocol_B_sha256':hashlib.sha256(pbytes).hexdigest(),'original_CH23_ambiguous':case['ambiguous'],'mode':'direct_MPFR_bnb_with_curvature_root_probe'}
(HERE/'certificates'/f'{tag}.json').write_text(json.dumps(cert,indent=2,allow_nan=False)+'\n')
out={'case_id':tag,'solver_status':cert['status'],'nodes':len(cert['nodes']),'leaves':cert['leaf_count'],'lower':cert['lower_bound_floor_display'],'upper':cert['upper_bound_ceil_display'],'elapsed_seconds':round(time.monotonic()-start,3)}
(HERE/'logs'/f'{tag}_solve.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out),flush=True)
