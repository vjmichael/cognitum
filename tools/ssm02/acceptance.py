"""Same-head bounded system analysis acceptance, downstream of SSM-01."""
import argparse, json, os, platform, sys
from pathlib import Path
from fractions import Fraction as Q
from cognitum.research import ssm_linear as s, ssm_analysis as a
from tools.ssm01.acceptance import PINS, git, need, sha, run_tests

NEW_PINS={"cognitum/research/ssm_analysis.py":"a488a260a029b114f0e5294e5f20ead8da759bac","research_tests/ssm02/test_analysis.py":"e72b9f6bc5bcd532d545cdce291e4036a92168d3"}

def run(prior,out):
    import numpy as np, scipy
    root=Path(prior).resolve();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    head=git('rev-parse','HEAD');need(not os.getenv('GITHUB_SHA') or os.environ['GITHUB_SHA']==head,'source SHA')
    need(not git('status','--porcelain','--untracked-files=no'),'tracked drift')
    for path,blob in dict(PINS,**NEW_PINS).items():
        need(git('rev-parse',head+':'+path)==blob,'source drift '+path)
    oldraw=(root/'receipt.json').read_bytes();old=json.loads(oldraw)
    need(old['source_sha']==head and old['status']=='PASS' and old['source_pins']==PINS,'same-head SSM-01')
    for key,count in [('dedicated',38),('legacy',115)]:
        need(old[key]==dict(tests=count,failures=0,errors=0,skipped=0),'prior inventory '+key)
    for name,digest in old['artifacts'].items():
        p=(root/name).resolve();need(p.is_relative_to(root) and p.is_file() and sha(p.read_bytes())==digest,'prior artifact integrity')
    totals=run_tests(['research_tests/ssm02/test_analysis.py'],out/'tests.xml',out/'tests.log',40)
    cases=[]
    for domain,A,expected_p,expected_w,expected_o,expected_h,cert_hash in [
        ('discrete',((Q(1,2),2),(0,Q(1,2))),((Q(4,3),Q(16,9)),(Q(16,9),Q(356,27))),((Q(320,27),Q(16,9)),(Q(16,9),Q(4,3))),((Q(4,3),Q(16,9)),(Q(16,9),Q(320,27))),Q(320,27),'20bbac08d7482367d168b155cecefb7c3eca0a0cf13f0860274066557766a1ee'),
        ('continuous',((-1,2),(0,-1)),((Q(1,2),Q(1,2)),(Q(1,2),Q(3,2))),((Q(1),Q(1,2)),(Q(1,2),Q(1,2))),((Q(1,2),Q(1,2)),(Q(1,2),Q(1))),Q(1),'a8a33a9a74a0d3eaffe35b7598889fcef913917d27b78b46bc07192ac0783b7b')]:
        m=s.Model(A,((0,),(1,)),((1,0),),((0,),),('x','x'),('u',),('y',),domain)
        p=a.stability(m)['p'];g=a.gramians(m);rank=a.ranks(m);h=a.h2_squared(m)
        need(p==expected_p and g['reach']==expected_w and g['observe']==expected_o and h==expected_h,'frozen analytic exact witness')
        need(rank['controllable'] and rank['observable'],'rank control')
        cert=a.lyapunov_certificate(m,p);need(sha(cert)==cert_hash and a.replay_lyapunov(m,p,cert),'certificate bytes')
        path=domain+'-lyapunov.json';(out/path).write_bytes(cert)
        summary=s.canonical(dict(model=m,rank=rank,gramians=g,h2_squared=h,execution_authorized=False))
        filename=domain+'-analysis.json';(out/filename).write_bytes(summary)
        cases.append(dict(domain=domain,certificate=path,certificate_sha256=sha(cert),analysis=filename,analysis_sha256=sha(summary)))
    result=dict(source_sha=head,status='PASS',platform=platform.platform(),python=sys.version,versions=dict(numpy=np.__version__,scipy=scipy.__version__),prior_ssm01_sha256=sha(oldraw),source_pins=dict(PINS,**NEW_PINS),dedicated=totals,exact_cases=cases,riccati_optimality_certified=False,execution_authorized=False,artifacts={p.name:sha(p.read_bytes()) for p in sorted(out.iterdir()) if p.is_file()})
    (out/'receipt.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(totals,'two deterministic exact systems-analysis witnesses')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prior',required=True);p.add_argument('--out',required=True);args=p.parse_args();run(args.prior,args.out)
