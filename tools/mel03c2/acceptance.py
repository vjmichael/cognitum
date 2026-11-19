"""Source-bound shared HDC/KAN admission; no Lu/model promotion."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from cognitum.mel import admission as a, engines as e
from tools.mel03b1.acceptance import check
from cognitum.mel.engine_limits import HdcLimits, KanLimits, account
from cognitum.mel import engines_pb2 as pb
from cognitum.registry import Registry
from cognitum.runtime import Runtime

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'cog03bc-artifacts'/'mel03c2'
EXPECTED={'tests':50,'failures':0,'errors':0,'skipped':0}


def examples():
    registry=Registry();registry.install(e.EnginePlugin,enabled=True)
    for op in e.OPERATIONS:registry.nominate(op,e.NAME)
    h=a.Admission(Runtime(registry),'host',enable_engines=True);s=a.Scope('host','workspace','subject','turn')
    v=pb.BinaryVector(dimension=3,bits=b'\x05');w=pb.BinaryVector(dimension=3,bits=b'\x03')
    inputs={'hdc.bind':pb.BindInput(left=v,right=w),'hdc.query':pb.QueryInput(probe=v,candidates=[v,v,w]),
        'kan.evaluate':pb.KanInput(rows=1,coordinates=[0.],layers=[pb.KanLayer(inputs=1,outputs=1,knots=3,basis=pb.RBF,grid=[-1.,0.,1.],coefficients=[0.,2.,0.],mask=[1.])])}
    rows=[]
    for i,route in enumerate(x for x in a.routes(include_engines=True) if x.operation in e.OPERATIONS):
        op=route.operation;lim=KanLimits(timeout_ms=8000) if op=='kan.evaluate' else HdcLimits(timeout_ms=8000)
        c=e.make_call(op,inputs[op],f'call-{i}',s.turn);wcost=account(c,lim)
        t=h.issue(s,route,lim,ttl_ms=20000);offer=h.discover(s,t)
        if offer['model_advertised'] or 'tool_schema' in offer:raise RuntimeError('unexpected advertising')
        r=h.execute(s,t,c.message.request_id,c.wire,timeout_ms=8000)
        if r.status!='completed' or r.scope!=s or r.result_frame is None:raise RuntimeError('worker failed')
        m=pb.EngineResult.FromString(r.result_frame)
        if op=='hdc.bind':value=list(m.bound.bits);expected=[6]
        elif op=='hdc.query':value=[list(m.query.hamming_distance),list(m.query.best_index)];expected=[[0,0,2],[0,1]]
        else:value=list(m.kan.values);expected=[2.]
        if value!=expected:raise RuntimeError('independent oracle mismatch')
        replay=h.execute(s,t,c.message.request_id,c.wire,timeout_ms=8000)
        if replay.status!='replay_denied' or replay.result_frame is not None or not h.revoke(s,t):raise RuntimeError('scope control')
        rows.append(dict(operation=op,work_units=wcost,request_sha256=r.request_sha256,result_sha256=r.result_sha256,
                         values=value,status=r.status,replay=replay.status,revoked=True,assurance=m.assurance))
    h.close();return rows


def main():
    os.chdir(ROOT);OUT.mkdir(parents=True,exist_ok=True)
    head=os.getenv('COG03BC_EXPECTED_SHA');hosted=os.getenv('GITHUB_ACTIONS')=='true'
    if hosted and not head:raise RuntimeError('missing expected SHA')
    if head and subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()!=head:raise RuntimeError('wrong checkout')
    m=json.loads((ROOT/'docs/research/mel03c2/manifest.json').read_text(encoding='utf8'));check(m,head)
    if hosted:
        p=json.loads((OUT.parent/'mel03c'/'receipt.json').read_text(encoding='utf8'))
        if (p['source_sha']!=head or p['totals']!={'tests':43,'failures':0,'errors':0,'skipped':0} or p['hosted_predecessor_checked'] is not True or p['compiled_descriptor_match'] is not True or p['production_enabled'] is not False or p['scoped_admission'] is not False):raise RuntimeError('missing MEL-03C1 same-head receipt')
    ds={r.operation:r.descriptor_sha256 for r in a.routes(include_engines=True)}
    if ds!=m['descriptor_sha256']:raise RuntimeError('route identity drift')
    collected=subprocess.check_output([sys.executable,'-m','pytest','--collect-only','-q','research_tests/mel03c2'],text=True,timeout=60)
    ids=[s for s in collected.splitlines() if '::test_' in s]
    if len(ids)!=EXPECTED['tests'] or max(map(len,ids))>1024:raise RuntimeError('test collection or node ID budget')
    (OUT/'collection.log').write_text(collected,encoding='utf8')
    xml=OUT/'tests.xml';log=OUT/'tests.log'
    with log.open('w',encoding='utf8') as f:subprocess.run([sys.executable,'-m','pytest','-q','research_tests/mel03c2','--junitxml',str(xml)],stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    totals={k:sum(int(s.get(k,0)) for s in ET.parse(xml).getroot().findall('.//testsuite')) for k in EXPECTED}
    if totals!=EXPECTED:raise RuntimeError(str(totals))
    rows=examples();(OUT/'examples.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf8');check(m,head)
    artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (xml,log,OUT/'collection.log',OUT/'examples.json')}
    (OUT/'receipt.json').write_text(json.dumps(dict(source_sha=head,totals=totals,examples=len(rows),nodeids=len(ids),max_nodeid_chars=max(map(len,ids)),
        hosted_predecessor_checked=hosted,production_enabled=False,lu_registered=False,model_advertised=False,scoped_reference_admission=True,
        approved_checkpoint_integration=False,immediate_worker_interrupt=False,durable_grants=False,descriptor_sha256=ds,git_blobs=m['git_blobs'],artifacts=artifacts),indent=2)+'\n',encoding='utf8')
    print(totals,'five reviewed routes; three HDC/KAN scoped worker round trips; no model exposure')

if __name__=='__main__':main()
