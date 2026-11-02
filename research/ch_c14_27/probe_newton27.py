"""Frozen-original-data narrow-box interval-Newton diagnostic, not global pruning claim."""
from __future__ import annotations
from pathlib import Path
from decimal import Decimal
import json,time,hashlib,sys
D=Path(__file__).resolve().parent;BASE=D.parent;C=BASE/'CH_C14_25'
sys.path.insert(0,str(BASE/'CH_C14_24'))
sys.path.insert(0,str(BASE/'CH_C14_26'))
sys.path.insert(0,str(D))
import mpfr_interval as impl
from verified_bnb import logistic_model
from coupled27 import CoupledObjective
from interval_newton27 import contract,interior,replay_check
P=json.loads((D/'frozen_newton_probes.json').read_text())
Q=json.loads((D/'frozen_duals.json').read_text())
assert hashlib.sha256((D/'frozen_duals.json').read_bytes()).hexdigest()==P['dual_matrices_sha256']
results=[]
for c in P['cases']:
 case_id=c['id'];raw=(C/'inputs'/f'{case_id}.json').read_bytes()
 assert hashlib.sha256(raw).hexdigest()==c['original_input_sha256']
 inp=json.loads(raw)
 assert inp['original_CH23_identity']['data_digest']==c['original_digest']
 root=inp['bounds'];rad=Decimal(P['probe_radius_each_axis'])
 if not inp['seeds']:
  results.append({'case_id':case_id,'status':'SKIPPED_NO_ORIGINAL_SEED','original_digest':c['original_digest']});print(case_id,'SKIPPED_NO_ORIGINAL_SEED',flush=True);continue
 seed=inp['seeds'][0]
 box=[[str(Decimal(s)-rad),str(Decimal(s)+rad)] for s in seed]
 if not interior(box,root):
  results.append({'case_id':case_id,'status':'SKIPPED_ROOT_BOUNDARY','original_digest':c['original_digest']});continue
 impl.PRECISION=P['solve_precision_bits']
 model=CoupledObjective(logistic_model(inp['rows']),Q[case_id]);t=time.monotonic()
 receipt=contract(model,box,root);sec=time.monotonic()-t
 replay_status='NOT_APPLICABLE';replay_sec=0
 if receipt['status'] in ('CONTRACTED','NO_STATIONARY'):
  impl.PRECISION=P['replay_precision_bits']
  model=CoupledObjective(logistic_model(inp['rows']),Q[case_id]);t=time.monotonic()
  replay_check(model,box,root,receipt)
  replay_sec=time.monotonic()-t;replay_status='HIGHER_PRECISION_REPLAY_OK'
 rec={'case_id':case_id,'status':receipt['status'],'original_digest':c['original_digest'],
      'box':box,'receipt':receipt,'solve_seconds':round(sec,3),
      'replay_seconds':round(replay_sec,3),'replay_status':replay_status,
      'global_domain_contraction_claim':False}
 results.append(rec)
 print(case_id,rec['status'],receipt.get('volume_ratio_display'),replay_status,flush=True)
out={'milestone':'CH-C14-27','protocol_sha256':hashlib.sha256((D/'frozen_newton_probes.json').read_bytes()).hexdigest(),
     'results':results,'global_certifications':0,'scope':'local narrow-box stationary-root diagnostic'}
(D/'newton_probe_results.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
print('COMPLETE',len(results))
