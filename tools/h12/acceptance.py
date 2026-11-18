"""Independent H12 source-bound scoped research gate. Does not relax F2."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'cog03bc-artifacts';M=ROOT/'docs/research/h12/manifest.json'

def blob(p):
    b=p.read_bytes();return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def source_check(scoped):
    m=json.loads(M.read_text(encoding='utf8'))['git_blobs']
    for p,h in m.items():
        if blob(ROOT/p)!=h or not scoped and subprocess.check_output(['git','rev-parse','HEAD:'+p],cwd=ROOT,text=True).strip()!=h:raise RuntimeError('H12 source drift '+p)
    return m

def main():
    scoped='--scoped-only' in sys.argv
    if scoped and os.getenv('GITHUB_ACTIONS')=='true':raise RuntimeError('scoped bypass forbidden')
    commit=None
    if not scoped:
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        if commit!=os.environ['COG03BC_EXPECTED_SHA']:raise RuntimeError('unexpected SHA')
        f2=json.loads((OUT/'f2-result.json').read_text(encoding='utf8'))
        if f2['source_sha']!=commit or not f2['passed'] or f2['expected_hosted_tests']!=765:raise RuntimeError('F2 gate missing')
    before=source_check(scoped);OUT.mkdir(exist_ok=True)
    xml=OUT/'h12-tests.xml';log=OUT/'h12-tests.log';bench=OUT/'h12-quick.json';blog=OUT/'h12-quick.log'
    with log.open('wb') as f:subprocess.run([sys.executable,'-m','pytest','-q','research_tests/hdc_h12','--junitxml='+str(xml)],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    tests=list(ET.parse(xml).iter('testcase'))
    if len(tests)!=19 or any(c.find(k) is not None for c in tests for k in ('failure','error','skipped')):raise RuntimeError('H12 test failure')
    with blog.open('wb') as f:subprocess.run([sys.executable,'-m','tools.h12.pipeline','--quick','--out',str(bench)],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    r=json.loads(bench.read_text(encoding='utf8'));rows=r['rows'];assert len(rows)==12 and all(v['score_parity'] for v in rows)
    for d in (256,1024):
        for b in (1,16):
            a=[v for v in rows if v['dimension']==d and v['batch']==b];assert {v['arm'] for v in a}=={'dense','packed','packed_generated'} and len({v['score_hash'] for v in a})==len({v['prediction_hash'] for v in a})==1
    assert before==source_check(scoped)
    if commit:assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==commit and not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip()
    (OUT/'h12-result.json').write_text(json.dumps(dict(source_sha=commit,source_blobs=before,scoped_only=scoped,passed=True,new_tests=len(tests),expected_hosted_tests=765+len(tests),quick_timing_rows=len(rows),production_enabled=False,timing_qualified=False,artifact_hashes={p.name:digest(p) for p in (xml,log,bench,blog)}),indent=2)+'\n',encoding='utf8')
if __name__=='__main__':main()
