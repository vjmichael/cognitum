#!/usr/bin/env python3
"""Fresh independent proof replay of frozen original CH23 case for one past C14 milestone."""
import argparse,json,sys,time,traceback
from pathlib import Path

def main():
 a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True);a.add_argument('--case',required=True);a.add_argument('--phase',required=True);q=a.parse_args()
 base=q.root.resolve();cid=q.case;p=q.phase
 for n in (24,25,26,27,28,29,30,31):sys.path.insert(0,str(base/f'CH_C14_{n}'))
 def load(f):return json.loads(Path(f).read_text(encoding='utf8'))
 original=base/'CH_C14_25'/'inputs'/(cid+'.json')
 if not original.is_file():raise ValueError('Not a frozen original case')
 inp=load(original);t=time.perf_counter();cpu=time.process_time()
 if p=='25':
  from mpfr_interval import checked_threshold,UP,DOWN
  import mpfr_interval
  from verified_bnb import logistic_model,FirthObjective,bound_node,candidate_lower,model_digest
  from verify_certificate import check_tree,validate_model
  from decimal import Decimal
  import hashlib
  d=base/'CH_C14_25';proto=load(d/'frozen_protocol_B.json')
  assert hashlib.sha256((d/'frozen_protocol_B.json').read_bytes()).hexdigest()==(d/'frozen_protocol_B.sha256').read_text().split()[0]
  case=next(c for c in proto['cases'] if c['id']==cid)
  assert hashlib.sha256(original.read_bytes()).hexdigest()==case['exact_input_sha256']
  cert=load(d/'certificates'/(cid+'.json'))
  assert cert['CH25_original_case']['original_digest']==case['original_digest']
  assert logistic_model(inp['rows'])==cert['model']
  validate_model(cert['model']);assert model_digest(cert['model'])==cert['model_sha256']
  mpfr_interval.PRECISION=proto['verifier_precision_bits']
  leaves=check_tree(cert['nodes'],cert['root_box']);model=FirthObjective(cert['model'])
  lower=candidate_lower(model,cert['incumbent']);caps=[bound_node(model,x['box'],curvature=False)[0].hi for x in leaves]
  certified=all(checked_threshold(u,lower,proto['objective_absolute_tolerance']) for u in caps)
  status='VERIFIED_BOUNDED_GAP' if certified else 'REPLAYED_BUT_UNRESOLVED';nodes=len(cert['nodes'])
 elif p=='26':
  from verifier26 import verify
  d=base/'CH_C14_26';cert=load(d/'certificates'/(cid+'.json'));proto=load(d/'frozen_protocol.json')
  receipt=verify(cert,inp,proto,precision_bits=proto['replay_precision_bits']);status=receipt['replay_status'];nodes=len(cert['nodes'])
 elif p=='27':
  from verifier27 import verify
  d=base/'CH_C14_27';cert=load(d/'certificates'/(cid+'.json'));proto=load(d/'frozen_protocol.json');duals=load(d/'frozen_duals.json')[cid]
  receipt=verify(cert,inp,proto,duals);status=receipt['replay_status'];nodes=len(cert['nodes'])
 elif p=='28':
  from verifier28 import verify
  d=base/'CH_C14_28';proto={**load(d/'frozen_protocol.json'),'node_budget_per_case':127}
  cert=load(d/'runs'/'127'/'certificates'/(cid+'.json'));duals=load(base/'CH_C14_27'/'frozen_duals.json')[cid]
  receipt=verify(cert,inp,proto,duals);status=receipt['replay_status'];nodes=len(cert['nodes'])
 else:
  from verifier31 import load_original_case
  inp,proto,duals,archived=load_original_case(cid)
  if p=='29':
   from verifier29 import verify
   cert,_=archived(127);receipt=verify(cert,inp,{**proto,'node_budget_per_case':127},duals)
   status=receipt['replay_status'];nodes=len(cert['nodes'])
  elif p=='30':
   from verifier30 import verify_full
   cert,_=archived(127);receipt=verify_full(cert,inp,{**proto,'node_budget_per_case':127},duals)
   status=receipt['replay_status'];nodes=receipt['nodes_verified']
  elif p=='31':
   from verifier31 import ProgressiveVerifier
   from prefix31 import project_prefix
   cert,_=archived(127);verifier=ProgressiveVerifier();stages=[]
   for count in (7,15,31,63,127):
    projected=project_prefix(cert,count)
    got=verifier.verify_stage(projected,inp,{**proto,'node_budget_per_case':count},duals)
    if got['receipt']['replay_status']!='REPLAYED_BUT_UNRESOLVED':raise AssertionError('Unexpected proof status')
    stages.append(count)
   status='REPLAYED_BUT_UNRESOLVED';nodes=127
  else:raise ValueError('Unexpected phase '+p)
 if status!='REPLAYED_BUT_UNRESOLVED':raise AssertionError('Scientific status changed: '+status)
 out={'PASS':True,'phase':'CH'+p,'case':cid,'nodes':nodes,'bits':224,'scientific':'REPLAYED_BUT_UNRESOLVED',
      'cpu_seconds':round(time.process_time()-cpu,3),'wall_seconds':round(time.perf_counter()-t,3)}
 print('C14_CASE_RESULT='+json.dumps(out,sort_keys=True),flush=True)
 return 0
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as exc:
  print('C14_CASE_ERROR='+str(exc)+'\n'+traceback.format_exc(),file=sys.stderr,flush=True)
  raise SystemExit(1)
