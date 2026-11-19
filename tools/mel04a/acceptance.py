"""Exact-source typed cross-engine exchange and independent compiler gate."""
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from google.protobuf.descriptor_pb2 import FileDescriptorProto, FileDescriptorSet
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.mel import native as n, engines as e, engines_pb2 as ep, model_engines as m, admission as a
from cognitum.mel import exchange as x, exchange_pb2 as pb
from cognitum.mel.engine_limits import KanLimits,HdcLimits
from tools.mel03b1.acceptance import check,normalize

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'cog03bc-artifacts'/'mel04a'
EXPECTED={'tests':62,'failures':0,'errors':0,'skipped':0}


def examples():
    r=Registry();r.install(n.NativeVFAPlugin,enabled=True);r.install(e.EnginePlugin,enabled=True)
    for op in n.OP:r.nominate(op,n.NAME)
    for op in e.OPERATIONS:r.nominate(op,e.NAME)
    s=a.Scope('exchange-fixture','workspace','owner','turn');h=a.Admission(Runtime(r),s.session,enable_engines=True,enable_model_codecs=True)
    def execute(t,rid,limits,approval=None):
        transfer=t.message();route=next(z for z in a.routes(include_engines=True) if z.operation==transfer.operation)
        token=h.issue(s,route,limits,ttl_ms=60000,model_codec=approval is not None,checkpoint_sha256=approval.checkpoint.identity if approval else None)
        result=h.execute(s,token,rid,transfer.request_frame,timeout_ms=10000)
        if result.status!='completed':raise RuntimeError('authorized exchange worker failed: '+result.status)
        (OUT/(rid+'.transfer.pb')).write_bytes(t.wire);(OUT/(rid+'.result.pb')).write_bytes(result.result_frame)
        return result
    f=n.gaussian([[0]],[[1]],[1],constant=0,axes=[('x','1')],domain=[(-3,3)],output_unit='1')
    source=x.from_vfa_points(s,n.points(f,[[0.],[.5],[1.]]))
    layer=ep.KanLayer(inputs=1,outputs=1,knots=3,basis=ep.RBF,grid=[-1.,0.,1.],coefficients=[0.,2.,0.],mask=[1.])
    cp=m.Checkpoint(m.checkpoint_wire([layer]));approval=m.Approval(cp,'fixture-review');h.approve_checkpoint(s,cp.wire,expected_sha256=cp.identity,review_id=approval.review_id)
    k=x.prepare_kan(s,source,approval,('x',),'kan');kr=execute(k,'kan',KanLimits(timeout_ms=10000),approval)
    kv=x.from_transfer_result(s,k,(source,),kr,approval=approval,dimensionless_axes=('x',),output_axes=('x',))
    kvalues=list(kv.message().body.samples.values);kerr=max(abs(v-2*math.exp(-z*z)) for v,z in zip(kvalues,(0,.5,1)))
    v=x.prepare_vfa(s,kv,f,'mel_vfa_evaluate','vfa');vr=execute(v,'vfa',a.Limits(timeout_ms=10000))
    vv=x.from_transfer_result(s,v,(kv,),vr,function=f);vvalues=list(vv.message().body.samples.values);verr=max(abs(got-math.exp(-.5*z*z)) for got,z in zip(vvalues,kvalues))
    alt=x.prepare_vfa(s,source,f,'mel_vfa_evaluate','baseline');ar=execute(alt,'baseline',a.Limits(timeout_ms=10000));av=x.from_transfer_result(s,alt,(source,),ar,function=f)
    probe=x.threshold(s,vv,.5,'1');candidate=x.threshold(s,av,.5,'1')
    query=x.prepare_query(s,probe,(candidate,probe,probe),'query');qr=execute(query,'query',HdcLimits(timeout_ms=10000));q=ep.EngineResult.FromString(qr.result_frame).query
    lifted=x.lift(s,probe,3,1)
    if kerr>3e-7 or verr>5e-13 or list(q.hamming_distance)!=[2,0,0] or list(q.best_index)!=[1,2] or not lifted.message().body.lossy_history:raise RuntimeError('independent exchange oracle')
    for name,o in [('source',source),('kan-samples',kv),('vfa-samples',vv),('baseline-samples',av),('probe',probe),('candidate',candidate),('lifted',lifted)]:
        (OUT/(name+'.object.pb')).write_bytes(o.wire)
    if not h.revoke_checkpoint(s,cp.identity):raise RuntimeError('approval revocation')
    h.close()
    return dict(kan_values=kvalues,vfa_values=vvalues,kan_oracle_max_abs_error=kerr,vfa_oracle_max_abs_error=verr,hamming_distance=list(q.hamming_distance),best_index=list(q.best_index),lossy_history=True,source_sha256=source.identity,kan_transfer=k.identity,vfa_transfer=v.identity,query_transfer=query.identity,checkpoint_sha256=cp.identity,independently_authorized_worker_calls=4)


