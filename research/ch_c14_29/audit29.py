"""Read-only audit of CH29 original CH23 cohort, fixed and equal-CPU controls."""
from __future__ import annotations
import argparse,copy,hashlib,json,statistics,sys
from pathlib import Path
D=Path(__file__).resolve().parent;BASE=D.parent
sha=lambda b:hashlib.sha256(b).hexdigest()
proto=json.loads((D/'frozen_protocol.json').read_text())
assert sha((D/'frozen_protocol.json').read_bytes())==(D/'frozen_protocol.sha256').read_text().split()[0]
for p,h in proto['solver_source_sha256'].items():assert sha((D/p).read_bytes())==h,(p,'source altered')
for p,h in proto['dependency_source_sha256'].items():assert sha((BASE/p).read_bytes())==h,(p,'dependency altered')
assert sha((BASE/'CH_C14_28/frozen_protocol.json').read_bytes())==proto['baseline_CH28_protocol_sha256']
for b in (63,127):
 for cid,ref in proto['CH28_control'][str(b)].items():
  f=BASE/'CH_C14_28/runs'/str(b)/'logs'/(cid+'.json')
  assert sha(f.read_bytes())==ref['log_sha256'],('baseline tampering',b,cid)
  assert json.loads(f.read_text())['status']==ref['status']
ids=sorted(proto['original_case_sha256'])
for cid,h in proto['original_case_sha256'].items():
 assert sha((BASE/'CH_C14_25/inputs'/(cid+'.json')).read_bytes())==h,cid
assert sha((BASE/'CH_C14_27/frozen_duals.json').read_bytes())==proto['original_dual_sha256']
parser=argparse.ArgumentParser();parser.add_argument('--replay',action='store_true');parser.add_argument('--mode',choices=('fixed','equal_cpu'),nargs='*',default=['fixed','equal_cpu']);parser.add_argument('--budget',type=int,choices=(63,127),nargs='*',default=[63,127]);args=parser.parse_args()
if args.replay:
 sys.path.insert(0,str(D));from verifier29 import verify
for mode in args.mode:
 for b in args.budget:
  for cid in ids:
   root=D/'runs'/mode/str(b)
   cp=root/'certificates'/(cid+'.json');vp=root/'verifications'/(cid+'.json');lp=root/'logs'/(cid+'.json')
   cert=json.loads(cp.read_text());v=json.loads(vp.read_text());log=json.loads(lp.read_text())
   assert v['certificate_sha256']==sha(cp.read_bytes()),(mode,b,cid,'certificate changed')
   assert cert['original_case_sha256']==proto['original_case_sha256'][cid]
   assert log['CH23_digest']==cert['original_data_identity']['data_digest']
   assert v['nodes_verified']==len(cert['nodes']) and v['ancestor_caps_recomputed']==len(cert['nodes'])
   assert v['partition_verified'] and v['release']=='NO_GO' and v['unbounded_global_claim'] is False
   assert cert['status']=='UNRESOLVED_REFUSE_CERTIFICATION' and v['replay_status']=='REPLAYED_BUT_UNRESOLVED'
   assert abs(v['gap_upper_display']-log['gap'])<1e-10
   assert all(n.get('parent_id') is None if n['id']==0 else isinstance(n.get('parent_id'),int) for n in cert['nodes'])
   if args.replay:
    inp=json.loads((BASE/'CH_C14_25/inputs'/(cid+'.json')).read_text())
    duals=json.loads((BASE/'CH_C14_27/frozen_duals.json').read_text())[cid]
    cfg={**proto,'node_budget_per_case':(b if mode=='fixed' else 2*b+1)}
    if mode=='equal_cpu':cfg['cpu_budget_seconds']=proto['CH28_control'][str(b)][cid]['solve_cpu_seconds']
    rv=verify(cert,inp,cfg,duals)
    assert rv['replay_status']==v['replay_status']
    assert abs(rv['gap_upper_display']-v['gap_upper_display'])<1e-10
  print('PASS',mode,b,len(ids),'original cases',flush=True)
print('AUDIT COMPLETED. Source and baseline hashes intact; no synthetic substitution.',flush=True)
