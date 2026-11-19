"""Exact-source MEL-03B1 protobuf contracts/compiler/worker gate."""
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from google.protobuf.descriptor_pb2 import FileDescriptorProto, FileDescriptorSet
from cognitum.contracts import HostContext, Request
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.mel import native as n
from cognitum.mel import mel_pb2 as pb

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'cog03bc-artifacts'/'mel03b1'
EXPECTED={'tests':63,'failures':0,'errors':0,'skipped':0}


def blob(raw):return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


def check(manifest,head):
    for p,h in manifest['git_blobs'].items():
        raw=(ROOT/p).read_bytes()
        if blob(raw)!=h and (p not in manifest['inherited_text'] or blob(raw.replace(b'\r\n',b'\n'))!=h):raise RuntimeError('source drift '+p)
        if head and subprocess.check_output(['git','rev-parse','HEAD:'+p],text=True).strip()!=h:raise RuntimeError('commit drift '+p)


def normalize(d):
    # Compare complete descriptor semantics (includes packed flags, enums,
    # oneof/presence and type names), ignoring compiler presentation metadata.
    f=FileDescriptorProto();f.CopyFrom(d);f.ClearField('source_code_info')
    for msg in f.message_type:
        for v in msg.field:v.ClearField('json_name')
    return f.SerializeToString(deterministic=True)


def compile_schema(out,hosted):
    override=os.getenv('MEL03B1_LOCAL_PROTOC')
    if hosted and override:raise RuntimeError('hosted compiler override forbidden')
    cmd=[override] if override else [sys.executable,'-m','grpc_tools.protoc']
    version=subprocess.check_output(cmd+['--version'],text=True).strip()
    subprocess.run(cmd+['-Iproto','--descriptor_set_out='+str(out),'proto/'+pb.DESCRIPTOR.name],check=True,timeout=60)
    f=FileDescriptorSet.FromString(out.read_bytes())
    if len(f.file)!=1 or normalize(f.file[0])!=normalize(FileDescriptorProto.FromString(pb.DESCRIPTOR.serialized_pb)):
        raise RuntimeError('compiler descriptor drift')
    return version


def examples():
    r=Registry();r.install(n.NativeVFAPlugin)
    for op in n.OP:r.nominate(op,n.NAME)
    r.enable(n.NAME);rt=Runtime(r)
    ds=tuple((b['public_name'],h) for h,b in n.catalog());offers=n.discover(r,ds);rows=[]
    a=dict(axes=[dict(name='x',unit='m'),dict(name='t',unit='s')],domain=[dict(lower=-2,upper=2),dict(lower=-3,upper=3)],constant=.2,output_unit='K',terms=[dict(center=[0.,0.],width=[1.,2.],weight=1.5)],points=[[0.,0.],[1.,2.],[-1.,-2.]])
    for i,(name,h) in enumerate(ds):
        c=n.bind_model(r,ds,name,json.dumps(a),request_id='example-'+str(i),correlation_id='reference')
        req=Request(c.request_id,c.correlation_id,c.operation,c.payload(),workspace_id='fixture',subject_id='fixture',operation_schema_version=n.VERSION,timeout_ms=10000)
        response=rt.call(req,HostContext('fixture','fixture',allow_research=True));result=n.model_feedback(c,response)
        if not result['ok']:raise RuntimeError('worker failed')
        raw=n.decode_carrier(response.result['frame'],n.MAX_RESULT);error=0.
        for (x,t),got in zip(a['points'],result['result']['values']):
            y=1.5*math.exp(-.5*(x*x+(t/2)**2))
            error=max(error,abs(got-y-.2)) if name=='mel_vfa_evaluate' else max(error,abs(got[0]+x*y),abs(got[1]+t*y/4))
        if error>5e-13:raise RuntimeError('analytic oracle')
        denied=n.model_feedback(c,rt.call(req,HostContext('fixture','fixture')))
        if denied['ok'] or denied['error']['code']!='UNAVAILABLE':raise RuntimeError('research disabled control')
        request_file=OUT/(name+'.request.pb');response_file=OUT/(name+'.result.pb')
        request_file.write_bytes(c.wire());response_file.write_bytes(raw)
        rows.append(dict(name=name,descriptor_sha256=h,request_bytes=len(c.wire()),response_bytes=len(raw),oracle_max_abs_error=error,model_arguments=a,model_result=result,disabled_control=denied,request_sha256=hashlib.sha256(c.wire()).hexdigest(),result_sha256=hashlib.sha256(raw).hexdigest()))
    return offers,rows


def main():
    os.chdir(ROOT);OUT.mkdir(parents=True,exist_ok=True)
    head=os.getenv('COG03BC_EXPECTED_SHA');hosted=os.getenv('GITHUB_ACTIONS')=='true'
    if hosted and not head:raise RuntimeError('missing expected SHA')
    if head and subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()!=head:raise RuntimeError('wrong checkout')
    manifest=json.loads((ROOT/'docs/research/mel03b1/manifest.json').read_text(encoding='utf8'));check(manifest,head)
    if hosted:
        predecessor=json.loads((OUT.parent/'mel03a'/'receipt.json').read_text(encoding='utf8'))
        if predecessor['source_sha']!=head or predecessor['totals']!={'tests':80,'failures':0,'errors':0,'skipped':0} or predecessor['hosted_predecessor_checked'] is not True or predecessor['model_advertised'] is not False:raise RuntimeError('missing same-head MEL-03A')
    ds={b['public_name']:h for h,b in n.catalog()}
    if ds!=manifest['descriptor_sha256']:raise RuntimeError('descriptor identity drift')
    comp=OUT/'compiled-math.pb';compiler=compile_schema(comp,hosted)
    collected=subprocess.check_output([sys.executable,'-m','pytest','--collect-only','-q','research_tests/mel03a','research_tests/mel03b1'],text=True,timeout=60)
    nodeids=[line for line in collected.splitlines() if '::test_' in line]
    if len(nodeids)!=143 or max(map(len,nodeids))>1024 or not any('test_strict_parser[oversized]' in x for x in nodeids):raise RuntimeError('Windows node-ID regression')
    (OUT/'collection.log').write_text(collected,encoding='utf8')
    log=OUT/'tests.log';xml=OUT/'tests.xml'
    with log.open('w',encoding='utf8') as f:
        subprocess.run([sys.executable,'-m','pytest','-q','research_tests/mel03b1','--junitxml',str(xml)],stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    suites=ET.parse(xml).getroot().findall('.//testsuite');totals={k:sum(int(s.get(k,0)) for s in suites) for k in EXPECTED}
    if totals!=EXPECTED:raise RuntimeError(str(totals))
    offers,rows=examples();(OUT/'catalog.json').write_text(json.dumps(offers,indent=2)+'\n',encoding='utf8');(OUT/'examples.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf8')
    check(manifest,head)
    artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='receipt.json'}
    (OUT/'receipt.json').write_text(json.dumps(dict(source_sha=head,totals=totals,compiler=compiler,compiled_descriptor_match=True,descriptor_sha256=ds,nodeids=len(nodeids),max_nodeid_chars=max(map(len,nodeids)),examples=len(rows),max_oracle_error=max(r['oracle_max_abs_error'] for r in rows),hosted_predecessor_checked=hosted,production_enabled=False,model_advertised=False,lu_registered=False,git_blobs=manifest['git_blobs'],artifacts=artifacts),indent=2)+'\n',encoding='utf8')
    print(totals,compiler,'schema parity; 143 bounded node IDs; two protobuf worker round trips')


if __name__=='__main__':main()
