"""SSM-09B comprehensive same-head scientific acceptance. No partial promotion."""
import argparse,json,os,platform,sys
from pathlib import Path
from tools.ssm01.acceptance import PINS,git,need,sha,run_tests
from tools.ssm02.acceptance import NEW_PINS as LINEAR
from tools.ssm02r1.acceptance import NEW_PINS as VERIFY
from tools.ssm03.acceptance import NEW_PINS as DYNAMICS
from tools.ssm03r1.acceptance import NEW_PINS as EXTENDED
from tools.ssm04.acceptance import NEW_PINS as STOCHASTIC
from tools.ssm04r1.acceptance import NEW_PINS as ADVANCED
from tools.ssm05.acceptance import NEW_PINS as IDENTIFICATION
from tools.ssm05r1.acceptance import NEW_PINS as DISCOVERY
from tools.ssm06.acceptance import NEW_PINS as CONTROL
from tools.ssm06r1.acceptance import NEW_PINS as CONTROL_EXTENDED
from tools.ssm07.acceptance import NEW_PINS as LEARNED
from tools.ssm07r1.acceptance import NEW_PINS as SELECTIVE
from tools.ssm08.acceptance import NEW_PINS as SCIENTIFIC
from tools.ssm08r1.acceptance import NEW_PINS as INFERENCE
from tools.ssm09a.acceptance import NEW_PINS as INTEROP

NEW_PINS={
    'cognitum/research/ssm_research_validation.py':'eac04a2688bcea74760aebf41c3ea45f837957f1',
    'cognitum/research/ssm_scientist_bridge.py':'0525fa2a57d843677ae779d88ac8ca6872f1959f',
    'research_tests/ssm09b/test_validation.py':'7b79c9351dc320178755e2878e7d6c7c80590d6b',
    'research_tests/ssm09b/test_science_model.py':'1ed012964dad00d4668cfcb5c89acbb79d8b0d5a',
    'research_tests/ssm09b/test_native_composition.py':'97bd1ad69146cf9a95d5c60ac6609c717f000d07',
    'cognitum/research/hdc_associative.py':'42121bc738737ce3dbe3b3921d41404ceec47d73',
    'cognitum/research/hdc_algebra.py':'1b64d122fd0a34e5de3e747c4076ffaa80216284',
}

def run(prior,out):
    import numpy as np, scipy
    root=Path(prior).resolve();out=Path(out).resolve()
    head=git('rev-parse','HEAD')
    need(not os.getenv('GITHUB_SHA') or os.environ['GITHUB_SHA']==head,'source SHA')
    need(not git('status','--porcelain','--untracked-files=no'),'tracked drift')
    prev=dict(PINS,**LINEAR,**VERIFY,**DYNAMICS,**EXTENDED,**STOCHASTIC,**ADVANCED,**IDENTIFICATION,**DISCOVERY,**CONTROL,**CONTROL_EXTENDED,**LEARNED,**SELECTIVE,**SCIENTIFIC,**INFERENCE,**INTEROP);pins=dict(prev,**NEW_PINS)
    for path,blob in pins.items():need(git('rev-parse',head+':'+path)==blob,'source pin '+path)
    raw=(root/'receipt.json').read_bytes();old=json.loads(raw)
    need(old['source_sha']==head and old['status']=='PASS' and old['source_pins']==prev,'same-head SSM-09A')
    need(old['dedicated']==dict(tests=22,failures=0,errors=0,skipped=0),'predecessor inventory')
    for name,digest in old['artifacts'].items():
        p=(root/name).resolve();need(p.is_relative_to(root) and p.is_file() and sha(p.read_bytes())==digest,'prior artifact integrity')
    out.mkdir(parents=True,exist_ok=False)
    totals=run_tests(['research_tests/ssm09b'],out/'tests.xml',out/'tests.log',37)
    suites=['ssm03r1','ssm04','ssm04r1','ssm05','ssm05r1','ssm06','ssm06r1','ssm07','ssm07r1','ssm08','ssm08r1','ssm09a','ssm09b']
    consolidated=run_tests([f'research_tests/{name}' for name in suites],out/'consolidated.xml',out/'consolidated.log',391)
    r=dict(source_sha=head,status='PASS',platform=platform.platform(),python=sys.version,
        versions=dict(numpy=np.__version__,scipy=scipy.__version__),prior_ssm09a_sha256=sha(raw),
        source_pins=pins,dedicated=totals,consolidated=consolidated,all_research_scopes_complete=False,execution_authorized=False,
        artifacts={p.name:sha(p.read_bytes()) for p in sorted(out.iterdir()) if p.is_file()})
    (out/'receipt.json').write_text(json.dumps(r,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(totals)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prior',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();run(a.prior,a.out)
