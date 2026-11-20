"""Frozen native real-observation qualification, no source or external authority."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
PINS={
'cognitum/research/ssm_observed_dynamics.py':'ca76a27489eb8edc86a7df1644c2490de63171db',
'research_tests/ssm_postnative03/test_observed.py':'43981538491a13b923f0f68c7a3c48726f8c3188',
'research_tests/ssm_postnative03/test_native_integration.py':'06c6374509252b84932709b13f9f51fd5b74078a',
'research_tests/ssm_postnative03/data/uci374.csv':'ee385681af4610c26f99ab358dc9e1117bc42894',
'research_tests/ssm_postnative03/data/uci501.csv':'b5d3646fe409bf3a309ea43db8374d82b493c74d',
'research_tests/ssm_postnative03/data/sources.json':'c41db5a029489520a1d9c007f1501284425eadcb',
}
def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def sha(b): return hashlib.sha256(b).hexdigest()
def need(ok,msg):
    if not ok:raise ValueError(msg)
def run(out):
    out=Path(out).resolve();head=git('rev-parse','HEAD')
    need(not os.getenv('GITHUB_SHA') or head==os.environ['GITHUB_SHA'],'native SHA mismatch')
    need(not git('status','--porcelain','--untracked-files=no'),'tracked source drift')
    for path,blob in PINS.items():
        need(git('rev-parse',head+':'+path)==blob,'pinned Git source '+path)
    from cognitum.research import ssm_observed_dynamics as science
    manifest=(ROOT/'research_tests/ssm_postnative03/data/sources.json').read_bytes()
    need(sha(manifest)==science.EXPECTED_MANIFEST_SHA,'manifest digest')
    out.mkdir(parents=True,exist_ok=False)
    cmd=[sys.executable,'-m','pytest','-q','research_tests/ssm_postnative03','--junitxml',str(out/'tests.xml')]
    result=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=420,encoding='utf-8',errors='replace')
    (out/'tests.log').write_text(result.stdout+'\n'+result.stderr)
    need(result.returncode==0,'native tests failed (see tests.log)')
    tree=ET.parse(out/'tests.xml').getroot()
    tests=int(tree.attrib.get('tests',tree[0].attrib.get('tests',0)))
    fails=int(tree.attrib.get('failures',tree[0].attrib.get('failures',0)))
    errors=int(tree.attrib.get('errors',tree[0].attrib.get('errors',0)))
    skipped=int(tree.attrib.get('skipped',tree[0].attrib.get('skipped',0)))
    need((tests,fails,errors,skipped)==(29,0,0,0),'unmodified 29-case inventory')
    results={}
    for name in ('uci374','uci501'):
        source=(ROOT/'research_tests/ssm_postnative03/data'/(name+'.csv')).read_bytes()
        results[name]=science.experiment(name,source,manifest,integrated=True)
    receipt=dict(
        source_sha=head,status='PASS',python=sys.version,platform=platform.platform(),
        source_pins=PINS,tests=dict(tests=29,failures=0,errors=0,skipped=0),
        externally_sourced_observed_rows=12288,
        original_archives_in_separate_acquisition_artifact=True,
        uci374_original_author_git_blob_matched=True,
        license='CC BY 4.0 with attribution',
        results=results,legacy_391_native_baseline_sha='c382da2ef3e31643c39f7a01acf2aa1098df469a',
        legacy_postnative02_native_sha='bd2b332a06291f005adf5ab8183c56c8d36ba81f',
        broad_scientific_capabilities_complete=False,
        independently_validated_physical_law=False,
        distribution_shift_coverage_guaranteed=False,
        execution_authorized=False,
        artifacts={p.name:sha(p.read_bytes()) for p in out.iterdir() if p.is_file()})
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True,allow_nan=False)+'\n')
    print(json.dumps({'status':'PASS','head':head,'tests':tests,
                      'results':{k:v['metrics'] for k,v in results.items()}},indent=2))
if __name__=='__main__':run(sys.argv[1])
