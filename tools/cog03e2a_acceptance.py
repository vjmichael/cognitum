"""Consolidated source-bound HDC E2A gate; scoped local preflight is explicit."""
import hashlib,json,os,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'cog03bc-artifacts'

def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()

def source_check():
    sha=git('rev-parse','HEAD')
    if sha!=os.environ.get('COG03BC_EXPECTED_SHA') or git('status','--porcelain','--untracked-files=no'):raise RuntimeError('unexpected or dirty tracked source')
    m=json.loads((ROOT/'docs/research/COG03E2A_SOURCE_MANIFEST.json').read_text(encoding='utf8'))
    for p,s in m['git_blobs'].items():
        if git('rev-parse','HEAD:'+p)!=s:raise RuntimeError('E2A source drift: '+p)
    return sha

def e2a_gate(scoped=False):
    before=source_check();OUT.mkdir(exist_ok=True)
    xml=OUT/'e2a-tests.xml';log=OUT/'e2a-tests.log';pilot=OUT/'e2a-pilot.json';plog=OUT/'e2a-pilot.log';close=OUT/'e2a-closeout.json';clog=OUT/'e2a-closeout.log'
    with log.open('wb') as f:subprocess.run([sys.executable,'-m','pytest','-q','-ra','research_tests/hdc_e2a',f'--junitxml={xml}'],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    cases=list(ET.parse(xml).iter('testcase'));assert len(cases)==22 and not any(x.find(t) is not None for x in cases for t in ('failure','error','skipped'))
    for module,dest,output in [('tools.cog03e2a_pilot',pilot,plog),('tools.cog03e2a_closeout',close,clog)]:
        with output.open('wb') as f:subprocess.run([sys.executable,'-m',module,'--quick','--out',str(dest)],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=240)
    rows=json.loads(pilot.read_text(encoding='utf8'))['rows'];assert len(rows)==len({r['arm'] for r in rows})==21 and len({r['split'] for r in rows})==1
    assert all(0<=r['correct']<=r['n']==36 and 0<r['bytes']<=r['budget'] for r in rows)
    for r in rows:
        if r['arm'].startswith('native_lehdc'):assert r['training_array_bytes']<=r['budget'] and r['weight_disagreements']==r['prediction_disagreements']==0
    data=json.loads(close.read_text(encoding='utf8'));assert len(data['refine'])==12 and len(data['drift'])==12 and len(data['memory'])==6
    for r in data['refine']:assert r['fit_failure'] is None and 0<=r['correct']<=r['n']==36
    for r in data['drift']:
        assert [q['phase'] for q in r['trajectory']]==[0,1,2] and all(0<=q['correct']<=q['n']==120 and 0<=q['abstain']<=q['n'] and len(q['probe_accuracy'])==3 for q in r['trajectory'])
    for r in data['memory']:
        assert 0<r['persistent_bytes']<=r['budget'] and 0<r['baseline_peak_bytes']<=r['training_peak_process_bytes']<=r['process_cap_bytes'] and 0<=r['correct']<=r['n']==36
    assert len({r['split'] for r in data['memory']})==1 and len({r['arm'] for r in data['memory']})==6
    after=source_check();assert before==after
    (OUT/'e2a-result.json').write_text(json.dumps({'schema':'cognitum.cog03e2a.acceptance.v1','source_sha':before,'source_after':after,'new_tests':len(cases),'expected_tests_with_inherited':475+len(cases),'passed':True,'scoped_only':scoped,'production_enabled':False,'paper_fidelity_complete':False,'artifact_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (xml,log,pilot,plog,close,clog)}},indent=2)+'\n',encoding='utf8')

def main():
    before=source_check();scoped='--scoped-only' in sys.argv
    if scoped:
        if os.environ.get('GITHUB_ACTIONS')=='true':raise RuntimeError('scoped gate forbidden in hosted acceptance')
    else:
        from tools import cog03e1b_acceptance as prior
        prior.main();assert prior.source_check()==before
    e2a_gate(scoped);assert source_check()==before
if __name__=='__main__':main()
