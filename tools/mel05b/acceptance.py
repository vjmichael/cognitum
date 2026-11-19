"""Same-checkout native gate for inline verification and pre-dispatch refusal."""
from pathlib import Path
import os, json, hashlib, subprocess, sys
import xml.etree.ElementTree as ET
from google.protobuf.descriptor_pb2 import FileDescriptorSet, FileDescriptorProto
from cognitum.mel import uncertainty_pb2 as pb, verified_graph as vg
from tools.mel03b1.acceptance import normalize, check

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'cog03bc-artifacts'/'mel05b'
EXPECTED=dict(tests=87,failures=0,errors=0,skipped=0)


def examples():
    # Reuse the existing real Admission/registry fixture; it issues separate
    # host-scoped worker grants, not automatic graph or verifier authority.
    from research_tests.mel04b.test_cooperation import fixture_plan, setup
    from research_tests.mel05b.test_graph_acceptance import TOL
    from research_tests.mel05b.test_inline_enforcement import _tail_plan
    p=fixture_plan('accepted');h,t=setup(p)
    try:
        r=vg.execute_verified(h,p,t,TOL)
        if r.status!='verified' or r.reserved_calls!=4:raise RuntimeError('verified three-engine execution failed '+r.status)
        digest=vg.replay(p,r.outcome,TOL,r.witness)
        w=pb.GraphWitness.FromString(r.witness);nodes={n.node_id:n for n in w.nodes}
        if list(nodes['query'].hamming_distance)!=[2,0,0] or list(nodes['query'].best_index)!=[1,2]:raise RuntimeError('HDC oracle mismatch')
        (OUT/'three-engine.witness.pb').write_bytes(r.witness)
        good=dict(status=r.status,plan_sha256=p.identity,witness_sha256=digest,worker_calls=r.reserved_calls,charged_work=r.charged_work,reserved_bytes=r.reserved_bytes,witness_bytes=len(r.witness),hamming_distance=list(nodes['query'].hamming_distance),ties=list(nodes['query'].best_index))
    finally:h.close()
    p,tol=_tail_plan('refusal');h,t=setup(p)
    try:
        r=vg.execute_verified(h,p,t,tol)
        seen=sorted(rid for scope,rid in h._seen)
        if r.status!='verification_refused' or r.witness is not None or r.outcome is not None or r.reserved_calls!=1 or seen!=['refusal:value'] or h._grants[dict(t)['query']].calls_left!=1:raise RuntimeError('ambiguous threshold crossed downstream admission')
        bad=dict(status=r.status,worker_calls=r.reserved_calls,admitted_requests=seen,unused_query_calls=h._grants[dict(t)['query']].calls_left,charged_work=r.charged_work,reserved_bytes=r.reserved_bytes,output_published=False)
    finally:h.close()
    return dict(verified=good,ambiguity_refusal=bad)


def main():
    os.chdir(ROOT);OUT.mkdir(parents=True,exist_ok=True)
    head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    hosted=os.getenv('GITHUB_ACTIONS')=='true'
    if hosted:
        if os.getenv('COG03BC_EXPECTED_SHA')!=head:raise RuntimeError('wrong checkout')
        prior=json.loads((OUT.parent/'mel05a'/'receipt.json').read_text(encoding='utf8'))
        if prior['source_sha']!=head or prior['totals']!=dict(tests=65,failures=0,errors=0,skipped=0) or prior['hosted_predecessor_checked'] is not True or prior['production_enabled'] is not False:raise RuntimeError('missing same-head MEL-05A evidence')
    manifest=json.loads((ROOT/'docs/research/mel05b/manifest.json').read_text(encoding='utf8'))
    check(manifest,head)
    digest=hashlib.sha256(pb.DESCRIPTOR.serialized_pb).hexdigest()
    if manifest['uncertainty_schema_sha256']!=digest:raise RuntimeError('schema identity drift')
    override=os.getenv('MEL05B_LOCAL_PROTOC')
    if hosted and override:raise RuntimeError('hosted compiler override forbidden')
    cmd=[override] if override else [sys.executable,'-m','grpc_tools.protoc']
    version=subprocess.check_output(cmd+['--version'],text=True).strip()
    desc=OUT/'compiled-uncertainty.pb'
    subprocess.run(cmd+['-Iproto','--descriptor_set_out='+str(desc),'proto/'+pb.DESCRIPTOR.name],check=True,timeout=60)
    ds=FileDescriptorSet.FromString(desc.read_bytes())
    if len(ds.file)!=1 or normalize(ds.file[0])!=normalize(FileDescriptorProto.FromString(pb.DESCRIPTOR.serialized_pb)):raise RuntimeError('schema mismatch')
    xml=OUT/'tests.xml';log=OUT/'tests.log'
    with log.open('w',encoding='utf8') as f:subprocess.run([sys.executable,'-m','pytest','-q','research_tests/mel05b','--junitxml',str(xml)],stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    totals={k:sum(int(s.get(k,0)) for s in ET.parse(xml).getroot().findall('.//testsuite')) for k in EXPECTED}
    if totals!=EXPECTED:raise RuntimeError(str(totals))
    (OUT/'examples.json').write_text(json.dumps(examples(),indent=2)+'\n',encoding='utf8')
    check(manifest,head)
    artifacts={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(OUT.iterdir()) if f.is_file() and f.name!='receipt.json'}
    (OUT/'receipt.json').write_text(json.dumps(dict(source_sha=head,totals=totals,compiler=version,compiled_descriptor_match=True,hosted_predecessor_checked=hosted,represented_inputs_only=True,production_enabled=False,publication_guard_only=False,inline_threshold_enforced=True,verification_grants_authority=False,verification_work_and_bytes_charged=True,git_blobs=manifest['git_blobs'],artifacts=artifacts),indent=2)+'\n',encoding='utf8')
    print(totals,version,'inline graph verification and no-dispatch refusal')

if __name__=='__main__':main()
