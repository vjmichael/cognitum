"""CH28 provenance audit and measured summary; optional 224-bit proof replays.

Audit treats cached solver bounds as UNTRUSTED. Replays certify the entire
finite-domain partition with recomputed bound modes, not stored display floats.
"""
from __future__ import annotations
import hashlib,json,statistics,sys,argparse
from pathlib import Path
D=Path(__file__).resolve().parent;BASE=D.parent
sys.path.insert(0,str(D))
from verifier28 import verify
sha=lambda b:hashlib.sha256(b).hexdigest()
read=lambda p:json.loads(p.read_text())

def main(replay=False):
 proto=read(D/'frozen_protocol.json'); pinned=(D/'frozen_protocol.sha256').read_text().split()[0]
 assert sha((D/'frozen_protocol.json').read_bytes())==pinned
 assert sha((BASE/'CH_C14_27'/'frozen_protocol.json').read_bytes())==proto['cohort_CH27_sha256']
 for name,digest in proto['solver_source_sha256'].items():
  assert sha((D/name).read_bytes())==digest,name
 for name,digest in proto['dependency_source_sha256'].items():
  assert sha((BASE/name).read_bytes())==digest,name
 dualpath=BASE/'CH_C14_27'/'frozen_duals.json'
 assert sha(dualpath.read_bytes())==proto['original_dual_sha256']
 duals=read(dualpath)
 entries=[]
 for budget in proto['node_budgets']:
  for cid,original_digest in sorted(proto['original_case_sha256'].items()):
   inp_file=BASE/'CH_C14_25'/'inputs'/f'{cid}.json'
   assert sha(inp_file.read_bytes())==original_digest,cid
   inp=read(inp_file)
   assert inp['bounds']==proto['original_root_box']
   path=D/'runs'/str(budget)
   cf=path/'certificates'/f'{cid}.json';vf=path/'verifications'/f'{cid}.json';lf=path/'logs'/f'{cid}.json'
   cert=read(cf);v=read(vf);log=read(lf)
   assert cert['research_case_id']==cid and cert['node_budget_used']==budget
   assert cert['original_case_sha256']==original_digest
   assert cert['original_data_identity']==inp['original_CH23_identity']
   assert cert['frozen_protocol_sha256']==pinned
   assert v['certificate_sha256']==sha(cf.read_bytes())
   assert log['data_digest']==inp['original_CH23_identity']['data_digest']
   assert len(cert['nodes'])<=budget and cert['leaf_count']==cert['counters']['cached_leaf']
   assert v['partition_verified'] is True and v['release']=='NO_GO' and v['unbounded_global_claim'] is False
   assert (cert['status'],v['replay_status']) in [('UNRESOLVED_REFUSE_CERTIFICATION','REPLAYED_BUT_UNRESOLVED'), ('CERTIFIED_BOUNDED_GAP','VERIFIED_BOUNDED_GAP')]
   assert abs(log['gap']-v['gap_upper_display'])<1e-12
   assert log['counter']==cert['counters']
   if replay:
    again=verify(cert,inp,{**proto,'node_budget_per_case':budget},duals[cid])
    assert again['replay_status']==v['replay_status']
    assert abs(again['gap_upper_display']-v['gap_upper_display'])<1e-10
   entries.append({'case_id':cid,'budget':budget,'family':inp['original_CH23_identity']['family'],
    'n':inp['original_CH23_identity']['n'],'original_index':inp['original_CH23_identity']['index'],
    'original_data_digest':inp['original_CH23_identity']['data_digest'],
    'gap':v['gap_upper_display'],'status':v['replay_status'],
    'nodes':log['nodes'],'leaf_count':v['leaf_count'],
    'solve_cpu_seconds':log['solve_cpu_seconds'],'replay_cpu_seconds':log['replay_cpu_seconds'],
    'cpu_total_seconds':round(log['solve_cpu_seconds']+log['replay_cpu_seconds'],4),
    'solve_wall_seconds':log['solve_wall_seconds'],'replay_wall_seconds':log['replay_wall_seconds'],
    'coupled_calls':cert['counters']['coupled'],'direct_calls':cert['counters']['direct'],
    'cached_leaf_uses':cert['counters']['cached_leaf'],
    'newton_calls':cert['counters']['newton'],'newton_contractions':cert['newton_contractions'],
    'newton_exclusions':cert['newton_exclusions']})
 summaries={}
 for budget in proto['node_budgets']:
  es=[x for x in entries if x['budget']==budget]
  summaries[str(budget)]={'cases':len(es),'mean_gap':statistics.mean(x['gap'] for x in es),
   'median_gap':statistics.median(x['gap'] for x in es),'maximum_gap':max(x['gap'] for x in es),
   'certified':sum(x['status']=='VERIFIED_BOUNDED_GAP' for x in es),
   'solve_cpu_seconds':round(sum(x['solve_cpu_seconds'] for x in es),3),
   'replay_cpu_seconds':round(sum(x['replay_cpu_seconds'] for x in es),3),
   'cached_leaf_uses':sum(x['cached_leaf_uses'] for x in es),
   'coupled_calls':sum(x['coupled_calls'] for x in es),
   'direct_calls':sum(x['direct_calls'] for x in es),
   'newton_contractions':sum(x['newton_contractions'] for x in es)}
 summary={'milestone':'CH-C14-28','protocol_sha256':pinned,
  'original_CH23_datasets':len(proto['original_case_sha256']),
  'completed_replayed_runs':len(entries),'budgets':summaries,
  'case_results':entries,'scientific_release':'NO_GO',
  'unbounded_global_certifications':0,
  'limitations':'Finite-box 0.05 objective-gap research, 160-bit MPFR + 224-bit recomputation; prior already-seen CH23 datasets; no causal or production claims. Equal-budget baseline not inferred from the 15-node CH27 study.'}
 (D/'study_summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
 print('CH28 AUDIT PASS',len(entries),'runs; full replay',replay,'summary',summaries,flush=True)
 return summary

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--replay',action='store_true');a=p.parse_args();main(replay=a.replay)