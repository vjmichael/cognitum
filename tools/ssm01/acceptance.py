"""Same-source SSM-01 native mathematical and inherited C17 qualification."""
import argparse, hashlib, json, os, platform, subprocess, sys
from pathlib import Path
from xml.etree import ElementTree as ET
from fractions import Fraction as Q
from cognitum.research import ssm_linear as s

ROOT=Path(__file__).resolve().parents[2]
PINS={"cognitum/proto/temporal_filter_pb2.py":"e0e654958a4f8042d1738af9f34f200b879622b5","cognitum/proto/temporal_practical_pb2.py":"c12ba98567e702063f1deb447a71ec104968bf1e","cognitum/research/ssm_recovered.py":"10a862fd6be0d0d0b3a01586d32a06873ff7b4ee","cognitum/specialists/ssm.py":"ae9329b6b0873906b3f4fd781823b6ae48407e15","cognitum/temporal_evaluation.py":"130bba8909dad509919ad92f9a682cdbf55d6343","cognitum/temporal_filter.py":"f573370602042b342818890ea7abbe0a5603e9f0","cognitum/temporal_hidden.py":"03be1e4d25e894c2a2db1c7a98653f04618944b2","cognitum/temporal_learned.py":"68714ee6394c089e838f9c6ff426afd781f847b8","cognitum/temporal_learned_wire.py":"3b37fc11e63a6327f99180f0c85b9860f44f13eb","cognitum/temporal_practical_wire.py":"2548b42220994511a87117f6b2a0dd468dcf2ca1","cognitum/temporal_statespace.py":"29ad2f036abd14a8dabc9be5469a430a374c765a","proto/cognitum/temporal/v1/filter.proto":"222b9c17c4569c897cedd82a728ec860e1fa0547","proto/cognitum/temporal/v1/practical.proto":"b135ea002eff725d635c8e4bba76db16721d0f6f","tests/test_c17_heldout.py":"4ad6c983ecf9673cdfcc4b95f766bf0012010069","tests/test_c17_learned_wire.py":"8aee0e3d0cf4e3ef92b8763d3be324054d1c911d","tests/test_c17_practical.py":"b2e829e249a9638b33245601a9944fe8dac7f414","tests/test_c17_practical_wire.py":"ca96ee0d127c64ac8e2b5fd24a1f60d760a166ba","tests/test_c17_real_temporal.py":"d9b24c757a5f65d4cc7f7ef1a60addce311d0206","tests/test_c17_reference_filter.py":"b836c9fe98a98e89cd0d230182cfba4a84e42970","tests/test_cog00_ssm_alias.py":"0c37abb71cd4bf1284bd95835bbf0a1befdd5abf","tests/test_hdc_kan_ssm_recovery.py":"28a66e57d9c72706a3b47601da6c00e3a4f87aa1","tests/test_ssm_state_resume_p1.py":"16f397755c146d4ceb002777281112a39a37eb70","tools/c17_real_temporal_acceptance.py":"de3b315c8dcdb6505781e49c66fdf58ef62a2eaf","tools/c17_temporal_benchmark.py":"02ff15648b58cedccf27d27af5f8154cc9ac6be1","tools/verify_c17_proto.py":"44ec9b72490c2aa0f32ea4896bd7797614741e50"}
TESTS=["tests/test_c17_heldout.py","tests/test_c17_learned_wire.py","tests/test_c17_practical.py","tests/test_c17_practical_wire.py","tests/test_c17_real_temporal.py","tests/test_c17_reference_filter.py","tests/test_cog00_ssm_alias.py","tests/test_hdc_kan_ssm_recovery.py","tests/test_ssm_state_resume_p1.py"]
def need(ok,msg):
    if not ok: raise ValueError(msg)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def run_tests(paths,xml,log,expected=None):
    p=subprocess.run([sys.executable,'-m','pytest','-q',*paths,'--junitxml',str(xml)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
    log.write_text(p.stdout+'\n'+p.stderr,encoding='utf-8')
    need(p.returncode==0,'test failure: '+str(xml))
    totals={k:sum(int(x.get(k,0)) for x in ET.parse(xml).getroot().iter('testsuite')) for k in ('tests','failures','errors','skipped')}
    need(totals['tests']>0 and not any(totals[k] for k in ('failures','errors','skipped')),'unqualified tests')
    if expected is not None:need(totals['tests']==expected,'dedicated test inventory')
    return totals
def run(prior,out):
    import numpy as np, scipy, mpmath as mp, sklearn
    root=Path(prior).resolve();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    head=git('rev-parse','HEAD');need(not os.getenv('GITHUB_SHA') or os.environ['GITHUB_SHA']==head,'source SHA');need(not git('status','--porcelain','--untracked-files=no'),'tracked drift')
    for path,blob in PINS.items():need(git('rev-parse',head+':'+path)==blob,'inherited source drift '+path)
    oldraw=(root/'receipt.json').read_bytes();old=json.loads(oldraw)
    need(old['source_sha']==head and old['status']=='PASS' and len(old['held_out'])==27 and len(old['historic'])==24,'same-head COG-05C prerequisite')
    for name,digest in old['artifacts'].items():
        p=(root/name).resolve();need(p.is_relative_to(root) and p.is_file() and sha(p.read_bytes())==digest,'prior artifact integrity')
    dedicated=run_tests(['research_tests/ssm01/test_linear.py'],out/'dedicated.xml',out/'dedicated.log',17)
    legacy=run_tests(TESTS,out/'legacy.xml',out/'legacy.log')
    rows=[]
    for n in (1,2,3,5,8):
        a=tuple(tuple(Q((i*3+j*5+1)%7-3,4) for j in range(n)) for i in range(n))
        b=tuple((Q(i+1,8),Q(-i,8)) for i in range(n));c=(tuple(Q(1,n) for _ in range(n)),);d=((Q(1,3),Q(0)),)
        m=s.Model(a,b,c,d,('x',)*n,('u','u'),('y',));x=tuple(Q(i,8) for i in range(n));us=tuple((Q(k,16),Q(-k,16)) for k in range(1,13))
        start=s.state(m,x);end,ys,raw=s.scan(m,start,us);need(s.replay(m,start,us,raw),'exact replay')
        # Literal scalar recurrence, independent of candidate matrix operators.
        ref=x;outputs=[]
        for u in us:
            outputs.append(tuple(sum((v*w for v,w in zip(row,ref)),Q(0))+sum((v*w for v,w in zip(feed,u)),Q(0)) for row,feed in zip(m.c,m.d)))
            ref=tuple(sum((v*w for v,w in zip(row,ref)),Q(0))+sum((v*w for v,w in zip(force,u)),Q(0)) for row,force in zip(m.a,m.b))
        need(end.x==ref and ys==tuple(outputs),'independent exact rollout')
        name=f'exact-{n}.json';(out/name).write_bytes(raw);rows.append(dict(dimension=n,steps=12,receipt=name,sha256=sha(raw)))
    result=dict(source_sha=head,status='PASS',platform=platform.platform(),python=sys.version,versions=dict(numpy=np.__version__,scipy=scipy.__version__,mpmath=mp.__version__,sklearn=sklearn.__version__),prior_cog05c_sha256=sha(oldraw),source_pins=PINS,dedicated=dedicated,legacy=legacy,exact_cases=rows,certified_continuous_bounds=False,execution_authorized=False,artifacts={p.name:sha(p.read_bytes()) for p in sorted(out.iterdir()) if p.is_file()})
    (out/'receipt.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(dedicated=dedicated,legacy=legacy,exact=len(rows))))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prior',required=True);p.add_argument('--out',required=True);a=p.parse_args();run(a.prior,a.out)
