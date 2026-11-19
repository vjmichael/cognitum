"""COG-04G exact scientific operator and actual MEL field worker evidence."""
import argparse, hashlib, json, os, subprocess, sys
from fractions import Fraction as Q
from pathlib import Path
import xml.etree.ElementTree as ET
from cognitum.mel import kan_fields as s, kan_multivariate as m, polynomial_kan as pk
from cognitum.contracts import Response
from tools.cog04a.acceptance import check
ROOT=Path(__file__).resolve().parents[2]
TOTALS=dict(tests=57,failures=0,errors=0,skipped=0)


def require(ok,msg):
    if not ok:raise RuntimeError(msg)


def main(out):
    os.chdir(ROOT);out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((ROOT/'docs/research/cog04g/manifest.json').read_text(encoding='utf8'));head=None;hosted=os.getenv('GITHUB_ACTIONS')=='true'
    if hosted:
        head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();require(os.getenv('COG03BC_EXPECTED_SHA')==head,'wrong checkout')
        prior=json.loads((out.parent/'cog04f'/'receipt.json').read_text(encoding='utf8'))
        require(prior['source_sha']==head and prior['totals']==dict(tests=37,failures=0,errors=0,skipped=0) and prior['hosted_predecessor_checked'] is True and prior['actual_worker_calls']==2 and prior['production_enabled'] is False and prior['mixed_partial']==3,'missing same-head COG-04F receipt')
    check(manifest,head=head)
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1');xml=out/'tests.xml'
    with (out/'tests.log').open('w',encoding='utf8') as f:
        subprocess.run([sys.executable,'-m','pytest','-q','research_tests/cog04g','--basetemp='+str(out/'retained'),'--junitxml',str(xml)],env=env,stdout=f,stderr=subprocess.STDOUT,timeout=180,check=True)
    totals={k:sum(int(t.get(k,0)) for t in ET.parse(xml).getroot().findall('.//testsuite')) for k in TOTALS};require(totals==TOTALS,str(totals))
    paths=list((out/'retained').rglob('scientific_field_evidence.json'));require(len(paths)==1,'unique worker evidence required');p=paths[0];rows=json.loads(p.read_text(encoding='utf8'));require([v['name'] for v in rows]==['gradient','laplacian','diffusion'],'evidence profiles')
    def load(name):
        raw=(p.parent/(name+'.symbolic.json')).read_bytes();return m.load_snapshot(raw,hashlib.sha256(raw).hexdigest())
    source=load('source');k=load('conductivity');src=pk.Checkpoint((p.parent/'source.checkpoint.pb').read_bytes());require(m.replay(src,m.extract(src))==source,'source checkpoint identity')
    # Fixed independent analytic source coefficients, not generated from results.
    box=((-1,1),(-1,1));x,y=(m.variable(2,i) for i in range(2));const=lambda v:m.constant(2,v);fn=lambda *ps:m.Function(box,ps)
    require(source==fn(m.make(2,[((2,0),1),((0,2),2),((1,1),3),((1,0),Q(1,2)),((0,0),Q(1,4))])) and k==fn(m.make(2,[((0,0),1),((1,0),1)])),'source fixture drift')
    independent={'gradient':fn(m.make(2,[((1,0),2),((0,1),3),((0,0),Q(1,2))]),m.make(2,[((1,0),3),((0,1),4)])), 'laplacian':fn(const(6)), 'diffusion':fn(m.make(2,[((1,0),8),((0,1),3),((0,0),Q(13,2))]))}
    expected={'gradient':[.75,.5,2.5,2.75],'laplacian':[6.,6.],'diffusion':[9.75,10.]};functions={}
    for v in rows:
        name=v['name'];files={name+suffix for suffix in ('.checkpoint.pb','.symbolic.json','.request.pb','.result.pb')};require(set(v['sha256'])==files,'unexpected evidence files');blobs={n:(p.parent/n).read_bytes() for n in files}
        require(all(hashlib.sha256(b).hexdigest()==v['sha256'][n] for n,b in blobs.items()),'evidence hash mismatch')
        cp=pk.Checkpoint(blobs[name+'.checkpoint.pb']);sym=m.load_snapshot(blobs[name+'.symbolic.json'],v['sha256'][name+'.symbolic.json']);require(m.replay(cp,m.extract(cp))==sym==independent[name],'independent symbolic field identity');functions[name]=sym
        require(m.export_additive(sym).wire==cp.wire,'checkpoint replay drift')
        call=pk.Call(pk.OP,blobs[name+'.request.pb']);q=call.message;require(pk.serialize(q.checkpoint)==cp.wire,'request checkpoint mismatch')
        response=Response(q.request_id,q.correlation_id,pk.OP,'completed',module={'name':pk.NAME,'version':pk.VERSION},result={'frame':pk.encode_carrier(blobs[name+'.result.pb'],pk.MAX_RESULT)},assurance='numerical')
        require(pk.checked_result(call,response)==blobs[name+'.result.pb'],'worker receipt replay mismatch');values=[c.observed for c in pk.pb.Result.FromString(blobs[name+'.result.pb']).components];require(values==v['values']==expected[name],'independent analytic worker mismatch')
        operands=(source,k) if name=='diffusion' else (source,);require(s.replay(s.certify(name,*operands),*operands)==sym,'field witness replay drift')
    residual=s.certify('poisson_residual',source,fn(const(6))).result;zero=s.residual_certificate(residual);require(zero.identically_zero and zero.squared_l2==0,'Poisson identity')
    negative=s.residual_certificate(s.certify('poisson_residual',source,fn(const(5).add(x))).result);require(not negative.identically_zero and negative.squared_l2==Q(16,3) and negative.absolute_upper==(2,),'nonzero residual control')
    D=s.derivative(2,(1,0));X=s.multiplier(x);require(D.after(X).add(X.after(D).scale(-1))==s.multiplier(const(1)),'commutator identity')
    require(s.laplace_operator(2).after(s.laplace_operator(2)).apply(fn(x.multiply(x).multiply(y.multiply(y))))==fn(const(8)),'biharmonic identity')
    check(manifest,head=head);artifacts={f.relative_to(out).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(out.rglob('*')) if f.is_file() and not f.is_symlink() and f.name!='receipt.json'}
    (out/'receipt.json').write_text(json.dumps(dict(source_sha=head,reference_parent=manifest['base'],totals=totals,source_pins=len(manifest['git_blobs']),hosted_predecessor_checked=hosted,represented_parameters_only=True,independent_operator_identity=True,independent_field_identity=True,actual_worker_calls=3,worker_values=expected,poisson_zero_residual=True,nonzero_residual_squared_l2=str(negative.squared_l2),nonzero_residual_absolute_upper=['2'],fresh_gguf_inference=False,production_enabled=False,native_lu_accepted=False,artifacts=artifacts),indent=2)+'\n',encoding='utf8');print(totals,'exact Cartesian fields and variable-coefficient operators; three actual MEL workers; independent coefficient and receipt replay')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);main(p.parse_args().out)
