"""SSM-03 scientific dynamics, downstream of same-head SSM-02-R1."""
import argparse,json,os,platform,sys
from pathlib import Path
from fractions import Fraction as Q
from cognitum.research import ssm_linear as s, ssm_verification as v, ssm_dynamics as d
from tools.ssm01.acceptance import PINS,git,need,sha,run_tests
from tools.ssm02.acceptance import NEW_PINS as LINEAR_PINS
from tools.ssm02r1.acceptance import NEW_PINS as VERIFY_PINS
NEW_PINS={"cognitum/research/ssm_dynamics.py":"fd8109b0b1cf709aef41edd36352933bf17e0bba","research_tests/ssm03/test_dynamics.py":"9f44f89c89e4764823a2a659cd5fef51498cb909"}
EXPECTED={'verlet.json':'c472db0db8ba691b475dd14ae0a4fefe8de642aa7acafe1bee93015e7a86af71','port.json':'1a41d2e09bb2e0ef28316dd2d1afd12ccee2057fc8aeffb138594c6ea61c2160','integral.json':'f48d585212e77b8d7c189d3821d501c414515c4252e2315f9f5b2cb3305e1edb','network.json':'a6bc7a8cf1e4ccb45c6dba44183ad359ef93a93f11daf1c7f56dbbbaa0d3dda0'}

def run(prior,out):
    import numpy as np, scipy
    root=Path(prior).resolve();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    head=git('rev-parse','HEAD');need(not os.getenv('GITHUB_SHA') or os.environ['GITHUB_SHA']==head,'source SHA')
    need(not git('status','--porcelain','--untracked-files=no'),'tracked drift')
    prev=dict(PINS,**LINEAR_PINS,**VERIFY_PINS);pins=dict(prev,**NEW_PINS)
    for path,blob in pins.items():need(git('rev-parse',head+':'+path)==blob,'source pin '+path)
    oldraw=(root/'receipt.json').read_bytes();old=json.loads(oldraw)
    need(old['source_sha']==head and old['status']=='PASS' and old['source_pins']==prev,'same-head SSM-02-R1')
    need(old['dedicated']==dict(tests=33,failures=0,errors=0,skipped=0),'predecessor inventory')
    for name,digest in old['artifacts'].items():
        p=(root/name).resolve();need(p.is_relative_to(root) and p.is_file() and sha(p.read_bytes())==digest,'prior artifact integrity')
    totals=run_tests(['research_tests/ssm03/test_dynamics.py'],out/'tests.xml',out/'tests.log',29)
    m=d.Mechanics(((1,),),(((2,),Q(1,2)),));r=d.verlet(m,(1,),(0,),Q(1,4))
    need(r['final']==((Q(31,32),),(Q(-63,256),)) and r['energy_after']==Q(65473,131072),'analytic symplectic step')
    need(d.verlet(m,*r['final'],-Q(1,4))['final']==((Q(1),),(Q(0),)),'reverse step')
    p=d.quadratic_port(((2,0),(0,1)),((0,1),(-1,0)),((0,0),(0,1)),((0,),(1,)),(Q(1),Q(1,2)),(1,),Q(1,4))
    need(p['final']==(Q(40,37),Q(11,74)) and p['work']==Q(3,37) and p['dissipation']==Q(36,1369),'analytic port balance')
    poly=v.Polynomial(((((0,1),1),),(((1,0),-1),((3,0),-1))))
    integral=d.polynomial_invariant(poly,(((2,0),Q(1,2)),((4,0),Q(1,4)),((0,2),Q(1,2))))
    model=s.Model(((-1,1,0),(1,-2,1),(0,1,-1)),((0,),(0,),(0,)),((1,0,0),),((0,),),('x',)*3,('u',),('y',),'continuous')
    network=d.invariant_linear(model,(1,1,1))
    witnesses={'verlet.json':r,'port.json':p,'integral.json':integral,'network.json':network}
    for name,w in witnesses.items():
        raw=s.canonical(w);need(sha(raw)==EXPECTED[name],'frozen witness '+name);(out/name).write_bytes(raw)
    result=dict(source_sha=head,status='PASS',platform=platform.platform(),python=sys.version,versions=dict(numpy=np.__version__,scipy=scipy.__version__),prior_ssm02r1_sha256=sha(oldraw),source_pins=pins,dedicated=totals,exact_witnesses=EXPECTED,execution_authorized=False,artifacts={p.name:sha(p.read_bytes()) for p in sorted(out.iterdir()) if p.is_file()})
    (out/'receipt.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(totals,'four exact scientific dynamics witnesses')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prior',required=True);p.add_argument('--out',required=True);args=p.parse_args();run(args.prior,args.out)
