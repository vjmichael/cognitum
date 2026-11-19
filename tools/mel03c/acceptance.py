"""MEL-03C initial HDC/KAN reference contracts; not scoped host admission."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from google.protobuf.descriptor_pb2 import FileDescriptorProto, FileDescriptorSet
from cognitum.mel import engines as e, engines_pb2 as pb
from tools.mel03b1.acceptance import check, normalize

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'cog03bc-artifacts'/'mel03c'
EXPECTED={'tests':43,'failures':0,'errors':0,'skipped':0}


def main():
    os.chdir(ROOT);OUT.mkdir(parents=True,exist_ok=True)
    head=os.getenv('COG03BC_EXPECTED_SHA');hosted=os.getenv('GITHUB_ACTIONS')=='true'
    if hosted and not head:raise RuntimeError('missing expected SHA')
    if head and subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()!=head:raise RuntimeError('wrong checkout')
    manifest=json.loads((ROOT/'docs/research/mel03c/manifest.json').read_text(encoding='utf8'));check(manifest,head)
    if hosted:
        p=json.loads((OUT.parent/'mel03b2'/'receipt.json').read_text(encoding='utf8'))
        if (p['source_sha']!=head or p['totals']!={'tests':52,'failures':0,'errors':0,'skipped':0} or p['hosted_predecessor_checked'] is not True
            or p['production_enabled'] is not False or p['model_advertised'] is not False or p['lu_registered'] is not False):raise RuntimeError('missing same-head MEL-03B2')
    ds={b['operation']:h for h,b in e.catalog()}
    if ds!=manifest['descriptor_sha256']:raise RuntimeError('descriptor drift')
    override=os.getenv('MEL03C_LOCAL_PROTOC')
    if hosted and override:raise RuntimeError('hosted compiler override forbidden')
    cmd=[override] if override else [sys.executable,'-m','grpc_tools.protoc']
    version=subprocess.check_output(cmd+['--version'],text=True).strip();comp=OUT/'compiled-engines.pb'
    subprocess.run(cmd+['-Iproto','--descriptor_set_out='+str(comp),'proto/'+pb.DESCRIPTOR.name],check=True,timeout=60)
    f=FileDescriptorSet.FromString(comp.read_bytes())
    if len(f.file)!=1 or normalize(f.file[0])!=normalize(FileDescriptorProto.FromString(pb.DESCRIPTOR.serialized_pb)):raise RuntimeError('compiler schema mismatch')
    collected=subprocess.check_output([sys.executable,'-m','pytest','--collect-only','-q','research_tests/mel03c'],text=True,timeout=60)
    ids=[x for x in collected.splitlines() if '::test_' in x]
    if len(ids)!=EXPECTED['tests'] or max(map(len,ids))>1024:raise RuntimeError('collection or node ID budget')
    (OUT/'collection.log').write_text(collected,encoding='utf8')
    xml=OUT/'tests.xml';log=OUT/'tests.log'
    with log.open('w',encoding='utf8') as f:subprocess.run([sys.executable,'-m','pytest','-q','research_tests/mel03c','--junitxml',str(xml)],stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    totals={k:sum(int(s.get(k,0)) for s in ET.parse(xml).getroot().findall('.//testsuite')) for k in EXPECTED}
    if totals!=EXPECTED:raise RuntimeError(str(totals))
    check(manifest,head)
    (OUT/'catalog.json').write_text(json.dumps(e.catalog(),indent=2)+'\n',encoding='utf8')
    artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (comp,xml,log,OUT/'collection.log',OUT/'catalog.json')}
    (OUT/'receipt.json').write_text(json.dumps(dict(source_sha=head,totals=totals,compiler=version,compiled_descriptor_match=True,
        descriptor_sha256=ds,hosted_predecessor_checked=hosted,production_enabled=False,model_advertised=False,
        lu_registered=False,scoped_admission=False,git_blobs=manifest['git_blobs'],artifacts=artifacts),indent=2)+'\n',encoding='utf8')
    print(totals,version,'3 initial HDC/KAN reference descriptors; no scoped grants or model advertising')

if __name__=='__main__':main()
