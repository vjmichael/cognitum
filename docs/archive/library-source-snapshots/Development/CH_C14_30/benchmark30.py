"""Prospectively frozen original-data replay comparisons, with separate processes."""
from __future__ import annotations
import json,os,sys,time,hashlib,argparse,concurrent.futures,traceback
from pathlib import Path
D=Path(__file__).resolve().parent;BASE=D.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run_one(cid):
    sys.path.insert(0,str(D));sys.path.insert(0,str(BASE/'CH_C14_29'))
    from verifier30 import VerifiedSession,verify_full
    from verifier29 import verify as legacy
    proto=json.loads((BASE/'CH_C14_29/frozen_protocol.json').read_text())
    if sha(BASE/'CH_C14_29/frozen_protocol.json')!=(BASE/'CH_C14_29/frozen_protocol.sha256').read_text().split()[0]:
        raise ValueError('Historical protocol changed')
    inpfile=BASE/'CH_C14_25/inputs'/(cid+'.json')
    if sha(inpfile)!=proto['original_case_sha256'][cid]:raise ValueError('Original dataset digest mismatch')
    inp=json.loads(inpfile.read_text())
    dualfile=BASE/'CH_C14_27/frozen_duals.json'
    if sha(dualfile)!=proto['original_dual_sha256']:raise ValueError('Original dual digest mismatch')
    duals=json.loads(dualfile.read_text())[cid]
    certs={}
    for b in (63,127):
        certfile=BASE/'CH_C14_29/runs/fixed'/str(b)/'certificates'/(cid+'.json')
        verificationfile=BASE/'CH_C14_29/runs/fixed'/str(b)/'verifications'/(cid+'.json')
        expected=json.loads(verificationfile.read_text())
        if expected['certificate_sha256']!=sha(certfile):raise ValueError('Archived certificate digest mismatch')
        cert=json.loads(certfile.read_text())
        if cert.get('original_case_sha256')!=proto['original_case_sha256'][cid]:
            raise ValueError('Original certificate/case link changed')
        certs[b]=(cert,expected)
    session=VerifiedSession();results={}
    for budget in (63,127):
        cfg={**proto,'node_budget_per_case':budget}
        tick=time.process_time()
        result=session.verify(certs[budget][0],inp,cfg,duals)
        results[budget]={'cpu_seconds':time.process_time()-tick,'receipt':result}
        previous=certs[budget][1]
        if (result['replay_status']!=previous['replay_status'] or
            abs(result['gap_upper_display']-previous['gap_upper_display'])>1e-10 or
            result['leaf_count']!=previous['leaf_count']):
            raise AssertionError('New incremental result disagrees with original complete verification')
    cfg={**proto,'node_budget_per_case':127}
    tick=time.process_time();old=legacy(certs[127][0],inp,cfg,duals)
    cold_cpu=time.process_time()-tick
    if abs(old['gap_upper_display']-results[127]['receipt']['gap_upper_display'])>1e-10:
        raise AssertionError('Fresh original full replay disagrees with incremental')
    if results[127]['receipt']['verified_prefix_nodes_reused']!=63 or results[127]['receipt']['ancestor_caps_recomputed']!=64:
        raise AssertionError('Missing expected 63 -> 127 incremental node savings')
    return {'case_id':cid,'identity':inp['original_CH23_identity'],
            'cold_63_cpu_seconds':results[63]['cpu_seconds'],
            'incremental_127_cpu_seconds':results[127]['cpu_seconds'],
            'legacy_cold_127_cpu_seconds':cold_cpu,
            'baseline_63_gap':results[63]['receipt']['gap_upper_display'],
            'baseline_127_gap':results[127]['receipt']['gap_upper_display'],
            'node_reuse_127':results[127]['receipt']['verified_prefix_nodes_reused'],
            'fresh_nodes_127':results[127]['receipt']['ancestor_caps_recomputed'],
            'status':results[127]['receipt']['replay_status'],'pass':True}


def main():
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=3);p.add_argument('--limit',type=int);p.add_argument('--case',action='append')
    a=p.parse_args()
    frozen=json.loads((D/'frozen_protocol.json').read_text())
    if sha(D/'frozen_protocol.json')!=(D/'frozen_protocol.sha256').read_text().split()[0]:raise ValueError('CH30 protocol mismatch')
    hist=json.loads((BASE/'CH_C14_29/frozen_protocol.json').read_text())
    if sha(BASE/'CH_C14_29/frozen_protocol.json')!=frozen['historical_protocol_sha256']:raise ValueError('CH29 protocol changed')
    cids=sorted(hist['original_case_sha256'])
    if a.case:cids=[x for x in cids if x in a.case]
    if a.limit:cids=cids[:a.limit]
    results=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
        futures={pool.submit(run_one,cid):cid for cid in cids}
        for f in concurrent.futures.as_completed(futures):
            cid=futures[f]
            try:r=f.result()
            except Exception:
                print('FAIL',cid,traceback.format_exc(),flush=True);raise
            results.append(r)
            print('PASS',cid,'cold127',round(r['legacy_cold_127_cpu_seconds'],2),
                  'increment127',round(r['incremental_127_cpu_seconds'],2),
                  'reuse',r['node_reuse_127'],flush=True)
    results.sort(key=lambda r:r['case_id'])
    out={'protocol_sha256':sha(D/'frozen_protocol.json'), 'cohort_size':len(results), 'per_case':results,
         'total_cold_63_cpu_seconds':sum(x['cold_63_cpu_seconds'] for x in results),
         'total_incremental_127_cpu_seconds':sum(x['incremental_127_cpu_seconds'] for x in results),
         'total_legacy_cold_127_cpu_seconds':sum(x['legacy_cold_127_cpu_seconds'] for x in results),
         'total_reused_mpfr_caps':sum(x['node_reuse_127'] for x in results),
         'total_fresh_mpfr_caps':sum(x['fresh_nodes_127'] for x in results),
         'global_certificates':sum(x['status']=='VERIFIED_BOUNDED_GAP' for x in results)}
    out['speedup_incremental_step_vs_cold_127']=(out['total_legacy_cold_127_cpu_seconds']/out['total_incremental_127_cpu_seconds'])
    out['reduction_for_two_certificates']=(1-(out['total_cold_63_cpu_seconds']+out['total_incremental_127_cpu_seconds'])/(out['total_cold_63_cpu_seconds']+out['total_legacy_cold_127_cpu_seconds']))
    name='benchmark_results.json' if len(results)==15 else 'benchmark_partial.json'
    (D/name).write_text(json.dumps(out,indent=2,sort_keys=True,allow_nan=False)+'\n')
    print('RESULT',name,'CASES',len(results),'INCREMENTAL_SPEEDUP',round(out['speedup_incremental_step_vs_cold_127'],3),flush=True)

if __name__=='__main__':main()