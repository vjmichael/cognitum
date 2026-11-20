"""Same-head qualification and native receipts for tensor continuum eigenproblems."""
import argparse,hashlib,json,os,platform,subprocess,sys
from pathlib import Path
import xml.etree.ElementTree as ET
from cognitum.research import kan_tensor_ritz as s
from tools.cog04s.fixtures import CASES
from tools.cog04s.oracle import continuum,verify

ROOT=Path(__file__).resolve().parents[2]
R_PINS={'cognitum/research/kan_sturm_liouville.py':'92e4a2e4ae5447427546275f1d2341b67d9b5029',
'tools/cog04r/oracle.py':'2b1359129cb2b077fd20f33c04e53a1d06f9adfc',
'tools/cog04r/acceptance.py':'407dc029f51bac5fab57297f361339b1f7a378be',
'tools/cog04r/profile.py':'dedb322ddcfbd1181d4cf8a2a8ad1560f21c5136',
'tools/cog04r/fixtures.py':'46950ee8f9c65644758a31de19347801e1c72e92',
'research_tests/cog04r/test_sturm_liouville.py':'261e12f4312c1ada74026c5c99884b7929df6269'}
def sha(data):return hashlib.sha256(data).hexdigest()
def main(prior,out):
    os.chdir(ROOT);prior=Path(prior).resolve();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    s.need(not os.getenv('GITHUB_SHA') or head==os.getenv('GITHUB_SHA'),'wrong source')
    s.need(not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True).strip(),'tracked source drift')
    for path,blob in R_PINS.items():
        s.need(subprocess.check_output(['git','rev-parse',head+':'+path],text=True).strip()==blob,'R source pin drift')
    oldraw=(prior/'receipt.json').read_bytes();old=json.loads(oldraw)
    s.need(old['source_sha']==head and old['status']=='PASS' and old['totals']==dict(tests=19,errors=0,failures=0,skipped=0)
        and len(old['cases'])==6,'same-head R receipt')
    for name,digest in old['artifacts'].items():
        path=(prior/name).resolve()
        s.need(path.is_relative_to(prior) and path.is_file() and sha(path.read_bytes())==digest,'R artifact drift')
    env=os.environ.copy();env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    xml=out/'tests.xml'
    with (out/'tests.log').open('w',encoding='utf8') as log:
        run=subprocess.run([sys.executable,'-m','pytest','-q','research_tests/cog04s','--junitxml',str(xml)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=240)
    s.need(run.returncode==0,'tensor continuum tests failed')
    totals={k:sum(int(n.get(k,0)) for n in ET.parse(xml).getroot().findall('.//testsuite'))
        for k in ('tests','errors','failures','skipped')}
    s.need(totals==dict(tests=10,errors=0,failures=0,skipped=0),str(totals))
    cases=[]
    for name,p in CASES.items():
        folder=out/name
        run=subprocess.run([sys.executable,'-m','tools.cog04s.profile','--case',name,'--out',str(folder)],
            env=env,capture_output=True,text=True,timeout=120,check=True)
        profile=json.loads(run.stdout)
        s.need(profile['case']==name and len(profile['rows'])==4 and profile['process_cpu_ns']>0
            and profile['elapsed_ns']>0 and profile['peak_bytes']>=profile['before_peak_bytes']>0,'profile custody')
        ref=continuum(p);profile['reference']=ref
        for row in profile['rows']:
            raw=(folder/row['matrix_file']).read_bytes()
            s.need(sha(raw)==row['matrix_sha256'],'matrix hash')
            row['oracle']=verify(p,raw,row,ref)
        s.need(max(profile['rows'][-1]['oracle']['scaled_errors'])<1e-5,'continuum convergence target')
        cases.append(profile)
    result=dict(source_sha=head,status='PASS',platform=platform.platform(),python=sys.version,totals=totals,
        prior_r_sha256=sha(oldraw),r_source_pins=R_PINS,cases=cases,production_enabled=False,
        certified_continuum_eigenvalue_bounds=False,
        artifacts={f.relative_to(out).as_posix():sha(f.read_bytes()) for f in sorted(out.rglob('*')) if f.is_file()})
    (out/'receipt.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf8')
    print(totals,'five tensor cases, 20 nested spectra and five native measured profiles')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prior',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();main(a.prior,a.out)
