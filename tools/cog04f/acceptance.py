"""COG-04F exact multivariate polynomial and real MEL worker acceptance."""
import argparse, hashlib, json, os, subprocess, sys
from pathlib import Path
import xml.etree.ElementTree as ET
from cognitum.mel import kan_multivariate as m, polynomial_kan as pk
from cognitum.contracts import Response
from tools.cog04a.acceptance import check
ROOT=Path(__file__).resolve().parents[2]
TOTALS=dict(tests=37,failures=0,errors=0,skipped=0)


def require(ok,msg):
    if not ok:raise RuntimeError(msg)


def main(out):
    os.chdir(ROOT);out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((ROOT/'docs/research/cog04f/manifest.json').read_text(encoding='utf8'));head=None;hosted=os.getenv('GITHUB_ACTIONS')=='true'
    if hosted:
        head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();require(os.getenv('COG03BC_EXPECTED_SHA')==head,'wrong checkout')
        prior=json.loads((out.parent/'cog04e'/'receipt.json').read_text(encoding='utf8'))
        require(prior['source_sha']==head and prior['totals']==dict(tests=38,failures=0,errors=0,skipped=0) and prior['hosted_predecessor_checked'] is True and prior['actual_worker_calls']==5 and prior['production_enabled'] is False,'missing same-head COG-04E receipt')
    check(manifest,head=head)
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1');xml=out/'tests.xml'
    with (out/'tests.log').open('w',encoding='utf8') as f:
        subprocess.run([sys.executable,'-m','pytest','-q','research_tests/cog04f','--basetemp='+str(out/'retained'),'--junitxml',str(xml)],env=env,stdout=f,stderr=subprocess.STDOUT,timeout=180,check=True)
    totals={k:sum(int(t.get(k,0)) for t in ET.parse(xml).getroot().findall('.//testsuite')) for k in TOTALS};require(totals==TOTALS,str(totals))
    paths=list((out/'retained').rglob('multivariate_evidence.json'));require(len(paths)==1,'unique worker evidence required');p=paths[0];rows=json.loads(p.read_text(encoding='utf8'));require([v['name'] for v in rows]==['quadratic','derivative'],'evidence profiles')
    expected={'quadratic':[.5,1.3125,.75,.5,2.5,2.75,2.,3.,3.,4.,2.,3.,3.,4.], 'derivative':[.75,2.5,2.,3.,2.,3.,0.,0.,0.,0.,0.,0.,0.,0.]};functions={}
    for v in rows:
        name=v['name'];files={name+s for s in ('.checkpoint.pb','.symbolic.json','.request.pb','.result.pb')};require(set(v['sha256'])==files,'unexpected evidence files');blobs={n:(p.parent/n).read_bytes() for n in files}
        require(all(hashlib.sha256(b).hexdigest()==v['sha256'][n] for n,b in blobs.items()),'evidence hash mismatch')
        cp=pk.Checkpoint(blobs[name+'.checkpoint.pb']);sym=m.load_snapshot(blobs[name+'.symbolic.json'],v['sha256'][name+'.symbolic.json']);require(m.replay(cp,m.extract(cp))==sym,'symbolic checkpoint mismatch');functions[name]=sym
        require((m.export_quadratic(sym) if name=='quadratic' else m.export_additive(sym)).wire==cp.wire,'checkpoint replay drift')
        call=pk.Call(pk.OP,blobs[name+'.request.pb']);q=call.message;require(pk.serialize(q.checkpoint)==cp.wire,'request checkpoint mismatch')
        response=Response(q.request_id,q.correlation_id,pk.OP,'completed',module={'name':pk.NAME,'version':pk.VERSION},result={'frame':pk.encode_carrier(blobs[name+'.result.pb'],pk.MAX_RESULT)},assurance='numerical')
        require(pk.checked_result(call,response)==blobs[name+'.result.pb'],'worker receipt replay mismatch');values=[c.observed for c in pk.pb.Result.FromString(blobs[name+'.result.pb']).components];require(values==v['values']==expected[name],'independent analytic value/gradient/Hessian mismatch')
    require(m.replay_operation(m.manipulate(m.Operator((('D',0),)),functions['quadratic']),functions['quadratic'])==functions['derivative'],'derived checkpoint identity')
    require(m.Operator((('D',0),('D',1))).apply(functions['quadratic']).evaluate([0,0])==(3,),'mixed partial identity')
    check(manifest,head=head);artifacts={f.relative_to(out).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(out.rglob('*')) if f.is_file() and not f.is_symlink() and f.name!='receipt.json'}
    (out/'receipt.json').write_text(json.dumps(dict(source_sha=head,reference_parent=manifest['base'],totals=totals,source_pins=len(manifest['git_blobs']),hosted_predecessor_checked=hosted,represented_parameters_only=True,exact_sparse_multivariate_extraction=True,exact_atlas_faces=True,quadratic_roundtrip=True,actual_worker_calls=2,mixed_partial=3,worker_values=expected,fresh_gguf_inference=False,production_enabled=False,native_lu_accepted=False,artifacts=artifacts),indent=2)+'\n',encoding='utf8');print(totals,'exact multivariate extraction and operators; two actual MEL workers, independent result replay')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);main(p.parse_args().out)
