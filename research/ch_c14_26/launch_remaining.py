import concurrent.futures,hashlib,json,os,subprocess,time,sys
from pathlib import Path
D=Path(__file__).resolve().parent
P=json.loads((D/'frozen_protocol.json').read_text())
ids=[x['id'] for x in P['cases'] if x['id']!='rare_5pct_n80_i00']
def run(tag):
 ch24=D.parent/'CH_C14_24'
 if not ch24.exists():ch24=D.parent/'ch_c14_24'
 env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONPATH=str(ch24)+':'+str(D))
 t=time.monotonic()
 r=subprocess.run([sys.executable,str(D/'run_case.py'),tag],cwd=D,env=env,capture_output=True,text=True,timeout=1200)
 (D/'logs'/f'{tag}_process.log').write_text(r.stdout+'\n'+r.stderr)
 return tag,r.returncode,round(time.monotonic()-t,3),r.stdout[-500:],r.stderr[-900:]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
 futures=[ex.submit(run,tag) for tag in ids]
 for f in concurrent.futures.as_completed(futures):
  tag,rc,elapsed,stdout,stderr=f.result()
  print(json.dumps(dict(case=tag,returncode=rc,elapsed_seconds=elapsed,stdout=stdout,stderr=stderr)),flush=True)
