"""Run original uninstrumented CH29 frozen producer for all fifteen 127-node cases, independently compare proof-bearing fields."""
from __future__ import annotations
import concurrent.futures,subprocess,pathlib,sys,json,time,hashlib,zipfile
E=pathlib.Path('/mnt/data/CH_C14_40_E');F=pathlib.Path('/mnt/data/CH_C14_40_F')
ARCH=E/'Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'
PIN='9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b'
assert hashlib.sha256(ARCH.read_bytes()).hexdigest()==PIN
with zipfile.ZipFile(ARCH) as z:
 for n in z.namelist():
  if n.endswith('/') or not (n.startswith('CH_C14_24/') or n.startswith('CH_C14_25/') or n.startswith('CH_C14_26/') or n.startswith('CH_C14_27/') or n.startswith('CH_C14_29/')):continue
  if not n.endswith('.py') and n!='CH_C14_29/frozen_protocol.json' and n!='CH_C14_27/frozen_duals.json' and not (n.startswith('CH_C14_25/inputs/') and n.endswith('.json')):continue
  if (E/'source'/n).read_bytes()!=z.read(n):raise RuntimeError('Unmodified original executable/input differs from frozen archive: '+n)
CASES='''one_event_n160_i00 quasi_separated_n160_i00 quasi_separated_n80_i00 rare_1pct_n160_i00 rare_1pct_n160_i13 rare_1pct_n80_i00 rare_5pct_n160_i00 rare_5pct_n80_i00 zero_balanced_n160_i00 zero_balanced_n80_i00 zero_imbalanced_n160_i00 zero_imbalanced_n160_i05 zero_imbalanced_n160_i07 zero_imbalanced_n80_i00'''.split()
def work(c):
 trace=F/'results'/f'{c}_127_original_mpfr_trace.json'
 while not trace.exists():
  status=F/'producer_progress.json'
  if status.exists() and json.loads(status.read_text()).get(c,{}).get('status')=='FAIL':raise RuntimeError('Producer failed')
  time.sleep(3)
 t=time.monotonic();cmd=[sys.executable,str(E/'compare_baseline40e.py'),'--trace',str(trace)]
 r=subprocess.run(cmd,capture_output=True,text=True,timeout=2400)
 (F/'logs'/f'{c}_baseline.log').write_text(r.stdout+'\nSTDERR\n'+r.stderr)
 if r.returncode:raise RuntimeError('Baseline differs: '+r.stderr[-800:])
 if 'all certificate proof fields identical' not in r.stdout:raise RuntimeError('No explicit proof equivalence acknowledgment')
 return {'status':'PASS_UNMODIFIED_PROOF_FIELD_EQUIVALENCE','trace_sha256':hashlib.sha256(trace.read_bytes()).hexdigest(),'wall_seconds':round(time.monotonic()-t,2)}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 futures={pool.submit(work,c):c for c in CASES}
 for i,fut in enumerate(concurrent.futures.as_completed(futures),1):
  case=futures[fut];p=F/'baseline_progress.json'
  try:got=fut.result();print('BASELINE MATCH',i,'/',len(CASES),case,'seconds',got['wall_seconds'],flush=True)
  except Exception as exc:got={'status':'FAIL','reason':str(exc)};print('BASELINE MISMATCH',case,got['reason'],flush=True)
  current=json.loads(p.read_text()) if p.exists() else {};current[case]=got
  p.write_text(json.dumps(current,indent=2)+'\n')
print('BASELINE COMPLETE',sum(x['status'].startswith('PASS') for x in json.loads((F/'baseline_progress.json').read_text()).values()),'/',len(CASES),flush=True)