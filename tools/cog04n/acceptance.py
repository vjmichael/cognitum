"""Strict same-head M/N scoped reference acceptance (not installed Lu authority)."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
import xml.etree.ElementTree as ET
from tools.cog04m.acceptance import check,need
from tools.cog04n.benchmark import run
ROOT=Path(__file__).resolve().parents[2]
EXPECTED=dict(tests=54,failures=0,errors=0,skipped=0)

def main(out):
    os.chdir(ROOT);out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    m=json.loads((ROOT/'docs/research/cog04n/manifest.json').read_text(encoding='utf8'));head=None;hosted=os.getenv('GITHUB_ACTIONS')=='true'
    if hosted:
        head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();need(head==os.getenv('COG03BC_EXPECTED_SHA'),'wrong checkout')
        prior=json.loads((out.parent/'cog04m'/'receipt.json').read_text(encoding='utf8'))
        need(prior['source_sha']==head and prior['totals']==dict(tests=114,failures=0,errors=0,skipped=0) and all(prior[k] is True for k in ('hosted_predecessor_checked','descriptor_parity','typed_tensor_wire_verified','existing_mel_carrier_checked','certificate_replay_verified')) and prior['reference_worker_roundtrips']==9 and prior['actual_mel_worker_calls']==0 and prior['production_enabled'] is False and prior['native_lu_accepted'] is False,'missing same-head M acceptance')
    check(m,head)
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1');xml=out/'tests.xml'
    with (out/'tests.log').open('w',encoding='utf8') as log:
        proc=subprocess.run([sys.executable,'-m','pytest','-q','research_tests/cog04n','--junitxml',str(xml)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=300)
    need(proc.returncode==0,'tensor cooperation tests failed; inspect tests.log artifact')
    totals={k:sum(int(t.get(k,0)) for t in ET.parse(xml).getroot().findall('.//testsuite')) for k in EXPECTED};need(totals==EXPECTED,str(totals))
    rows=run(out/'benchmark');need([r['stage'] for r in rows]==['J','K','L'] and [r['worker_calls'] for r in rows]==[5,5,6] and [r['tensor_calls'] for r in rows]==[4,4,5] and all(r['symbolic_calls']==1 and r['receipt_replay'] is True and r['oracle_difference']<=1e-10 for r in rows),'incomplete scoped benchmark')
    check(m,head)
    artifacts={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file() and not p.is_symlink() and p.name!='receipt.json'}
    (out/'receipt.json').write_text(json.dumps(dict(source_sha=head,reference_parent=m['base'],totals=totals,source_pins=len(m['git_blobs']),hosted_predecessor_checked=hosted,scoped_reference_admission=True,cooperative_receipt_replay=True,actual_reference_runtime_worker_calls=16,tensor_calls=13,symbolic_calls=3,production_enabled=False,native_lu_accepted=False,model_advertised=False,os_custody_accepted=False,artifacts=artifacts),indent=2)+'\n',encoding='utf8')
    print(totals,'scoped tensor computation and independently replayed cooperative residuals; 16 existing Runtime worker calls; research only')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);main(p.parse_args().out)
