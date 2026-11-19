"""Source-bound, no-skip VFA research gate; inherited HDC gate is separate."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'cog03bc-artifacts'/'vfa'


def blob(path):
    b=path.read_bytes()
    return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()


def main():
    os.chdir(ROOT);OUT.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((ROOT/'docs/research/vfa/manifest.json').read_text(encoding='utf-8'))
    def check():
        for p,expected in manifest['git_blobs'].items():
            if blob(ROOT/p)!=expected: raise RuntimeError('source mismatch: '+p)
    check()
    sha=os.getenv('COG03BC_EXPECTED_SHA')
    if sha and subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()!=sha:
        raise RuntimeError('wrong checkout')
    xml=OUT/'tests.xml';log=OUT/'tests.log';result=OUT/'benchmark.json'
    with log.open('w',encoding='utf-8') as f:
        subprocess.run([sys.executable,'-m','pytest','-q','research_tests/hdc_vfa','--junitxml',str(xml)],stdout=f,stderr=subprocess.STDOUT,check=True)
    suites=ET.parse(xml).getroot().findall('.//testsuite')
    totals={k:sum(int(s.get(k,0)) for s in suites) for k in ('tests','failures','errors','skipped')}
    if totals!={'tests':manifest['expected_tests'],'failures':0,'errors':0,'skipped':0}: raise RuntimeError(str(totals))
    subprocess.run([sys.executable,'-m','tools.vfa.benchmark','--out',str(result)],check=True)
    rows=json.loads(result.read_text(encoding='utf-8'))['rows']
    if len(rows)!=96 or not all(r['product_max_abs']<=1e-11 and r['quotient_max_abs']<=r['residual_bound']+1e-11 for r in rows): raise RuntimeError('oracle failed')
    check()
    (OUT/'receipt.json').write_text(json.dumps(dict(source_sha=sha,git_blobs=manifest['git_blobs'],totals=totals,rows=len(rows),production_enabled=False,artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (xml,log,result)}),indent=2)+'\n',encoding='utf-8')
    print(totals, '96 benchmark rows')

if __name__=='__main__': main()
