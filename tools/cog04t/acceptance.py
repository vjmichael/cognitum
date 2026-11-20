"""Same-head coupled/adjoint continuum qualification and native evidence."""
import argparse,hashlib,json,os,platform,subprocess,sys
from pathlib import Path
import xml.etree.ElementTree as ET
from cognitum.research import kan_coupled_ritz as t
from tools.cog04t.fixtures import CASES
from tools.cog04t.oracle import continuum,verify

ROOT=Path(__file__).resolve().parents[2]
S_PINS={'cognitum/research/kan_tensor_ritz.py':'03154b6dc1b73347bf633de730d84c1ce208edde',
'tools/cog04s/acceptance.py':'fb424af963c6ad33800224b9678e3a498dee37da',
'tools/cog04s/oracle.py':'e5818f21406bea8bfea4be61e19c87fa85e96d94',
'tools/cog04s/profile.py':'bdd0a470840e8b7112b1a59de802ec2cbfbdab73',
'tools/cog04s/fixtures.py':'16bce91fb983433a217001761020109c2fd1082d',
'research_tests/cog04s/test_tensor_ritz.py':'b9738bef473ad6bb1c42c49a7040198b0f61e001'}
def sha(data):return hashlib.sha256(data).hexdigest()

def main(prior,out):
    os.chdir(ROOT);prior=Path(prior).resolve();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    t.need(not os.getenv('GITHUB_SHA') or head==os.getenv('GITHUB_SHA'),'wrong source')
    t.need(not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True).strip(),'tracked source drift')
    for path,blob in S_PINS.items():
        t.need(subprocess.check_output(['git','rev-parse',head+':'+path],text=True).strip()==blob,'S source pin drift')
    raw=(prior/'receipt.json').read_bytes();old=json.loads(raw)
    t.need(old['source_sha']==head and old['status']=='PASS' and old['totals']==dict(tests=10,errors=0,failures=0,skipped=0)
        and len(old['cases'])==5,'same-head S receipt')
    for name,digest in old['artifacts'].items():
        p=(prior/name).resolve()
        t.need(p.is_relative_to(prior) and p.is_file() and sha(p.read_bytes())==digest,'S artifact drift')
    env=os.environ.copy();env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    xml=out/'tests.xml'
    with (out/'tests.log').open('w',encoding='utf8') as log:
        run=subprocess.run([sys.executable,'-m','pytest','-q','research_tests/cog04t','--junitxml',str(xml)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180)
    t.need(run.returncode==0,'coupled continuum tests failed')
    totals={k:sum(int(s.get(k,0)) for s in ET.parse(xml).getroot().findall('.//testsuite'))
        for k in ('tests','errors','failures','skipped')}
    t.need(totals==dict(tests=10,errors=0,failures=0,skipped=0),str(totals))
    cases=[]
    for name,p in CASES.items():
        folder=out/name
        run=subprocess.run([sys.executable,'-m','tools.cog04t.profile','--case',name,'--out',str(folder)],
            env=env,capture_output=True,text=True,timeout=120,check=True)
        profile=json.loads(run.stdout)
        t.need(profile['case']==name and len(profile['rows'])==4 and profile['process_cpu_ns']>0
            and profile['elapsed_ns']>0 and profile['peak_bytes']>=profile['before_peak_bytes']>0,'profile custody')
        ref=continuum(p)
        profile['reference']=[dict(mode=x['mode'],value=t.pack(x['value']),left=t.pack(x['left']),right=t.pack(x['right'])) for x in ref]
        checks=[]
        for row in profile['rows']:
            data=(folder/row['matrix_file']).read_bytes()
            t.need(sha(data)==row['matrix_sha256'],'matrix hash')
            check=verify(p,data,row,ref);row['oracle']=check;checks.append(check)
        e=[max(c['scaled_errors']) for c in checks]
        f=[max(c['left_function_errors']+c['right_function_errors']) for c in checks]
        t.need(e[-1]<1e-5 and f[-1]<1e-3 and e[-1]<e[0]/100 and f[-1]<f[0]/100 and e[-1]<e[-2] and f[-1]<f[-2],'continuum convergence target')
        cases.append(profile)
    receipt=dict(source_sha=head,status='PASS',platform=platform.platform(),python=sys.version,totals=totals,
        prior_s_sha256=sha(raw),s_source_pins=S_PINS,cases=cases,production_enabled=False,certified_continuum_eigenvalue_bounds=False,
        artifacts={p.relative_to(out).as_posix():sha(p.read_bytes()) for p in sorted(out.rglob('*')) if p.is_file()})
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2,allow_nan=False)+'\n',encoding='utf8')
    print(totals,'five coupled cases, 20 spectra, 80 eigenvalues, 160 left/right continuum function comparisons and five native profiles')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prior',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();main(a.prior,a.out)
