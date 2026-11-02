"""Deterministic root-only baseline/dual comparison on the original CH23 cases."""
import sys,json,hashlib,time
from pathlib import Path
D=Path(__file__).resolve().parent;ROOT=D.parent
for s in (ROOT/'CH_C14_24',ROOT/'CH_C14_26'):sys.path.insert(0,str(s))
sys.path.insert(0,str(D))
from coupled27 import CoupledObjective
from improved_bounds import ImprovedObjective
from verified_bnb import logistic_model,interval_box
import mpfr_interval as impl
P=json.loads((D/'frozen_protocol.json').read_text())
Q=json.loads((D/'frozen_duals.json').read_text())
impl.PRECISION=P['precision_bits'];out=[]
for cid in sorted(P['case_input_sha256']):
  f=ROOT/'CH_C14_25'/'inputs'/f'{cid}.json'
  assert hashlib.sha256(f.read_bytes()).hexdigest()==P['case_input_sha256'][cid]
  inp=json.loads(f.read_text());d=logistic_model(inp['rows'])
  old=ImprovedObjective(d);old.set_tangents(inp['seeds'][:1])
  t=time.process_time();first=old.objective(interval_box(inp['bounds']))[0];old_cpu=time.process_time()-t
  new=CoupledObjective(d,Q[cid]);new.set_tangents(inp['seeds'][:1]);t=time.process_time()
  dualupper=new.coupled_upper(inp['bounds']);new_cpu=time.process_time()-t
  improved=dualupper.cmp(first.hi)<0
  out.append({'case_id':cid,'original_digest':inp['original_CH23_identity']['data_digest'],
     'input_sha256':P['case_input_sha256'][cid],'CH26_root_upper':first.upper_float(),
     'CH27_dual_upper':dualupper.as_float(impl.UP),
     'dual_upper_strictly_tighter':improved,
     'CH26_root_cpu_sec':round(old_cpu,4),'dual_cpu_sec':round(new_cpu,4)})
  print(cid,'dual_tighter',improved,flush=True)
(D/'root_profile.json').write_text(json.dumps({'cases':out,'research_only':True,'methods':'CH26 original vs CH27 coupled original root'},indent=2,allow_nan=False)+'\n')
