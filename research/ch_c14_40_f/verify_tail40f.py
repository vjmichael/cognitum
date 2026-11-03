"""Independently replay the final 6 full original CH29 producer traces in a disjoint audit shard."""
from __future__ import annotations
import subprocess,sys,pathlib,json,time,hashlib
E=pathlib.Path('/mnt/data/CH_C14_40_E');F=pathlib.Path('/mnt/data/CH_C14_40_F')
ARCHIVE=E/'Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'
CASES='''zero_balanced_n160_i00 zero_balanced_n80_i00 zero_imbalanced_n160_i00 zero_imbalanced_n160_i05 zero_imbalanced_n160_i07 zero_imbalanced_n80_i00'''.split()
progress=F/'verifier_tail_progress.json';old=json.loads(progress.read_text()) if progress.exists() else {}
for i,case in enumerate(CASES,1):
 trace=F/'results'/f'{case}_127_original_mpfr_trace.json';checked=F/'results'/f'{case}_127_audit.json'
 assert trace.exists()
 p=[sys.executable,str(E/'verify_trace40e.py'),'--archive',str(ARCHIVE),'--trace',str(trace),'--output',str(checked)]
 t=time.monotonic();r=subprocess.run(p,capture_output=True,text=True,timeout=2200)
 (F/'logs'/f'{case}_audit.log').write_text(r.stdout+'\nSTDERR\n'+r.stderr)
 if r.returncode:
  old[case]={'status':'FAIL','reason':r.stderr[-1000:]};progress.write_text(json.dumps(old,indent=2)+'\n')
  print('INDEPENDENT REFUSAL',i,case,r.stderr[-250:],flush=True);continue
 o=json.loads(checked.read_text());c=o['checks']
 if o['case']!=case or not o['all_recorded_selected_caps_certified'] or c['nodes']!=127 or c['untrusted_caps']!=0 or c['inherited_caps_certified']!=127 or c['direct_certified']+c['coupled_certified']!=127 or o['global_optimality_certified'] or o['scientific_release']!='NO_GO':
  old[case]={'status':'FAIL','reason':'Independent checker acceptance invariants mismatch'};progress.write_text(json.dumps(old,indent=2)+'\n');print('SAFETY REFUSAL',case,flush=True);continue
 old[case]={'status':'PASS_INDEPENDENT_FINITE_BOUND_CAPS','trace_sha256':hashlib.sha256(trace.read_bytes()).hexdigest(),'audit_sha256':hashlib.sha256(checked.read_bytes()).hexdigest(),'counts':c,'finite_root_gap_certified':o['finite_root_gap_certified'],'wall_seconds':round(time.monotonic()-t,2)}
 progress.write_text(json.dumps(old,indent=2)+'\n')
 print('TAIL CERTIFIED',i,'/',len(CASES),case,'direct',c['direct_certified'],'coupled',c['coupled_certified'],'seconds',old[case]['wall_seconds'],flush=True)
print('TAIL DONE',sum(v['status']=='PASS_INDEPENDENT_FINITE_BOUND_CAPS' for v in old.values()),'/',len(CASES),flush=True)
