from pathlib import Path
import sys,json,time,signal,platform
from fractions import Fraction
sys.path[:0]=['/mnt/data/CH40M3/site','/mnt/data/CH40M2/source']
from frozen40m2 import load_cases,point_lower
from flint_arb_backend import arb_point
case_list=load_cases(Path('/mnt/data/CH40K/traces'),Path('/mnt/data/CH40K/CH40K_ACCEPTANCE.json'))
out=Path('/mnt/data/CH40M3/results/flint15_point_check.json');out.parent.mkdir(exist_ok=True)
result={'protocol':'CH40-M3-NATIVE-FLINT-POINT-RECHECK-V1','scientific_release':'NO_GO','python':platform.python_version(),'cases':[],'frozen_15_sha_verified':True,'note':'Only point enclosure, not certified global upper bound; independent rational evaluator run with time budget. Failure/timeout not treated as pass.'}
def timed_out(sig,frame):raise TimeoutError('independent check exceeded 16s wall budget')
signal.signal(signal.SIGALRM,timed_out)
for idx,c in enumerate(case_list):
 rec={'case':c.name,'trace_sha256':c.source_sha256,'point':[str(float(x)) for x in c.incumbent]};t=time.monotonic()
 try:
  p=arb_point(c,c.incumbent)
  rec['flint_version']=p['version']; rec['precision_bits']=p['precision_bits']; rec['flint_enclosure']={'lower':p['lower'],'upper':p['upper']}
  rec['arb_cpu_seconds']=p['cpu_seconds']
  signal.alarm(16)
  try:r=point_lower(c,c.incumbent,Path('/mnt/data/CH40J/source'))
  finally:signal.alarm(0)
  low,high=Fraction(p['lower']),Fraction(p['upper'])
  rec['status']='INDEPENDENT_POINT_OVERLAP_VERIFIED' if max(low,r.lo)<=min(high,r.hi) else 'REJECTED_DISJOINT_INTERVALS'
  rec['reference_interval']={'lower':str(r.lo),'upper':str(r.hi)}
  rec['flint_contains_reference']=low<=r.lo and r.hi<=high
 except Exception as exc:rec['status']='UNRESOLVED';rec['error']=repr(exc)[:240]
 rec['wall_seconds']=round(time.monotonic()-t,3)
 result['cases'].append(rec)
 out.write_text(json.dumps(result,indent=2)+'\n')
 print(f'{idx+1:02d}/15 {c.name}: {rec["status"]} ({rec["wall_seconds"]:.2f}s)',flush=True)
result['passing']=sum(x['status']=='INDEPENDENT_POINT_OVERLAP_VERIFIED' for x in result['cases'])
result['unresolved']=15-result['passing']
out.write_text(json.dumps(result,indent=2)+'\n')
print('SUMMARY',result['passing'],'PASS',result['unresolved'],'UNRESOLVED',flush=True)

