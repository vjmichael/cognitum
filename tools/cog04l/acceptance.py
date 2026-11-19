"""Strict same-SHA 2+1D research acceptance; no MEL tensor wire or Lu grant."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
import xml.etree.ElementTree as ET
from tools.cog04a.acceptance import check
from tools.cog04l.benchmark import run
ROOT=Path(__file__).resolve().parents[2]
EXPECTED=dict(tests=79,failures=0,errors=0,skipped=0)

def need(ok,msg):
    if not ok:raise RuntimeError(msg)

def main(out):
    os.chdir(ROOT);out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    m=json.loads((ROOT/'docs/research/cog04l/manifest.json').read_text(encoding='utf8'));head=None;hosted=os.getenv('GITHUB_ACTIONS')=='true'
    if hosted:
        head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();need(head==os.getenv('COG03BC_EXPECTED_SHA'),'wrong checkout')
        prior=json.loads((out.parent/'cog04k'/'receipt.json').read_text(encoding='utf8'))
        need(prior['source_sha']==head and prior['totals']==dict(tests=61,failures=0,errors=0,skipped=0) and all(prior[k] is True for k in ('hosted_predecessor_checked','checkpoint_replay_verified','certified_full_domain_error','certified_time_prefix_error','hard_conditions')) and prior['production_enabled'] is False,'missing same-head K acceptance')
    check(m,head=head)
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1');xml=out/'tests.xml'
    with (out/'tests.log').open('w',encoding='utf8') as log:
        subprocess.run([sys.executable,'-m','pytest','-q','research_tests/cog04l','--junitxml',str(xml)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180,check=True)
    totals={k:sum(int(t.get(k,0)) for t in ET.parse(xml).getroot().findall('.//testsuite')) for k in EXPECTED};need(totals==EXPECTED,str(totals))
    rows=run(out/'benchmark');need(len(rows)==4 and all(r['accepted'] and r['initial_exact'] and r['boundary_exact'] and r['c2'] for r in rows),'2+1D benchmark/condition gate incomplete')
    check(m,head=head)
    artifacts={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file() and not p.is_symlink() and p.name!='receipt.json'}
    (out/'receipt.json').write_text(json.dumps(dict(source_sha=head,reference_parent=m['base'],totals=totals,source_pins=len(m['git_blobs']),hosted_predecessor_checked=hosted,checkpoint_replay_verified=True,certified_full_domain_error=True,certified_time_prefix_error=True,hard_conditions=True,actual_mel_worker_calls=0,mel_tensor_wire_supported=False,production_enabled=False,native_lu_accepted=False,artifacts=artifacts),indent=2)+'\n',encoding='utf8')
    print(totals,'2+1D transient tensor KAN residual learning and exact error-bound replay')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);main(p.parse_args().out)
