"""CH31 original CH23 cohort: progressive six-stage verification + real restart.

The 7/15/31/95 intermediates are derived projections of the archived CH29
63/127 proof trees; they are not newly generated optimizer searches.
"""
from __future__ import annotations
import argparse,concurrent.futures,hashlib,json,os,subprocess,sys,time,traceback
from pathlib import Path
D=Path(__file__).resolve().parent;BASE=D.parent
sys.path.insert(0,str(D))
from verifier31 import ProgressiveVerifier,load_original_case,sha
from prefix31 import project_prefix
STAGES=(7,15,31,63,95,127)

def verify_case(cid,do_restart=True):
    inp,proto,duals,archived=load_original_case(cid)
    c63,receipt63=archived(63);c127,receipt127=archived(127)
    prog=ProgressiveVerifier();chain=[]
    for size in STAGES:
        source=c63 if size<=63 else c127
        cert=source if size in (63,127) else project_prefix(source,size)
        stage=prog.verify_stage(cert,inp,{**proto,'node_budget_per_case':size},duals)
        if stage['receipt']['replay_status']!='REPLAYED_BUT_UNRESOLVED':
            raise AssertionError('Unexpected scientific promotion')
        chain.append({'nodes':size,'cpu_seconds':round(stage['cpu_seconds'],6),
                      'fresh':stage['receipt']['ancestor_caps_recomputed'],
                      'reused':stage['receipt']['verified_prefix_nodes_reused'],
                      'gap_upper_display':stage['receipt']['gap_upper_display'],
                      'projection':size not in (63,127),
                      'certificate_digest_diagnostic':stage['certificate_digest']})
    for size,original in ((63,receipt63),(127,receipt127)):
        observed=next(s for s in chain if s['nodes']==size)
        if abs(observed['gap_upper_display']-original['gap_upper_display'])>1e-10:
            raise AssertionError('Original CH29 receipt mismatch')
    if any(chain[i+1]['gap_upper_display']>chain[i]['gap_upper_display']+1e-10
           for i in range(len(chain)-1)):
        raise AssertionError('Upper-gap regression within original fixed proof tree')
    out={'case_id':cid,'original_case_sha256':proto['original_case_sha256'][cid],
         'original_data_identity':inp['original_CH23_identity'],'stages':chain,
         'ch29_127_gap':receipt127['gap_upper_display'],'same_process_pid':os.getpid(),
         'total_incremental_cpu_seconds':sum(x['cpu_seconds'] for x in chain),
         'verified':True,'global_certified':False}
    if do_restart:
        # A new interpreter is a real process boundary. It cannot receive any
        # MPFR objects: it loads only the original data and source certificates,
        # then REPLAYS the 63-node prefix before extending to 95 and 127.
        proc=subprocess.run([sys.executable,str(D/'restart31.py'),'--case',cid],
                            check=True,text=True,capture_output=True,timeout=900)
        rec=json.loads(proc.stdout.strip())
        if rec['pid']==os.getpid() or not rec['verified'] or rec['imported_cache'] or rec['restart_reverified_from_scratch']!=63:
            raise AssertionError('Restart cold verification was not enforced')
        if rec['chain'][0]['fresh']!=63 or rec['chain'][0]['reused']!=0:
            raise AssertionError('Fresh process imported trusted prefix incorrectly')
        if abs(rec['chain'][-1]['gap_upper_display']-receipt127['gap_upper_display'])>1e-10:
            raise AssertionError('Restart failed to reproduce original proof')
        out['fresh_process_restart']=rec
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=3)
    p.add_argument('--case',action='append');p.add_argument('--no-restart',action='store_true');a=p.parse_args()
    frozen=D/'frozen_protocol.json';stamp=(D/'frozen_protocol.sha256').read_text().split()[0]
    if sha(frozen)!=stamp:raise ValueError('CH31 frozen protocol digest mismatch')
    fp=json.loads(frozen.read_text());hp=BASE/'CH_C14_29/frozen_protocol.json'
    if sha(hp)!=fp['parent_protocol_sha256']:raise ValueError('CH29 provenance mismatch')
    cases=sorted(fp['original_case_sha256']);cases=[c for c in cases if not a.case or c in a.case]
    start=time.perf_counter();results=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
        futures={pool.submit(verify_case,c,not a.no_restart):c for c in cases}
        for f in concurrent.futures.as_completed(futures):
            try:r=f.result()
            except Exception:
                print('FAILED',futures[f],traceback.format_exc(),flush=True);raise
            results.append(r)
            print('PASS',r['case_id'],'stages','/'.join(str(s['nodes']) for s in r['stages']),
                  'reused',sum(s['reused'] for s in r['stages']),
                  'restart',bool(r.get('fresh_process_restart')),flush=True)
    results.sort(key=lambda x:x['case_id'])
    m={'milestone':'CH-C14-31','frozen_protocol_sha256':stamp,'cases':len(results),
       'per_case':results,'total_cpu_incremental_chain_seconds':sum(x['total_incremental_cpu_seconds'] for x in results),
       'total_cpu_fresh_restart_seconds':sum(sum(s['cpu_seconds'] for s in x['fresh_process_restart']['chain'])
                                             for x in results if 'fresh_process_restart' in x),
       'total_reused_caps_during_chain':sum(sum(s['reused'] for s in x['stages']) for x in results),
       'total_fresh_caps_during_chain':sum(sum(s['fresh'] for s in x['stages']) for x in results),
       'restart_reverified_cases':sum('fresh_process_restart' in x for x in results),
       'global_certificates':0,'scientific_production':'NO_GO',
       'elapsed_wall_seconds':time.perf_counter()-start,
       'intermediate_certificates':'derived_original_CH29_proof_prefixes_not_new_optimizer_runs'}
    name='benchmark_results.json' if len(results)==len(fp['original_case_sha256']) and not a.no_restart else 'benchmark_partial.json'
    (D/name).write_text(json.dumps(m,indent=2,sort_keys=True,allow_nan=False)+'\n')
    print('COMPLETE',name,'original cases',len(results),'restart cold checks',m['restart_reverified_cases'],flush=True)

if __name__=='__main__':main()