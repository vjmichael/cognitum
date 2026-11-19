"""Source-bound MEL-02 tests and independent numeric oracle receipts."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from tools.mel02.benchmark import run

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'cog03bc-artifacts'/'mel02'


def blob(raw):return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


def main():
    os.chdir(ROOT);OUT.mkdir(parents=True,exist_ok=True)
    sha=os.getenv('COG03BC_EXPECTED_SHA');hosted=os.getenv('GITHUB_ACTIONS')=='true'
    if hosted and not sha:raise RuntimeError('missing hosted SHA')
    if sha and subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()!=sha:raise RuntimeError('wrong checkout')
    manifest=json.loads((ROOT/'docs/research/mel02/manifest.json').read_text(encoding='utf8'))
    def check():
        for p,expected in manifest['git_blobs'].items():
            raw=(ROOT/p).read_bytes()
            if blob(raw)!=expected and (p not in manifest['inherited_text'] or blob(raw.replace(b'\r\n',b'\n'))!=expected):raise RuntimeError('source drift '+p)
            if sha and subprocess.check_output(['git','rev-parse','HEAD:'+p],text=True).strip()!=expected:raise RuntimeError('commit drift '+p)
    check()
    if hosted:
        prev=json.loads((OUT.parent/'vfa3'/'receipt.json').read_text(encoding='utf8'))
        inv=json.loads((OUT.parent/'mel01'/'inventory.json').read_text(encoding='utf8'))
        if prev['source_sha']!=sha or prev['totals']!={'tests':48,'failures':0,'errors':0,'skipped':0} or inv['current_source_sha']!=sha or len(inv['groups'])!=164 or len(inv['legacy_links'])!=85 or inv['mel_admission'] is not False:raise RuntimeError('missing predecessor same-SHA gates')
    xml=OUT/'tests.xml';log=OUT/'tests.log';bench=OUT/'benchmark.json'
    with log.open('w',encoding='utf8') as f:
        subprocess.run([sys.executable,'-m','pytest','-q','research_tests/mel02','--junitxml',str(xml)],stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    suites=ET.parse(xml).getroot().findall('.//testsuite')
    totals={k:sum(int(s.get(k,0)) for s in suites) for k in ('tests','failures','errors','skipped')}
    if totals!={'tests':38,'failures':0,'errors':0,'skipped':0}:raise RuntimeError(str(totals))
    rows=run()
    if len(rows)!=36:raise RuntimeError('benchmark case mismatch')
    bench.write_text(json.dumps(rows,indent=2)+'\n',encoding='utf8');check()
    (OUT/'receipt.json').write_text(json.dumps(dict(source_sha=sha,totals=totals,benchmark_rows=len(rows),max_value_error=max(r['value_max_abs_error'] for r in rows),max_gradient_error=max(r['gradient_max_abs_error'] for r in rows),git_blobs=manifest['git_blobs'],production_enabled=False,model_advertised=False,hosted_predecessors_checked=hosted,artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (xml,log,bench)}),indent=2)+'\n',encoding='utf8')
    print(totals,'36 matched scalar-oracle cases; research-only')


if __name__=='__main__':main()
