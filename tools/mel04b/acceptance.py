"""Exact-source graph admission, independent mathematical oracles and receipts."""
import hashlib
import json
import math
import os
from dataclasses import replace
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.mel import admission as a, native as n, engines as e, engines_pb2 as ep
from cognitum.mel import model_engines as m, cooperation as g, exchange as x, exchange_pb2 as pb
from cognitum.mel.engine_limits import HdcLimits, KanLimits
from tools.mel03b1.acceptance import check

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'cog03bc-artifacts'/'mel04b'
EXPECTED={'tests':60,'failures':0,'errors':0,'skipped':0}


def setup(s):
    registry=Registry();registry.install(n.NativeVFAPlugin,enabled=True);registry.install(e.EnginePlugin,enabled=True)
    for op in n.OP:registry.nominate(op,n.NAME)
    for op in e.OPERATIONS:registry.nominate(op,e.NAME)
    return a.Admission(Runtime(registry),s.session,enable_engines=True,enable_model_codecs=True)


def grants(h,p):
    out=[]
    for node in p.nodes:
        op=g._op(node)
        if op is None:continue
        route=next(r for r in a.routes(include_engines=True) if r.operation==op);kw={}
        if op=='kan.evaluate':
            ck=node.approval.checkpoint;h.approve_checkpoint(p.scope,ck.wire,expected_sha256=ck.identity,review_id=node.approval.review_id)
            kw={'model_codec':True,'checkpoint_sha256':ck.identity}
        limits=a.Limits(timeout_ms=10000) if op=='vfa.evaluate' else KanLimits(timeout_ms=10000) if op=='kan.evaluate' else HdcLimits(timeout_ms=10000)
        out.append((node.id,h.issue(p.scope,route,limits,ttl_ms=60000,**kw)))
    return tuple(out)


def archive(plan,o):
    rows=[]
    for v in o.nodes:
        stem=OUT/(plan.id+'-'+v.node_id)
        if v.output is not None:(stem.with_suffix('.object.pb')).write_bytes(v.output.wire)
        if v.transfer is not None:(stem.with_suffix('.transfer.pb')).write_bytes(v.transfer.wire)
        if v.worker is not None:(stem.with_suffix('.result.pb')).write_bytes(v.worker.result_frame)
        rows.append({name:getattr(v,name) for name in ('node_id','status','operation','request_sha256','result_sha256','transfer_sha256','object_sha256','lossy_history')})
    return dict(plan_sha256=o.plan_sha256,status=o.status,charged_work=o.charged_work,reserved_bytes=o.reserved_bytes,reserved_calls=o.reserved_calls,nodes=rows)


def examples():
    s=a.Scope('graph-fixture','workspace','owner','turn');h=setup(s)
    f=n.gaussian([[0]],[[1]],[1],constant=0,axes=[('x','1')],domain=[(-3,3)],output_unit='1')
    layer=ep.KanLayer(inputs=1,outputs=1,knots=3,basis=ep.RBF,grid=[-1.,0.,1.],coefficients=[0.,2.,0.],mask=[1.])
    app=m.Approval(m.Checkpoint(m.checkpoint_wire([layer])),'fixture-review')
    p=g.Plan('three',s,(g.Query('query','probe',('candidate','probe','probe')),g.Threshold('probe','vfa',.5,'1'),g.Vfa('vfa','kan',f),g.Kan('kan','seed',app,('x',),('x',)),g.Threshold('candidate','base',.5,'1'),g.Vfa('base','seed',f),g.Seed('seed',n.points(f,[[0.],[.5],[1.]]))))
    o=g.execute(h,p,grants(h,p));r={v.node_id:v for v in o.nodes}
    if o.status!='completed' or o.reserved_calls!=4 or o.plan_sha256!=p.identity:raise RuntimeError('three engine graph did not execute')
    kv=list(r['kan'].output.message().body.samples.values);vv=list(r['vfa'].output.message().body.samples.values)
    kerr=max(abs(y-2*math.exp(-z*z)) for y,z in zip(kv,(0,.5,1)));verr=max(abs(y-math.exp(-.5*z*z)) for y,z in zip(vv,kv))
    q=ep.EngineResult.FromString(r['query'].worker.result_frame).query
    if kerr>3e-7 or verr>5e-13 or list(q.hamming_distance)!=[2,0,0] or list(q.best_index)!=[1,2] or not r['query'].lossy_history:raise RuntimeError('independent graph oracle')
    first=archive(p,o);first.update(kan_values=kv,vfa_values=vv,kan_oracle_max_abs_error=kerr,vfa_oracle_max_abs_error=verr,hamming_distance=list(q.hamming_distance),best_index=list(q.best_index))
    c=e.make_call('hdc.bind',ep.BindInput(left=ep.BinaryVector(dimension=3,bits=b'\x05'),right=ep.BinaryVector(dimension=3,bits=b'\x03')),'reverse:bind',s.turn)
    f2=n.gaussian([[0]],[[1]],[1],constant=0,axes=[('bit0','1')],domain=[(-1,2)],output_unit='1')
    p2=g.Plan('reverse',s,(g.Bind('bind',c),g.Lift('lift','bind',3,1),g.Vfa('eval','lift',f2)))
    o2=g.execute(h,p2,grants(h,p2));r2={v.node_id:v for v in o2.nodes}
    if o2.status!='completed' or o2.reserved_calls!=2:raise RuntimeError('reverse graph did not execute')
    values=list(r2['eval'].output.message().body.samples.values);err=max(abs(v-math.exp(-.5*z*z)) for v,z in zip(values,(0,1,1)))
    if r2['bind'].output.message().body.bits.packed_bits!=b'\x06' or err>5e-13 or r2['eval'].lossy_history:raise RuntimeError('reverse oracle')
    second=archive(p2,o2);second.update(lifted=[0,1,1],vfa_values=values,vfa_oracle_max_abs_error=err)
    seen=len(h._seen);bad=replace(p2,budget=replace(p2.budget,work=1));denied=g.execute(h,bad,grants(h,bad));ctrl=g.Cancellation();ctrl.cancel();cancelled=g.execute(h,p2,grants(h,p2),cancellation=ctrl)
    if denied.status!='resource_denied' or cancelled.status!='cancelled' or len(h._seen)!=seen or seen!=6 or any(v.worker or v.transfer or v.output for o in (denied,cancelled) for v in o.nodes):raise RuntimeError('budget/cancel negative control')
    h.close();return dict(three_engine_graph=first,reverse_graph=second,budget_refusal=archive(bad,denied),cancellation=archive(p2,cancelled),actual_worker_calls=seen)