def main():
    os.chdir(ROOT);OUT.mkdir(parents=True,exist_ok=True)
    head=os.getenv('COG03BC_EXPECTED_SHA');hosted=os.getenv('GITHUB_ACTIONS')=='true'
    if hosted and not head:raise RuntimeError('missing expected SHA')
    if head and subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()!=head:raise RuntimeError('wrong checkout')
    manifest=json.loads((ROOT/'docs/research/mel04a/manifest.json').read_text(encoding='utf8'));check(manifest,head)
    if hosted:
        p=json.loads((OUT.parent/'mel03c3'/'receipt.json').read_text(encoding='utf8'))
        if p['source_sha']!=head or p['totals']!={'tests':60,'failures':0,'errors':0,'skipped':0} or p['hosted_predecessor_checked'] is not True or p['production_enabled'] is not False or p['model_advertised'] is not False or p['approved_checkpoint_reference'] is not True or p['durable_checkpoint_custody'] is not False:raise RuntimeError('missing same-head MEL-03C3 evidence')
    schema_hash=hashlib.sha256(pb.DESCRIPTOR.serialized_pb).hexdigest()
    if schema_hash!=manifest['schema_sha256']:raise RuntimeError('exchange schema drift')
    override=os.getenv('MEL04A_LOCAL_PROTOC')
    if hosted and override:raise RuntimeError('hosted compiler override forbidden')
    cmd=[override] if override else [sys.executable,'-m','grpc_tools.protoc'];version=subprocess.check_output(cmd+['--version'],text=True).strip();comp=OUT/'compiled-exchange.pb'
    subprocess.run(cmd+['-Iproto','--descriptor_set_out='+str(comp),'proto/'+pb.DESCRIPTOR.name],check=True,timeout=60)
    ds=FileDescriptorSet.FromString(comp.read_bytes())
    if len(ds.file)!=1 or normalize(ds.file[0])!=normalize(FileDescriptorProto.FromString(pb.DESCRIPTOR.serialized_pb)):raise RuntimeError('compiler schema drift')
    collected=subprocess.check_output([sys.executable,'-m','pytest','--collect-only','-q','research_tests/mel04a'],text=True,timeout=60)
    ids=[line for line in collected.splitlines() if '::test_' in line]
    if len(ids)!=EXPECTED['tests'] or max(map(len,ids))>1024:raise RuntimeError('collection or node ID budget')
    (OUT/'collection.log').write_text(collected,encoding='utf8');xml=OUT/'tests.xml';log=OUT/'tests.log'
    with log.open('w',encoding='utf8') as f:subprocess.run([sys.executable,'-m','pytest','-q','research_tests/mel04a','--junitxml',str(xml)],stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    totals={k:sum(int(s.get(k,0)) for s in ET.parse(xml).getroot().findall('.//testsuite')) for k in EXPECTED}
    if totals!=EXPECTED:raise RuntimeError(str(totals))
    results=examples();(OUT/'examples.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf8');check(manifest,head)
    artifacts={z.name:hashlib.sha256(z.read_bytes()).hexdigest() for z in sorted(OUT.iterdir()) if z.is_file() and z.name!='receipt.json'}
    (OUT/'receipt.json').write_text(json.dumps(dict(source_sha=head,totals=totals,compiler=version,compiled_descriptor_match=True,schema_sha256=schema_hash,nodeids=len(ids),max_nodeid_chars=max(map(len,ids)),hosted_predecessor_checked=hosted,production_enabled=False,lu_registered=False,model_advertised=False,exchange_grants_authority=False,general_function_conversion=False,independently_authorized_worker_calls=4,git_blobs=manifest['git_blobs'],artifacts=artifacts),indent=2)+'\n',encoding='utf8')
    print(totals,version,'typed exchange; four authorized workers; explicit loss lineage')

if __name__=='__main__':main()
