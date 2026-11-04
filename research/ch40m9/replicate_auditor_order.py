"""CH40-M.9 reversed audit-order control using the SAME immutable native journals."""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path
from run_m9 import ROOT,CASE_ORDER,run_isolated,compare_audits,atomic_json,sha

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    src=a.input.resolve();out=a.output.resolve()
    env=os.environ.copy();env['CH40M8_WORKSPACE']=str(ROOT)
    env['OPENBLAS_NUM_THREADS']='1';env['OMP_NUM_THREADS']='1';env['PYTHONHASHSEED']='0'
    env['PYTHONPATH']=str(ROOT/'CH40M3/site')+os.pathsep+env.get('PYTHONPATH','')
    audits={};metrics={}
    for mode in ('cache','fresh'):
        result=out/(mode+'_audit.json')
        cmd=[sys.executable,str(ROOT/'CH40M8/audit_m8.py'),
             '--input',str(src),'--mode',mode,'--output',str(result),'--cases',*CASE_ORDER]
        met=run_isolated(cmd,out/'metrics'/mode,75,1500,env)
        audits[mode]=json.loads(result.read_text());metrics[mode]=met['timing']
        print(f'REVERSED ORDER {mode}: CPU={metrics[mode]["cpu_seconds"]:.3f}s; proofs={audits[mode]["independent_rational_computations"]}',flush=True)
    compare_audits(audits['cache'],audits['fresh'],src,CASE_ORDER)
    a0=json.loads((src.parent/'CH40M9_ACCEPTANCE.json').read_text())
    if a0['auditor_receipt_sha256']!=audits['cache']['archive_sha256'] or a0['proof_ledger_sha256']!=audits['cache']['proposition_ledger_sha256']:
        raise ValueError('reversal audit diverged from first production acceptance')
    wc=metrics['cache']['cpu_seconds'];wf=metrics['fresh']['cpu_seconds'];search=a0['search_full_subprocess_cpu_seconds']
    report={'protocol':'CH40M9-AUDIT-ORDER-REPLICATION-V1','original_cases':15,'journal_count':30,
            'bound_checks':audits['cache']['children_checked'],
            'cache_hits':audits['cache']['same_box_cache_hits'],
            'audit_order':['cache','fresh'],'cached_auditor_cpu_seconds':wc,'fresh_auditor_cpu_seconds':wf,
            'whole_batch_cached_cpu_seconds':search+wc,'whole_batch_fresh_cpu_seconds':search+wf,
            'whole_batch_cpu_savings_fraction':(wf-wc)/(search+wf),
            'identical_receipt_commitment':audits['cache']['archive_sha256'],
            'same_receipt_as_initial_run':True,'scientific_release':'NO_GO','status':'RESEARCH_ACCEPTED',
            'note':'Single reversed-order replay; warm OS filesystem caches still affect both; no confidence interval.'}
    atomic_json(out/'REVERSED_ORDER_ACCEPTANCE.json',report)
    print('REVERSE ACCEPTED',json.dumps({k:report[k] for k in ('cached_auditor_cpu_seconds','fresh_auditor_cpu_seconds','whole_batch_cpu_savings_fraction')}),flush=True)
if __name__=='__main__':main()
