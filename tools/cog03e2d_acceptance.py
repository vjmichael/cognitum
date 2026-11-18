"""Source-bound E2D gate. Inherited full chain required on hosted runners."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'cog03bc-artifacts'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def source_check():
    sha=git('rev-parse','HEAD');assert sha==os.environ['COG03BC_EXPECTED_SHA'] and not git('status','--porcelain','--untracked-files=no')
    m=json.loads((ROOT/'docs/research/COG03E2D_SOURCE_MANIFEST.json').read_text(encoding='utf8'))
    for p,b in m['git_blobs'].items():assert git('rev-parse','HEAD:'+p)==b,p
    return sha
def main():
    scoped='--scoped-only' in sys.argv;before=source_check()
    if scoped:
        assert os.environ.get('GITHUB_ACTIONS')!='true'
    else:
        from tools import cog03e2c_acceptance as prior
        prior.main();subprocess.run([sys.executable,'-m','pip','install','networkx==3.6.1'],check=True,timeout=180);assert source_check()==before
    OUT.mkdir(exist_ok=True);xml=OUT/'e2d-tests.xml';pilot=OUT/'e2d-pilot.json';close=OUT/'e2d-closeout.json';paths=[xml,pilot,close]
    for name,args in [('tests',['-m','pytest','-q','-ra','research_tests/hdc_e2d','--junitxml='+str(xml)]),('pilot',['-m','tools.cog03e2d_pilot','--quick','--out',str(pilot)]),('closeout',['-m','tools.cog03e2d_closeout','--quick','--out',str(close)])]:
        log=OUT/f'e2d-{name}.log';paths.append(log)
        with log.open('wb') as f:subprocess.run([sys.executable,*args],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    cases=list(ET.parse(xml).iter('testcase'));assert len(cases)==31 and not any(c.find(t) is not None for c in cases for t in ('failure','error','skipped'))
    r=json.loads(pilot.read_text());assert len(r['clustering'])==6 and len(r['anomaly'])==10 and len(r['wafer'])==2
    assert all(-1<=x['ari']<=1 and 0<=x['nmi']<=1 and x['numeric_bytes']>0 for x in r['clustering'])
    assert all(0<=x['roc_auc']<=1 and 0<=x['pr_auc']<=1 and 0<=x['fpr']<=1 for x in r['anomaly'])
    assert all(0<=x['defect_promotion_coverage']<=x['defect_assignment_coverage']<=1 and x['persistent_modes']<=x['capacity'] for x in r['wafer'])
    q=json.loads(close.read_text(encoding='utf8'));assert len(q['clustering'])==16 and len(q['drift'])==6 and len(q['anomaly'])==36
    assert all(0<=x['threshold']<=1 and -1<=x['ari']<=1 for x in q['clustering'])
    assert all(x['peak_numeric_bytes']<=x['budget'] and 0<=x['old_identity_retention']<=1 and 0<=x['assignment_coverage']<=1 for x in q['drift'])
    assert all(0<=x['roc_auc']<=1 and 0<=x['pr_auc']<=1 and (x['budget'] is None or x['numeric_bytes']<=x['budget']) for x in q['anomaly'])
    after=source_check();assert before==after
    (OUT/'e2d-result.json').write_text(json.dumps({'source_sha':before,'source_after':after,'passed':True,'scoped_only':scoped,'new_tests':len(cases),'expected_hosted_tests_with_inherited':554+len(cases),'production_enabled':False,'artifact_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}},indent=2)+'\n')
if __name__=='__main__':main()
