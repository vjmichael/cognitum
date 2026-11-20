"""SSM-04-R1 advanced stochastic dynamics, same-head predecessor acceptance."""
import argparse,json,os,platform,sys
from pathlib import Path
from tools.ssm01.acceptance import PINS,git,need,sha,run_tests
from tools.ssm02.acceptance import NEW_PINS as LINEAR
from tools.ssm02r1.acceptance import NEW_PINS as VERIFY
from tools.ssm03.acceptance import NEW_PINS as DYNAMICS
from tools.ssm03r1.acceptance import NEW_PINS as EXTENDED
from tools.ssm04.acceptance import NEW_PINS as STOCHASTIC

NEW_PINS={
    'cognitum/research/ssm_stochastic_extended.py':'19aefcc2c01ff629f6da5778b12fa0d495a3b610',
    'research_tests/ssm04r1/test_extended_stochastic.py':'4ea283a170fd3018eaf3c406f982e441a6733275',
}

def run(prior,out):
    import numpy as np, scipy
    root=Path(prior).resolve();out=Path(out).resolve()
    head=git('rev-parse','HEAD')
    need(not os.getenv('GITHUB_SHA') or os.environ['GITHUB_SHA']==head,'source SHA')
    need(not git('status','--porcelain','--untracked-files=no'),'tracked drift')
    prev=dict(PINS,**LINEAR,**VERIFY,**DYNAMICS,**EXTENDED,**STOCHASTIC);pins=dict(prev,**NEW_PINS)
    for path,blob in pins.items():need(git('rev-parse',head+':'+path)==blob,'source pin '+path)
    raw=(root/'receipt.json').read_bytes();old=json.loads(raw)
    need(old['source_sha']==head and old['status']=='PASS' and old['source_pins']==prev,'same-head SSM-04')
    need(old['dedicated']==dict(tests=28,failures=0,errors=0,skipped=0),'predecessor inventory')
    for name,digest in old['artifacts'].items():
        p=(root/name).resolve();need(p.is_relative_to(root) and p.is_file() and sha(p.read_bytes())==digest,'prior artifact integrity')
    out.mkdir(parents=True,exist_ok=False)
    totals=run_tests(['research_tests/ssm04r1'],out/'tests.xml',out/'tests.log',31)
    r=dict(source_sha=head,status='PASS',platform=platform.platform(),python=sys.version,
        versions=dict(numpy=np.__version__,scipy=scipy.__version__),prior_ssm04_sha256=sha(raw),
        source_pins=pins,dedicated=totals,execution_authorized=False,
        artifacts={p.name:sha(p.read_bytes()) for p in sorted(out.iterdir()) if p.is_file()})
    (out/'receipt.json').write_text(json.dumps(r,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(totals)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prior',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();run(a.prior,a.out)
