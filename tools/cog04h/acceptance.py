"""Unchanged-head full dependency closure and exact equation solution gate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from fractions import Fraction as Q
from cognitum.mel import kan_equations as s, kan_multivariate as m, kan_fields as f
from tools.cog04a.acceptance import check
ROOT=Path(__file__).resolve().parents[2]
EXPECTED=dict(tests=37,failures=0,errors=0,skipped=0)


def require(ok,msg):
    if not ok:raise RuntimeError(msg)


def main(out):
    os.chdir(ROOT);out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    hosted=os.getenv('GITHUB_ACTIONS')=='true';head=None
    manifest=json.loads((ROOT/'docs/research/cog04h/manifest.json').read_text(encoding='utf8'))
    if hosted:
        head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
        require(os.getenv('COG03BC_EXPECTED_SHA')==head,'wrong checkout')
        prior=json.loads((out.parent/'cog04g'/'receipt.json').read_text(encoding='utf8'))
        require(prior['source_sha']==head and prior['totals']==dict(tests=57,failures=0,errors=0,skipped=0)
                and prior['hosted_predecessor_checked'] is True and prior['actual_worker_calls']==3
                and prior['production_enabled'] is False,'missing same-head G acceptance')
    check(manifest,head=head)
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    xml=out/'tests.xml'
    with (out/'tests.log').open('w',encoding='utf8') as log:
        subprocess.run([sys.executable,'-m','pytest','-q','research_tests/cog04h','--junitxml',str(xml)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180,check=True)
    totals={k:sum(int(t.get(k,0)) for t in ET.parse(xml).getroot().findall('.//testsuite')) for k in EXPECTED}
    require(totals==EXPECTED,str(totals))
    x=m.variable(1,0);c=lambda a:m.constant(1,a);box=((0,1),);fn=lambda p:m.Function(box,(p,))
    cs=tuple(s.Condition(0,side,0,c(0)) for side in ('lower','upper'))
    p=s.Problem(f.derivative(1,(2,)),fn(c(-2)),cs,2)
    solution=s.solve(p);u=s.replay(p,solution)
    require(u==fn(m.make(1,[((1,),1),((2,),-1)])),'independent analytic solution')
    require(u.evaluate((Q(1,2),))==(Q(1,4),),'independent sample value')
    cp=m.export_additive(u);w=s.certify_checkpoint(p,cp)
    require(s.replay_checkpoint(p,cp,w)==u and w.extraction.checkpoint_sha256==cp.identity,'checkpoint solution replay')
    bad=s.assess_candidate(p,fn(u.outputs[0].add(c(1))))
    require(bad.equation.identically_zero and all(not r.identically_zero and r.squared_l2==1 for r in bad.conditions),'boundary negative control')
    bad2=s.assess_candidate(p,fn(x));require(not bad2.equation.identically_zero and bad2.equation.squared_l2==4,'equation negative control')
    (out/'solution.checkpoint.pb').write_bytes(cp.wire);(out/'solution.symbolic.json').write_bytes(u.snapshot())
    check(manifest,head=head)
    artifacts={a.relative_to(out).as_posix():hashlib.sha256(a.read_bytes()).hexdigest() for a in sorted(out.rglob('*')) if a.is_file() and not a.is_symlink() and a.name!='receipt.json'}
    (out/'receipt.json').write_text(json.dumps(dict(source_sha=head,reference_parent=manifest['base'],totals=totals,source_pins=len(manifest['git_blobs']),hosted_predecessor_checked=hosted,unique_in_trial_space=True,global_uniqueness_claim=False,exact_equation_residual=True,exact_boundary_initial_traces=True,checkpoint_replay_verified=True,checkpoint_sha256=cp.identity,zero_equation_bad_boundary_rejected=True,represented_parameters_only=True,production_enabled=False,native_lu_accepted=False,artifacts=artifacts),indent=2)+'\n',encoding='utf8')
    print(totals,'exact ODE/PDE trial solutions, trace residuals, KAN checkpoint replay')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);main(p.parse_args().out)
