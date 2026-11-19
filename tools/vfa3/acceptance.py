"""No-skip VFA-03 gate; require exact-head VFA-02 receipt on hosted CI."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'cog03bc-artifacts'/'vfa3'


def main():
    os.chdir(ROOT);OUT.mkdir(parents=True,exist_ok=True)
    sha=os.getenv('COG03BC_EXPECTED_SHA')
    if os.getenv('GITHUB_ACTIONS')=='true' and not sha:raise RuntimeError('missing expected SHA')
    manifest=json.loads((ROOT/'docs/research/vfa3/manifest.json').read_text(encoding='utf8'))
    def check():
        for p,expected in manifest['git_blobs'].items():
            b=(ROOT/p).read_bytes()
            actual=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
            if actual!=expected:raise RuntimeError('source drift '+p)
            if sha and subprocess.check_output(['git','rev-parse','HEAD:'+p],text=True).strip()!=expected:raise RuntimeError('commit drift '+p)
    if sha and subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()!=sha:raise RuntimeError('wrong checkout')
    check();prev=json.loads((OUT.parent/'vfa2'/'receipt.json').read_text(encoding='utf8'))
    if prev['source_sha']!=sha or prev['totals']!={'tests':27,'errors':0,'failures':0,'skipped':0} or prev['expected_hdc_cases']!=870:raise RuntimeError('missing VFA-02 gate')
    xml=OUT/'tests.xml';log=OUT/'tests.log';result=OUT/'benchmark.json'
    with log.open('w',encoding='utf8') as f:
        subprocess.run([sys.executable,'-m','pytest','-q','research_tests/hdc_vfa3','--junitxml',str(xml)],stdout=f,stderr=subprocess.STDOUT,check=True,timeout=120)
    suites=ET.parse(xml).getroot().findall('.//testsuite')
    totals={k:sum(int(s.get(k,0)) for s in suites) for k in ('tests','failures','errors','skipped')}
    if totals!={'tests':48,'failures':0,'errors':0,'skipped':0}:raise RuntimeError(str(totals))
    subprocess.run([sys.executable,'-m','tools.vfa3.benchmark',str(result)],check=True,timeout=120)
    r=json.loads(result.read_text(encoding='utf8'))
    if len(r['interpolation'])!=9 or len(r['features'])!=72 or len(r['composition'])!=12:raise RuntimeError('benchmark drift')
    check()
    (OUT/'receipt.json').write_text(json.dumps(dict(source_sha=sha,totals=totals,expected_hdc_cases=918,git_blobs=manifest['git_blobs'],production_enabled=False,artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (xml,log,result)}),indent=2)+'\n',encoding='utf8')
    print(totals,'93 benchmark rows')


if __name__=='__main__':main()
