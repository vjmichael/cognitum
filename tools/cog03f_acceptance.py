"""Scoped source-bound research gate; hosted suite retains inherited RGB acceptance."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'cog03bc-artifacts'
def blob(p):
    b=p.read_bytes();return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def check(scoped):
    m=json.loads((ROOT/'docs/research/COG03F_SOURCE_MANIFEST.json').read_text())['git_blobs']
    for p,h in m.items():
        assert blob(ROOT/p)==h,p
        if not scoped:assert subprocess.check_output(['git','rev-parse','HEAD:'+p],cwd=ROOT,text=True).strip()==h,p
    return m
def main():
    scoped='--scoped-only' in sys.argv
    if scoped and os.environ.get('GITHUB_ACTIONS')=='true':raise RuntimeError('scoped bypass')
    before=check(scoped);commit=None
    if not scoped:
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();assert commit==os.environ['COG03BC_EXPECTED_SHA'];assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip()
        from tools import cog03e2g_rgb_acceptance
        cog03e2g_rgb_acceptance.main()
    OUT.mkdir(exist_ok=True);xml=OUT/'f-tests.xml';log=OUT/'f-tests.log'
    with log.open('wb') as f:subprocess.run([sys.executable,'-m','pytest','-q','research_tests/hdc_f','--junitxml='+str(xml)],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    cases=list(ET.parse(xml).iter('testcase'));assert len(cases)==37 and not any(c.find(t) is not None for c in cases for t in ('failure','error','skipped'))
    dispatch=OUT/'f-dispatch.json';dlog=OUT/'f-dispatch.log'
    with dlog.open('wb') as f:subprocess.run([sys.executable,'-m','tools.cog03f_dispatch_pilot','--quick','--out',str(dispatch)],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=120)
    d=json.loads(dispatch.read_text(encoding='utf8'));assert d['rows'] and all(r['parity'] for r in d['rows'])
    from tools.cog03f_rtl import run as rtl_run
    required=not scoped and os.environ.get('COG03F_RTL_REQUIRED')=='1'
    if required:
        meta=rtl_run(OUT)
        assert meta['rtl_simulated'] is True and meta['cycles']>=2000
    else:meta=rtl_run(OUT,oracle_only=True)
    files=[xml,log,dispatch,dlog,OUT/'f-rtl-result.json',OUT/'f-rtl-vectors.txt']
    if required:files.extend([OUT/'f-rtl-compile.log',OUT/'f-rtl-run.log'])
    assert before==check(scoped)
    if commit:assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==commit and not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip()
    (OUT/'f-result.json').write_text(json.dumps({'source_sha':commit,'source_blobs':before,'scoped_only':scoped,'passed':True,'new_tests':len(cases),'expected_hosted_tests':691+len(cases),'production_enabled':False,'rtl_required':required,'rtl_simulated':meta['rtl_simulated'],'artifact_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}},indent=2)+'\n')
if __name__=='__main__':main()
