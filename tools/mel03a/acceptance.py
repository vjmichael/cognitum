"""MEL-03A source-bound descriptor and reference JSON/typed/worker evidence."""
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

from cognitum.contracts import HostContext, Request
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.mel.discovery import catalog, selection_for, discover, bind_call, decode_result
from cognitum.mel.vfa import VFAPlugin, NAME, OPERATIONS

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'cog03bc-artifacts'/'mel03a'
EXPECTED={'tests':80,'failures':0,'errors':0,'skipped':0}


def git_blob(raw):
    return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


def check_sources(manifest,head):
    for p,expected in manifest['git_blobs'].items():
        raw=(ROOT/p).read_bytes()
        if git_blob(raw)!=expected and (p not in manifest['inherited_text'] or git_blob(raw.replace(b'\r\n',b'\n'))!=expected):
            raise RuntimeError('source drift '+p)
        if head and subprocess.check_output(['git','rev-parse','HEAD:'+p],text=True).strip()!=expected:
            raise RuntimeError('commit drift '+p)


def reference_examples():
    registry=Registry();registry.install(VFAPlugin)
    for op in OPERATIONS:registry.nominate(op,NAME)
    registry.enable(NAME)
    runtime=Runtime(registry)
    selection=selection_for(('mel_vfa_evaluate','mel_vfa_gradient'))
    offers=discover(registry,selection)
    args=dict(axes=[dict(name='x',unit='m'),dict(name='t',unit='s')],
              domain=[dict(lower=-2,upper=2),dict(lower=-3,upper=3)],constant=.2,output_unit='K',
              terms=[dict(center=[0.,0.],width=[1.,2.],weight=1.5)],points=[[0.,0.],[1.,2.],[-1.,-2.]])
    rows=[]
    for i,(name,descriptor) in enumerate(selection):
        call=bind_call(registry,selection,name,json.dumps(args),request_id=f'example-{i}',correlation_id='reference-turn')
        # A trusted test harness explicitly provides local authority, not the descriptor or JSON.
        req=Request(call.request_id,call.correlation_id,call.operation,call.payload(),workspace_id='fixture',subject_id='fixture',timeout_ms=10000)
        response=runtime.call(req,HostContext('fixture','fixture',allow_research=True))
        model_result=decode_result(call,response)
        if not model_result['ok']:raise AssertionError('example execution failed')
        error=0.
        for j,(x,t) in enumerate(args['points']):
            y=1.5*math.exp(-.5*(x*x+(t/2)**2))
            got=model_result['result']['values'][j]
            if name=='mel_vfa_evaluate':error=max(error,abs(got-y-.2))
            else:error=max(error,abs(got[0]+x*y),abs(got[1]+t*y/4))
        if error>5e-13:raise AssertionError('example oracle mismatch')
        denied=decode_result(call,runtime.call(req,HostContext('fixture','fixture',allow_research=False)))
        if denied['ok'] or denied['error']['code']!='UNAVAILABLE':raise AssertionError('discovery widened authorization')
        rows.append(dict(public_name=name,descriptor_sha256=descriptor,arguments=args,
                         typed_function_id=call.function.identity,typed_points_id=call.coordinates.identity,
                         result=model_result,scope_refusal=denied,oracle_max_abs_error=error))
    return offers,rows


def main():
    os.chdir(ROOT);OUT.mkdir(parents=True,exist_ok=True)
    head=os.getenv('COG03BC_EXPECTED_SHA');hosted=os.getenv('GITHUB_ACTIONS')=='true'
    if hosted and not head:raise RuntimeError('missing expected SHA')
    if head and subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()!=head:raise RuntimeError('wrong checkout')
    manifest=json.loads((ROOT/'docs/research/mel03a/manifest.json').read_text(encoding='utf8'))
    check_sources(manifest,head)
    if hosted:
        prev=json.loads((OUT.parent/'mel02'/'receipt.json').read_text(encoding='utf8'))
        if prev['source_sha']!=head or prev['totals']!={'tests':38,'failures':0,'errors':0,'skipped':0} or prev['benchmark_rows']!=36 or prev['hosted_predecessors_checked'] is not True or prev['model_advertised'] is not False or prev['production_enabled'] is not False:
            raise RuntimeError('missing MEL-02 same-SHA gate')
    ds={d.body['public_name']:d.identity for d in catalog()}
    if ds!=manifest['descriptor_sha256']:raise RuntimeError('descriptor/schema identity drift')
    xml=OUT/'tests.xml';log=OUT/'tests.log';cat=OUT/'catalog.json';examples=OUT/'examples.json'
    with log.open('w',encoding='utf8') as f:
        subprocess.run([sys.executable,'-m','pytest','-q','research_tests/mel03a','--junitxml',str(xml)],stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    suites=ET.parse(xml).getroot().findall('.//testsuite')
    totals={k:sum(int(s.get(k,0)) for s in suites) for k in EXPECTED}
    if totals!=EXPECTED:raise RuntimeError(str(totals))
    offers,rows=reference_examples()
    cat.write_text(json.dumps(offers,indent=2)+'\n',encoding='utf8')
    examples.write_text(json.dumps(rows,indent=2)+'\n',encoding='utf8')
    check_sources(manifest,head)
    (OUT/'receipt.json').write_text(json.dumps(dict(source_sha=head,totals=totals,descriptor_sha256=ds,
        example_count=len(rows),max_oracle_error=max(r['oracle_max_abs_error'] for r in rows),
        production_enabled=False,model_advertised=False,lu_registered=False,hosted_predecessor_checked=hosted,
        git_blobs=manifest['git_blobs'],artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (xml,log,cat,examples)}),indent=2)+'\n',encoding='utf8')
    print(totals,'2 reviewed descriptors; 2 reference worker round trips; no host/model activation')


if __name__=='__main__':main()
