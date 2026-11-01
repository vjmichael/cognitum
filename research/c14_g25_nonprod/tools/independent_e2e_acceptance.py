#!/usr/bin/env python3
"""Independent process-level C14 G25 acceptance, no candidate imports.

The host is a black box. Statistical references use statsmodels and a separate
SciPy HiGHS LP decomposition; no import from g25_release_guard or g25i_core.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import numpy as np
from scipy.optimize import linprog
from statsmodels.stats.proportion import proportion_confint

ROOT=Path(__file__).resolve().parents[1]
ARCHIVE=Path(os.environ.get('G25N_ARCHIVE_RESULTS','/mnt/data/Cognitum_C14_G25N_2026-11-01/results'))
HOST=ROOT/'integration'/'c14_research_host.py'
PROTOCOL=ROOT/'docs'/'Independent_E2E_Freeze.json'
RESULTS=ROOT/'results'
ACTION='c14.g25.sensitivity.report'

SAFE={
 'sampling_iid_supported':True,'consistency_supported':True,
 'measurement_validity_supported':True,
 'gamma_justification':'External analyst-specified confounding-difference restriction, not data-verified',
 'exchangeability_justification':'Independent observational design assessment, not empirically verified'
}

def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False)

def sha(data):return hashlib.sha256(data).hexdigest()

def req(ident,z,g,ev=SAFE,observations=False):
    out={'schema_version':1,'request_id':ident,'action':ACTION,'gamma':g,'assumption_evidence':ev}
    if observations:
        rows=[]
        for w in (0,1):
            for t in (0,1):
                for y in (0,1):rows.extend([{'w':w,'t':t,'y':y}]*int(z[w,t,y]))
        out['observations']=rows
    else:out['counts']=z.tolist()
    return out

def cp(k,n,alpha):
    if n==0:raise AssertionError('unexpected zero denominator')
    return tuple(float(x) for x in proportion_confint(k,n,alpha=alpha,method='beta'))

def independent_math(z,g):
    """Different libraries and LP for point-identified set; reference CP bounds."""
    n=int(z.sum());nr=z.sum(axis=(1,2));a=z.sum(axis=2)
    p0=int(nr[0])/n
    # Solve counterfactual mean extrema with a separate linear-programming implementation.
    strata=[];lo_strata=[];hi_strata=[]
    for w in (0,1):
        denom=int(nr[w]);a0=int(a[w,0]);a1=int(a[w,1])
        e=a1/denom
        m0=int(z[w,0,1])/a0;m1=int(z[w,1,1])/a1
        cbounds=[(max(0,m1-g),min(1,m1+g)),(max(0,m0-g),min(1,m0+g))]
        objective=np.array([1-e,-e],dtype=float)
        baseline=e*m1-(1-e)*m0
        l=linprog(objective,bounds=cbounds,method='highs')
        h=linprog(-objective,bounds=cbounds,method='highs')
        if not(l.success and h.success):raise AssertionError('independent counterfactual LP failed')
        strata.append((baseline+l.fun,baseline-h.fun))
        eel=cp(a1,denom,.05/7)
        m0l=cp(int(z[w,0,1]),a0,.05/7)
        m1l=cp(int(z[w,1,1]),a1,.05/7)
        # Endpoints of the partial-identification contrast at the confidence-rectangle corners.
        def lb(e_):
            return e_*m1l[0]+(1-e_)*max(0.,m1l[0]-g)-(1-e_)*m0l[1]-e_*min(1.,m0l[1]+g)
        def ub(e_):
            return e_*m1l[1]+(1-e_)*min(1.,m1l[1]+g)-(1-e_)*m0l[0]-e_*max(0.,m0l[0]-g)
        lo_strata.append(min(lb(eel[0]),lb(eel[1])))
        hi_strata.append(max(ub(eel[0]),ub(eel[1])))
    identified=[p0*strata[0][k]+(1-p0)*strata[1][k] for k in (0,1)]
    pw=cp(int(nr[0]),n,.05/7)
    lower=min(p*lo_strata[0]+(1-p)*lo_strata[1] for p in pw)
    upper=max(p*hi_strata[0]+(1-p)*hi_strata[1] for p in pw)
    return identified,[max(-1.,lower),min(1.,upper)]

def check_sha(r):
    body={k:v for k,v in r.items() if k!='host_receipt_sha256'}
    if r['host_receipt_sha256']!=sha(canonical(body).encode()):
        raise AssertionError('host receipt hash mismatch')
    if r.get('result') is not None:
        core=r['result'];body={k:v for k,v in core.items() if k!='receipt_sha256'}
        if core['receipt_sha256']!=sha(canonical(body).encode()):
            raise AssertionError('guard semantic receipt hash mismatch')

def assert_blackbox_result(response,input_raw,z,g,ev):
    if response['input_sha256']!=sha(input_raw):raise AssertionError('input digest mismatch')
    check_sha(response)
    for key in ('automatic_causal_certification','production_estimator_promotion'):
        if response.get(key) is not False:raise AssertionError('host incorrectly granted '+key)
    if response['research_only'] is not True:raise AssertionError('research flag absent')
    arm=z.sum(axis=2)
    if int(arm.min())==0:expected='blocked_missing_observed_arm'
    elif int(arm.min())<25:expected='blocked_sparse_observed_arm'
    elif ev is None or ev=={}:expected='blocked_missing_assumption_evidence'
    else:expected='conditional_sensitivity_report_only'
    ret=response['result']
    if ret is None or ret['status']!=expected:
        raise AssertionError(f'wrong refusal/completion status expected={expected} actual={ret}')
    if ret['automatic_causal_certification'] or ret['production_estimator_promotion'] or ret['unmeasured_confounding_excluded'] or ret['identification_verified_from_data']:
        raise AssertionError('inference/identification authorization exposed')
    if ret['counts_sha256']!=sha(canonical(z.tolist()).encode()):
        raise AssertionError('counts digest mismatch')
    if expected!='conditional_sensitivity_report_only':
        if ret['identified_set_plugin'] is not None or ret['identified_set_outer95_conditional'] is not None:
            raise AssertionError('numerical result leaked after refusal')
        return expected,0.
    ref_id,ref_ci=independent_math(z,g)
    delta=max(abs(float(a)-float(b)) for x,y in ((ret['identified_set_plugin'],ref_id),(ret['identified_set_outer95_conditional'],ref_ci)) for a,b in zip(x,y))
    if delta>1e-10:raise AssertionError(f'independent numerical mismatch: {delta}')
    return expected,delta

def build_cases(protocol):
    cells=sorted(ARCHIVE.glob('G25N_[AB]_*.jsonl'))
    assert len(cells)==28, len(cells)
    samples=[]
    for p in cells:
        count=0
        with p.open() as f:
            for ln in f:
                d=json.loads(ln)
                z=np.array(d['counts'],dtype=np.int64)
                assert z.shape==(2,2,2) and z.sum()==d['n']
                ident=f"archive-{p.stem.replace('G25N_','')}-{count:03d}"
                samples.append((req(ident,z,.25,SAFE),z,.25,SAFE,'archived',d))
                count+=1
                if count==20:break
        assert count==20
    assert len(samples)==protocol['archived_total_expected']
    rng=np.random.default_rng(protocol['fresh_rng_seed'])
    for i in range(protocol['fresh_count']):
        n=int(rng.choice([400,650,900,1800]))
        probs=rng.dirichlet(np.full(8,rng.choice([.22,.55,1.1,2.0])))
        z=rng.multinomial(n,probs).reshape(2,2,2).astype(np.int64)
        if i%17==0:z[0,1,:]=0
        if i%19==0:z[1,0,:]=0
        if i%13==0:z[0,0,:]=[2,3]
        ev={} if i%23==0 else SAFE
        g=protocol['gamma_values'][i%len(protocol['gamma_values'])]
        obs=(i%27==0 and int(z.sum())<=1800)
        samples.append((req(f'fresh-{i:04d}',z,g,ev,observations=obs),z,g,ev,'fresh',None))
    return samples

def run_binary_messages(raw_lines,timeout=75):
    env=os.environ.copy();env.update({'COGNITUM_G25_RESEARCH_OPT_IN':'1','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'})
    payload=b'\n'.join(raw_lines)+b'\n'
    r=subprocess.run([sys.executable,str(HOST),'--research-only'],input=payload,
       stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,timeout=timeout)
    if r.returncode!=0:raise AssertionError(f'host failed exit={r.returncode}, stderr={r.stderr[:200]!r}')
    lines=r.stdout.splitlines()
    if len(lines)!=len(raw_lines):raise AssertionError(f'wrong response count {len(lines)} expected {len(raw_lines)}')
    return [json.loads(t) for t in lines]

def test_bad_requests():
    base={'schema_version':1,'request_id':'invalid-001','action':ACTION,'counts':[[[1,1],[1,1]],[[1,1],[1,1]]],
         'gamma':.25,'assumption_evidence':SAFE}
    bad=[]
    def add(name,raw):bad.append((name,raw))
    add('invalid_json',b'{')
    add('duplicate_key',b'{"a":1,"a":2}')
    add('invalid_nan',b'{"value": NaN}')
    for name,change in [
      ('missing_gamma',{'__remove_gamma__':True}),('bad_shape',{'counts':[[1,2],[3,4]]}),
      ('noninteger',{'counts':[[[1.5,2],[3,4]],[[5,6],[7,8]]]}),
      ('negative',{'counts':[[[-1,2],[3,4]],[[5,6],[7,8]]]}),
      ('wrong_action',{'action':'c14.g25.production.promote'}),
      ('bool_count',{'counts':[[[True,2],[3,4]],[[5,6],[7,8]]]}),
      ('huge_count',{'counts':[[[2_000_000,2],[3,4]],[[5,6],[7,8]]]}),
      ('wrong_schema',{'schema_version':0}),
      ('bad_request_id',{'request_id':'../../etc/passwd'}),
    ]:
        m=base.copy();m.update(change)
        if name!='bad_request_id':m['request_id']=f'adversarial-{name}'
        if change.get('__remove_gamma__'):
            m.pop('__remove_gamma__');m.pop('gamma')
        add(name,canonical(m).encode())
    m=base.copy();m['request_id']='adversarial-boolean';m.pop('counts');m['observations']=[{'w':True,'t':0,'y':1}]
    add('boolean_observation',canonical(m).encode())
    m=base.copy();m['request_id']='adversarial-nonbinary';m.pop('counts');m['observations']=[{'w':0,'t':0,'y':3}]
    add('nonbinary_observation',canonical(m).encode())
    m=base.copy();m['request_id']='adversarial-unknown';m['extra']='unauthorized';add('unknown_field',canonical(m).encode())
    r=run_binary_messages([x[1] for x in bad])
    expected_error_codes={
      'duplicate_key':'duplicate_json_key','invalid_nan':'invalid_json_constant',
      'missing_gamma':'gamma_must_be_explicit', 'bad_shape':'expected exactly eight W,T,Y count cells',
      'noninteger':'counts must be integers, not booleans or real-valued inputs',
      'negative':'count outside supported exact-integer range',
      'wrong_action':'unsupported_action','bool_count':'counts must be integers, not booleans or real-valued inputs',
      'huge_count':'sample_exceeds_host_limit','wrong_schema':'unsupported_schema_version',
      'bad_request_id':'invalid_request_id',
      'boolean_observation':'nonbinary_or_boolean_observation',
      'nonbinary_observation':'nonbinary_or_boolean_observation',
      'unknown_field':'invalid_request_object_or_fields'}
    for (name,raw),item in zip(bad,r):
        if item['host_status']!='invalid_request' or item['result'] is not None:
            raise AssertionError(f'unsafe malformed request {name}: {item}')
        check_sha(item)
        if name in expected_error_codes and item['error_code']!=expected_error_codes[name]:
            raise AssertionError(f'{name} failed for unexpected reason: {item["error_code"]!r}')
    duplicate=base.copy();duplicate['request_id']='adversarial-replay'
    responses=run_binary_messages([canonical(duplicate).encode()]*2)
    if responses[0]['host_status']!='refused' or responses[1]['error_code']!='duplicate_request_id':
        raise AssertionError('duplicate request ID accepted')
    return [name for name,_ in bad]+['duplicate_request_id']

def check_host_disabled_and_termination():
    e=os.environ.copy();e.pop('COGNITUM_G25_RESEARCH_OPT_IN',None)
    res=subprocess.run([sys.executable,str(HOST),'--research-only'],env=e,input=b'',stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=5)
    if res.returncode!=78 or res.stdout:raise AssertionError('disabled-by-default gate bypass')
    env=os.environ.copy();env['COGNITUM_G25_RESEARCH_OPT_IN']='1'
    res=subprocess.run([sys.executable,str(HOST)],env=env,input=b'',stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=5)
    if res.returncode!=78 or res.stdout:raise AssertionError('explicit flag gate bypass')
    child=subprocess.Popen([sys.executable,str(HOST),'--research-only'],env=env,stdin=subprocess.PIPE,
         stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        child.stdin.write(b'{"partial":');child.stdin.flush()
        child.terminate()
        child.wait(timeout=3)
    finally:
        if child.poll() is None:child.kill();child.wait(timeout=3)
    return {'env_disabled_exit_code':res.returncode,'partial_input_process_terminated':True}

def main():
    proto=json.loads(PROTOCOL.read_text())
    if sha(PROTOCOL.read_bytes())!='8fee77828ee869d2dc20ab88bed8d65b1e3048099902113898707e08b730ad07':
        raise AssertionError('frozen protocol hash changed')
    cases=build_cases(proto)
    req_lines=[canonical(q[0]).encode() for q in cases]
    RESULTS.mkdir(parents=True,exist_ok=True)
    (RESULTS/'Independent_E2E_Requests.jsonl').write_bytes(b'\n'.join(req_lines)+b'\n')
    answers=run_binary_messages(req_lines,timeout=80)
    (RESULTS/'Independent_E2E_Responses.jsonl').write_text(''.join(canonical(q)+'\n' for q in answers))
    status={};delta=0.;audit=[]
    for (request,z,g,ev,source,original),raw,response in zip(cases,req_lines,answers):
        if response['request_id']!=request['request_id']:raise AssertionError('request ID misrouted')
        s,d=assert_blackbox_result(response,raw,z,g,ev)
        if original is not None and original['supported'] is False and s!='blocked_missing_observed_arm':
            raise AssertionError('original research negative control no longer refused')
        if original is not None and s=='conditional_sensitivity_report_only':
            if max(abs(a-b) for a,b in zip(original['cp_ref'],response['result']['identified_set_outer95_conditional']))>1e-10:
                raise AssertionError('archived G25I numerical equivalence changed')
        status[s]=status.get(s,0)+1;delta=max(d,delta)
        audit.append({'id':request['request_id'],'source':source,'input_sha256':sha(raw),'host_status':response['host_status'],'guard_status':s,'numerical_reference_abs_max_delta':d})
    invalid=test_bad_requests()
    kill=check_host_disabled_and_termination()
    (RESULTS/'Independent_E2E_Receipt_Audit.jsonl').write_text(''.join(canonical(x)+'\n' for x in audit))
    summary={
      'milestone':proto['milestone'],'research_only':True,'accepted_nonproduction_e2e':True,
      'frozen_protocol_sha256':sha(PROTOCOL.read_bytes()),
      'pinned_G25I_sha256':sha((ROOT/'baseline'/'g25i_core.py').read_bytes()),
      'pinned_guard_sha256':sha((ROOT/'tools'/'g25_release_guard.py').read_bytes()),
      'total_valid_envelopes':len(cases),'archived_cases':proto['archived_total_expected'],'fresh_cases':proto['fresh_count'],
      'status_accounting':status,'numerical_independent_reference_max_abs_delta':delta,
      'malformed_negative_controls_passed':len(invalid),'negative_control_names':invalid,
      'host_disabled_and_termination':kill,'automatic_causal_certifications':0,'production_promotions':0,
      'candidate_source_imported_by_independent_harness':False,
      'no_production_or_lu_changes':True,
      'remaining_open_gates':['statistical generality/calibration','external Firth software parity','independent human scientific review','in-flight soft cancellation','Windows process containment test','production authorization'],
    }
    (RESULTS/'Independent_E2E_Acceptance.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    main()
