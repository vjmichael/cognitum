"""Same-head rigorous scalar bounds, equivalence and paired native measurements."""
import argparse,hashlib,json,os,platform,statistics,subprocess,sys,time
from fractions import Fraction as Q
from pathlib import Path
import xml.etree.ElementTree as ET
from cognitum.research import kan_certified_spectrum as u
from tools.cog04r.fixtures import CASES
from tools.cog04r.oracle import reference
from tools.cog04u.oracle import verify
from tools.cog04p.profile import memory

ROOT=Path(__file__).resolve().parents[2]
T_PINS={'cognitum/research/kan_coupled_ritz.py':'af19cee250e1f6bfa340a40a44e3f6c43b4b30af',
'tools/cog04t/acceptance.py':'a6cc870a7554127970dd25f2296e84199acb6f3d',
'tools/cog04t/oracle.py':'ea25e4b374f6b11ed5183bfc4efb7e699300c6d9',
'tools/cog04t/profile.py':'443e4daa540df91f6494d93d96a9ee9985962a67',
'tools/cog04t/fixtures.py':'79ca40996da21c9cabd2d0311068875ff5cddb49',
'research_tests/cog04t/test_coupled_ritz.py':'18ed2b2a5bb2ec6872d276e5d1a68c77f7a3742c'}
def sha(x):return hashlib.sha256(x).hexdigest()

def main(prior,out):
    os.chdir(ROOT);prior=Path(prior).resolve();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    u.need(not os.getenv('GITHUB_SHA') or head==os.getenv('GITHUB_SHA'),'wrong source')
    u.need(not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True).strip(),'tracked source drift')
    for path,blob in T_PINS.items():u.need(subprocess.check_output(['git','rev-parse',head+':'+path],text=True).strip()==blob,'T source pin')
    oldraw=(prior/'receipt.json').read_bytes();old=json.loads(oldraw)
    u.need(old['source_sha']==head and old['status']=='PASS' and old['totals']==dict(tests=10,errors=0,failures=0,skipped=0)
        and len(old['cases'])==5,'same-head T receipt')
    for name,digest in old['artifacts'].items():
        path=(prior/name).resolve()
        u.need(path.is_relative_to(prior) and path.is_file() and sha(path.read_bytes())==digest,'T artifact drift')
    env=os.environ.copy();env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    xml=out/'tests.xml'
    with (out/'tests.log').open('w',encoding='utf8') as log:
        run=subprocess.run([sys.executable,'-m','pytest','-q','research_tests/cog04u','--junitxml',str(xml)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180)
    u.need(run.returncode==0,'certified continuum tests failed')
    totals={k:sum(int(s.get(k,0)) for s in ET.parse(xml).getroot().findall('.//testsuite')) for k in ('tests','errors','failures','skipped')}
    u.need(totals==dict(tests=20,errors=0,failures=0,skipped=0),str(totals))
    cases=[]
    for name,p in CASES.items():
        folder=out/name;folder.mkdir();ref=reference(p,rtol=2e-12);rows=[]
        for n in (2,4,8,16):
            cuts=tuple(Q(i,n) for i in range(1,n));before,method=memory();cpu=time.process_time_ns();start=time.perf_counter_ns()
            raw,cert=u.certify(p,cuts)
            elapsed=time.perf_counter_ns()-start;cpu=time.process_time_ns()-cpu;peak,check=memory()
            u.need(method==check and peak>=before>0 and elapsed>0 and cpu>=0,'certificate resource counters')
            (folder/f'{n}.matrix.json').write_bytes(raw);(folder/f'{n}.certificate.json').write_bytes(cert)
            rows.append(dict(cells=n,matrix_sha256=sha(raw),certificate_sha256=sha(cert),
                reference_checks=verify(p,cuts,raw,cert,ref),certificate_cpu_ns=cpu,certificate_elapsed_ns=elapsed,
                certificate_before_peak_bytes=before,certificate_peak_bytes=peak,certificate_memory_method=method))
        profiles=[]
        # Alternate process launch order across cases; identical locked inputs and BLAS settings.
        routes=('baseline','optimized') if len(cases)%2==0 else ('optimized','baseline')
        for route in routes:
            proc=subprocess.run([sys.executable,'-m','tools.cog04u.profile','--case',name,'--route',route],env=env,capture_output=True,text=True,timeout=120,check=True)
            v=json.loads(proc.stdout)
            u.need(v['case']==name and v['route']==route and len(v['samples'])==3
                and v['matrix_hashes']==[row['matrix_sha256'] for row in rows],'matched exact profile fidelity')
            profiles.append(v)
        b,o=(next(v for v in profiles if v['route']==k) for k in ('baseline','optimized'))
        bc,oc=(statistics.median(x['process_cpu_ns'] for x in v['samples']) for v in (b,o))
        bw,ow=(statistics.median(x['elapsed_ns'] for x in v['samples']) for v in (b,o))
        cases.append(dict(case=name,rows=rows,reference=ref,profiles=profiles,cpu_speed_ratio=bc/oc,wall_speed_ratio=bw/ow))
    result=dict(source_sha=head,status='PASS',platform=platform.platform(),python=sys.version,totals=totals,
        prior_t_sha256=sha(oldraw),t_source_pins=T_PINS,cases=cases,production_enabled=False,
        certified_scalar_continuum_bounds=True,general_nonnormal_bounds=False,
        performance_claim='measured matched assembly ratios; no universal runtime improvement threshold',
        artifacts={f.relative_to(out).as_posix():sha(f.read_bytes()) for f in sorted(out.rglob('*')) if f.is_file()})
    (out/'receipt.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf8')
    print(totals,'24 certified meshes, 72 rational eigenvalue enclosures, 36 matched native assembly samples')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prior',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();main(a.prior,a.out)
