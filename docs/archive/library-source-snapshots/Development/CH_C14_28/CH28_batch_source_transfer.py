"""Run frozen original CH23 cases with measured per-case subprocess CPU time."""
import concurrent.futures as cf,subprocess,json,time,os,pathlib
D=pathlib.Path(__file__).resolve().parent
P=json.loads((D/'frozen_protocol.json').read_text())
ids=list(P['original_case_sha256'])
jobs=[(budget,k) for budget in [63,127] for k in ids]
log=D/'batch.log'
def execute(z):
 budget,cid=z
 start=time.monotonic()
 env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1'}
 cmd=['python',str(D/'run_case28.py'),cid,'--budget',str(budget)]
 try:
  p=subprocess.run(cmd,cwd=D.parent,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=360)
  status='ok' if p.returncode==0 else 'failed'
  out=p.stdout
 except subprocess.TimeoutExpired as e:
  status='timeout';out=(e.stdout or b'').decode(errors='replace') if isinstance(e.stdout,bytes) else str(e.stdout)
 (D/'runs'/str(budget)).mkdir(exist_ok=True,parents=True)
 (D/'runs'/str(budget)/f'{cid}.stdout').write_text(out or '')
 return {'case':cid,'budget':budget,'status':status,'wall_seconds':round(time.monotonic()-start,3),'log':(out or '')[-350:]}
if __name__=='__main__':
 print('BEGIN 30 frozen jobs',flush=True)
 with cf.ThreadPoolExecutor(max_workers=4) as pool:
  futures={pool.submit(execute,z):z for z in jobs}
  for f in cf.as_completed(futures):
   r=f.result(); print(json.dumps(r),flush=True)
 print('DONE',flush=True)