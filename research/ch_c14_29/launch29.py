"""Run pre-frozen CH29 matrix with bounded parallelism and per-job stdout logs."""
from __future__ import annotations
import argparse,concurrent.futures,json,os,subprocess,sys,time
from pathlib import Path
D=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--mode',choices=('fixed','equal_cpu'),required=True)
p.add_argument('--workers',type=int,default=4);a=p.parse_args()
proto=json.loads((D/'frozen_protocol.json').read_text())
ids=sorted(proto['original_case_sha256'])
jobs=[(str(b),cid) for b in (63,127) for cid in ids]
completed=D/('progress_'+a.mode+'.jsonl'); completed.touch(exist_ok=True)
previous={tuple((str(x['budget']),x['case_id'])):x for x in (json.loads(line) for line in completed.read_text().splitlines() if line.strip())}
jobs=[(b,cid) for b,cid in jobs if (b,cid) not in previous or previous[(b,cid)]['returncode']!=0]
print('START',a.mode,'jobs',len(jobs),'workers',a.workers,flush=True)
def run(job):
 b,cid=job
 t=time.monotonic()
 cmd=[sys.executable,str(D/'run_case29.py'),cid,'--budget',b,'--mode',a.mode]
 env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','PYTHONUNBUFFERED':'1'}
 result=subprocess.run(cmd,cwd=str(D.parent),env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 logfile=D/'runs'/a.mode/b/'output';logfile.mkdir(exist_ok=True,parents=True)
 (logfile/(cid+'.txt')).write_text(result.stdout)
 return {'mode':a.mode,'budget':int(b),'case_id':cid,'returncode':result.returncode,'wall_seconds':round(time.monotonic()-t,3),'output_tail':result.stdout[-800:]}
with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as ex:
 futs={ex.submit(run,j):j for j in jobs}
 for fut in concurrent.futures.as_completed(futs):
  rec=fut.result();print('COMPLETE',rec['case_id'],rec['budget'],'status',rec['returncode'],'wall',rec['wall_seconds'],'tail',rec['output_tail'][-140:].replace('\n',' '),flush=True)
  with completed.open('a') as f:f.write(json.dumps(rec,sort_keys=True)+'\n')
print('DONE',a.mode,flush=True)
