"""Local nonproduction Cognitum Runtime/Registry/Worker integration smoke.

Uses byte-for-byte six GitHub module copies, compared against Git blob hashes.
The external JSONL acceptance is in independent_e2e_acceptance.py.
"""
import hashlib
import json
import os
from pathlib import Path
from dataclasses import replace
import sys
import multiprocessing as mp

ROOT=Path(__file__).resolve().parents[1]
NATIVE_ROOT=(ROOT/'runtime_reference') if (ROOT/'runtime_reference'/'cognitum'/'runtime.py').is_file() else ROOT.parents[1]
sys.path.insert(0,str(NATIVE_ROOT))
sys.path.insert(1,str(ROOT))
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.contracts import HostContext, Request
from cognitum.tracing import Trace
from integration.cognitum_research_plugin import G25ConditionalResearchPlugin, PLUGIN_NAME, SLOT
from integration.c14_research_host import ACTION, canonical

EXPECTED_GITHUB_BLOBS={
  'contracts':'11d129fb057641ac5da67fccd2f541da0860992f',
  'registry':'288171a1113e1d7d259b353ae8703e6ca34fc7b1',
  'policy':'a86abb2231d9594f591e5958f44f006cbf7d3eb6',
  'worker':'8246e955525655414c2da95d7153a794f011a0ef',
  'runtime':'885c4bf56114c7cab98252539e5900113ae3418b',
  'tracing':'338e59dd8acd5f22d2e8becbd626595486698aba'
}

def git_blob_sha(data):return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()

def make_request(ident='native-test',gamma=.25,counts=None,timeout_ms=10000):
    evidence={'sampling_iid_supported':True,'consistency_supported':True,
      'measurement_validity_supported':True,
      'gamma_justification':'Independent analyst-supplied assumption for research reporting',
      'exchangeability_justification':'External observational adjustment design documentation'}
    body={'schema_version':1,'request_id':ident,'action':ACTION,
       'counts':counts if counts is not None else [[[67,35],[45,31]],[[75,30],[48,39]]],
       'gamma':gamma,'assumption_evidence':evidence}
    return Request(ident,'correlation-'+ident,ACTION,{'request_json':canonical(body)},
       workspace_id='research',subject_id='tester',timeout_ms=timeout_ms)

def main():
    original_env=os.environ.get('COGNITUM_G25_RESEARCH_OPT_IN')
    try:
        os.environ.pop('COGNITUM_G25_RESEARCH_OPT_IN',None)
        registry=Registry()
        try:registry.install(G25ConditionalResearchPlugin,enabled=False)
        except ValueError:pass
        else:raise AssertionError('nonproduction plugin installed without explicit environment opt-in')
        os.environ['COGNITUM_G25_RESEARCH_OPT_IN']='1'
        info=registry.install(G25ConditionalResearchPlugin,enabled=False)
        assert info.track=='research' and info.maturity=='prototype'
        assert info.operations[0].effects==()
        registry.nominate(SLOT,PLUGIN_NAME)
        trace=Trace()
        rt=Runtime(registry,trace)
        allow=HostContext('research','tester',allow_research=True)
        deny=HostContext('research','tester',allow_research=False)
        cases=[]
        def run(name,request,context,expected):
            r=rt.call(request,context)
            assert r.execution_status==expected,(name,r.to_dict())
            cases.append({'name':name,'status':r.execution_status,'error':r.error,'module':r.module})
            return r
        rq=make_request()
        run('disabled_registry',rq,allow,'unavailable')
        registry.enable(PLUGIN_NAME,True)
        run('research_not_authorized',rq,deny,'unavailable')
        run('wrong_workspace_identity',rq,HostContext('other','tester',allow_research=True),'denied')
        r=run('research_admitted',rq,allow,'completed')
        outer=json.loads(r.result['report_json'])
        assert outer['host_status']=='completed'
        assert outer['automatic_causal_certification'] is False
        assert outer['result']['automatic_causal_certification'] is False
        assert outer['result']['status']=='conditional_sensitivity_report_only'
        assert r.assurance=='unverified' and r.outcome['kind']=='conditional_sensitivity_research_report'
        absent=[[[67,35],[0,0]],[[75,30],[48,39]]]
        r=run('scientific_refusal_not_runtime_failure',make_request('missing',counts=absent),allow,'completed')
        assert json.loads(r.result['report_json'])['host_status']=='refused'
        assert json.loads(r.result['report_json'])['result']['identified_set_outer95_conditional'] is None
        bad=replace(make_request('bad-schema'),operation_schema_version='99.0.0')
        run('schema_version_rejected',bad,allow,'invalid_input')
        dry=replace(make_request('dry-run'),dry_run=True)
        r=run('dry_run_no_computation',dry,allow,'validated')
        assert r.result is None
        # Source worker uses spawn, so a 1ms deadline enforces termination on Linux.
        timed=make_request('deadline-1ms',timeout_ms=1)
        run('worker_timeout',timed,allow,'timed_out')
        assert not mp.active_children(),'spawned child survived timeout'
        assert len(trace.events)==len(cases)
        assert all(set(e)=={'trace_version','request_id','correlation_id','operation','module',
                 'execution_status','error','latency_ms'} for e in trace.events)
        validated=[]
        for name,sha in EXPECTED_GITHUB_BLOBS.items():
            data=(NATIVE_ROOT/'cognitum'/(name+'.py')).read_bytes()
            assert git_blob_sha(data)==sha,(name,git_blob_sha(data),sha)
            validated.append({'module':name,'github_blob_sha':sha})
        summary={'native_registry_runtime_worker_e2e':'PASS','cases':cases,
          'unmodified_github_runtime_modules':validated,
          'spawning_worker_timeout_and_cleanup':'PASS_LINUX',
          'research_authorization_denial':'PASS',
          'workspace_identity_denial':'PASS',
          'no_causal_certification':'PASS',
          'production_registration':False,'lu_integration':False}
        p=ROOT/'results'/'Native_Runtime_Integration_Acceptance.json'
        p.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
        print(json.dumps(summary,indent=2))
    finally:
        if original_env is None:os.environ.pop('COGNITUM_G25_RESEARCH_OPT_IN',None)
        else:os.environ['COGNITUM_G25_RESEARCH_OPT_IN']=original_env

if __name__=='__main__':main()
