"""D1C gated research extension; retain all 333 earlier dedicated tests."""
import hashlib,json,subprocess,sys
from xml.etree import ElementTree as ET
from tools import cog03d1_acceptance as prior
ROOT=prior.ROOT;OUT=prior.OUT

def source_check():
    sha=prior.source_check();m=json.loads((ROOT/'docs/research/COG03D1C_SOURCE_MANIFEST.json').read_text(encoding='utf8'))
    for p,b in m['git_blobs'].items():
        if prior.prior.c2.prior.git('rev-parse','HEAD:'+p)!=b:raise RuntimeError('D1C source drift '+p)
    return sha

def main():
    before=source_check();prior.main();log=OUT/'d1c-tests.log';xml=OUT/'d1c-tests.xml'
    with log.open('wb') as f:subprocess.run([sys.executable,'-m','pytest','-q','-ra','--junitxml='+str(xml),'research_tests/hdc_d1c'],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    cases=list(ET.parse(xml).iter('testcase'))
    if len(cases)!=29 or any(c.find(t) is not None for c in cases for t in ('failure','error','skipped')):raise RuntimeError('D1C test cohort mismatch')
    files=[log,xml];results={}
    for arm,cap in [('sdm',131072),('packed_sdm',131072),('signed',16384),('hrr',262144),('sqlite',262144)]:
        f=OUT/('d1c-'+arm+'.json');err=OUT/('d1c-'+arm+'.log')
        with f.open('wb') as o,err.open('wb') as e:subprocess.run([sys.executable,'-m','tools.cog03d1c_pilot','--arm',arm,'--seed','301','--cap',str(cap)],cwd=ROOT,stdout=o,stderr=e,check=True,timeout=180)
        a=json.loads(f.read_text(encoding='utf8'));assert a['payload_bytes']<=cap;results[arm]=a;files.extend([f,err])
    a,b=results['sdm'],results['packed_sdm'];assert a['correct']==b['correct'] and a['abstain']==b['abstain'] and b['payload_bytes']<a['payload_bytes']
    assert results['hrr']['verified_wrong']==0 and results['hrr']['tp']+results['hrr']['fn']==results['sqlite']['tp']
    # Performance and approximate accuracy are evidence, not enforced superiority.
    after=source_check();assert before==after
    (OUT/'d1c-result.json').write_text(json.dumps({'schema':'cognitum.cog03d1c.acceptance.v1','source_sha':before,'source_after':after,'tests':333+len(cases),'new_tests':len(cases),'passed':True,'smoke':results,'scope':'portable bounded reference gate; native platform peak RSS may be unavailable; no OS memory limit in CI smoke','artifact_hashes':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in files},'production_enabled':False},indent=2)+'\n',encoding='utf8')
if __name__=='__main__':main()
