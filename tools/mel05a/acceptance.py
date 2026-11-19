"""Source-bound independent numerical verification and typed witness gate."""
import hashlib
import json
import os
from decimal import Decimal
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from google.protobuf.descriptor_pb2 import FileDescriptorProto, FileDescriptorSet
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.mel import admission as a, native as n, engines as e, engines_pb2 as ep
from cognitum.mel import verification as v, verification_pb2 as pb
from cognitum.mel.engine_limits import HdcLimits
from tools.mel03b1.acceptance import check, normalize

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'cog03bc-artifacts'/'mel05a'
EXPECTED={'tests':65,'failures':0,'errors':0,'skipped':0}


def examples():
    registry=Registry();registry.install(n.NativeVFAPlugin,enabled=True);registry.install(e.EnginePlugin,enabled=True)
    for op in n.OP:registry.nominate(op,n.NAME)
    for op in e.OPERATIONS:registry.nominate(op,e.NAME)
    s=a.Scope('verification-fixture','workspace','owner','turn');host=a.Admission(Runtime(registry),s.session,enable_engines=True)
    rows=[]
    def run(c,limits,tol=None):
        route=next(r for r in a.routes(include_engines=True) if r.operation==c.operation);token=host.issue(s,route,limits,ttl_ms=60000)
        raw=c.wire() if type(c) is n.NativeCall else c.wire;rid=c.request_id if type(c) is n.NativeCall else c.message.request_id
        r=host.execute(s,token,rid,raw,timeout_ms=10000)
        if r.status!='completed':raise RuntimeError('verification worker did not complete')
        cert=v.certify_vfa(s,c,r,tol) if tol is not None else v.certify_hdc(s,c,r)
        expected=pb.WITHIN_TOLERANCE if tol is not None else pb.EXACT_SUBMITTED_BITS
        if v.replay(s,c,r,cert,absolute_tolerance=tol)!=expected:raise RuntimeError('verification witness failed')
        m=cert.message();stem=OUT/rid
        stem.with_suffix('.request.pb').write_bytes(raw);stem.with_suffix('.result.pb').write_bytes(r.result_frame);stem.with_suffix('.certificate.pb').write_bytes(cert.wire)
        rows.append(dict(operation=c.operation,certificate_sha256=cert.identity,verdict=pb.Verdict.Name(m.verdict),shape=list(m.shape),absolute_tolerance=list(m.absolute_tolerance),components=[dict(observed=q.observed,lower=q.lower,upper=q.upper,absolute_error_lower=q.absolute_error_lower,absolute_error_upper=q.absolute_error_upper) for q in m.components],request_sha256=r.request_sha256,result_sha256=r.result_sha256,represented_inputs_only=m.represented_inputs_only))
        return r,cert
    f=n.gaussian([[0.,0.],[1.,-1.]],[[1.,2.],[1.,1.]],[2.,-.25],constant=.5,axes=[('x','m'),('t','s')],domain=[(-2.,2.),(-3.,3.)],output_unit='K');p=n.points(f,[[0.,0.],[.5,1.],[1.,-1.]])
    for name,rid,tol in [('mel_vfa_evaluate','value',(1e-12,)),('mel_vfa_gradient','gradient',(1e-12,1e-12))]:
        c=n.make_call(name,f,p,rid,s.turn);run(c,a.Limits(timeout_ms=10000),tol)
    left=ep.BinaryVector(dimension=5,bits=b'\x15');right=ep.BinaryVector(dimension=5,bits=b'\x03')
    cb=e.make_call('hdc.bind',ep.BindInput(left=left,right=right),'bind',s.turn);br,_=run(cb,HdcLimits(timeout_ms=10000))
    if ep.EngineResult.FromString(br.result_frame).bound.bits!=b'\x16':raise RuntimeError('independent binding oracle')
    cq=e.make_call('hdc.query',ep.QueryInput(probe=left,candidates=[right,left,left]),'query',s.turn);qr,_=run(cq,HdcLimits(timeout_ms=10000));q=ep.EngineResult.FromString(qr.result_frame).query
    if list(q.hamming_distance)!=[3,0,0] or list(q.best_index)!=[1,2]:raise RuntimeError('independent query oracle')
    host.close()
    return dict(examples=rows,hamming_distance=list(q.hamming_distance),best_index=list(q.best_index),max_certified_absolute_error_upper=str(max(Decimal(z['absolute_error_upper']) for r in rows for z in r['components'])),actual_worker_calls=4,represented_inputs_only=True)


