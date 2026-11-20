"""Strict independent typed tensor exchange gate; requires complete source tree."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
import xml.etree.ElementTree as ET
from google.protobuf.descriptor_pb2 import FileDescriptorSet,FileDescriptorProto
from cognitum.mel import tensor_field as f,tensor_field_pb2 as pb
from tools.cog04m.benchmark import run
ROOT=Path(__file__).resolve().parents[2]
EXPECTED=dict(tests=114,failures=0,errors=0,skipped=0)

def need(ok,msg):
    if not ok:raise RuntimeError(msg)

def check(manifest,head):
    for p,h in manifest['git_blobs'].items():
        raw=(ROOT/p).read_bytes()
        pin=lambda b:hashlib.sha1(f'blob {len(b)}\0'.encode()+b).hexdigest()
        if pin(raw)!=h:
            norm=raw.replace(b'\r\n',b'\n');need(p in manifest['crlf_text'] and raw==norm.replace(b'\n',b'\r\n') and pin(norm)==h,'source drift '+p)
        if head:need(subprocess.check_output(['git','rev-parse',head+':'+p],cwd=ROOT,text=True).strip()==h,'tree identity drift '+p)

def descriptor_parity(path):
    actual=FileDescriptorSet.FromString(path.read_bytes())
    expected=FileDescriptorProto.FromString(pb.DESCRIPTOR.serialized_pb)
    def normalize(p):
        p=FileDescriptorProto.FromString(p.SerializeToString());p.ClearField('source_code_info')
        def message(m):
            for q in m.field:q.ClearField('json_name')
            for nested in m.nested_type:message(nested)
        for m in p.message_type:message(m)
        return p
    need(len(actual.file)==1 and normalize(actual.file[0])==normalize(expected),'descriptor mismatch')

def main(out):
    os.chdir(ROOT);out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    m=json.loads((ROOT/'docs/research/cog04m/manifest.json').read_text(encoding='utf8'))
    head=None;hosted=os.getenv('GITHUB_ACTIONS')=='true'
    if hosted:
        head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();need(head==os.getenv('COG03BC_EXPECTED_SHA'),'wrong checkout')
        prior=json.loads((out.parent/'cog04l'/'receipt.json').read_text(encoding='utf8'))
        need(prior['source_sha']==head and prior['totals']==dict(tests=79,failures=0,errors=0,skipped=0) and all(prior[k] is True for k in ('hosted_predecessor_checked','checkpoint_replay_verified','certified_full_domain_error','certified_time_prefix_error','hard_conditions')) and prior['production_enabled'] is False,'missing same-head L acceptance')
    check(m,head)
    desc=out/'tensor.desc';subprocess.run([sys.executable,'-m','grpc_tools.protoc','-Iproto','--descriptor_set_out='+str(desc),'proto/cognitum/mel/v1/tensor_field.proto'],check=True,timeout=30);descriptor_parity(desc)
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1');xml=out/'tests.xml'
    with (out/'tests.log').open('w',encoding='utf8') as log:
        p=subprocess.run([sys.executable,'-m','pytest','-q','research_tests/cog04m','--junitxml',str(xml)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180)
    need(p.returncode==0,'tensor tests failed; inspect bounded tests.log artifact')
    totals={k:sum(int(t.get(k,0)) for t in ET.parse(xml).getroot().findall('.//testsuite')) for k in EXPECTED};need(totals==EXPECTED,str(totals))
    rows=run(out/'benchmark');need(len(rows)==3 and all(r['independent_replay'] and r['reference_worker_roundtrips']==3 and r['represented_oracle_max_difference']<=1e-11 for r in rows),'incomplete exchange benchmark')
    # On the full checkout, cross-check actual existing MEL helper behavior.
    # No new registry route, authority, or admission is conferred by this check.
    from cognitum.mel import native
    for stage in ('J','K','L'):
        raw=(out/'benchmark'/f'{stage}.checkpoint.pb').read_bytes()
        need(native.encode_carrier(raw,native.MAX_OBJECT)==f.carrier(raw) and native.decode_carrier(f.carrier(raw),native.MAX_OBJECT)==raw,'MEL native carrier mismatch')
        need(native.serialize(native.parse(raw,pb.Checkpoint,native.MAX_OBJECT))==raw,'MEL native canonical parser mismatch')
    check(m,head)
    artifacts={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file() and not p.is_symlink() and p.name!='receipt.json'}
    (out/'receipt.json').write_text(json.dumps(dict(source_sha=head,reference_parent=m['base'],totals=totals,source_pins=len(m['git_blobs']),hosted_predecessor_checked=hosted,descriptor_parity=True,typed_tensor_wire_verified=True,existing_mel_carrier_checked=True,certificate_replay_verified=True,reference_worker_roundtrips=9,actual_mel_worker_calls=0,production_enabled=False,native_lu_accepted=False,artifacts=artifacts),indent=2)+'\n',encoding='utf8')
    print(totals,'typed tensor checkpoint wire and exact scientific field exchange; reference workers only')
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--out',required=True);main(a.parse_args().out)
