"""Same-checkout continuous represented-function verification acceptance."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from google.protobuf.descriptor_pb2 import FileDescriptorSet, FileDescriptorProto
from cognitum.mel import native as n, admission as a, model_engines as m
from cognitum.mel import function_verification as f, spectral_verification as s, functions_pb2 as pb
from cognitum.research.vfa_periodic import Periodic
from tools.mel03b1.acceptance import check, normalize

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'cog03bc-artifacts'/'mel05c'
EXPECTED=dict(tests=84,failures=0,errors=0,skipped=0)


def examples():
    scope=a.Scope('function-example','workspace','subject','turn');box=((-1.,1.),);tol=(1e-12,1e-12)
    source=n.gaussian([[-1.],[0.],[1.]],[[2**-.5]]*3,[.5,1.,-.25],constant=.125,axes=[('x','1')],domain=box,output_unit='1')
    kan=f.KanFunction(m.Approval(f.propose_kan(source),'fixture-review'),'x');target=f.propose_vfa(kan)
    rows=[]
    for label,x,y in [('vfa-to-kan',source,kan),('kan-to-vfa',kan,target)]:
        c=f.certify(scope,x,y,box,tol)
        tr=f.verified_target(scope,x,y,c,box,tol)
        if not tr.covers(scope,box):raise RuntimeError('box mismatch')
        (OUT/(label+'.certificate.pb')).write_bytes(c.wire)
        rows.append(dict(direction=label,verdict=c.message().verdict,box=box,value_upper=float(c.bounds[0].hi),gradient_upper=float(c.bounds[1].hi),cells=c.message().cells,certificate_sha256=c.identity))
    (OUT/'source.function.pb').write_bytes(source.wire);(OUT/'candidate.checkpoint.pb').write_bytes(kan.approval.checkpoint.wire);(OUT/'reverse.function.pb').write_bytes(target.wire)
    rng=f.enclose(scope,source,box);(OUT/'gaussian-range.certificate.pb').write_bytes(rng.wire)
    wrong=n.gaussian([[.127]],[[.001]],[1.],constant=0.,axes=[('x','1')],domain=box,output_unit='1');zero=n.gaussian([],[],[],constant=0.,axes=[('x','1')],domain=box,output_unit='1')
    unresolved=f.certify(scope,wrong,zero,box,(.1,1e12),max_cells=1);refused=f.certify(scope,wrong,zero,box,(.1,1e12),max_cells=128)
    if (unresolved.message().verdict,refused.message().verdict)!=('inconclusive','outside'):raise RuntimeError('sampling negative control')
    (OUT/'narrow-peak.certificate.pb').write_bytes(refused.wire)
    left=Periodic([1.,.25]);right=Periodic([2.,.1+.05j]);candidate=left.divide(right,order=12,grid=1024,max_error=1e-10).function
    spec=s.certify(scope,'quotient',left,candidate,(1e-10,1e-9),right=right,minimum_separation=1.)
    if s.replay(scope,'quotient',left,candidate,spec,(1e-10,1e-9),right=right,minimum_separation=1.)!='within':raise RuntimeError('spectral proof')
    (OUT/'quotient.certificate.pb').write_bytes(spec.wire)
    return dict(transforms=rows,narrow_peak=dict(first_verdict=unresolved.message().verdict,final_verdict=refused.message().verdict,cells=refused.message().cells),spectral_quotient=dict(value_error_upper=float(spec.error_upper[0]),derivative_error_upper=float(spec.error_upper[1]),certificate_sha256=spec.identity,coefficients={k:[[float(z.real),float(z.imag)] for z in v.positive] for k,v in [('left',left),('right',right),('candidate',candidate)]}),represented_inputs_only=True)


def main():
    os.chdir(ROOT);OUT.mkdir(parents=True,exist_ok=True)
    head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();hosted=os.getenv('GITHUB_ACTIONS')=='true'
    if hosted:
        if os.getenv('COG03BC_EXPECTED_SHA')!=head:raise RuntimeError('wrong checkout')
        p=json.loads((OUT.parent/'mel05b'/'receipt.json').read_text(encoding='utf8'))
        if p['source_sha']!=head or p['totals']!=dict(tests=87,failures=0,errors=0,skipped=0) or p['hosted_predecessor_checked'] is not True or p['inline_threshold_enforced'] is not True or p['production_enabled'] is not False or p['compiled_descriptor_match'] is not True:raise RuntimeError('missing same-head MEL-05B evidence')
    manifest=json.loads((ROOT/'docs/research/mel05c/manifest.json').read_text(encoding='utf8'));check(manifest,head)
    digest=hashlib.sha256(pb.DESCRIPTOR.serialized_pb).hexdigest()
    if digest!=manifest['schema_sha256']:raise RuntimeError('schema identity drift')
    override=os.getenv('MEL05C_LOCAL_PROTOC')
    if hosted and override:raise RuntimeError('hosted compiler override forbidden')
    cmd=[override] if override else [sys.executable,'-m','grpc_tools.protoc'];version=subprocess.check_output(cmd+['--version'],text=True).strip()
    desc=OUT/'compiled-functions.pb';subprocess.run(cmd+['-Iproto','--descriptor_set_out='+str(desc),'proto/'+pb.DESCRIPTOR.name],check=True,timeout=60)
    ds=FileDescriptorSet.FromString(desc.read_bytes())
    if len(ds.file)!=1 or normalize(ds.file[0])!=normalize(FileDescriptorProto.FromString(pb.DESCRIPTOR.serialized_pb)):raise RuntimeError('descriptor mismatch')
    collected=subprocess.check_output([sys.executable,'-m','pytest','--collect-only','-q','research_tests/mel05c'],text=True,timeout=60);ids=[line for line in collected.splitlines() if '::test_' in line]
    if len(ids)!=EXPECTED['tests'] or max(map(len,ids))>1024:raise RuntimeError('collection budget')
    (OUT/'collection.log').write_text(collected,encoding='utf8')
    xml=OUT/'tests.xml';log=OUT/'tests.log'
    with log.open('w',encoding='utf8') as stream:subprocess.run([sys.executable,'-m','pytest','-q','research_tests/mel05c','--junitxml',str(xml)],stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=180)
    totals={k:sum(int(v.get(k,0)) for v in ET.parse(xml).getroot().findall('.//testsuite')) for k in EXPECTED}
    if totals!=EXPECTED:raise RuntimeError(str(totals))
    (OUT/'examples.json').write_text(json.dumps(examples(),indent=2)+'\n',encoding='utf8');check(manifest,head)
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='receipt.json'}
    (OUT/'receipt.json').write_text(json.dumps(dict(source_sha=head,totals=totals,compiler=version,schema_sha256=digest,compiled_descriptor_match=True,hosted_predecessor_checked=hosted,continuous_box_verified=True,represented_inputs_only=True,worker_rounding_separate=True,production_enabled=False,transformation_grants_authority=False,git_blobs=manifest['git_blobs'],artifacts=hashes),indent=2)+'\n',encoding='utf8')
    print(totals,version,'continuous Gaussian boxes, bidirectional RBF transforms and exact Fourier residuals')

if __name__=='__main__':main()
