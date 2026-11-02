"""Read-only CH27 provenance, certificate and optional higher-precision proof audit."""
from __future__ import annotations
import json,hashlib,argparse,statistics,sys
from pathlib import Path
D=Path(__file__).resolve().parent;ROOT=D.parent
sys.path.insert(0,str(ROOT/'CH_C14_24'));sys.path.insert(0,str(ROOT/'CH_C14_26'));sys.path.insert(0,str(D))
from verifier27 import verify
from interval_newton27 import replay_check
from coupled27 import CoupledObjective
from verified_bnb import logistic_model
import mpfr_interval as impl

def sha(b):return hashlib.sha256(b).hexdigest()
def read(path):return json.loads(path.read_text())
def main(replay=False):
 P=read(D/'frozen_protocol.json');Q=read(D/'frozen_duals.json')
 assert sha((D/'frozen_protocol.json').read_bytes())==(D/'frozen_protocol.sha256').read_text().split()[0]
 assert sha((D/'frozen_duals.json').read_bytes())==P['dual_matrices_sha256']
 for p,h in P['source_sha256'].items():assert sha((D/p).read_bytes())==h,p
 for p,h in P['dependency_sha256'].items():assert sha((ROOT/p).read_bytes())==h,p
 assert sha((ROOT/'CH_C14_26'/'frozen_protocol.json').read_bytes())==P['cohort_from_CH26_sha256']
 cases=[]
 for cid, h in sorted(P['case_input_sha256'].items()):
  inpfile=ROOT/'CH_C14_25'/'inputs'/f'{cid}.json'
  assert sha(inpfile.read_bytes())==h,cid
  inp=read(inpfile)
  assert inp['bounds']==P['original_root_box'],cid
  certpath=D/'certificates'/f'{cid}.json';cert=read(certpath)
  v=read(D/'verifications'/f'{cid}.json');run=read(D/'logs'/f'{cid}.json')
  assert cert['original_data_identity']==inp['original_CH23_identity']
  assert cert['frozen_case_sha256']==h
  assert cert['frozen_protocol_sha256']==sha((D/'frozen_protocol.json').read_bytes())
  assert v['certificate_sha256']==sha(certpath.read_bytes()),cid
  assert v['replay_status']==run['status'] and v['replay_status']=='REPLAYED_BUT_UNRESOLVED'
  assert cert['production_release']=='NO_GO' and cert['unbounded_global_claim'] is False
  comparator=read(D/'comparator15'/f'{cid}.json')
  assert comparator['input_sha256']==h
  if replay:
   print('AUDIT_REPLAY_BEGIN',cid,flush=True)
   w=verify(cert,inp,P,Q[cid])
   print('AUDIT_REPLAY_DONE',cid,flush=True)
   assert w['replay_status']==v['replay_status'] and abs(w['gap_upper_display']-v['gap_upper_display'])<1e-10
  cases.append({'id':cid,'family':inp['original_CH23_identity']['family'],'n':inp['original_CH23_identity']['n'],
    'original_index':inp['original_CH23_identity']['index'],'data_digest':inp['original_CH23_identity']['data_digest'],
    'CH26_15_gap':comparator['gap'],'CH27_15_gap':v['gap_upper_display'],
    'CH26_15_cpu_sec':comparator['solve_cpu_seconds']+comparator['replay_cpu_seconds'],
    'CH27_15_cpu_sec':run['solver_cpu_seconds']+run['replay_cpu_seconds'],
    'CH27_newton_calls':cert['newton_calls'],'status':v['replay_status']})
 probes=read(D/'newton_probe_results.json')
 fplan=read(D/'frozen_newton_probes.json')
 assert probes['protocol_sha256']==sha((D/'frozen_newton_probes.json').read_bytes())
 assert len(probes['results'])==len(cases)
 for r in probes['results']:
  cid=r['case_id'];inp=read(ROOT/'CH_C14_25'/'inputs'/f'{cid}.json')
  assert inp['original_CH23_identity']['data_digest']==r['original_digest']
  if r['status']=='CONTRACTED':
   assert r['replay_status']=='HIGHER_PRECISION_REPLAY_OK'
   if replay:
    print('AUDIT_PROBE_BEGIN',cid,flush=True)
    impl.PRECISION=fplan['replay_precision_bits']
    mod=CoupledObjective(logistic_model(inp['rows']),Q[cid])
    replay_check(mod,r['box'],inp['bounds'],r['receipt'])
    print('AUDIT_PROBE_DONE',cid,flush=True)
  if r['status']=='SKIPPED_NO_ORIGINAL_SEED':assert not inp['seeds']
 x=read(D/'root_profile.json')['cases']
 assert len(x)==len(cases)
 for rec in x:
  assert rec['input_sha256']==P['case_input_sha256'][rec['case_id']]
 wins=sum(c['CH27_15_gap']<c['CH26_15_gap']-1e-9 for c in cases)
 ties=sum(abs(c['CH27_15_gap']-c['CH26_15_gap'])<=1e-9 for c in cases)
 losses=len(cases)-wins-ties
 summary={'milestone':'CH-C14-27','source_frozen_protocol_sha256':sha((D/'frozen_protocol.json').read_bytes()),
 'CH23_original_cases':15,'complete_high_precision_replays':len(cases),'certified_global_gaps':0,
 'node_budget_each':P['node_budget_per_case'],'newton_global_search_calls':sum(c['CH27_newton_calls'] for c in cases),
 'equal_node_improved':wins,'equal_node_tied':ties,'equal_node_worsened':losses,
 'CH26_15_mean_gap':statistics.mean(c['CH26_15_gap'] for c in cases),
 'CH27_15_mean_gap':statistics.mean(c['CH27_15_gap'] for c in cases),
 'CH26_15_median_gap':statistics.median(c['CH26_15_gap'] for c in cases),
 'CH27_15_median_gap':statistics.median(c['CH27_15_gap'] for c in cases),
 'CH26_15_cpu_seconds':sum(c['CH26_15_cpu_sec'] for c in cases),
 'CH27_15_cpu_seconds':sum(c['CH27_15_cpu_sec'] for c in cases),
 'root_only_dual_strictly_better':sum(r['dual_upper_strictly_tighter'] for r in x),
 'newton_local_contractions':sum(r['status']=='CONTRACTED' for r in probes['results']),
 'newton_local_no_gain':sum(r['status']=='NO_GAIN' for r in probes['results']),
 'newton_local_missing_seed':sum(r['status']=='SKIPPED_NO_ORIGINAL_SEED' for r in probes['results']),
 'case_results':cases,'scientific_release':'NO_GO',
 'independent_replay_requested':replay,
 'limitations':'Coupled+CH26 bounds share MPFR implementation, not formal proof assistant. No unrestricted global guarantee. Same original cohort already seen, exploratory engineering study.'}
 (D/'study_summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
 print('AUDIT PASS:',len(cases),'original cases, 15 SHA256 bindings, 15 proof records,',wins,'wins',ties,'ties',losses,'losses;',summary['newton_local_contractions'],'Newton contractions, replay',replay)
 return summary
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--replay',action='store_true');args=parser.parse_args();main(args.replay)
