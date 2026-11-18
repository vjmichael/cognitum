"""Bounded D2A research gate; inherited D1C and C2 evidence is mandatory."""
import hashlib,json,subprocess,sys
from xml.etree import ElementTree as ET
from tools import cog03d1c_acceptance as prior
ROOT=prior.ROOT;OUT=prior.OUT

def source_check():
    sha=prior.source_check();m=json.loads((ROOT/'docs/research/COG03D2A_SOURCE_MANIFEST.json').read_text(encoding='utf8'))
    for p,b in m['git_blobs'].items():
        if subprocess.check_output(['git','rev-parse','HEAD:'+p],cwd=ROOT,text=True).strip()!=b:raise RuntimeError('D2A source drift '+p)
    return sha

def d2_gate():
    before=source_check();OUT.mkdir(exist_ok=True);log=OUT/'d2a-tests.log';xml=OUT/'d2a-tests.xml'
    with log.open('wb') as f:subprocess.run([sys.executable,'-m','pytest','-q','-ra','--junitxml='+str(xml),'research_tests/hdc_d2'],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    cases=list(ET.parse(xml).iter('testcase'))
    if len(cases)!=29 or any(c.find(t) is not None for c in cases for t in ('failure','error','skipped')):raise RuntimeError('D2A test cohort mismatch')
    f=OUT/'d2a-pilot.json';err=OUT/'d2a-pilot.log'
    with err.open('wb') as e:subprocess.run([sys.executable,'-m','tools.cog03d2_pilot','--quick','--out',str(f)],cwd=ROOT,stdout=e,stderr=subprocess.STDOUT,check=True,timeout=180)
    r=json.loads(f.read_text(encoding='utf8'))
    if len(r['factor'])!=20 or len(r['hopfield'])!=3 or len(r['graph'])!=3:raise RuntimeError('smoke cohort mismatch')
    assert all(x['counts'].get('correct',0)+x['counts'].get('wrong',0)+x['counts'].get('abstained',0)==x['queries'] for x in r['factor'])
    assert all(x['counts']['correct']==x['queries'] for x in r['factor'] if x['arm']=='exhaustive')
    assert all(x['energy_violations']==0 for x in r['hopfield'])
    assert all(x['wrong']==0 and x['verified']+x['miss']==x['truth_count'] for x in r['graph'] if x['arm']!='exact_graph')
    after=source_check();assert before==after
    (OUT/'d2a-result.json').write_text(json.dumps({'schema':'cognitum.cog03d2a.acceptance.v1','source_sha':before,'source_after':after,'new_tests':len(cases),'expected_tests_with_inherited':362+len(cases),'passed':True,'smoke':r,'scope':'bounded reference; no production, hardware or LLM efficacy','artifact_hashes':{x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in [log,xml,f,err]},'production_enabled':False},indent=2)+'\n',encoding='utf8')

def main():
    source_check();prior.main();d2_gate();source_check()
if __name__=='__main__':main()
