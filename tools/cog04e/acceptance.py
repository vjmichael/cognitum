"""COG-04E: source-bound exact functional algebra / real MEL execution gate."""
import argparse, hashlib, json, os, subprocess, sys
from pathlib import Path
import xml.etree.ElementTree as ET
from cognitum.mel import kan_symbolic as s, polynomial_kan as pk, uncertainty_pb2 as wp
from cognitum.contracts import Response
from tools.cog04a.acceptance import check
ROOT=Path(__file__).resolve().parents[2]
TOTALS=dict(tests=38,failures=0,errors=0,skipped=0)


def require(ok,msg):
    if not ok:raise RuntimeError(msg)


def main(out):
    os.chdir(ROOT);out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    m=json.loads((ROOT/'docs/research/cog04e/manifest.json').read_text(encoding='utf8'));head=None;hosted=os.getenv('GITHUB_ACTIONS')=='true'
    if hosted:
        head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
        require(os.getenv('COG03BC_EXPECTED_SHA')==head,'wrong checkout')
        prior=json.loads((out.parent/'cog04d'/'receipt.json').read_text(encoding='utf8'))
        require(prior['source_sha']==head and prior['totals']==dict(tests=34,failures=0,errors=0,skipped=0) and prior['hosted_predecessor_checked'] is True and prior['actual_worker_calls']==3 and prior['production_enabled'] is False,'missing same-head COG-04D receipt')
    check(m,head=head)
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    xml=out/'tests.xml'
    with (out/'tests.log').open('w',encoding='utf8') as f:
        subprocess.run([sys.executable,'-m','pytest','-q','research_tests/cog04e','--basetemp='+str(out/'retained'),'--junitxml',str(xml)],env=env,stdout=f,stderr=subprocess.STDOUT,timeout=180,check=True)
    totals={k:sum(int(t.get(k,0)) for t in ET.parse(xml).getroot().findall('.//testsuite')) for k in TOTALS}
    require(totals==TOTALS,str(totals))
    def summary(name,derivative):
        paths=list((out/'retained').rglob(name));require(len(paths)==1,'missing unique evidence '+name)
        file=paths[0];d=json.loads(file.read_text(encoding='utf8'));blobs={}
        for n,h in d['sha256'].items():
            require(Path(n).name==n,'unsafe evidence name');blobs[n]=(file.parent/n).read_bytes();require(hashlib.sha256(blobs[n]).hexdigest()==h,'evidence drift '+n)
        source=pk.Checkpoint(blobs['source.checkpoint.pb']);f=s.extract(source).function
        derived=s.arithmetic('multiply',f,f).result
        if derivative:derived=s.replay_operator(s.apply_verified(s.Operator(('D',)),derived),derived)
        c=pk.Checkpoint(blobs['derived.checkpoint.pb']);stored=s.load_snapshot(blobs['symbolic.json'],d['sha256']['symbolic.json'])
        require(derived==stored==s.extract(c).function and s.export_candidate(derived).wire==c.wire,'symbolic replay mismatch')
        if derivative:
            call=pk.Call(pk.OP,blobs['request.pb']);q=call.message
            response=Response(q.request_id,q.correlation_id,pk.OP,'completed',module={'name':pk.NAME,'version':pk.VERSION},result={'frame':pk.encode_carrier(blobs['result.pb'],pk.MAX_RESULT)},assurance='numerical')
            require(pk.serialize(q.checkpoint)==c.wire and pk.checked_result(call,response)==blobs['result.pb'],'worker result replay mismatch')
            values=[v.observed for v in pk.pb.Result.FromString(blobs['result.pb']).components]
            require(values==d['values']==[-.5,.0625,3.,.75,-12.,6.],'value/Jacobian/Hessian mismatch')
        else:
            nodes={v.node_id:v for v in wp.GraphWitness.FromString(blobs['graph_witness.pb']).nodes}
            require(d['calls']==4 and d['values']==[0.,.0625,1.] and list(nodes['query'].best_index)==d['ties']==[1,2] and list(nodes['query'].hamming_distance)==d['distances']==[1,0,0],'graph witness mismatch')
            require([v.observed for v in pk.pb.Result.FromString(blobs['poly.result.pb']).components]==d['values'],'graph polynomial sample mismatch')
        return d
    one=summary('symbolic_evidence.json',True);graph=summary('symbolic_graph.json',False)
    check(m,head=head)
    artifacts={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file() and not p.is_symlink() and p.name!='receipt.json'}
    (out/'receipt.json').write_text(json.dumps(dict(source_sha=head,reference_parent=m['base'],totals=totals,source_pins=len(m['git_blobs']),hosted_predecessor_checked=hosted,represented_parameters_only=True,exact_scalar_symbolic_extraction=True,quotient_requires_separation=True,exact_checkpoint_roundtrip=True,actual_worker_calls=1+graph['calls'],verified_graph_ties=graph['ties'],derivative_worker_values=one['values'],fresh_gguf_inference=False,production_enabled=False,native_lu_accepted=False,artifacts=artifacts),indent=2)+'\n',encoding='utf8')
    print(totals,'exact symbolic extraction, verified arithmetic and composition, five actual MEL workers')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);main(p.parse_args().out)
