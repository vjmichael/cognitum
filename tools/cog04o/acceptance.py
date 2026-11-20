"""Native scoped exact metric gate and independent numerical oracle."""
import argparse,hashlib,json,os,platform,subprocess,sys,time
from fractions import Fraction as Q
from pathlib import Path
import xml.etree.ElementTree as ET
from cognitum.research import kan_function_metrics as m
from tools.cog04o.fixtures import baseline
from tools.cog04o.oracle import reference

ROOT=Path(__file__).resolve().parents[2]
need=m.need
EXPECTED=dict(tests=14,failures=0,errors=0,skipped=0)
def sha(x):return hashlib.sha256(x).hexdigest()

def main(out,prior):
    os.chdir(ROOT);out=Path(out).resolve();prior=Path(prior).resolve()
    out.mkdir(parents=True,exist_ok=False)
    head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    need(not os.getenv('GITHUB_SHA') or head==os.getenv('GITHUB_SHA'),'wrong source checkout')
    need(not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True).strip(),'tracked source drift')
    manifest=json.loads((ROOT/'docs/research/cog04o/RECONCILIATION.json').read_text(encoding='utf8'))
    tree=subprocess.check_output(['git','ls-tree','-r',head],text=True)
    blobs={line.split('\t',1)[1]:line.split('\t',1)[0].split(' ')[2] for line in tree.splitlines()}
    count=0;pins={}
    for group,expected in manifest['prior_manifests'].items():
        path=f'docs/research/cog04{group.lower()}/manifest.json'
        need(blobs.get(path)==expected,'prior manifest identity drift')
        old=json.loads((ROOT/path).read_text(encoding='utf8'))
        for path,blob in old['git_blobs'].items():
            need(blobs.get(path)==blob and pins.get(path,blob)==blob,'inherited source drift')
            pins[path]=blob;count+=1
    need(count==1650 and len(manifest['groups'])==60,'prior scope')
    prior_raw=(prior/'qualification.json').read_bytes();old=json.loads(prior_raw)
    need(old['source_commit']==head and old['status']=='PASS' and old['actual_worker_calls']==49
         and old['tensor']['actual_worker_calls']==16,'missing same-head tensor predecessor')
    for key,digest in old['artifact_sha256'].items():
        file=(prior/key).resolve()
        need(file.is_relative_to(prior) and file.is_file() and sha(file.read_bytes())==digest,'predecessor artifact drift')
    env=os.environ.copy();env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    xml=out/'tests.xml'
    with (out/'tests.log').open('w',encoding='utf8') as log:
        proc=subprocess.run([sys.executable,'-m','pytest','-q','research_tests/cog04o','--junitxml',str(xml)],
            env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180)
    need(proc.returncode==0,'functional metric tests failed')
    totals={k:sum(int(t.get(k,0)) for t in ET.parse(xml).getroot().findall('.//testsuite')) for k in EXPECTED}
    need(totals==EXPECTED,str(totals))
    rows=[]
    for stage in ('J','K','L'):
        left=(prior/'tensor'/f'{stage}.checkpoint.pb').read_bytes()
        right=baseline(left);start=time.perf_counter()
        raw=m.compare(left,right);seconds=time.perf_counter()-start
        need(m.replay(left,right,raw),'metric receipt replay')
        result=json.loads(raw);values,points=reference(left,right)
        need(len(values)==len(result['components']),'reference component layout')
        discrepancies=[]
        for x,y in zip(result['components'],values):
            for key in y:
                err=abs(float(Q(x[key]))-y[key]);discrepancies.append(err)
                need(err<=1e-10+1e-10*abs(y[key]),'independent SciPy quadrature disagreement')
        (out/f'{stage}.left.checkpoint.pb').write_bytes(left)
        (out/f'{stage}.right.checkpoint.pb').write_bytes(right)
        (out/f'{stage}.metrics.json').write_bytes(raw)
        rows.append(dict(stage=stage,left_sha256=sha(left),right_sha256=sha(right),metrics_sha256=sha(raw),
                         l2_distance_squared=result['l2']['distance_squared'],h1_distance_squared=result['h1']['distance_squared'],
                         work_units=result['work_units'],independent_quadrature_points=points,
                         max_abs_reference_difference=max(discrepancies),seconds=seconds,exact_replay=True))
    result=dict(source_sha=head,status='PASS',profile=m.PROFILE,totals=totals,platform=platform.platform(),
        python=sys.version,prior_sha256=sha(prior_raw),inherited_unique_pins=len(pins),
        prior_manifest_pins=count,rows=rows,host_side_operator=True,new_worker_calls=0,
        production_enabled=False,native_lu_accepted=False,
        artifacts={p.name:sha(p.read_bytes()) for p in sorted(out.iterdir()) if p.is_file()})
    (out/'receipt.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf8')
    print(totals,'three exact functional-metric comparisons with independently integrated reference fields')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--prior',required=True)
    a=p.parse_args();main(a.out,a.prior)