def main():
    os.chdir(ROOT);OUT.mkdir(parents=True,exist_ok=True)
    head=os.getenv('COG03BC_EXPECTED_SHA');hosted=os.getenv('GITHUB_ACTIONS')=='true'
    if hosted and not head:raise RuntimeError('missing expected SHA')
    if head and subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()!=head:raise RuntimeError('wrong checkout')
    manifest=json.loads((ROOT/'docs/research/mel04b/manifest.json').read_text(encoding='utf8'));check(manifest,head)
    if hosted:
        p=json.loads((OUT.parent/'mel04a'/'receipt.json').read_text(encoding='utf8'))
        if p['source_sha']!=head or p['totals']!={'tests':62,'failures':0,'errors':0,'skipped':0} or p['hosted_predecessor_checked'] is not True or p['compiled_descriptor_match'] is not True or p['schema_sha256']!=manifest['schema_sha256'] or p['exchange_grants_authority'] is not False or p['production_enabled'] is not False:raise RuntimeError('missing same-head MEL-04A evidence')
    if hashlib.sha256(pb.DESCRIPTOR.serialized_pb).hexdigest()!=manifest['schema_sha256']:raise RuntimeError('exchange schema drift')
    collected=subprocess.check_output([sys.executable,'-m','pytest','--collect-only','-q','research_tests/mel04b'],text=True,timeout=60);ids=[line for line in collected.splitlines() if '::test_' in line]
    if len(ids)!=EXPECTED['tests'] or max(map(len,ids))>1024:raise RuntimeError('collection or node ID budget')
    (OUT/'collection.log').write_text(collected,encoding='utf8');xml=OUT/'tests.xml';log=OUT/'tests.log'
    with log.open('w',encoding='utf8') as f:subprocess.run([sys.executable,'-m','pytest','-q','research_tests/mel04b','--junitxml',str(xml)],stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    totals={k:sum(int(s.get(k,0)) for s in ET.parse(xml).getroot().findall('.//testsuite')) for k in EXPECTED}
    if totals!=EXPECTED:raise RuntimeError(str(totals))
    result=examples();(OUT/'examples.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');check(manifest,head)
    artifacts={z.name:hashlib.sha256(z.read_bytes()).hexdigest() for z in sorted(OUT.iterdir()) if z.is_file() and z.name!='receipt.json'}
    (OUT/'receipt.json').write_text(json.dumps(dict(source_sha=head,totals=totals,schema_sha256=manifest['schema_sha256'],nodeids=len(ids),max_nodeid_chars=max(map(len,ids)),hosted_predecessor_checked=hosted,production_enabled=False,lu_registered=False,model_advertised=False,graph_grants_authority=False,graph_ipc=False,durable_graph_recovery=False,independently_authorized_worker_calls=result['actual_worker_calls'],git_blobs=manifest['git_blobs'],artifacts=artifacts),indent=2)+'\n',encoding='utf8')
    print(totals,'six independently authorized worker round trips; graph budget and cancellation negative controls')

if __name__=='__main__':main()
