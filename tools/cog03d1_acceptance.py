"""Grouped D1 research gate; preserves the entire accepted C2C suite."""
import hashlib,json,os,subprocess,sys
from xml.etree import ElementTree as ET
from tools import cog03c2c_acceptance as prior

ROOT=prior.ROOT; OUT=prior.OUT

def source_check():
    sha=prior.source_check()
    m=json.loads((ROOT/'docs/research/COG03D1_SOURCE_MANIFEST.json').read_text(encoding='utf8'))
    for p,b in {**m['git_blobs'],**m['preserved_c08_blobs']}.items():
        if prior.c2.prior.git('rev-parse','HEAD:'+p)!=b:raise RuntimeError('D1 source drift '+p)
    return sha

def main():
    before=source_check();prior.main()
    if '--installed' not in sys.argv:prior.c2.prior.run('-m','pip','install','protobuf==6.33.6')
    from importlib.metadata import version
    if version('protobuf')!='6.33.6':raise RuntimeError('protobuf version mismatch')
    log=OUT/'d1-tests.log';xml=OUT/'d1-tests.xml'
    with log.open('wb') as f:
        subprocess.run([sys.executable,'-m','pytest','-q','-ra','--junitxml='+str(xml),'research_tests/hdc_memory'],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    cases=list(ET.parse(xml).iter('testcase'))
    groups={name:sum(test in c.attrib.get('classname','') for c in cases) for name,test in [('d1a','test_cog03d1_associative'),('d1b','test_cog03d1b_lifecycle')]}
    if len(cases)!=45 or groups!={'d1a':17,'d1b':28} or any(c.find(tag) is not None for c in cases for tag in ('failure','error','skipped')):raise RuntimeError('D1 cohort mismatch '+repr(groups))
    runlog=OUT/'d1-churn.log';result=OUT/'d1-churn.json'
    with runlog.open('wb') as f:subprocess.run([sys.executable,'-m','tools.cog03d1b_churn','--steps','1000','--out',str(result)],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    churn=json.loads(result.read_text(encoding='utf8'))
    if churn['oracle_checks']!=100 or churn['restarts']!=10 or churn['verified_false_positives']!=0 or churn['steps']!=1000 or not churn['verified']:raise RuntimeError('churn evidence mismatch')
    after=source_check()
    if before!=after:raise RuntimeError('source changed')
    files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (log,xml,runlog,result)}
    (OUT/'d1-result.json').write_text(json.dumps({'schema':'cognitum.cog03d1.acceptance.v1','source_sha':before,'source_after':after,'passed':True,'total_hdc_tests':288+len(cases),'new_tests':len(cases),'groups':groups,'churn':churn,'artifact_hashes':files,'production_enabled':False},indent=2)+'\n',encoding='utf8')

if __name__=='__main__':main()
