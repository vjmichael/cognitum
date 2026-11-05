import pathlib,json,hashlib,sys,time
HERE=pathlib.Path(__file__).resolve().parent;CH24=HERE.parent/'ch_c14_24'
if not CH24.exists():CH24=pathlib.Path('/mnt/data/CH_C14_24');sys.path.insert(0,str(CH24))
from verified_bnb import logistic_model,FirthObjective,bound_node
import mpfr_interval
pbytes=(HERE/'frozen_protocol_B.json').read_bytes();p=json.loads(pbytes)
assert hashlib.sha256(pbytes).hexdigest()==(HERE/'frozen_protocol_B.sha256').read_text().split()[0]
tag=sys.argv[1];case=next(c for c in p['cases'] if c['id']==tag)
blob=(HERE/'inputs'/f'{tag}.json').read_bytes();assert hashlib.sha256(blob).hexdigest()==case['exact_input_sha256']
inp=json.loads(blob);t=time.monotonic();mpfr_interval.PRECISION=p['precision_bits']
m=FirthObjective(logistic_model(inp['rows']))
base,bs=bound_node(m,inp['bounds'],False)
cur,method=bound_node(m,inp['bounds'],True)
out={'case_id':tag,'original_digest':case['original_digest'],'root_basic_upper':base.upper_float(),'root_curvature_upper':cur.upper_float(),'root_curvature_method':method,'elapsed_seconds':round(time.monotonic()-t,3)}
(HERE/'logs'/f'{tag}_root.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out),flush=True)