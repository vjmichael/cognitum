#!/usr/bin/env python3
"""Black-box C14 G25 v2 supervisor audit. No imports of candidate host/guard/baseline."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time
import numpy as np
from statsmodels.stats.proportion import proportion_confint

ROOT=Path(__file__).resolve().parents[1]
RESULTS=ROOT/'results'
SCRIPT=ROOT/'integration/g25_cancellable_supervisor.py'
ASSUME={'sampling_iid_supported':True,'consistency_supported':True,
       'measurement_validity_supported':True,
       'gamma_justification':'Precommitted scientific knowledge of selection bias upper bound',
       'exchangeability_justification':'Assumed full adjustment for observed W'}


def c(x): return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)


def cp(k,n):
    v=proportion_confint(k,n,alpha=.05/7,method='beta')
    return (float(v[0]),float(v[1]))


def bound_e(e,m0,m1,g):
    return (e*m1+(1-e)*max(0.,m1-g)-(1-e)*m0-e*min(1.,m0+g),
            e*m1+(1-e)*min(1.,m1+g)-(1-e)*m0-e*max(0.,m0-g))


def separate_oracle(z,g):
    n=int(z.sum()); stratum=z.sum(axis=(1,2));arm=z.sum(axis=2)
    if arm.min()<25: return None
    plug=[];outer=[]
    for w in (0,1):
        e=arm[w,1]/stratum[w]
        m0=z[w,0,1]/arm[w,0];m1=z[w,1,1]/arm[w,1]
        plug.append(bound_e(e,m0,m1,g))
        e_ci=cp(int(arm[w,1]),int(stratum[w]))
        m0_ci=cp(int(z[w,0,1]),int(arm[w,0]))
        m1_ci=cp(int(z[w,1,1]),int(arm[w,1]))
        vals=[bound_e(x,a,b,g) for x in e_ci for a in m0_ci for b in m1_ci]
        outer.append((min(v[0] for v in vals),max(v[1] for v in vals)))
    weights=cp(int(stratum[0]),n)
    p=float(stratum[0]/n)
    plugin=[p*plug[0][0]+(1-p)*plug[1][0],p*plug[0][1]+(1-p)*plug[1][1]]
    lo=min(x*outer[0][0]+(1-x)*outer[1][0] for x in weights)
    hi=max(x*outer[0][1]+(1-x)*outer[1][1] for x in weights)
    return plugin,[max(-1.,lo),min(1.,hi)]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--part",type=int,choices=range(4),required=True)
    part=parser.parse_args().part
    RESULTS.mkdir(exist_ok=True)
    rng=np.random.default_rng(2026110157)
    cases=[]
    # 32 fresh, independent of prior holdouts. Each arm >=25 by construction.
    for i in range(32):
        z=np.zeros((2,2,2),dtype=int)
        for w in (0,1):
            for t in (0,1):
                n=int(rng.integers(75,225))
                k=int(rng.binomial(n,float(rng.uniform(.12,.73))))
                z[w,t,:]=[n-k,k]
        cases.append((f'positive-{i:02}',z,float([0.,.1,.25,.5,1.][i%5]),'completed'))
    for i in range(4):
        z=np.array([[[67,35],[45,31]],[[75,30],[48,39]]])
        if i%2==0: z[0,1,:]=0
        else: z[1,0,:]=0
        cases.append((f'missing-{i}',z,.25,'refused'))
    for i in range(4):
        z=np.array([[[67,35],[45,31]],[[75,30],[48,39]]])
        if i%2==0:z[0,1,:]=[10,12]
        else:z[1,0,:]=[9,13]
        cases.append((f'sparse-{i}',z,.25,'refused'))
    cases=cases[part*10:(part+1)*10]
    controls=[]
    for ident,z,g,expect in cases:
        req={'schema_version':1,'request_id':ident,'action':'c14.g25.sensitivity.report',
             'counts':z.tolist(),'gamma':g,'assumption_evidence':ASSUME}
        controls.append({'protocol_version':2,'type':'run','request_id':ident,'request':req})
    expected_cases={i:(z,g,k) for i,z,g,k in cases}
    env=os.environ.copy()
    env['COGNITUM_G25_RESEARCH_OPT_IN']='1'
    env['OPENBLAS_NUM_THREADS']=env['OMP_NUM_THREADS']=env['MKL_NUM_THREADS']='1'
    process=subprocess.Popen([sys.executable,str(SCRIPT),'--research-only'],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,bufsize=0)
    controls_log=[];events_log=[];maxerr=0.; issued=0;refused=0
    start=time.monotonic()
    try:
        for ctrl in controls:
            raw=c(ctrl).encode()+b'\n'
            process.stdin.write(raw);process.stdin.flush();controls_log.append(c(ctrl))
            for target in ('accepted','result'):
                readable,_,_=select.select([process.stdout],[],[],10)
                if not readable: raise AssertionError(f'no {target} for {ctrl["request_id"]}')
                event=json.loads(process.stdout.readline())
                events_log.append(c(event))
                if event['event']!=target or event['request_id']!=ctrl['request_id']:
                    raise AssertionError('wrong event/identity/order')
                if event['automatic_causal_certification'] is not False or event['production_estimator_promotion'] is not False:
                    raise AssertionError('unauthorized certification')
                if target=='result':
                    r=event['response'];z,g,kind=expected_cases[ctrl['request_id']]
                    assert r['host_status']==kind and r['research_only'] is True
                    assert r['request_id']==ctrl['request_id']
                    body={k:v for k,v in r.items() if k!='host_receipt_sha256'}
                    assert hashlib.sha256(c(body).encode()).hexdigest()==r['host_receipt_sha256']
                    if kind=='completed':
                        issued+=1
                        plugin,outer=separate_oracle(z,g)
                        got=r['result']
                        assert got['status']=='conditional_sensitivity_report_only'
                        for key,expect in [('identified_set_plugin',plugin),('identified_set_outer95_conditional',outer)]:
                            delta=max(abs(float(v)-float(w)) for v,w in zip(got[key],expect))
                            maxerr=max(maxerr,delta)
                            assert delta < 1e-12,(key,delta)
                        assert got['automatic_causal_certification'] is False
                    else:
                        refused+=1
                        assert r['result']['identified_set_outer95_conditional'] is None
        # Release task IDs cannot be replayed.
        control=controls[0]
        process.stdin.write(c(control).encode()+b'\n');process.stdin.flush();controls_log.append(c(control))
        readable,_,_=select.select([process.stdout],[],[],5)
        assert readable
        dup=json.loads(process.stdout.readline());events_log.append(c(dup))
        assert dup['event']=='rejected' and dup['code']=='duplicate_task_id'
    finally:
        process.stdin.close()
        try:code=process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill();code=process.wait(timeout=3)
        err=process.stderr.read()
        process.stdout.close();process.stderr.close()
    assert code==0 and not err,(code,err[:200])
    assert issued+refused==10
    (RESULTS/f'Supervisor_Blackbox_Requests_part{part}.jsonl').write_text('\n'.join(controls_log)+'\n')
    (RESULTS/f'Supervisor_Blackbox_Responses_part{part}.jsonl').write_text('\n'.join(events_log)+'\n')
    summary={'milestone':'C14_G25_STANDALONE_CANCEL_RESEARCH', 'date':'2026-11-01',
         'source_sha256':hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),
         'part':part, 'fresh_datasets':len(cases),'accepted_numerical':issued,'scientifically_refused':refused,
         'blackbox_request_exchanges':len(cases),'duplicate_control_rejected':True,
         'matched_independent_binomial_oracle':issued,
         'max_abs_numeric_difference':maxerr,'duration_seconds':round(time.monotonic()-start,3),
         'default_cognitum_modified':False,'lu_modified':False,
         'causal_certifications':0,'production_promotions':0,
         'windows_process_tree_containment':'NOT_TESTED',
         'linux_process_group_containment':'TESTED_IN_UNIT_HOSTILE_DESCENDANT',
         'g25_scientific_calibration':'FAIL_UNCHANGED'}
    for key in (f'Supervisor_Blackbox_Requests_part{part}.jsonl',f'Supervisor_Blackbox_Responses_part{part}.jsonl'):
        summary[key+'_sha256']=hashlib.sha256((RESULTS/key).read_bytes()).hexdigest()
    (RESULTS/f'Standalone_Supervisor_Acceptance_part{part}.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(json.dumps(summary,indent=2,sort_keys=True))

if __name__=='__main__':main()
