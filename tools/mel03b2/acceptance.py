"""Source-bound scoped admission reference gate; not installed Lu acceptance."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.mel import admission as a, native as n, mel_pb2 as pb
from tools.mel03b1.acceptance import check

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'cog03bc-artifacts'/'mel03b2'
EXPECTED={'tests':52,'failures':0,'errors':0,'skipped':0}


def examples():
    registry=Registry();registry.install(n.NativeVFAPlugin)
    for op in n.OP:registry.nominate(op,n.NAME)
    registry.enable(n.NAME)
    host=a.Admission(Runtime(registry),'fixture-session')
    scope=a.Scope('fixture-session','fixture-workspace','fixture-subject','fixture-turn')
    rows=[]
    for i,route in enumerate(a.routes()):
        token=host.issue(scope,route,a.Limits(timeout_ms=8000),ttl_ms=15000)
        schema=host.discover(scope,token)
        f=n.gaussian([[0.]],[[1.]],[2.],constant=1.,axes=[('x','1')],domain=[(-2.,2.)],output_unit='1')
        c=n.make_call(route.public_name,f,n.points(f,[[0.]]),f'call-{i}',scope.turn)
        receipt=host.execute(scope,token,c.request_id,c.wire(),timeout_ms=8000)
        if receipt.status!='completed' or receipt.result_frame is None:raise RuntimeError('admitted worker failed')
        m=pb.VfaResult.FromString(receipt.result_frame)
        expected=[3.] if route.operation=='vfa.evaluate' else [0.]
        values=list(m.result.body.values.values if route.operation=='vfa.evaluate' else m.result.body.gradient.values)
        if values!=expected:raise RuntimeError('independent analytic control')
        replay=host.execute(scope,token,c.request_id,c.wire(),timeout_ms=8000)
        if replay.status!='replay_denied' or replay.result_frame is not None:raise RuntimeError('replay escaped')
        if not host.revoke(scope,token):raise RuntimeError('revocation failed')
        try:host.discover(scope,token)
        except ValueError:pass
        else:raise RuntimeError('revoked discovery escaped')
        rows.append(dict(operation=route.operation,effect=route.effect.value,tool=schema['function']['name'],
            descriptor_sha256=receipt.descriptor_sha256,request_sha256=receipt.request_sha256,result_sha256=receipt.result_sha256,
            values=values,scope_bound=receipt.scope==scope,status=receipt.status,replay_status=replay.status,revoked=True))
    host.close()
    return rows


def verify_predecessor(head, hosted):
    if not hosted:return
    p=json.loads((OUT.parent/'mel03b1'/'receipt.json').read_text(encoding='utf8'))
    if (p['source_sha']!=head or p['totals']!={'tests':63,'failures':0,'errors':0,'skipped':0}
            or p['hosted_predecessor_checked'] is not True or p['compiled_descriptor_match'] is not True
            or p['production_enabled'] is not False or p['model_advertised'] is not False or p['lu_registered'] is not False):
        raise RuntimeError('missing same-head MEL-03B1 predecessor')


def main():
    os.chdir(ROOT);OUT.mkdir(parents=True,exist_ok=True)
    head=os.getenv('COG03BC_EXPECTED_SHA');hosted=os.getenv('GITHUB_ACTIONS')=='true'
    if hosted and not head:raise RuntimeError('missing expected SHA')
    if head and subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()!=head:raise RuntimeError('wrong checkout')
    manifest=json.loads((ROOT/'docs/research/mel03b2/manifest.json').read_text(encoding='utf8'));check(manifest,head)
    verify_predecessor(head,hosted)
    if {r.public_name:r.descriptor_sha256 for r in a.routes()}!=manifest['descriptor_sha256']:raise RuntimeError('reviewed route drift')
    collected=subprocess.check_output([sys.executable,'-m','pytest','--collect-only','-q','research_tests/mel03b2'],text=True,timeout=60)
    ids=[line for line in collected.splitlines() if '::test_' in line]
    if len(ids)!=EXPECTED['tests'] or max(map(len,ids))>1024:raise RuntimeError('test collection or Windows node ID budget')
    (OUT/'collection.log').write_text(collected,encoding='utf8')
    xml=OUT/'tests.xml';log=OUT/'tests.log'
    with log.open('w',encoding='utf8') as f:
        subprocess.run([sys.executable,'-m','pytest','-q','research_tests/mel03b2','--junitxml',str(xml)],stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    totals={k:sum(int(s.get(k,0)) for s in ET.parse(xml).getroot().findall('.//testsuite')) for k in EXPECTED}
    if totals!=EXPECTED:raise RuntimeError(str(totals))
    rows=examples();(OUT/'examples.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf8')
    check(manifest,head)
    artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (xml,log,OUT/'collection.log',OUT/'examples.json')}
    (OUT/'receipt.json').write_text(json.dumps(dict(source_sha=head,totals=totals,examples=len(rows),nodeids=len(ids),max_nodeid_chars=max(map(len,ids)),
        hosted_predecessor_checked=hosted,production_enabled=False,model_advertised=False,lu_registered=False,
        immediate_worker_interrupt=False,durable_grants=False,git_blobs=manifest['git_blobs'],artifacts=artifacts),indent=2)+'\n',encoding='utf8')
    print(totals,'scoped compute-only admission; 2 actual worker round trips; no native Lu authority')


if __name__=='__main__':main()
