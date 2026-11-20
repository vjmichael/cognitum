"""Same-head native qualification; independent continuum ODE and exact form provenance."""
import argparse,hashlib,json,os,platform,subprocess,sys
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from cognitum.research import kan_sturm_liouville as r
from tools.cog04r.fixtures import CASES
from tools.cog04r.oracle import reference,verify

ROOT=Path(__file__).resolve().parents[2]
Q_PINS={'cognitum/research/kan_continuum_ritz.py':'39dc96691906867bb3f1a81423c3305a340b3574',
 'tools/cog04q/oracle.py':'d1778a4c53b70aca00a64c570858209007b39a5a',
 'tools/cog04q/acceptance.py':'1af512f87a7af844d9b9dee01939eb8df613629b',
 'research_tests/cog04q/test_continuum.py':'3f939b1b6827d8b88b24d719c63b2a2fb1d74e91'}
def sha(data):return hashlib.sha256(data).hexdigest()
def main(prior,out):
    os.chdir(ROOT);prior=Path(prior).resolve();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    r.need(not os.getenv('GITHUB_SHA') or head==os.getenv('GITHUB_SHA'),'wrong source')
    r.need(not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True).strip(),'tracked source drift')
    for name,blob in Q_PINS.items():
        r.need(subprocess.check_output(['git','rev-parse',head+':'+name],text=True).strip()==blob,'Q source pin drift')
    oldraw=(prior/'receipt.json').read_bytes();old=json.loads(oldraw)
    r.need(old['source_sha']==head and old['status']=='PASS' and old['totals']==dict(tests=8,errors=0,failures=0,skipped=0)
        and len(old['rows'])==9,'same-head Q receipt')
    for name,digest in old['artifacts'].items():
        path=(prior/name).resolve()
        r.need(path.is_relative_to(prior) and path.is_file() and sha(path.read_bytes())==digest,'Q artifact drift')
    env=os.environ.copy();env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    xml=out/'tests.xml'
    with (out/'tests.log').open('w',encoding='utf8') as log:
        run=subprocess.run([sys.executable,'-m','pytest','-q','research_tests/cog04r','--junitxml',str(xml)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=240)
    r.need(run.returncode==0,'Sturm–Liouville tests failed')
    totals={k:sum(int(s.get(k,0)) for s in ET.parse(xml).getroot().findall('.//testsuite'))
        for k in ('tests','errors','failures','skipped')}
    r.need(totals==dict(tests=19,errors=0,failures=0,skipped=0),str(totals))
    cases=[]
    for name,problem in CASES.items():
        folder=out/name
        proc=subprocess.run([sys.executable,'-m','tools.cog04r.profile','--case',name,'--out',str(folder)],
            env=env,capture_output=True,text=True,timeout=120,check=True)
        profile=json.loads(proc.stdout)
        r.need(profile['case']==name and len(profile['rows'])==4 and profile['peak_bytes']>=profile['before_peak_bytes']>0
            and profile['elapsed_ns']>0 and profile['process_cpu_ns']>0,'profile custody')
        ref=reference(problem);tight=reference(problem,rtol=2e-12)
        r.need(np.allclose(ref['values'],tight['values'],atol=2e-8,rtol=2e-9),'shooting tolerance stability')
        profile['reference']=ref;profile['tight_reference']=tight
        for row in profile['rows']:
            path=folder/row['matrix_file'];raw=path.read_bytes()
            r.need(sha(raw)==row['matrix_sha256'],'profile matrix hash')
            row['oracle']=verify(problem,raw,row,tight)
        r.need(max(profile['rows'][-1]['oracle']['scaled_errors'])<1e-5,'continuum convergence target')
        cases.append(profile)
    result=dict(source_sha=head,status='PASS',platform=platform.platform(),python=sys.version,totals=totals,
        prior_q_sha256=sha(oldraw),q_source_pins=Q_PINS,cases=cases,production_enabled=False,
        certified_continuum_eigenvalue_bounds=False,
        artifacts={f.relative_to(out).as_posix():sha(f.read_bytes()) for f in sorted(out.rglob('*')) if f.is_file()})
    (out/'receipt.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf8')
    print(totals,'six continuum cases, 24 nested spectra and six native profiles')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prior',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();main(a.prior,a.out)
