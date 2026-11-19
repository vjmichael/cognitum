"""COG-04D exact source, supervised adaptation and native execution gate."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
import xml.etree.ElementTree as ET
from tools.cog04a.acceptance import check
from cognitum.mel.polynomial_kan import Checkpoint
from cognitum.research.kan_trainable import load_snapshot
from cognitum.mel.polynomial_kan import export_checkpoint
ROOT=Path(__file__).resolve().parents[2]
EXPECTED=dict(tests=34,failures=0,errors=0,skipped=0)

def main(out):
    os.chdir(ROOT);out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    m=json.loads((ROOT/'docs/research/cog04d/manifest.json').read_text(encoding='utf8'));head=None;hosted=os.getenv('GITHUB_ACTIONS')=='true'
    if hosted:
        head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
        if os.getenv('COG03BC_EXPECTED_SHA')!=head:raise RuntimeError('wrong checkout')
        c=json.loads((out.parent/'cog04c'/'receipt.json').read_text(encoding='utf8'))
        if not (c['source_sha']==head and c['totals']==dict(tests=41,failures=0,errors=0,skipped=0) and c['hosted_predecessor_checked'] is True and c['compiled_descriptor_match'] is True and c['three_engine_verified'] is True and c['model_codec_worker_verified'] is True and c['production_enabled'] is False):raise RuntimeError('missing same-head COG-04C gate')
    check(m,head=head)
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    xml=out/'tests.xml'
    with (out/'tests.log').open('w',encoding='utf8') as f:
        subprocess.run([sys.executable,'-m','pytest','-q','research_tests/cog04d','--basetemp='+str(out/'retained'),'--junitxml',str(xml)],env=env,stdout=f,stderr=subprocess.STDOUT,timeout=180,check=True)
    totals={k:sum(int(s.get(k,0)) for s in ET.parse(xml).getroot().findall('.//testsuite')) for k in EXPECTED}
    if totals!=EXPECTED:raise RuntimeError(str(totals))
    def summary(name,labels):
        paths=list((out/'retained').rglob(name))
        if len(paths)!=1:raise RuntimeError('missing unique '+name)
        file=paths[0];d=json.loads(file.read_text(encoding='utf8'))
        for n,h in d['sha256'].items():
            if Path(n).name!=n or hashlib.sha256((file.parent/n).read_bytes()).hexdigest()!=h:raise RuntimeError('evidence drift '+n)
        for prefix in labels:
            cp=Checkpoint((file.parent/(prefix+'checkpoint.pb')).read_bytes());raw=(file.parent/(prefix+'snapshot.json')).read_bytes();net=load_snapshot(raw,d['sha256'][prefix+'snapshot.json'])
            if cp.identity!=d['sha256'][prefix+'checkpoint.pb'] or export_checkpoint(net).wire!=cp.wire:raise RuntimeError('checkpoint/snapshot drift')
        return d
    a=summary('adaptive.json',['refined.','pruned.']);c=summary('composition.json',[''])
    if not (a['training_points']==101 and a['heldout_points']==100 and len(a['history'])==4 and a['calls']==2 and a['adaptive_rmse']<a['baseline_rmse']*.1 and all(max(s['transport_error_upper'])<=1e-10 and s['after_mse']<s['before_mse'] for s in a['history']) and a['pruned_edges']==[[0,0,1]] and max(a['prune_error_upper'])<=.005 and c['rmse']<1e-12 and len(c['values'])==6):raise RuntimeError('incomplete experiment evidence')
    check(m,head=head)
    digests={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file() and not p.is_symlink() and p.name!='receipt.json'}
    (out/'receipt.json').write_text(json.dumps(dict(source_sha=head,reference_parent=m['base'],totals=totals,source_pins=len(m['git_blobs']),hosted_predecessor_checked=hosted,adaptive_refinements=len(a['history']),baseline_rmse=a['baseline_rmse'],adaptive_rmse=a['adaptive_rmse'],max_transport_error_upper=max(max(s['transport_error_upper']) for s in a['history']),prune_error_upper=a['prune_error_upper'],compositional_holdout_rmse=c['rmse'],actual_worker_calls=3,represented_inputs_only=True,production_enabled=False,native_lu_accepted=False,artifacts=digests),indent=2)+'\n',encoding='utf8')
    print(totals,'adaptive refinement, exact residual certificates, bounded pruning, frozen-feature composition; three actual MEL workers')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);main(p.parse_args().out)
