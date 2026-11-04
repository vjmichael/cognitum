"""CH40-M.9: fail-closed whole-pipeline B&B benchmark on original frozen C14 cases.

Research only: execute M.7 unchanged native workers, then M.8 standalone
non-native rational audit in independent processes. Compare cached vs uncached
verification on the EXACT SAME journal set. No new math theorem or release.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
from fractions import Fraction

ROOT = Path(os.environ.get('CH40M9_WORKSPACE','/mnt/data')).resolve()
HERE = Path(__file__).resolve().parent
CASE_ORDER=(
    'quasi_separated_n80_i00','quasi_separated_n160_i00',
    'zero_balanced_n80_i00','zero_balanced_n160_i00',
    'one_event_n80_i00','one_event_n160_i00',
    'zero_imbalanced_n80_i00','zero_imbalanced_n160_i00',
    'rare_1pct_n80_i00','rare_1pct_n160_i00',
    'rare_5pct_n80_i00','rare_5pct_n160_i00',
    'zero_imbalanced_n160_i05','zero_imbalanced_n160_i07',
    'rare_1pct_n160_i13',
)

ENGINES=('arb_gram','mpfr_gram')
PROTOCOL='CH40M9-WHOLE-PIPELINE-RESEARCH-V1'

class Refusal(RuntimeError): pass


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as fd:
        for chunk in iter(lambda:fd.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def atomic_json(path, data):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('w') as out:
        json.dump(data,out,indent=2,sort_keys=True)
        out.write('\n');out.flush();os.fsync(out.fileno())
    os.replace(tmp,path)


def read_time(path):
    # GNU time's private format. A subprocess may crash before producing a file.
    data={}
    for line in Path(path).read_text().splitlines():
        k,sep,v=line.partition('=')
        if sep and k in ('user','system','rss_kib','elapsed_seconds','exit_status'):
            try:data[k]=float(v)
            except ValueError:raise Refusal('invalid external time metric')
    if set(data)!= {'user','system','rss_kib','elapsed_seconds','exit_status'}:
        raise Refusal('external process telemetry missing')
    data['cpu_seconds']=data['user']+data['system']
    if not all(math.isfinite(x) and x>=0 for x in data.values()):
        raise Refusal('invalid external process telemetry')
    return data


def run_isolated(args, output_base, wall_limit, address_space_mib, env):
    output_base=Path(output_base); output_base.parent.mkdir(parents=True,exist_ok=True)
    # Resource limits enforced on /usr/bin/time and inherited by its program.
    def preexec():
        lim=address_space_mib*1024**2
        resource.setrlimit(resource.RLIMIT_AS,(lim,lim))
        cl=max(3,int(math.ceil(wall_limit))+1)
        resource.setrlimit(resource.RLIMIT_CPU,(cl,cl+1))
    metric_path=output_base.with_suffix('.time.txt')
    command=['/usr/bin/time','-f',
             'user=%U\nsystem=%S\nrss_kib=%M\nelapsed_seconds=%e\nexit_status=%x',
             '-o',str(metric_path),'--']+list(args)
    begun=time.monotonic()
    with subprocess.Popen(command,env=env,cwd=str(ROOT),stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,text=True,preexec_fn=preexec,
                          start_new_session=True) as proc:
        try:
            stdout,stderr=proc.communicate(timeout=wall_limit)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid,signal.SIGKILL)
            proc.communicate()
            raise Refusal('wall timeout '+str(args[:3]))
        if proc.returncode!=0:
            raise Refusal(f'process failed exit={proc.returncode} command={args[:3]} stderr={stderr[-2500:]}')
    timing=read_time(metric_path)
    if timing['exit_status']!=0:raise Refusal('GNU time reports nonzero exit')
    return {'timing':timing,'wall_monotonic_seconds':time.monotonic()-begun,
            'stdout_tail':stdout[-1200:],'stderr_tail':stderr[-1200:]}


def validate_case_list(cases):
    if not cases or len(set(cases))!=len(cases) or set(cases)-set(CASE_ORDER):
        raise Refusal('bad frozen case list')
    pins=ROOT/'CH40K/CH40K_ACCEPTANCE.json'
    if not pins.exists():raise Refusal('missing pinned original source')
    d=json.loads(pins.read_text())
    original={v['case'] for v in d['cases']}
    if len(original)!=15 or not set(cases)<=original:raise Refusal('original source identity failure')
    for case in cases:
        if not (ROOT/'CH40K/traces'/(case+'_127_original_mpfr_trace.json')).is_file():
            raise Refusal('missing original frozen case: '+case)
    return d


def compare_audits(cache, fresh, journals, cases):
    # A passed auditor result is not trusted just because its JSON says PASS.
    # For full acceptance, both independently executed verifier modes must
    # agree on every receipt, proof ledger, and expected original SHA pin.
    if any(x.get('status')!='PASS_RESEARCH_ONLY' or
           x.get('scientific_release')!='NO_GO' or
           x.get('cases')!=len(cases) or
           x.get('input_count')!=len(cases)*2 for x in (cache,fresh)):
        raise Refusal('auditor did not accept original evidence')
    if (cache.get('mode')!='cache' or fresh.get('mode')!='fresh' or
        cache['archive_sha256']!=fresh['archive_sha256'] or
        cache['proposition_ledger_sha256']!=fresh['proposition_ledger_sha256'] or
        cache['receipts']!=fresh['receipts'] or cache['propositions']!=fresh['propositions']):
        raise Refusal('cached/fresh independent auditor divergence')
    if (cache['same_box_cache_hits'] + cache['independent_rational_computations'] !=
        cache['children_checked'] or
        fresh['independent_rational_computations']!=fresh['children_checked'] or
        fresh['same_box_cache_hits']!=0):
        raise Refusal('missing independently verified child propositions')
    expected={(case,engine) for case in cases for engine in ENGINES}
    actual={(r.get('case'),r.get('backend')) for r in cache['receipts']}
    if actual!=expected or len(cache['receipts'])!=len(expected):
        raise Refusal('audit coverage incomplete')
    for r in cache['receipts']:
        f=journals/(r['case']+'_'+r['backend']+'.json')
        if r.get('journal_sha256')!=sha(f):raise Refusal('journal digest mismatch')
    return True


def generate_report(cases,workers,cache,fresh,audit_times,config):
    childsum=sum(w['children'] for w in workers)
    if cache['children_checked']!=childsum or fresh['children_checked']!=childsum:
        raise Refusal('bound check count mismatch')
    search_cpu=sum(w['telemetry']['cpu_seconds'] for w in workers)
    search_rss=max(w['telemetry']['rss_kib'] for w in workers)
    audit_cache_cpu=audit_times['cache']['cpu_seconds']
    audit_fresh_cpu=audit_times['fresh']['cpu_seconds']
    by_engine={}
    for e in ENGINES:
        ws=[w for w in workers if w['engine']==e]
        by_engine[e]={
            'split_count':sum(w['splits'] for w in ws),
            'children':sum(w['children'] for w in ws),
            'full_subprocess_cpu_seconds':sum(w['telemetry']['cpu_seconds'] for w in ws),
            'max_worker_rss_kib':max(w['telemetry']['rss_kib'] for w in ws),
            'frontier_reduction_sum_approx':sum(float(Fraction(w['upper_reduction'])) for w in ws),
            'per_case':[{'case':w['case'],'splits':w['splits'],
                         'frontier_reduction':w['upper_reduction'],
                         'measured_cpu':w['telemetry']['cpu_seconds']} for w in ws]
        }
    if search_cpu<=0:raise Refusal('zero search CPU')
    return {
        'protocol':PROTOCOL,'status':'RESEARCH_ACCEPTED','scientific_release':'NO_GO',
        'original_cases':len(cases),'paired_worker_runs':len(workers),
        'frozen_case_names':list(cases),'config':config,
        'case_hash_pinning':'CH40K original trace and certificate SHA pins validated by worker and auditor',
        'bound_formula':'PSD_GRAM_DOMINANCE for both native producers',
        'precision_bits':256,'online_rational_checks':childsum,
        'external_rational_checks':cache['children_checked'],
        'auditor_receipt_sha256':cache['archive_sha256'],
        'proof_ledger_sha256':cache['proposition_ledger_sha256'],
        'exact_unique_proof_statements':cache['independent_rational_computations'],
        'reused_exact_proofs':cache['same_box_cache_hits'],
        'search_full_subprocess_cpu_seconds':search_cpu,
        'max_search_worker_rss_kib':search_rss,
        'independent_audit_cpu_cached_seconds':audit_cache_cpu,
        'independent_audit_cpu_fresh_seconds':audit_fresh_cpu,
        'max_independent_audit_rss_kib':max(audit_times['cache']['rss_kib'],audit_times['fresh']['rss_kib']),
        'whole_batch_pipeline_cpu_cached_seconds':search_cpu+audit_cache_cpu,
        'whole_batch_pipeline_cpu_fresh_seconds':search_cpu+audit_fresh_cpu,
        'whole_batch_pipeline_saved_cpu_seconds':audit_fresh_cpu-audit_cache_cpu,
        'whole_batch_pipeline_cpu_reduction_fraction':(audit_fresh_cpu-audit_cache_cpu)/(search_cpu+audit_fresh_cpu),
        'engines':by_engine,
        'qualification':('Native search includes online independent rational checking. Post-search independent audit is a SECOND check. '
                         'Cache is reusable only across paired journals audited in one trusted process; do not attribute total-batch savings to a standalone single backend. '
                         'Search timer caps and startup CPU are not identical full-process budgets; no confidence interval or proof of whole-C14 optimizer superiority. '
                         'No global convergence or causal identification proved.')
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--cases',nargs='+',default=CASE_ORDER)
    p.add_argument('--cpu-budget',type=float,default=1.0)
    p.add_argument('--max-splits',type=int,default=256)
    p.add_argument('--wall-limit',type=float,default=18.0)
    p.add_argument('--as-mib',type=int,default=1500)
    a=p.parse_args()
    validate_case_list(a.cases)
    if not .5<=a.cpu_budget<=20 or not 1<=a.max_splits<=1000 or not 5<=a.wall_limit<=60 or not 700<=a.as_mib<=2048:
        raise Refusal('invalid resource limits')
    output=a.out.resolve(); journals=output/'journals';journals.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy();env['CH40M7_WORKSPACE']=str(ROOT);env['CH40M8_WORKSPACE']=str(ROOT)
    env['PYTHONPATH']=str(ROOT/'CH40M3/site')+os.pathsep+env.get('PYTHONPATH','')
    env['OPENBLAS_NUM_THREADS']='1';env['OMP_NUM_THREADS']='1';env['PYTHONHASHSEED']='0'
    config={'requested_worker_cpu_seconds':a.cpu_budget,'max_splits':a.max_splits,'wall_limit_seconds':a.wall_limit,
            'max_process_virtual_memory_mib':a.as_mib,'worker_formula':'PSD_GRAM_DOMINANCE',
            'worker':'CH40M7/worker_m7.py unchanged','auditor':'CH40M8/audit_m8.py unchanged',
            'run_order':'alternate FLINT/MPFR by original case position','audit_order':'fresh then cache (single-trial; OS cache order confound)'}
    workers=[]
    for idx,case in enumerate(a.cases):
        order=ENGINES if idx%2==0 else ENGINES[::-1]
        for engine in order:
            result_file=journals/(case+'_'+engine+'.json')
            cmd=[sys.executable,str(ROOT/'CH40M7/worker_m7.py'),
                 '--case',case,'--backend',engine,
                 '--cpu-budget',str(a.cpu_budget),'--max-splits',str(a.max_splits),
                 '--out',str(result_file)]
            meta=run_isolated(cmd,output/'metrics'/(case+'_'+engine),a.wall_limit,a.as_mib,env)
            r=json.loads(result_file.read_text())
            if (r.get('case')!=case or r.get('backend')!=engine or
                r.get('protocol')!='CH40M7-SAME-PSD-GRAM-FULL-PROCESS-RESEARCH-V1' or
                r.get('release_status')!='RESEARCH_ONLY_NO_GO' or
                r.get('children')!=2*r.get('splits')):
                raise Refusal('worker returned invalid record')
            w={'case':case,'engine':engine,'splits':r['splits'],'children':r['children'],
               'upper_reduction':r['upper_reduction'],'trace_sha256':r['trace_sha256'],
               'sha256':sha(result_file),'telemetry':meta['timing']}
            workers.append(w)
        atomic_json(output/'partial.json',{'workers':workers,'config':config,'status':'NOT_YET_ACCEPTED'})
        print(f'{idx+1}/{len(a.cases)} {case} '+', '.join(f'{w["engine"]}={w["splits"]} splits' for w in workers[-2:]),flush=True)
    aud={};aud_times={}
    for mode in ('fresh','cache'):
        target=output/(mode+'_audit.json')
        args=[sys.executable,str(ROOT/'CH40M8/audit_m8.py'),
              '--input',str(journals),'--mode',mode,'--output',str(target),'--cases',*a.cases]
        meta=run_isolated(args,output/'metrics'/('audit_'+mode),max(a.wall_limit,60),a.as_mib,env)
        aud[mode]=json.loads(target.read_text());aud_times[mode]=meta['timing']
        print(f'AUDIT {mode}: children={aud[mode]["children_checked"]} rational-computations={aud[mode]["independent_rational_computations"]} cpu={aud_times[mode]["cpu_seconds"]:.3f}',flush=True)
    compare_audits(aud['cache'],aud['fresh'],journals,a.cases)
    report=generate_report(a.cases,workers,aud['cache'],aud['fresh'],aud_times,config)
    report['workers']=workers
    atomic_json(output/'CH40M9_ACCEPTANCE.json',report)
    print('ACCEPTED',json.dumps({k:report[k] for k in ('paired_worker_runs','online_rational_checks','search_full_subprocess_cpu_seconds','whole_batch_pipeline_cpu_cached_seconds','whole_batch_pipeline_cpu_fresh_seconds','whole_batch_pipeline_cpu_reduction_fraction')}),flush=True)

if __name__=='__main__':main()
