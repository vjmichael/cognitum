"""Source-bound independent E2B gate; chain previously accepted E2A in CI."""
import hashlib,json,os,subprocess,sys
from xml.etree import ElementTree as ET
from tools import cog03e2a_acceptance as prior
ROOT=prior.ROOT;OUT=prior.OUT

def source_check():
    sha=prior.source_check();m=json.loads((ROOT/'docs/research/COG03E2B_SOURCE_MANIFEST.json').read_text(encoding='utf8'))
    for p,blob in m['git_blobs'].items():
        if prior.git('rev-parse','HEAD:'+p)!=blob:raise RuntimeError('E2B source drift: '+p)
    return sha

def gate(scoped):
    before=source_check();OUT.mkdir(exist_ok=True);xml=OUT/'e2b-tests.xml';log=OUT/'e2b-tests.log';pilot=OUT/'e2b-pilot.json';plog=OUT/'e2b-pilot.log';close=OUT/'e2b-closeout.json';clog=OUT/'e2b-closeout.log'
    for path,args in [(log,['-m','pytest','-q','-ra','research_tests/hdc_e2b',f'--junitxml={xml}']),(plog,['-m','tools.cog03e2b_pilot','--quick','--out',str(pilot)]),(clog,['-m','tools.cog03e2b_closeout','--quick','--out',str(close)])]:
        with path.open('wb') as f:subprocess.run([sys.executable,*args],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    cases=list(ET.parse(xml).iter('testcase'));assert len(cases)==30 and not any(x.find(t) is not None for x in cases for t in ('failure','error','skipped'))
    rows=json.loads(pilot.read_text(encoding='utf8'))['rows'];by={r['arm']:r for r in rows};assert len(rows)==len(by)==15 and len({r['split'] for r in rows})==1
    assert all(0<=r['correct']<=r['n'] and r['n']>0 for r in rows)
    a=by['phase_threshold'];b=by['phase_adam'];assert a['optimizer_bytes']==0 and b['optimizer_bytes']>0 and b['training_array_bytes']==9*a['training_array_bytes'] and a['writes']>0
    assert all(by[k]['exact_quantized_score_parity'] for k in ('informative_expanded','random_expanded'))
    cr=json.loads(close.read_text(encoding='utf8'));rr=cr['rows'];assert len(rr)==14
    assert all(0<=r['correct']<=r['n'] and r['training_numeric_bytes']==r['persistent_bytes']+r['gradient_bytes']+r['decoded_parameter_bytes'] and 0<r['baseline_peak_rss_bytes']<=r['observed_peak_rss_bytes'] for r in rr)
    assert all(r['training_numeric_bytes']<=r['budget'] for r in rr if r['mode']=='budget')
    dim={r['arm']:r for r in rr if r['mode']=='dimension'}
    assert dim['packed6']['prediction_sha256']==dim['dense6']['prediction_sha256'] and dim['packed6']['persistent_bytes']<dim['dense6']['persistent_bytes']
    assert all(r['native_weight_parity'] for r in rr if r['arm']=='lehdc')
    assert all(r['exact_score_parity'] for r in cr['structure'] if not r.get('empty'))
    assert any(not r.get('empty') for r in cr['structure'])
    after=source_check();assert before==after
    (OUT/'e2b-result.json').write_text(json.dumps({'schema':'cognitum.cog03e2b.acceptance.v1','source_sha':before,'source_after':after,'new_tests':len(cases),'expected_tests_with_inherited':497+len(cases),'passed':True,'scoped_only':scoped,'production_enabled':False,'paper_replication_complete':False,'artifact_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (xml,log,pilot,plog,close,clog)}},indent=2)+'\n',encoding='utf8')

def main():
    scoped='--scoped-only' in sys.argv;before=source_check()
    if scoped:
        if os.environ.get('GITHUB_ACTIONS')=='true':raise RuntimeError('scoped gate forbidden in hosted acceptance')
    else:prior.main();assert prior.source_check()==before
    gate(scoped);assert source_check()==before
if __name__=='__main__':main()
