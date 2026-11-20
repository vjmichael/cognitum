"""Same-head native continuum approximation qualification and CPU/RAM receipt."""
import argparse,hashlib,json,os,platform,subprocess,sys,time
from pathlib import Path
import xml.etree.ElementTree as ET
from cognitum.research import kan_continuum_ritz as q
from tools.cog04q.oracle import verify
from tools.cog04p.profile import memory

ROOT=Path(__file__).resolve().parents[2]
P_PINS={'cognitum/research/kan_weak_form.py':'96eab091950fc86ea700c756a17c655220f83e57',
'tools/cog04p/acceptance.py':'114cdf018dcd0a6ff7b79134e9dce9240eada049',
'tools/cog04p/profile.py':'0cb74f48306aa8faf21ac612d12cdac5ad0490e6',
'tools/cog04p/oracle.py':'5f8af15c150f7efa8b7e4cbe8dbba26a4bb2d74d',
'tools/cog04p/fixtures.py':'dc99566ed6be15ac2aaf0dc62374165be34db8b9',
'research_tests/cog04p/test_weak_form.py':'508dcb8eed519ba9f80c3c55c16fa80eb6b1456a'}
def sha(data):return hashlib.sha256(data).hexdigest()
def main(prior,out):
    os.chdir(ROOT);prior=Path(prior).resolve();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    q.need(not os.getenv('GITHUB_SHA') or head==os.getenv('GITHUB_SHA'),'wrong source')
    q.need(not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True).strip(),'tracked source drift')
    for name,blob in P_PINS.items():
        q.need(subprocess.check_output(['git','rev-parse',head+':'+name],text=True).strip()==blob,'P source pin drift')
    oldraw=(prior/'receipt.json').read_bytes();old=json.loads(oldraw)
    q.need(old['source_sha']==head and old['status']=='PASS' and old['totals']==dict(tests=14,errors=0,failures=0,skipped=0),'same-head P receipt')
    for name,digest in old['artifacts'].items():
        path=(prior/name).resolve()
        q.need(path.is_relative_to(prior) and path.is_file() and sha(path.read_bytes())==digest,'P artifact drift')
    env=os.environ.copy();env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    xml=out/'tests.xml'
    with (out/'tests.log').open('w',encoding='utf8') as log:
        run=subprocess.run([sys.executable,'-m','pytest','-q','research_tests/cog04q','--junitxml',str(xml)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180)
    q.need(run.returncode==0,'continuum tests failed')
    totals={k:sum(int(s.get(k,0)) for s in ET.parse(xml).getroot().findall('.//testsuite'))
            for k in ('tests','errors','failures','skipped')}
    q.need(totals==dict(tests=8,errors=0,failures=0,skipped=0),str(totals))
    before,method=memory();cpu=time.process_time_ns();start=time.perf_counter_ns()
    history=q.adaptive();elapsed=time.perf_counter_ns()-start;cpu=time.process_time_ns()-cpu;peak,check=memory()
    q.need(peak>=before>0 and method==check and cpu>0 and elapsed>0,'native resource counters')
    rows=[]
    for i,(raw,r) in enumerate(history):
        path=out/f'level-{i}.exact.json';path.write_bytes(raw)
        rows.append(dict(**r,matrix_sha256=sha(raw),oracle=verify(raw,r)))
    q.need(max(rows[-1]['oracle']['relative_errors'])<1e-4,'continuum convergence target')
    result=dict(source_sha=head,status='PASS',platform=platform.platform(),python=sys.version,totals=totals,
        prior_p_sha256=sha(oldraw),p_source_pins=P_PINS,rows=rows, elapsed_ns=elapsed,process_cpu_ns=cpu,
        peak_bytes=peak,before_peak_bytes=before,memory_method=method,
        resource_scope='adaptive interval; lifetime peak includes imports and parent setup; independent checks excluded',
        production_enabled=False,certified_continuum_eigenvalue_bounds=False,
        artifacts={f.name:sha(f.read_bytes()) for f in sorted(out.iterdir()) if f.is_file()})
    (out/'receipt.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf8')
    print(totals,'nine nested spaces, independently verified continuum reference and native CPU/RAM measurements')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prior',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();main(a.prior,a.out)
