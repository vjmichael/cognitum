"""Independent projection gate; existing H12 and F2 gates remain mandatory."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'cog03bc-artifacts';M=ROOT/'docs/research/h12_projection/manifest.json'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def blob(p):
    b=p.read_bytes();return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def source_check(scoped):
    m=json.loads(M.read_text(encoding='utf8'))['git_blobs']
    for p,h in m.items():
        if blob(ROOT/p)!=h or not scoped and subprocess.check_output(['git','rev-parse','HEAD:'+p],cwd=ROOT,text=True).strip()!=h:raise RuntimeError('projection source drift '+p)
    return m
def main():
    scoped='--scoped-only' in sys.argv
    if scoped and os.getenv('GITHUB_ACTIONS')=='true':raise RuntimeError('scoped bypass')
    commit=None
    if not scoped:
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        h12=json.loads((OUT/'h12-result.json').read_text(encoding='utf8'))
        if commit!=os.environ['COG03BC_EXPECTED_SHA'] or h12['source_sha']!=commit or not h12['passed'] or h12['expected_hosted_tests']!=784:raise RuntimeError('H12 predecessor missing')
    before=source_check(scoped);OUT.mkdir(exist_ok=True);xml=OUT/'projection-tests.xml';log=OUT/'projection-tests.log';bench=OUT/'projection-quick.json';blog=OUT/'projection-quick.log'
    with log.open('wb') as f:subprocess.run([sys.executable,'-m','pytest','-q','research_tests/hdc_h12_projection','--junitxml='+str(xml)],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=120)
    tests=list(ET.parse(xml).iter('testcase'))
    if len(tests)!=17 or any(c.find(k) is not None for c in tests for k in ('failure','error','skipped')):raise RuntimeError('projection test failure')
    with blog.open('wb') as f:subprocess.run([sys.executable,'-m','tools.h12_projection.benchmark','--quick','--out',str(bench)],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=240)
    r=json.loads(bench.read_text(encoding='utf8'));rows=r['rows'];assert len(rows)==10 and len(r['symbolic'])==4 and all(v['score_parity'] for v in rows)
    assert all(v['same_codebook_parity'] for v in rows if v['arm'] in ('dense','packed_weights','seed_regenerate'))
    assert before==source_check(scoped)
    if commit:assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==commit and not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip()
    (OUT/'projection-result.json').write_text(json.dumps(dict(source_sha=commit,source_blobs=before,passed=True,scoped_only=scoped,new_tests=len(tests),expected_hosted_tests=784+len(tests),timing_qualified=False,production_enabled=False,artifact_hashes={p.name:digest(p) for p in (xml,log,bench,blog)}),indent=2)+'\n',encoding='utf8')
if __name__=='__main__':main()
