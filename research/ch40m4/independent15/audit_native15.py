#!/usr/bin/env python3
"""Independently re-check displayed IBEX candidate points on immutable original cases.
Do NOT promote any IBEX global interval without a separate global proof verifier.
"""
from pathlib import Path
from fractions import Fraction as F
import hashlib, json,re,sys,time,signal,zipfile
HERE=Path(__file__).resolve().parent
sys.path[:0]=['/mnt/data/CH40M3/site','/mnt/data/CH40M2/source']
from frozen40m2 import load_cases,validated_candidate
from ibex_model import ibex_text
from flint_arb_backend import arb_point
from frozen40m2 import point_lower

CASES=load_cases(Path('/mnt/data/CH40K/traces'),Path('/mnt/data/CH40K/CH40K_ACCEPTANCE.json'))
REPORT=json.loads(Path('/mnt/data/ch40m4_ibex/ibexopt15_soplex_canonical.json').read_text())
ORIG={v['case']:v for v in json.loads(Path('/mnt/data/CH40L/CH40L_FRONTIER.json').read_text())['cases']}
ZIP=zipfile.ZipFile('/mnt/data/Cognitum_CH40M2_Standard_Solver_Adapters_All15_2026-11-03.zip')
PAT=re.compile(r'x\* in\s*\(\s*\[([^,]+),\s*([^\]]+)\]\s*;\s*\[([^,]+),\s*([^\]]+)\]\s*;\s*\[([^,]+),\s*([^\]]+)\]\s*\)',re.S)
OUT=HERE/'IBEX15_INDEPENDENT_AUDIT.json'
def wall(sig,frame):raise TimeoutError('independent rational check over 18s')
signal.signal(signal.SIGALRM,wall)
summary={'protocol':'CH40-M.4-FROZEN-15-IBEX-SOPLEX-POINT-INDEPENDENT-AUDIT-V1',
 'claim_scope':'Native IBEX solver output is NOT an independently certified global bound. Only exact displayed point re-evaluation + original interval overlap triage.',
 'frozen_input_sha256_pins':'ALL_15_VERIFIED_BY_LOADER', 'scientific_release':'NO_GO','cases':[]}
if OUT.exists():
 saved=json.loads(OUT.read_text())
 summary['cases']=saved.get('cases',[])
 completed={row['case'] for row in summary['cases']}
else:completed=set()
for case in CASES:
 name=case.name
 if name in completed:continue
 run=REPORT['cases'][name]; model=Path('/mnt/data/ch40m4_ibex/models')/(name+'.bch')
 full=ibex_text(case).encode(); frozen=ZIP.read('ibex_models/'+model.name)
 if full!=frozen or full!=model.read_bytes() or hashlib.sha256(full).hexdigest()!=run['model_sha256']:raise ValueError('Model not identical '+name)
 lo,hi=run['interval_reported']; old=ORIG[name]; oldL=F(old['feasible_lower_outward55']);oldU=F(old['finite_root_upper_outward55'])
 compatible=max(-F(str(hi)),oldL) <= min(-F(str(lo)),oldU)
 m=PAT.search(run['native_output_tail'])
 if not m:raise ValueError('Missing point '+name)
 point=[float(m.group(i)) for i in (1,3,5)]
 if not validated_candidate(case,point):raise ValueError('Infeasible displayed point '+name)
 start=time.monotonic()
 record={'case':name,'trace_sha256':case.source_sha256,'model_sha256':run['model_sha256'],
  'native_status':run['terminal'],'native_exit':run['exit'], 'ibex_reported_min_interval':run['interval_reported'],
  'ibex_reported_gap':run['gap_reported'],
  'original_verified_firth_max_interval':[str(oldL),str(oldU)],
  'solver_interval_overlaps_original_proof':compatible,
  'point_scope':'RE-EVALUATED_DISPLAYED_DECIMAL_POINT; not an exact readout of IBEX internal binary coordinates',
  'point_float_display':point,'independent_global_certificate':False}
 try:
  arb=arb_point(case,point,precision=256)
  signal.alarm(18)
  try:ref=point_lower(case,point,Path('/mnt/data/CH40J/source'))
  finally:signal.alarm(0)
  al,ah=F(arb['lower']),F(arb['upper'])
  overlap=max(al,ref.lo)<=min(ah,ref.hi)
  rec_lb=max(al,ref.lo)
  record.update({'point_status':'INDEPENDENT_POINT_INTERVAL_OVERLAP' if overlap else 'REJECTED_POINT_DISJOINT',
                 'arb_rational_point_overlap':overlap,
                 'arb_lower_exact':str(al),'arb_upper_exact':str(ah),
                 'rational_lower_exact':str(ref.lo),'rational_upper_exact':str(ref.hi),
                 'point_lower_beats_original_frozen_incumbent':bool(rec_lb>oldL) if overlap else None,
                 'candidate_firth_objective_lower_approx':float(rec_lb) if overlap else None,
                 'original_feasible_lower_approx':float(oldL)})
 except Exception as exc:
  signal.alarm(0);record.update({'point_status':'UNRESOLVED','point_error':repr(exc)[:300]})
 record['audit_wall_seconds']=round(time.monotonic()-start,3)
 summary['cases'].append(record)
 OUT.write_text(json.dumps(summary,indent=2)+'\n')
 print(f'{name}: {record["point_status"]}, stronger point? {record.get("point_lower_beats_original_frozen_incumbent")}, {record["audit_wall_seconds"]}s',flush=True)
summary.update({'cases_count':len(summary['cases']),
 'point_matches':sum(r['point_status']=='INDEPENDENT_POINT_INTERVAL_OVERLAP' for r in summary['cases']),
 'solver_exits_zero':sum(r['native_exit']==0 for r in summary['cases']),
 'solver_timelimits':sum(r['native_status']=='TIME_LIMIT' for r in summary['cases']),
 'solver_gaps_le_005':sum(r['ibex_reported_gap']<=.05 for r in summary['cases']),
 'solver_interval_overlaps_original_proof_count':sum(r['solver_interval_overlaps_original_proof'] for r in summary['cases']),
 'ibex_display_points_better_than_frozen_count':sum(r.get('point_lower_beats_original_frozen_incumbent') is True for r in summary['cases'])})
OUT.write_text(json.dumps(summary,indent=2)+'\n')
print('SUMMARY',json.dumps({k:v for k,v in summary.items() if k not in ('cases','claim_scope')},indent=2),flush=True)
