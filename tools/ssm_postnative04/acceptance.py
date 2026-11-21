"""COG-05-SSM-POST-NATIVE-04-R1: bounded immutable multisite science acceptance."""
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
PINS={
 'cognitum/research/ssm_multisite.py':'9a50fdc893eae88c956ce0ec0bc2a9379725ce9d',
 'research_tests/ssm_postnative04/test_multisite.py':'c53646d7c06ecca2348f0531ddb7b91885d77ab9',
 'research_tests/ssm_postnative04/test_native_hybrid.py':'54c1dd874b6000f968740ef4c92680eda209ed9f',
 'tools/ssm_postnative04/acquire.py':'d1261060d3e7942c4e964c882e9b98cbe9b25c4b',
 'research_tests/ssm_postnative04/data/sources.json':'bc4f1e632a08c677a861a9208036bf87df63df5c',
 'research_tests/ssm_postnative04/data/acquisition.json':'67afd02bd74dc6c2e856279f9437392c17f4312f',
 'research_tests/ssm_postnative04/data/Changping.csv':'60162fd7183d4ca62a869ddb4fa47d2eb43c076e',
 'research_tests/ssm_postnative04/data/Dingling.csv':'f083504372ba2ab3083d8518b910a8c1fd850ebd',
 'research_tests/ssm_postnative04/data/Guanyuan.csv':'12c1c4665eaedfc0d314fd4ede22c6bc8e27fff5',
 '.gitattributes':'e83fceb4c919fb7d0289e28a2727ffd2bc6cea9e',
}
PRIOR_SOURCE={
 'cognitum/research/ssm_observed_dynamics.py':'ca76a27489eb8edc86a7df1644c2490de63171db',
 'research_tests/ssm_postnative03/test_observed.py':'43981538491a13b923f0f68c7a3c48726f8c3188',
 'research_tests/ssm_postnative03/test_native_integration.py':'06c6374509252b84932709b13f9f51fd5b74078a',
 'research_tests/ssm_postnative03/data/uci374.csv':'ee385681af4610c26f99ab358dc9e1117bc42894',
 'research_tests/ssm_postnative03/data/uci501.csv':'b5d3646fe409bf3a309ea43db8374d82b493c74d',
 'research_tests/ssm_postnative03/data/sources.json':'c41db5a029489520a1d9c007f1501284425eadcb',
}
def require(ok,msg):
    if not ok:raise ValueError(msg)
def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def sha(b):return hashlib.sha256(b).hexdigest()

def run_suite(paths,folder,expected):
    folder.mkdir(parents=True,exist_ok=False)
    cmd=[sys.executable,'-m','pytest','-q',*paths,'--junitxml',str(folder/'tests.xml')]
    p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=720)
    (folder/'tests.log').write_text(p.stdout+'\n'+p.stderr,encoding='utf-8')
    require(p.returncode==0,'native pytest failure: '+folder.name+' (see tests.log)')
    xml=ET.parse(folder/'tests.xml').getroot()
    suite=xml if xml.tag=='testsuite' else xml.find('testsuite')
    require(suite is not None,'JUnit root')
    actual={k:int(suite.get(k,'0')) for k in ('tests','failures','errors','skipped')}
    require(actual==dict(tests=expected,failures=0,errors=0,skipped=0),'native test inventory '+folder.name)
    artifacts={q.name:sha(q.read_bytes()) for q in sorted(folder.iterdir()) if q.is_file()}
    return {'inventory':actual,'artifacts':artifacts}

def run(out):
    out=Path(out).resolve()
    head=git('rev-parse','HEAD')
    require(not os.getenv('GITHUB_SHA') or head==os.environ['GITHUB_SHA'],'exact workflow SHA')
    require(not git('status','--porcelain','--untracked-files=no'),'tracked source drift')
    for name,blob in dict(PRIOR_SOURCE,**PINS).items():
        require(git('rev-parse',head+':'+name)==blob,'source pin mismatch '+name)
    from cognitum.research import ssm_multisite as m
    manifest=(ROOT/'research_tests/ssm_postnative04/data/sources.json').read_bytes()
    require(sha(manifest)==m.MANIFEST_SHA,'original-multisite manifest SHA')
    dataset=json.loads(manifest)
    require(dataset['outer_archive_sha256']==m.BEIJING_ARCHIVE,'original UCI archive identity')
    require(dataset['license']=='CC BY 4.0' and len(dataset['entries'])==3,'dataset license/row contract')
    for site in m.SITES:
        raw=(ROOT/'research_tests/ssm_postnative04/data'/(site+'.csv')).read_bytes()
        s=m.ingest_site(site,raw,manifest)
        require(len(s['state'])==6144 and s['interval_seconds']==3600,'measured site profile')
    out.mkdir(parents=True,exist_ok=False)
    dedicated=run_suite(['research_tests/ssm_postnative04'],out/'dedicated',38)
    combined=run_suite(['research_tests/ssm_postnative03','research_tests/ssm_postnative04'],out/'combined',67)
    # The two inventories must be genuine equal-source scoped cases, not skipped statuses.
    receipt={
      'status':'PASS','source_sha':head,'platform':platform.platform(),'python':sys.version,
      'source_pins':PINS,'inherited_postnative03_pins':PRIOR_SOURCE,
      'dedicated':dedicated,'combined':combined,'reported_sites':list(m.SITES),
      'new_measured_rows':18432,'horizon_hours':[1,6,24],
      'source_archive_sha256':m.BEIJING_ARCHIVE,
      'license':'CC BY 4.0 with original author attribution',
      'upstream_publisher_signature_verified':False,
      'physical_law_discovered':False,
      'dependent_coverage_guaranteed':False,
      'all_scientific_capabilities_complete':False,
      'execution_authorized':False,
      'preserved_postnative03_native_sha':'9c02f020136744930e3708a2b00f5a1db6d34dd8',
      'preserved_postnative02_native_sha':'bd2b332a06291f005adf5ab8183c56c8d36ba81f',
    }
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'status':'PASS','sha':head,'dedicated':dedicated['inventory'],'combined':combined['inventory']},sort_keys=True))
if __name__=='__main__':
    require(len(sys.argv)==2,'output directory argument')
    run(sys.argv[1])
