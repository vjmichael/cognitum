"""Source-bound model codec/checkpoint custody gate. Reference, not installed Lu."""
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.mel import admission as a, engines as e, engines_pb2 as pb, model_engines as m
from cognitum.mel.engine_limits import HdcLimits, KanLimits
from tools.mel03b1.acceptance import check

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'cog03bc-artifacts'/'mel03c3'
EXPECTED={'tests':60,'failures':0,'errors':0,'skipped':0}


def examples():
    registry=Registry();registry.install(e.EnginePlugin,enabled=True)
    for op in e.OPERATIONS:registry.nominate(op,e.NAME)
    h=a.Admission(Runtime(registry),'host',enable_engines=True,enable_model_codecs=True)
    s=a.Scope('host','workspace','subject','turn')
    layer=pb.KanLayer(inputs=1,outputs=1,knots=3,basis=pb.RBF,grid=[-1.,0.,1.],coefficients=[0.,2.,0.],mask=[1.])
    wire=m.checkpoint_wire([layer]);pin=h.approve_checkpoint(s,wire,expected_sha256=hashlib.sha256(wire).hexdigest(),review_id='fixture-review')
    inputs={'hdc.bind':{'left':'101','right':'110'},'hdc.query':{'probe':'101','candidates':['101','101','110']},'kan.evaluate':{'points':[[0.],[.5]]}}
    rows=[]
    for i,route in enumerate(x for x in a.routes(include_engines=True) if x.operation in e.OPERATIONS):
        op=route.operation;limits=(KanLimits if op=='kan.evaluate' else HdcLimits)(timeout_ms=8000)
        t=h.issue(s,route,limits,ttl_ms=20000,model_codec=True,checkpoint_sha256=pin if op=='kan.evaluate' else None)
        offer=h.discover_model(s,t);rid=f'call-{i}'
        result=h.execute_model(s,t,rid,route.public_name,offer['codec_sha256'],json.dumps(inputs[op]),timeout_ms=8000)
        if not result['ok'] or offer['execution_authorized'] or offer['model_advertised']:raise RuntimeError('worker or authority failure')
        value=result['result']
        if op=='hdc.bind':correct=value['bits']=='011'
        elif op=='hdc.query':correct=value['hamming_distance']==[0,0,2] and value['best_index']==[0,1]
        else:correct=value['checkpoint_sha256']==pin and abs(value['values'][0][0]-2.)<3e-7 and abs(value['values'][1][0]-2*math.exp(-.25))<3e-7
        if not correct:raise RuntimeError('oracle mismatch')
        replay=h.execute_model(s,t,rid,route.public_name,offer['codec_sha256'],json.dumps(inputs[op]),timeout_ms=8000)
        if replay['ok'] or replay['error']['code']!='replay_denied':raise RuntimeError('replay escaped')
        rows.append(dict(operation=op,offer=offer,arguments=inputs[op],result=result,replay=replay))
    if not h.revoke_checkpoint(s,pin):raise RuntimeError('checkpoint revocation')
    h.close();return rows


def main():
    os.chdir(ROOT);OUT.mkdir(parents=True,exist_ok=True)
    head=os.getenv('COG03BC_EXPECTED_SHA');hosted=os.getenv('GITHUB_ACTIONS')=='true'
    if hosted and not head:raise RuntimeError('missing expected SHA')
    if head and subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()!=head:raise RuntimeError('wrong checkout')
    manifest=json.loads((ROOT/'docs/research/mel03c3/manifest.json').read_text(encoding='utf8'));check(manifest,head)
    if hosted:
        p=json.loads((OUT.parent/'mel03c2'/'receipt.json').read_text(encoding='utf8'))
        if p['source_sha']!=head or p['totals']!={'tests':50,'failures':0,'errors':0,'skipped':0} or p['hosted_predecessor_checked'] is not True or p['scoped_reference_admission'] is not True or p['production_enabled'] is not False or p['model_advertised'] is not False or p['approved_checkpoint_integration'] is not False:raise RuntimeError('missing same-head MEL-03C2 evidence')
    ds={op:m.descriptor(op)[0] for op in e.OPERATIONS}
    if ds!=manifest['codec_sha256']:raise RuntimeError('codec drift')
    collected=subprocess.check_output([sys.executable,'-m','pytest','--collect-only','-q','research_tests/mel03c3'],text=True,timeout=60)
    ids=[x for x in collected.splitlines() if '::test_' in x]
    if len(ids)!=EXPECTED['tests'] or max(map(len,ids))>1024:raise RuntimeError('collection or node ID budget')
    (OUT/'collection.log').write_text(collected,encoding='utf8')
    xml=OUT/'tests.xml';log=OUT/'tests.log'
    with log.open('w',encoding='utf8') as f:subprocess.run([sys.executable,'-m','pytest','-q','research_tests/mel03c3','--junitxml',str(xml)],stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    totals={k:sum(int(s.get(k,0)) for s in ET.parse(xml).getroot().findall('.//testsuite')) for k in EXPECTED}
    if totals!=EXPECTED:raise RuntimeError(str(totals))
    rows=examples();(OUT/'examples.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf8');check(manifest,head)
    artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (xml,log,OUT/'collection.log',OUT/'examples.json')}
    (OUT/'receipt.json').write_text(json.dumps(dict(source_sha=head,totals=totals,examples=len(rows),nodeids=len(ids),max_nodeid_chars=max(map(len,ids)),
        hosted_predecessor_checked=hosted,production_enabled=False,lu_registered=False,model_advertised=False,approved_checkpoint_reference=True,
        durable_checkpoint_custody=False,immediate_worker_interrupt=False,codec_sha256=ds,git_blobs=manifest['git_blobs'],artifacts=artifacts),indent=2)+'\n',encoding='utf8')
    print(totals,'three scoped JSON/Protobuf worker round trips; approved typed checkpoint reference')

if __name__=='__main__':main()
