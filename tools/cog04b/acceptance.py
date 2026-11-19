"""Scoped COG-04B qualification. Explicitly requires the same-head COG-04A receipt on CI."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from google.protobuf.descriptor_pb2 import FileDescriptorSet
from cognitum.mel import polynomial_kan_pb2 as pb
from tools.cog04a.acceptance import check

ROOT=Path(__file__).resolve().parents[2]
TOTALS=dict(tests=54,failures=0,errors=0,skipped=0)

def main(out,protoc=None):
    os.chdir(ROOT);out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    m=json.loads((ROOT/'docs/research/cog04b/manifest.json').read_text(encoding='utf8'));hosted=os.getenv('GITHUB_ACTIONS')=='true';head=None
    if hosted:
        if protoc:raise RuntimeError('hosted compiler override forbidden')
        head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
        if os.getenv('COG03BC_EXPECTED_SHA')!=head:raise RuntimeError('wrong checkout')
        prior=json.loads((out.parent/'cog04a'/'receipt.json').read_text(encoding='utf8'))
        if not (prior['source_sha']==head and prior['totals']==dict(tests=61,failures=0,errors=0,skipped=0) and prior['hosted_predecessor_checked'] is True and prior['production_enabled'] is False):raise RuntimeError('missing same-head COG-04A receipt')
    check(m,head=head)
    cmd=[protoc] if protoc else [sys.executable,'-m','grpc_tools.protoc'];version=subprocess.check_output(cmd+['--version'],text=True).strip()
    d=out/'descriptor.pb';subprocess.run(cmd+['-Iproto','--descriptor_set_out='+str(d),'proto/cognitum/mel/v1/polynomial_kan.proto'],check=True,timeout=60)
    fd=FileDescriptorSet.FromString(d.read_bytes()).file
    if len(fd)!=1 or fd[0].SerializeToString(deterministic=True)!=pb.DESCRIPTOR.serialized_pb:raise RuntimeError('independent descriptor mismatch')
    xml=out/'tests.xml';env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with (out/'tests.log').open('w',encoding='utf8') as f:subprocess.run([sys.executable,'-m','pytest','-q','research_tests/cog04b','--basetemp='+str(out/'retained'),'--junitxml='+str(xml)],check=True,stdout=f,stderr=subprocess.STDOUT,timeout=240,env=env)
    totals={k:sum(int(s.get(k,0)) for s in ET.parse(xml).getroot().findall('.//testsuite')) for k in TOTALS}
    if totals!=TOTALS:raise RuntimeError(str(totals))
    files=list((out/'retained').rglob('summary.json'))
    if len(files)!=1:raise RuntimeError('missing unique three-engine evidence')
    summary=json.loads(files[0].read_text(encoding='utf8'))
    if not (summary['calls']==3 and summary['verified_vfa'] and summary['verified_hdc'] and summary['exact_kan_sample_transfer'] and summary['distances']==[2,0,0] and summary['tied_indices']==[1,2]):raise RuntimeError('incomplete three-engine proof')
    for name,h in summary['sha256'].items():
        if hashlib.sha256((files[0].parent/name).read_bytes()).hexdigest()!=h:raise RuntimeError('evidence mismatch')
    check(m,head=head)
    hashes={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file() and p.name!='receipt.json'}
    (out/'receipt.json').write_text(json.dumps(dict(source_sha=head,reference_parent=m['base'],totals=totals,compiler=version,compiled_descriptor_match=True,source_pins=len(m['git_blobs']),hosted_predecessor_checked=hosted,three_engine_verified=True,represented_inputs_only=True,continuous_box_local=True,production_enabled=False,native_lu_accepted=False,artifacts=hashes),indent=2)+'\n',encoding='utf8')
    print(totals,'typed clamped spline/Chebyshev; independent point and box witness; one shared three-engine runtime')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);parser.add_argument('--protoc');args=parser.parse_args();main(args.out,args.protoc)
