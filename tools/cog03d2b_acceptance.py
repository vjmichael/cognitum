"""D2B source-bound research extension. Preserve inherited D2A and prior gates."""
import hashlib,json,subprocess,sys
from xml.etree import ElementTree as ET
from tools import cog03d2_acceptance as prior
ROOT=prior.ROOT;OUT=prior.OUT

def source_check():
    sha=prior.source_check();m=json.loads((ROOT/'docs/research/COG03D2B_SOURCE_MANIFEST.json').read_text(encoding='utf8'))
    for path,blob in m['git_blobs'].items():
        if subprocess.check_output(['git','rev-parse','HEAD:'+path],cwd=ROOT,text=True).strip()!=blob:raise RuntimeError('D2B source drift '+path)
    return sha

def d2b_gate():
    before=source_check();OUT.mkdir(exist_ok=True);log=OUT/'d2b-tests.log';xml=OUT/'d2b-tests.xml'
    with log.open('wb') as f:subprocess.run([sys.executable,'-m','pytest','-q','-ra','--junitxml='+str(xml),'research_tests/hdc_d2b'],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    cases=list(ET.parse(xml).iter('testcase'))
    if len(cases)!=27 or any(c.find(t) is not None for c in cases for t in ('failure','error','skipped')):raise RuntimeError('D2B test cohort mismatch')
    f=OUT/'d2b-pilot.json';err=OUT/'d2b-pilot.log'
    with err.open('wb') as e:subprocess.run([sys.executable,'-m','tools.cog03d2b_pilot','--quick','--out',str(f)],cwd=ROOT,stdout=e,stderr=subprocess.STDOUT,check=True,timeout=180)
    r=json.loads(f.read_text(encoding='utf8'))
    assert {k:len(v) for k,v in r.items()}=={'factor':3,'multi':2,'sparse':3,'graph':5,'hash':1,'arc':2,'rules':1,'equal_pair':1}
    for x in r['factor']+r['sparse']:
        assert x['correct']+x['wrong']+x['abstain']==x['queries']
        if x['arm']=='exhaustive':assert x['correct']==x['queries']
    assert all(x['full']+x['partial']+x['none']==x['queries'] for x in r['multi'])
    assert all(x['full']==x['queries'] and not x['spurious'] for x in r['multi'] if x['arm']=='exhaustive')
    assert all(x['correct']==x['queries'] for x in r['graph'] if x['arm']=='exact_structure')
    assert all(x['correct']==x['queries'] for x in r['arc'])
    assert all(x['wrong']==0 and x['correct']+x['miss']==x['truth'] for x in r['rules'])
    assert all(x['correct'] and x['pairs']==2016 for x in r['equal_pair'])
    after=source_check();assert before==after
    (OUT/'d2b-result.json').write_text(json.dumps({'schema':'cognitum.cog03d2b.acceptance.v1','source_sha':before,'source_after':after,'new_tests':len(cases),'expected_tests_with_inherited':391+len(cases),'passed':True,'smoke':r,'scope':'bounded reference; no full paper replication, production, hardware or LLM efficacy','artifact_hashes':{x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in [log,xml,f,err]},'production_enabled':False},indent=2)+'\n',encoding='utf8')

def main():
    source_check();prior.main();d2b_gate();source_check()
if __name__=='__main__':main()
