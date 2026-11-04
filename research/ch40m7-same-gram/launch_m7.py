"""Bounded subprocess benchmark with wait4 full-process resource accounting."""
from __future__ import annotations
import argparse,hashlib,json,os,resource,subprocess,sys,time
from pathlib import Path
from fractions import Fraction as F
HERE=Path(__file__).resolve().parent
ROOT=Path(os.environ.get('CH40M7_WORKSPACE','/mnt/data')).resolve()
CASE_ORDER=[
 'quasi_separated_n80_i00','quasi_separated_n160_i00',
 'zero_balanced_n80_i00','zero_balanced_n160_i00',
 'one_event_n80_i00','one_event_n160_i00',
 'zero_imbalanced_n80_i00','zero_imbalanced_n160_i00',
 'rare_1pct_n80_i00','rare_1pct_n160_i00',
 'rare_5pct_n80_i00','rare_5pct_n160_i00',
 'zero_imbalanced_n160_i05','zero_imbalanced_n160_i07','rare_1pct_n160_i13']

def run_one(command,env,wall_limit,as_bytes):
    def limits():
        resource.setrlimit(resource.RLIMIT_AS,(as_bytes,as_bytes))
        resource.setrlimit(resource.RLIMIT_CPU,(int(wall_limit)+1,int(wall_limit)+2))
    start=time.monotonic()
    before=resource.getrusage(resource.RUSAGE_CHILDREN)
    with subprocess.Popen(command,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
                          preexec_fn=limits) as p:
        try: out,err=p.communicate(timeout=wall_limit)
        except subprocess.TimeoutExpired:
            p.kill();out,err=p.communicate();return {'status':'WALL_TIMEOUT','stderr':err[-1000:]}
        # child just reaped by communicate(), which uses waitpid not wait4. Use /usr/bin/time
        # for externally recorded full-process CPU/RSS in separate optional runners.
        status='OK' if p.returncode==0 else 'FAIL'
    after=resource.getrusage(resource.RUSAGE_CHILDREN)
    full_cpu=(after.ru_utime+after.ru_stime)-(before.ru_utime+before.ru_stime)
    return {'status':status,'returncode':p.returncode,'stdout':out[-1000:],'stderr':err[-2000:],
            'full_child_process_cpu_seconds':full_cpu,
            'wall_elapsed':time.monotonic()-start}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cases',nargs='*',default=CASE_ORDER)
    ap.add_argument('--cpu-budget',type=float,default=1.25);ap.add_argument('--max-splits',type=int,default=256)
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--wall-limit',type=float,default=15.0)
    ap.add_argument('--address-space-mib',type=int,default=1500)
    a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    if len(set(a.cases))!=len(a.cases) or set(a.cases)-set(CASE_ORDER):raise ValueError('unknown/duplicate original case')
    env=os.environ.copy();env['CH40M7_WORKSPACE']=str(ROOT);env['PYTHONPATH']=str(ROOT/'CH40M3/site')+':'+env.get('PYTHONPATH','');env['OPENBLAS_NUM_THREADS']='1';env['OMP_NUM_THREADS']='1'
    rows=[]
    for i,case in enumerate(a.cases):
        arms={}
        for engine in (['arb_gram','mpfr_gram'] if i%2==0 else ['mpfr_gram','arb_gram']):
            out=a.output/(case+'_'+engine+'.json')
            command=[sys.executable,str(HERE/'worker_m7.py'),'--case',case,'--backend',engine,
                     '--cpu-budget',str(a.cpu_budget),'--max-splits',str(a.max_splits),'--out',str(out)]
            meta=run_one(command,env,a.wall_limit,a.address_space_mib*1024**2)
            if meta['status']!='OK':
                print('FAILED',case,engine,meta,flush=True)
                arms[engine]={'status':'NOT_ACCEPTED',**meta}
                continue
            report=json.loads(out.read_text());audit_out=a.output/(case+'_'+engine+'.audit.json')
            audit_start=resource.getrusage(resource.RUSAGE_CHILDREN)
            audit=subprocess.run([sys.executable,str(HERE/'audit_m7.py'),str(out),'--receipt',str(audit_out)],env=env,capture_output=True,text=True,timeout=a.wall_limit)
            audit_end=resource.getrusage(resource.RUSAGE_CHILDREN)
            audit_cpu=(audit_end.ru_utime+audit_end.ru_stime)-(audit_start.ru_utime+audit_start.ru_stime)
            if audit.returncode:raise RuntimeError('Independent auditor failure '+case+' '+engine+': '+audit.stderr[-2000:])
            arms[engine]={'status':'ACCEPTED','split_count':report['splits'],'child_checks':report['children'],
                          'cpu_measured_in_worker':report['process_cpu_including_import_input_and_online_verification'],
                          'rss_kib':report['peak_ru_maxrss_kib'],'wall_elapsed':meta['wall_elapsed'],
                          'full_child_process_cpu_seconds':meta['full_child_process_cpu_seconds'],
                          'external_auditor_cpu_seconds':audit_cpu,
                          'upper_reduction':report['upper_reduction'],
                          'budget_overshoot':report['budget_overshoot_seconds'],
                          'journal_tip':report['journal_tip']}
        rows.append({'case':case,'arms':arms})
        (a.output/'summary_partial.json').write_text(json.dumps({'rows':rows,'cpu_budget':a.cpu_budget},indent=2)+'\n')
        print(f"{i+1}/{len(a.cases)} {case}: "+' '.join(f'{k}={v.get("split_count","N/A")}@{v.get("cpu_measured_in_worker",0):.3f}s' for k,v in arms.items()),flush=True)
    accepted=[v for row in rows for v in row['arms'].values() if v['status']=='ACCEPTED']
    totals={e:{'splits':sum(row['arms'].get(e,{}).get('split_count',0) for row in rows),
               'cpu':sum(row['arms'].get(e,{}).get('cpu_measured_in_worker',0) for row in rows),
               'full_process_cpu':sum(row['arms'].get(e,{}).get('full_child_process_cpu_seconds',0) for row in rows),
               'audit_cpu':sum(row['arms'].get(e,{}).get('external_auditor_cpu_seconds',0) for row in rows),
               'children':sum(row['arms'].get(e,{}).get('child_checks',0) for row in rows)} for e in ('arb_gram','mpfr_gram')}
    summary={'protocol':'CH40M7-MATCHED-FORMULA-FULL-PROCESS-PILOT',
            'formula':'PSD_GRAM_DOMINANCE_BOTH_ENGINES','precision_bits':256,
            'requested_process_cpu_per_arm_seconds':a.cpu_budget,'max_splits':a.max_splits,
            'count_original_cases':len(a.cases),'count_accepted_arms':len(accepted),
            'totals':totals,'rows':rows,'independent_audit':'READ_ONLY_RATIONAL_REPLAY_PER_ARM',
            'limits':'Whole-child-process CPU includes Python interpreter startup, Python load, native producer calls, and online independent rational child checking. External standalone replay CPU measured separately; parent/orchestrator overhead excluded. Atomic split can overshoot, cap 256. Per-case independent processes, phase order alternating. No certified global convergence.',
            'scientific_release':'NO_GO'}
    (a.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('TOTAL',json.dumps(totals),flush=True)
if __name__=='__main__':main()
