"""F2 scoped gate; native synthesis is mandatory in designated hosted cell."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
from xml.etree import ElementTree as ET
from tools import cog03f_acceptance as prior
ROOT=prior.ROOT;OUT=prior.OUT
MANIFEST=ROOT/'docs/research/COG03F2_SOURCE_MANIFEST.json'

def blob(p):
    b=p.read_bytes();return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()

def source_check(scoped):
    prior.check(scoped)
    m=json.loads(MANIFEST.read_text(encoding='utf8'))['git_blobs']
    for n,h in m.items():
        if blob(ROOT/n)!=h or (not scoped and subprocess.check_output(['git','rev-parse','HEAD:'+n],cwd=ROOT,text=True).strip()!=h):raise RuntimeError('F2 source drift '+n)
    return m

def main():
    scoped='--scoped-only' in sys.argv
    if scoped and os.getenv('GITHUB_ACTIONS')=='true':raise RuntimeError('scoped hosted bypass')
    before=source_check(scoped);commit=None
    if not scoped:
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        if commit!=os.environ['COG03BC_EXPECTED_SHA']:raise RuntimeError('unexpected SHA')
        prior.main()
    OUT.mkdir(exist_ok=True);xml=OUT/'f2-tests.xml';log=OUT/'f2-tests.log'
    with log.open('wb') as f:subprocess.run([sys.executable,'-m','pytest','-q','research_tests/hdc_f2','--junitxml='+str(xml)],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=120)
    tests=list(ET.parse(xml).iter('testcase'))
    if len(tests)!=22 or any(c.find(t) is not None for c in tests for t in ('failure','error','skipped')):raise RuntimeError('F2 test failure')
    required=not scoped and os.getenv('COG03F2_SYNTH_REQUIRED')=='1'; native=False; artifacts=[xml,log]
    if required:
        from tools.cog03f2_synthesis import run
        result=run(OUT)
        assert len(result['rows'])==2 and all(r['simulated'] and r['mapped_simulated'] and r['cycles']==5325 for r in result['rows']);native=True
        artifacts.extend([OUT/'f2-synthesis.json',OUT/'f2-vectors.txt'])
        for top in ('score64','score64_balanced'):
            artifacts.extend(OUT/f'{top}-{name}' for name in ('compile.log','sim.log','yosys.log','mapped.json','mapped.v','mapped-compile.log','mapped-sim.log'))
    assert before==source_check(scoped)
    if commit:assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==commit and not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip()
    (OUT/'f2-result.json').write_text(json.dumps(dict(source_sha=commit,source_blobs=before,scoped_only=scoped,passed=True,new_tests=len(tests),expected_hosted_tests=728+len(tests),synthesis_required=required,mapped_native=native,timing_qualified=False,physical_verified=False,production_enabled=False,artifact_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in artifacts}),indent=2)+'\n',encoding='utf8')
if __name__=='__main__':main()
