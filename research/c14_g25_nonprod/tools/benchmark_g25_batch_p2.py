"""P2 fixed-work black-box benchmark, isolated local Linux only (not an LLM test)."""
from __future__ import annotations
import json, os, statistics, subprocess, sys, time, hashlib, platform
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'integration'))
from g25_task_batch import TaskBatch
from g25_cancellable_supervisor import canonical,HOST,safe_worker_environment
COUNTS=[[[67,35],[45,31]],[[75,30],[48,39]]]
EVIDENCE={'sampling_iid_supported':True,'consistency_supported':True,
          'measurement_validity_supported':True,
          'gamma_justification':'Externally justified domain sensitivity bound'}

def report(i):
    return {'schema_version':1,'request_id':str(i),'action':'c14.g25.sensitivity.report',
            'counts':COUNTS,'gamma':.25,'assumption_evidence':EVIDENCE}

def separate(requests):
    start=time.perf_counter()
    for r in requests:
        p=subprocess.run([sys.executable,str(HOST),'--research-only'],
            input=canonical(r)+'\n',text=True,stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,env=safe_worker_environment(),timeout=10)
        if p.returncode!=0 or json.loads(p.stdout)['host_status']!='completed':
            raise RuntimeError('independent process failed')
    return (time.perf_counter()-start)*1000

def batched(requests):
    b=TaskBatch(research_opt_in=True)
    st=time.perf_counter()
    ans=b.execute('benchmark',[r for r in requests])
    elapsed=(time.perf_counter()-st)*1000
    b.close()
    if ans['status']!='completed' or len(ans['responses'])!=len(requests):
        raise RuntimeError('batch failed: '+str(ans.get('error_code')))
    return elapsed

def quantile(v,p):
    a=sorted(v); return a[min(len(a)-1,int((len(a)-1)*p+.5))]

def main():
    output={'title':'C14 G25 same-task worker batching P2 research microbenchmark',
            'platform':platform.platform(),'python':platform.python_version(),
            'openblas_threads':'1','batch_restriction':'one research task, POSIX only',
            'cold_spawn_semantics':'both paths spawn new Python+SciPy worker, no cross-task reuse',
            'measurements':[]}
    for n,trials in [(1,1),(4,1),(8,1)]:
        reqs=[report(f'{n}-{i}') for i in range(n)]
        separate_runs=[];batch_runs=[]
        # Interleave each paired trial to limit drift.
        for k in range(trials):
            if k%2:
                batch_runs.append(batched(reqs));separate_runs.append(separate(reqs))
            else:
                separate_runs.append(separate(reqs));batch_runs.append(batched(reqs))
        output['measurements'].append({'n':n,'trials':trials,
            'separate_ms':separate_runs,'batch_ms':batch_runs,
            'separate_median_ms':statistics.median(separate_runs),
            'batch_median_ms':statistics.median(batch_runs),
            'separate_p95_nearest_ms':quantile(separate_runs,.95),
            'batch_p95_nearest_ms':quantile(batch_runs,.95),
            'speedup_median':statistics.median(separate_runs)/statistics.median(batch_runs),
            'batch_per_report_median_ms':statistics.median(batch_runs)/n})
    outfile=ROOT/'results'/'batch_benchmark.json'
    outfile.parent.mkdir(parents=True,exist_ok=True)
    outfile.write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps(output,indent=2))

if __name__=='__main__':main()
