"""Generate original full-depth MPFR producer traces under frozen CH39 source; research only."""
from __future__ import annotations
import concurrent.futures,subprocess,pathlib,sys,json,time,hashlib
E=pathlib.Path('/mnt/data/CH_C14_40_E'); F=pathlib.Path('/mnt/data/CH_C14_40_F')
CASES='''one_event_n160_i00 quasi_separated_n160_i00 quasi_separated_n80_i00 rare_1pct_n160_i00 rare_1pct_n160_i13 rare_1pct_n80_i00 rare_5pct_n160_i00 rare_5pct_n80_i00 zero_balanced_n160_i00 zero_balanced_n80_i00 zero_imbalanced_n160_i00 zero_imbalanced_n160_i05 zero_imbalanced_n160_i07 zero_imbalanced_n80_i00'''.split()

def work(case):
 out=F/'results'/f'{case}_127_original_mpfr_trace.json'
 cmd=[sys.executable,str(E/'run_trace40e.py'),'--archive',str(E/'Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'),'--case',case,'--nodes','127','--reuse-workspace','--result-dir',str(F/'results')]
 t=time.monotonic(); r=subprocess.run(cmd,capture_output=True,text=True,timeout=2400)
 (F/'logs'/f'{case}_producer.log').write_text(r.stdout+'\nSTDERR\n'+r.stderr)
 if r.returncode:raise RuntimeError(case+' producer failed '+r.stderr[-600:])
 data=json.loads(out.read_text());assert data['node_count']==127 and len(data['nodes'])==127
 return {'case':case,'status':'PRODUCER_PASS_PENDING_INDEPENDENT_VERIFIER','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'bytes':out.stat().st_size,'wall_seconds':round(time.monotonic()-t,2)}

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
 futs={ex.submit(work,c):c for c in CASES}
 for i,fut in enumerate(concurrent.futures.as_completed(futs),1):
  c=futs[fut];state=F/'producer_progress.json'
  try:
   v=fut.result(); print('PRODUCED',i,'/',len(CASES),c,'seconds',v['wall_seconds'],flush=True)
  except Exception as exc:
   v={'case':c,'status':'FAIL','reason':str(exc)};print('FAILED',i,'/',len(CASES),c,str(exc),flush=True)
  current=json.loads(state.read_text()) if state.exists() else {}
  current[c]=v;state.write_text(json.dumps(current,indent=2)+'\n')
print('PRODUCER COMPLETE',sum(x['status'].startswith('PRODUCER_PASS') for x in json.loads((F/'producer_progress.json').read_text()).values()),'/',len(CASES),flush=True)