"""Local host contract tests (separate from E2E independent acceptance)."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
HOST=ROOT/'integration'/'c14_research_host.py'
sys.path.insert(0,str(ROOT/'integration'))
from c14_research_host import handle, canonical, parse_request, to_counts, host_reply
import pytest

SAFE={
    'sampling_iid_supported':True,'consistency_supported':True,
    'measurement_validity_supported':True,
    'gamma_justification':'Analyst has a prior-specified risk-difference bound with external rationale',
    'exchangeability_justification':'Measured adjustment variables are believed to satisfy conditional exchangeability'
}
C=[[[67,35],[45,31]],[[75,30],[48,39]]]

def req(ident='t1',**k):
    v={'schema_version':1,'request_id':ident,'action':'c14.g25.sensitivity.report',
       'counts':C,'gamma':.25,'assumption_evidence':SAFE}
    v.update(k)
    return v

def call(v,ids=None):
    return handle(canonical(v).encode(),set() if ids is None else ids)

def test_good_research_host():
    r=call(req()); assert r['host_status']=='completed'
    assert r['result']['status']=='conditional_sensitivity_report_only'
    assert r['result']['identified_set_outer95_conditional'][0]<r['result']['identified_set_plugin'][0]
    assert r['result']['identified_set_outer95_conditional'][1]>r['result']['identified_set_plugin'][1]
    assert r['research_only'] and r['automatic_causal_certification'] is False
    assert r['result']['automatic_causal_certification'] is False

def test_missing_arm():
    z=[[[67,35],[0,0]],[[75,30],[48,39]]]
    r=call(req(counts=z)); assert r['host_status']=='refused'
    assert r['result']['status']=='blocked_missing_observed_arm'
    assert r['result']['identified_set_outer95_conditional'] is None

def test_sparse_arm():
    z=[[[67,35],[8,10]],[[75,30],[48,39]]]
    r=call(req(counts=z)); assert r['host_status']=='refused'
    assert r['result']['status']=='blocked_sparse_observed_arm'

def test_missing_gamma_assumptions():
    r=call(req(assumption_evidence={})); assert r['host_status']=='refused'
    assert r['result']['status']=='blocked_missing_assumption_evidence'
    o=req();del o['gamma']
    assert call(o)['host_status']=='invalid_request'

def test_empty_report_for_invalid_shape():
    assert call(req(counts=[[1,2],[3,4]]))['result'] is None

def test_duplicate_request_id_refused():
    seen=set();assert call(req(),seen)['host_status']=='completed'
    assert call(req(),seen)['error_code']=='duplicate_request_id'

def test_mutated_receipt_detectable():
    r=call(req());base={k:v for k,v in r.items() if k!='host_receipt_sha256'}
    assert r['host_receipt_sha256']==hashlib.sha256(canonical(base).encode()).hexdigest()
    r['automatic_causal_certification']=True
    base={k:v for k,v in r.items() if k!='host_receipt_sha256'}
    assert r['host_receipt_sha256']!=hashlib.sha256(canonical(base).encode()).hexdigest()

@pytest.mark.parametrize('bad',[
  b'{"schema_version":1,"schema_version":1}',
  b'{"schema_version":1,"request_id":"t1","action":"c14.g25.sensitivity.report","counts":[],"gamma":NaN}',
  b'not a json document',
])
def test_invalid_json_fails_closed(bad):
    r=handle(bad,set());assert r['host_status']=='invalid_request';assert r['result'] is None

@pytest.mark.parametrize('changed',[
    {'counts':[[[1.5,2],[3,4]],[[5,6],[7,8]]]},
    {'counts':[[[True,2],[3,4]],[[5,6],[7,8]]]},
    {'counts':[[[-1,2],[3,4]],[[5,6],[7,8]]]},
    {'gamma':True},{'gamma':float('inf')},
    {'request_id':'../../../usr'},
    {'action':'c14.g25.production.certify'},
])
def test_bad_request_fails_closed(changed):
    if changed.get('gamma')==float('inf'):
        obj=req();obj.update(changed);raw=json.dumps(obj).encode()
        r=handle(raw,set())
    else:
        obj=req();obj.update(changed);r=call(obj)
    assert r['host_status']=='invalid_request'
    assert r['result'] is None

def test_records_equivalent_to_counts():
    rows=[]
    for w in (0,1):
        for t in (0,1):
            for y in (0,1): rows += [{'w':w,'t':t,'y':y}]*C[w][t][y]
    a=call(req())
    b=req('records');del b['counts'];b['observations']=rows
    r=call(b)
    assert r['host_status']=='completed'
    assert r['result']==a['result']

def test_disablement_both_ways():
    for flag,env in [(False,True),(True,False),(False,False)]:
        e=os.environ.copy()
        e.pop('COGNITUM_G25_RESEARCH_OPT_IN',None)
        if env: e['COGNITUM_G25_RESEARCH_OPT_IN']='1'
        p=subprocess.run([sys.executable,str(HOST)]+(['--research-only'] if flag else []),
             env=e,input='',capture_output=True,text=True,timeout=5)
        assert p.returncode==78 and not p.stdout

def test_separate_process_json_lines():
    data=[canonical(req('p1')),canonical(req('p2',gamma=0)),canonical(req('p2',gamma=1))]
    e=os.environ.copy();e['COGNITUM_G25_RESEARCH_OPT_IN']='1'
    p=subprocess.run([sys.executable,str(HOST),'--research-only'],env=e,
       input='\n'.join(data)+'\n',capture_output=True,text=True,timeout=12)
    assert p.returncode==0,p.stderr
    v=[json.loads(s) for s in p.stdout.splitlines()]
    assert [x['host_status'] for x in v]==['completed','completed','invalid_request']


def test_host_can_be_terminated_while_blocked_reading_stdin():
    e=os.environ.copy();e['COGNITUM_G25_RESEARCH_OPT_IN']='1'
    p=subprocess.Popen([sys.executable,str(HOST),'--research-only'],env=e,
         stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        p.stdin.write(b'{"partial":');p.stdin.flush()
        p.terminate()
        assert p.wait(timeout=3) is not None
    finally:
        if p.poll() is None:p.kill();p.wait(timeout=3)


def test_unexpected_calculation_failure_is_fail_closed(monkeypatch):
    import c14_research_host as host
    def crash(*args,**kw):raise RuntimeError('simulated backend internal failure')
    monkeypatch.setattr(host,'report',crash)
    response=host.handle(canonical(req('fault')).encode(),set())
    assert response['host_status']=='internal_failure'
    assert response['result'] is None
    assert response['automatic_causal_certification'] is False
    assert response['error_code']=='research_worker_internal_error'
    assert 'simulated' not in canonical(response)


def test_oversized_input_aborts_without_echoing_request():
    e=os.environ.copy();e['COGNITUM_G25_RESEARCH_OPT_IN']='1'
    data=b'x'*(1024*1024+10)+b'\n'
    run=subprocess.run([sys.executable,str(HOST),'--research-only'],
        env=e,input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=12)
    assert run.returncode==65
    lines=run.stdout.splitlines()
    assert len(lines)==1
    r=json.loads(lines[0]);assert r['host_status']=='invalid_request'
    assert r['result'] is None
    assert r['error_code']=='line_too_large_stream_closed'
    assert len(lines[0])<1500
