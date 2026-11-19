"""Scoped native COG-04C acceptance: same host DAG, closed codec, grounded result."""
import argparse, hashlib, json, os, subprocess, sys
from pathlib import Path
import xml.etree.ElementTree as ET
from google.protobuf.descriptor_pb2 import FileDescriptorSet
from cognitum.mel import exchange_pb2 as pb, polynomial_model as pm
from tools.cog04a.acceptance import check
from tools.mel03b1.acceptance import normalize

ROOT=Path(__file__).resolve().parents[2]
TOTALS=dict(tests=41,failures=0,errors=0,skipped=0)

def main(out,protoc=None):
    os.chdir(ROOT);out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    m=json.loads((ROOT/'docs/research/cog04c/manifest.json').read_text(encoding='utf8'));hosted=os.getenv('GITHUB_ACTIONS')=='true';head=None
    if hosted:
        if protoc:raise RuntimeError('hosted compiler override forbidden')
        head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
        if os.getenv('COG03BC_EXPECTED_SHA')!=head:raise RuntimeError('wrong checkout')
        prior=json.loads((out.parent/'cog04b'/'receipt.json').read_text(encoding='utf8'))
        if not (prior['source_sha']==head and prior['totals']==dict(tests=54,failures=0,errors=0,skipped=0) and prior['compiled_descriptor_match'] is True and prior['hosted_predecessor_checked'] is True and prior['three_engine_verified'] is True and prior['production_enabled'] is False):raise RuntimeError('missing same-head COG-04B receipt')
    check(m,head=head)
    cmd=[protoc] if protoc else [sys.executable,'-m','grpc_tools.protoc'];compiler=subprocess.check_output(cmd+['--version'],text=True).strip()
    path=out/'exchange.pb';subprocess.run(cmd+['-Iproto','--descriptor_set_out='+str(path),'proto/'+pb.DESCRIPTOR.name],check=True,timeout=60)
    fd=FileDescriptorSet.FromString(path.read_bytes()).file
    from google.protobuf.descriptor_pb2 import FileDescriptorProto
    if len(fd)!=1 or normalize(fd[0])!=normalize(FileDescriptorProto.FromString(pb.DESCRIPTOR.serialized_pb)):raise RuntimeError('exchange descriptor mismatch')
    if pm.descriptor()[0]!=m['model_codec_sha256']:raise RuntimeError('codec descriptor drift')
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    xml=out/'tests.xml'
    with (out/'tests.log').open('w',encoding='utf8') as f:subprocess.run([sys.executable,'-m','pytest','-q','research_tests/cog04c','--basetemp='+str(out/'retained'),'--junitxml',str(xml)],check=True,stdout=f,stderr=subprocess.STDOUT,timeout=240,env=env)
    totals={k:sum(int(s.get(k,0)) for s in ET.parse(xml).getroot().findall('.//testsuite')) for k in TOTALS}
    if totals!=TOTALS:raise RuntimeError(str(totals))
    def summary(name):
        results=list((out/'retained').rglob(name))
        if len(results)!=1:raise RuntimeError('expected unique retained '+name)
        path=results[0];data=json.loads(path.read_text(encoding='utf8'))
        for filename,h in data['sha256'].items():
            if Path(filename).name!=filename or hashlib.sha256((path.parent/filename).read_bytes()).hexdigest()!=h:raise RuntimeError('retained evidence drift')
        return data
    graph=summary('summary.json');model=summary('model_summary.json')
    if graph['calls']!=4 or graph['ties']!=[1,2] or graph['distances']!=[1,0,0] or graph['source_origin']!='POLYNOMIAL_VALUES' or graph['plan_sha256']!=graph['sha256']['plan.material'] or graph['witness_sha256']!=graph['sha256']['graph_witness.pb']:raise RuntimeError('incomplete graph receipt')
    if model['values']!=[.25,1.,2.] or model['real_worker'] is not True or model['fresh_gguf_inference'] is not False:raise RuntimeError('incomplete model codec evidence')
    check(m,head=head)
    artifacts={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file() and not p.is_symlink() and p.name!='receipt.json'}
    (out/'receipt.json').write_text(json.dumps(dict(source_sha=head,reference_parent=m['base'],totals=totals,compiler=compiler,compiled_descriptor_match=True,model_codec_sha256=pm.descriptor()[0],source_pins=len(m['git_blobs']),hosted_predecessor_checked=hosted,three_engine_verified=True,model_codec_worker_verified=True,uncertain_threshold_blocks_successors=True,represented_inputs_only=True,fresh_gguf_inference=False,native_lu_accepted=False,production_enabled=False,artifacts=artifacts),indent=2)+'\n',encoding='utf8')
    print(totals,compiler,'shared graph polynomial KAN/VFA/HDC; scoped closed model codec; receipt-bound answer grounding; no fresh GGUF inference')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--protoc');a=p.parse_args();main(a.out,a.protoc)
