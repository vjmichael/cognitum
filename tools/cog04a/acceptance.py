"""COG-04A local reference acceptance, ready for separately reviewed workflow wiring."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from tools.cog04a.benchmark import run

ROOT=Path(__file__).resolve().parents[2]
MANIFEST=ROOT/'docs/research/cog04a/manifest.json'
EXPECTED=dict(tests=61,failures=0,errors=0,skipped=0)

def pin(raw):
    return hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()

def check(m,root=ROOT,head=None):
    for p,h in m['git_blobs'].items():
        raw=(root/p).read_bytes()
        if pin(raw)!=h:
            canonical=raw.replace(b'\r\n',b'\n')
            if p not in m['crlf_text'] or raw!=canonical.replace(b'\n',b'\r\n') or pin(canonical)!=h:
                raise RuntimeError('source drift: '+p)
        if head is not None:
            blob=subprocess.check_output(['git','rev-parse',head+':'+p],cwd=root,text=True).strip()
            if blob!=h:raise RuntimeError('tree identity drift: '+p)

def main(out):
    os.chdir(ROOT);out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    m=json.loads(MANIFEST.read_text(encoding='utf8'));check(m)
    hosted=os.getenv('GITHUB_ACTIONS')=='true'
    head=None
    if hosted:
        head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
        if os.getenv('COG03BC_EXPECTED_SHA')!=head:raise RuntimeError('wrong checkout')
        prior=json.loads((ROOT/'cog03bc-artifacts/mel06ar1/receipt.json').read_text(encoding='utf8'))
        if not (prior['source_sha']==head and prior['totals']==dict(tests=102,failures=0,errors=0,skipped=0) and prior['hosted_predecessor_checked'] is True and prior['production_enabled'] is False):raise RuntimeError('missing same-head predecessor')
    check(m,head=head)
    env=os.environ.copy();env['OPENBLAS_NUM_THREADS']='1';env['OMP_NUM_THREADS']='1'
    xml=out/'tests.xml'
    with (out/'tests.log').open('w',encoding='utf8') as f:
        subprocess.run([sys.executable,'-m','pytest','-q','research_tests/cog04a','--junitxml',str(xml)],check=True,stdout=f,stderr=subprocess.STDOUT,timeout=180,env=env)
    totals={k:sum(int(s.get(k,0)) for s in ET.parse(xml).getroot().findall('.//testsuite')) for k in EXPECTED}
    if totals!=EXPECTED:raise RuntimeError(str(totals))
    summary=run(out/'benchmark');check(m,head=head)
    if not summary['disjoint'] or summary['three_engine']['worker_calls']!=4 or summary['vfa_conversion']['verdict']!='within':raise RuntimeError('incomplete benchmark')
    digests={str(p.relative_to(out)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file() and p.name!='receipt.json'}
    (out/'receipt.json').write_text(json.dumps(dict(source_sha=head,reference_parent=m['base'],totals=totals,source_pins=len(m['git_blobs']),hosted_predecessor_checked=hosted,three_engine_verified=True,fresh_fitting=True,production_enabled=False,native_lu_accepted=False,artifacts=digests),indent=2)+'\n',encoding='utf8')
    print(totals,'bounded trainable KAN with independent calculus, actual verified cross-engine execution')

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);main(p.parse_args().out)
