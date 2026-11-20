"""SSM-02-R1 exact bounded verification gate, downstream of same-head SSM-02."""
import argparse,json,os,platform,sys
from pathlib import Path
from fractions import Fraction as Q
from cognitum.research import ssm_linear as s, ssm_verification as v
from tools.ssm01.acceptance import PINS,git,need,sha,run_tests
from tools.ssm02.acceptance import NEW_PINS as BASE_PINS

NEW_PINS={"cognitum/research/ssm_verification.py":"cf3c2fadd52be0e2cb028cd5f3dc96f1ca62925e","research_tests/ssm02r1/test_verification.py":"3cf7995aa245c9eca2800665931f7341733b236a"}

EXPECTED={'gain.json':'5536b5af29e1f5e27601993c600af7fd6c2414ec80b661b8a933112c7b7a48d9','passive.json':'dbaa18fa679f8e5b3b32e9314f5c1a4707e3a452b00456620f331158e0f6e400','contraction.json':'86f882fa18ce8d01d871162b168e472560d7b9bbaa075838962884a51bd1c0a0','tube.json':'29b87664a26a3a4399b35b7ea2ad723d0697860dae0b139d3c1e8fa9e4738c8f'}

def run(prior,out):
    import numpy as np,scipy
    root=Path(prior).resolve();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    head=git('rev-parse','HEAD');need(not os.getenv('GITHUB_SHA') or head==os.environ['GITHUB_SHA'],'source SHA')
    need(not git('status','--porcelain','--untracked-files=no'),'tracked drift')
    prior_pins=dict(PINS,**BASE_PINS);pins=dict(prior_pins,**NEW_PINS)
    for path,blob in pins.items():need(git('rev-parse',head+':'+path)==blob,'source drift '+path)
    oldraw=(root/'receipt.json').read_bytes();old=json.loads(oldraw)
    need(old['source_sha']==head and old['status']=='PASS' and old['source_pins']==prior_pins,'same-head SSM-02')
    need(old['dedicated']==dict(tests=40,failures=0,errors=0,skipped=0),'prior test inventory')
    for name,digest in old['artifacts'].items():
        p=(root/name).resolve();need(p.is_relative_to(root) and p.is_file() and sha(p.read_bytes())==digest,'prior artifact integrity')
    totals=run_tests(['research_tests/ssm02r1/test_verification.py'],out/'tests.xml',out/'tests.log',33)
    m=s.Model(((-1,),),((1,),),((1,),),((0,),),('x',),('u',),('y',),'continuous');p=((1,),)
    n=v.Polynomial(((((1,),-1),((3,),Q(-1,4))),))
    files={'gain.json':v.gain_bound(m,p,1),'passive.json':v.passivity(m,p),'contraction.json':v.local_contraction(n,(-Q(1,2),),(Q(1,2),),(0,),1),'tube.json':s.canonical(v.validated_step(n,(Q(1,2),),(Q(1,2),),(0,),(1,),Q(1,8)))}
    need(v.frequency_lower(m,0,0,(1,),(0,))['lower_squared']==1,'analytic tight gain')
    need(v.replay(m,p,1,files['gain.json'],'gain'),'gain replay')
    need(v.replay(m,p,((0,1),(1,0)),files['passive.json'],'dissipation'),'passivity replay')
    need(json.loads(files['tube.json'])['endpoint']==[['11/32','1/2']],'analytic interval arithmetic')
    for name,raw in files.items():
        need(sha(raw)==EXPECTED[name],'frozen witness mismatch '+name);(out/name).write_bytes(raw)
    result=dict(source_sha=head,status='PASS',platform=platform.platform(),python=sys.version,versions=dict(numpy=np.__version__,scipy=scipy.__version__),prior_ssm02_sha256=sha(oldraw),source_pins=pins,dedicated=totals,exact_witnesses=EXPECTED,execution_authorized=False,artifacts={p.name:sha(p.read_bytes()) for p in sorted(out.iterdir()) if p.is_file()})
    (out/'receipt.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(totals,'four deterministic exact witness files')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prior',required=True);p.add_argument('--out',required=True);args=p.parse_args();run(args.prior,args.out)