def main():
    os.chdir(ROOT);OUT.mkdir(parents=True,exist_ok=True)
    head=os.getenv('COG03BC_EXPECTED_SHA');hosted=os.getenv('GITHUB_ACTIONS')=='true'
    if hosted and not head:raise RuntimeError('missing expected SHA')
    if head and subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()!=head:raise RuntimeError('wrong checkout')
    manifest=json.loads((ROOT/'docs/research/mel05a/manifest.json').read_text(encoding='utf8'));check(manifest,head)
    if hosted:
        p=json.loads((OUT.parent/'mel04b'/'receipt.json').read_text(encoding='utf8'))
        if p['source_sha']!=head or p['totals']!={'tests':60,'failures':0,'errors':0,'skipped':0} or p['hosted_predecessor_checked'] is not True or p['graph_grants_authority'] is not False or p['production_enabled'] is not False or p['independently_authorized_worker_calls']!=6:raise RuntimeError('missing same-head MEL-04B evidence')
    digest=hashlib.sha256(pb.DESCRIPTOR.serialized_pb).hexdigest()
    if digest!=manifest['verification_schema_sha256']:raise RuntimeError('verification schema drift')
    override=os.getenv('MEL05A_LOCAL_PROTOC')
    if hosted and override:raise RuntimeError('hosted compiler override forbidden')
    cmd=[override] if override else [sys.executable,'-m','grpc_tools.protoc'];version=subprocess.check_output(cmd+['--version'],text=True).strip();comp=OUT/'compiled-verification.pb'
    subprocess.run(cmd+['-Iproto','--descriptor_set_out='+str(comp),'proto/'+pb.DESCRIPTOR.name],check=True,timeout=60)
    ds=FileDescriptorSet.FromString(comp.read_bytes())
    if len(ds.file)!=1 or normalize(ds.file[0])!=normalize(FileDescriptorProto.FromString(pb.DESCRIPTOR.serialized_pb)):raise RuntimeError('compiler schema drift')
    collected=subprocess.check_output([sys.executable,'-m','pytest','--collect-only','-q','research_tests/mel05a'],text=True,timeout=60);ids=[line for line in collected.splitlines() if '::test_' in line]
    if len(ids)!=EXPECTED['tests'] or max(map(len,ids))>1024:raise RuntimeError('collection or node ID budget')
    (OUT/'collection.log').write_text(collected,encoding='utf8');xml=OUT/'tests.xml';log=OUT/'tests.log'
    with log.open('w',encoding='utf8') as f:subprocess.run([sys.executable,'-m','pytest','-q','research_tests/mel05a','--junitxml',str(xml)],stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    totals={k:sum(int(s.get(k,0)) for s in ET.parse(xml).getroot().findall('.//testsuite')) for k in EXPECTED}
    if totals!=EXPECTED:raise RuntimeError(str(totals))
    evidence=examples();(OUT/'examples.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf8');check(manifest,head)
    artifacts={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(OUT.iterdir()) if f.is_file() and f.name!='receipt.json'}
    (OUT/'receipt.json').write_text(json.dumps(dict(source_sha=head,totals=totals,compiler=version,compiled_descriptor_match=True,verification_schema_sha256=digest,nodeids=len(ids),max_nodeid_chars=max(map(len,ids)),hosted_predecessor_checked=hosted,production_enabled=False,lu_registered=False,model_advertised=False,verification_grants_authority=False,represented_inputs_only=True,kan_numerical_certification=False,graph_error_propagation=False,independently_authorized_worker_calls=4,max_certified_absolute_error_upper=evidence['max_certified_absolute_error_upper'],git_blobs=manifest['git_blobs'],artifacts=artifacts),indent=2)+'\n',encoding='utf8')
    print(totals,version,'independent numerical enclosures; exact HDC witnesses; four admitted worker results')

if __name__=='__main__':main()
