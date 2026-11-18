"""Source-bound scoped gate; inherited E2B gate is mandatory in hosted acceptance."""
import hashlib,json,os,subprocess,sys
from xml.etree import ElementTree as ET
from tools import cog03e2b_acceptance as prior
ROOT=prior.ROOT;OUT=prior.OUT

def source_check():
    sha=prior.source_check();m=json.loads((ROOT/'docs/research/COG03E2C_SOURCE_MANIFEST.json').read_text(encoding='utf8'))
    for p,b in m['git_blobs'].items():
        if prior.prior.git('rev-parse','HEAD:'+p)!=b:raise RuntimeError('E2C source drift: '+p)
    return sha

def main():
    scoped='--scoped-only' in sys.argv;before=source_check()
    if scoped:
        if os.environ.get('GITHUB_ACTIONS')=='true':raise RuntimeError('scoped gate forbidden in hosted acceptance')
    else:
        prior.main();assert source_check()==before
        # Download only the reviewed classical source wheel; never install quantum dependencies.
        # Prior native gate installs CPU numerical dependencies; pin sklearn for E2C separately.
        subprocess.run([sys.executable,'-m','pip','install','scikit-learn==1.8.0','tabulate==0.10.0'],check=True,timeout=240)
        dest=OUT/'e2c-wheel';dest.mkdir(parents=True,exist_ok=True)
        subprocess.run([sys.executable,'-m','pip','download','--no-deps','--only-binary=:all:','--dest',str(dest),'hdlib==2.1.0'],check=True,timeout=180)
        os.environ['COG03E2C_HDLIB_WHEEL']=str(dest/'hdlib-2.1.0-py3-none-any.whl')
    wheel=os.environ['COG03E2C_HDLIB_WHEEL'];OUT.mkdir(exist_ok=True);xml=OUT/'e2c-tests.xml';pilot=OUT/'e2c-pilot.json';selection=OUT/'e2c-selection.json'
    tasks=[('tests',['-m','pytest','-q','-ra','research_tests/hdc_e2c',f'--junitxml={xml}']),('pilot',['-m','tools.cog03e2c_pilot','--quick','--wheel',wheel,'--out',str(pilot)]),('selection',['-m','tools.cog03e2c_selection','--out',str(selection)])]
    close=OUT/'e2c-closeout.json';classification=OUT/'e2c-classification.json'
    tasks.extend([('closeout',['-m','tools.cog03e2c_closeout','--quick','--wheel',wheel,'--out',str(close)]),('classification',['-m','tools.cog03e2c_classification','--quick','--stepwise','--wheel',wheel,'--out',str(classification)])])
    paths=[xml,pilot,selection,close,classification]
    for name,args in tasks:
        p=OUT/f'e2c-{name}.log';paths.append(p)
        with p.open('wb') as f:subprocess.run([sys.executable,*args],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    cases=list(ET.parse(xml).iter('testcase'));assert len(cases)==27 and not any(c.find(t) is not None for c in cases for t in ('failure','error','skipped'))
    r=json.loads(pilot.read_text());assert len(r['rows'])==8 and len(r['clustering'])==3 and len(r['graphs'])==1 and len(r['native_parity'])==1
    assert all(max(x[k] for k in ('max_prediction_error','cluster_max_error','weight_max_error'))<1e-8 for x in r['native_parity'])
    assert all(0<=x['coverage90']<=1 and x['model_numeric_bytes']>0 for x in r['rows'])
    s=json.loads(selection.read_text());assert len(s['rows'])==16 and all(x['ranking_parity'] and 0<=x['correct']<=x['n'] for x in s['rows'])
    q=json.loads(close.read_text(encoding='utf8'));assert len(q['rows'])==8 and len(q['quantized_parity'])==1 and q['quantized_parity'][0]['max_error']<1e-8
    assert all(a['explicit_training_bound_bytes']<=a['budget'] for a in q['rows'] if a['budget'])
    c=json.loads(classification.read_text(encoding='utf8'));assert len(c['rows'])==1 and c['rows'][0]['oracle_disagreements']==0 and c['rows'][0]['fit_train_only'] and not c['quantum_imported']
    assert c['native_stepwise']['models']>0 and c['native_stepwise']['outer_test_excluded'] and c['native_stepwise']['start_method']=='spawn'
    after=source_check();assert before==after
    (OUT/'e2c-result.json').write_text(json.dumps({'schema':'cognitum.cog03e2c.acceptance.v1','source_sha':before,'source_after':after,'new_tests':len(cases),'expected_hosted_tests_with_inherited':527+len(cases),'passed':True,'scoped_only':scoped,'production_enabled':False,'isolated_native_classical_classification_and_stepwise':True,'normal_package_import_verified':False,'artifact_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}},indent=2)+'\n')
if __name__=='__main__':main()
