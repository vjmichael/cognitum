"""Strictly bounded SCIP research comparison on 15 original hash-pinned cases."""
import json,sys,subprocess,os,time
from pathlib import Path
CASES=sorted(p.name.removesuffix('_127_original_mpfr_trace.json') for p in Path('/mnt/data/CH40K/traces').glob('*_127_original_mpfr_trace.json'))
out=Path('/mnt/data/CH40M3/results/scip15_bounded.json')
report={'protocol':'CH40-M3-SCIP-15-BOUNDED-RESEARCH-V1','scientific_release':'NO_GO','backend':'SCIP via PySCIPOpt 6.3.0','limits':{'real_seconds_per_case':1.5,'memory_scip_mb':512,'process_address_space_gb':1.4,'external_wall_seconds':12},'cases':[],'proven_global_bounds':0,'previous_model_oom':'replaced by factorized auxiliary variable formulation'}
if out.is_file():
    old=json.loads(out.read_text())
    original_names=[r.get('case') for r in old['cases']]
    if original_names != CASES[:len(original_names)]:raise RuntimeError('Partial SCIP journal changed frozen case order')
    report=old
print('RESUMING',len(report['cases']),'of 15',flush=True)
for i,name in enumerate(CASES,1):
    if i<=len(report['cases']):continue
    tmp=Path(f'/mnt/data/CH40M3/results/scip_case_{name}.json')
    cmd=[sys.executable,'/mnt/data/CH40M3/scip_compact.py','--case',name,'--seconds','1.5','--memory-mb','512','--output',str(tmp)]
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONPATH='/mnt/data/CH40M3/site')
    t=time.monotonic()
    try:
        cp=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=12)
        if cp.returncode or not tmp.exists():
            r={'adapter_status':'FAILED_OR_KILLED','returncode':cp.returncode,'stderr_tail':cp.stderr[-400:],'global_certificate':False}
        else:r=json.loads(tmp.read_text())
    except subprocess.TimeoutExpired:
        r={'adapter_status':'TIMEOUT','global_certificate':False}
    r['case']=name;r['external_wall_seconds']=round(time.monotonic()-t,3)
    r.pop('solver_bound_unverified',None)
    report['cases'].append(r)
    out.write_text(json.dumps(report,indent=2)+'\n')
    print(f'{i:02d}/15 {name}: {r["adapter_status"]} / {r.get("status","no status")} / candidate={r.get("feasible_frozen_domain",False)}',flush=True)
report['complete']=len(report['cases'])==15
report['candidate_cases']=sum(r.get('feasible_frozen_domain',False) for r in report['cases'])
report['native_executed_cases']=sum(r.get('adapter_status')=='EXECUTED_NATIVE_CANDIDATE_ONLY' for r in report['cases'])
out.write_text(json.dumps(report,indent=2)+'\n')
print('SUMMARY',report['native_executed_cases'],report['candidate_cases'],flush=True)

