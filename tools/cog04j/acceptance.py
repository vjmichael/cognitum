"""Strict same-head native CPU research gate; no claim of MEL wire support."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from tools.cog04a.acceptance import check
from tools.cog04j.benchmark import run

ROOT=Path(__file__).resolve().parents[2]
EXPECTED=dict(tests=56,failures=0,errors=0,skipped=0)


def need(ok,msg):
    if not ok:raise RuntimeError(msg)


def main(out):
    os.chdir(ROOT);out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    m=json.loads((ROOT/'docs/research/cog04j/manifest.json').read_text(encoding='utf8'))
    hosted=os.getenv('GITHUB_ACTIONS')=='true';head=None
    if hosted:
        head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
        need(os.getenv('COG03BC_EXPECTED_SHA')==head,'wrong checkout')
        prior=json.loads((out.parent/'cog04i'/'receipt.json').read_text(encoding='utf8'))
        need(prior['source_sha']==head and prior['totals']==dict(tests=53,failures=0,errors=0,skipped=0) and prior['hosted_predecessor_checked'] is True and prior['checkpoint_replay_verified'] is True and prior['actual_worker_calls']==1 and prior['production_enabled'] is False,'missing same-head I worker acceptance')
    check(m,head=head)
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1');xml=out/'tests.xml'
    with (out/'tests.log').open('w',encoding='utf8') as log:
        subprocess.run([sys.executable,'-m','pytest','-q','research_tests/cog04j','--junitxml',str(xml)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180,check=True)
    totals={k:sum(int(t.get(k,0)) for t in ET.parse(xml).getroot().findall('.//testsuite')) for k in EXPECTED};need(totals==EXPECTED,str(totals))
    rows=run(out/'benchmark');need(len(rows)==4 and all(v['accepted'] and v['conditions_exact'] and v['c2'] for v in rows),'benchmark or checkpoint gate incomplete')
    check(m,head=head)
    artifacts={a.relative_to(out).as_posix():hashlib.sha256(a.read_bytes()).hexdigest() for a in sorted(out.rglob('*')) if a.is_file() and not a.is_symlink() and a.name!='receipt.json'}
    (out/'receipt.json').write_text(json.dumps(dict(source_sha=head,reference_parent=m['base'],totals=totals,source_pins=len(m['git_blobs']),hosted_predecessor_checked=hosted,checkpoint_replay_verified=True,certified_full_domain_error=True,hard_conditions=True,actual_mel_worker_calls=0,mel_tensor_wire_supported=False,production_enabled=False,native_lu_accepted=False,artifacts=artifacts),indent=2)+'\n',encoding='utf8')
    print(totals,'2D tensor-product KAN elliptic residual learning, exact checkpoint and certificate replay')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);main(p.parse_args().out)
