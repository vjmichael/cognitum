"""Independently verify exactly 14 new full producer traces, fail closed and journal results."""
from __future__ import annotations
import subprocess,sys,pathlib,json,time,hashlib
E=pathlib.Path('/mnt/data/CH_C14_40_E'); F=pathlib.Path('/mnt/data/CH_C14_40_F')
ARCHIVE=E/'Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'
CASES='''one_event_n160_i00 quasi_separated_n160_i00 quasi_separated_n80_i00 rare_1pct_n160_i00 rare_1pct_n160_i13 rare_1pct_n80_i00 rare_5pct_n160_i00 rare_5pct_n80_i00 zero_balanced_n160_i00 zero_balanced_n80_i00 zero_imbalanced_n160_i00 zero_imbalanced_n160_i05 zero_imbalanced_n160_i07 zero_imbalanced_n80_i00'''.split()
for i,case in enumerate(CASES,1):
 trace=F/'results'/f'{case}_127_original_mpfr_trace.json'; checked=F/'results'/f'{case}_127_audit.json'
 while not trace.exists():
  status=F/'producer_progress.json'
  if status.exists() and json.loads(status.read_text()).get(case,{}).get('status')=='FAIL':raise RuntimeError('Upstream producer FAIL '+case)
  time.sleep(4)
 proc=[sys.executable,str(E/'verify_trace40e.py'),'--archive',str(ARCHIVE),'--trace',str(trace),'--output',str(checked)]
 t=time.monotonic()
 try:r=subprocess.run(proc,capture_output=True,text=True,timeout=2000)
 except subprocess.TimeoutExpired as exc:raise RuntimeError('TIMEOUT '+case) from exc
 (F/'logs'/f'{case}_audit.log').write_text(r.stdout+'\nSTDERR\n'+r.stderr)
 progress=F/'verifier_progress.json'; old=json.loads(progress.read_text()) if progress.exists() else {}
 if r.returncode:
  old[case]={'status':'FAIL','reason':r.stderr[-1000:]};progress.write_text(json.dumps(old,indent=2)+'\n')
  print('INDEPENDENT REFUSAL',i,case,r.stderr[-200:],flush=True);continue
 o=json.loads(checked.read_text());counts=o['checks'];t_obj=json.loads(trace.read_text())
 if o['case']!=case or not o['all_recorded_selected_caps_certified'] or counts['nodes']!=127 or counts['untrusted_caps']!=0 or counts['inherited_caps_certified']!=127 or counts['direct_certified']+counts['coupled_certified']!=127 or o['global_optimality_certified'] or o['scientific_release']!='NO_GO':
  old[case]={'status':'FAIL','reason':'Verifier output safety invariants failed'};progress.write_text(json.dumps(old,indent=2)+'\n');print('SAFETY FAIL',case,flush=True);continue
 old[case]={'status':'PASS_INDEPENDENT_FINITE_BOUND_CAPS','trace_sha256':hashlib.sha256(trace.read_bytes()).hexdigest(),'audit_sha256':hashlib.sha256(checked.read_bytes()).hexdigest(),'counts':counts,'finite_root_gap_certified':o['finite_root_gap_certified'],'wall_seconds':round(time.monotonic()-t,2)}
 progress.write_text(json.dumps(old,indent=2)+'\n')
 print('CERTIFIED',i,'/',len(CASES),case,'nodes',counts['nodes'],'direct',counts['direct_certified'],'coupled',counts['coupled_certified'],'seconds',old[case]['wall_seconds'],flush=True)
print('VERIFIER COMPLETE',sum(v['status']=='PASS_INDEPENDENT_FINITE_BOUND_CAPS' for v in json.loads((F/'verifier_progress.json').read_text()).values()),'/',len(CASES),flush=True)