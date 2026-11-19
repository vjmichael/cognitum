"""Strict full-tree hosted gate; no substitutions for missing checkpoint runtime."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
import numpy as np
from cognitum.research import kan_differential_learning as s
from tools.cog04i.benchmark import run
from tools.cog04a.acceptance import check

ROOT=Path(__file__).resolve().parents[2]
EXPECTED=dict(tests=53,failures=0,errors=0,skipped=0)


def require(ok,message):
    if not ok:raise RuntimeError(message)


def checkpoint_gate(out):
    from cognitum.contracts import Response
    from cognitum.mel import polynomial_kan as pk, admission as a, model_reference as r, polynomial_model as pm
    p=s.Problem('ivp',4,(0,),1);f=s.fit(p,.031);cp=pk.export_checkpoint(f.model)
    model=cp.model();require(model.research_snapshot()==f.model.research_snapshot(),'checkpoint not lossless')
    s.require_accuracy(p,model,f.certificate,.031)
    pts=[[.0625],[.3125],[.625],[.9375]]
    scope=a.Scope('cog04i','lab','owner','ode-solution');app=pk.Approval(cp,'ode-solution-review')
    with r.ReferenceTurn(scope,r.Allowed((pk.OP,),tolerance=1e-8,polynomial_approval=app)) as turn:
        feedback=turn.dispatch(r.canonical(dict(tool=pm.PUBLIC,arguments={'points':pts,'order':2})))
        require(feedback['ok'],'actual MEL worker failed: '+str(feedback))
        request=turn.last_call.wire;result=turn.last_receipt.result_frame
    call=pk.Call(pk.OP,request);q=call.message
    require(pk.serialize(q.checkpoint)==cp.wire,'request checkpoint binding')
    response=Response(q.request_id,q.correlation_id,pk.OP,'completed',module={'name':pk.NAME,'version':pk.VERSION},result={'frame':pk.encode_carrier(result,pk.MAX_RESULT)},assurance='numerical')
    require(pk.checked_result(call,response)==result,'receipt replay failed')
    v=np.concatenate([a.ravel() for a in model.evaluate(pts,2)])
    require(np.max(np.abs(v-feedback['result']['values']))<=1e-8,'worker numerical differential mismatch')
    for n,raw in [('solution.checkpoint.pb',cp.wire),('solution.request.pb',request),('solution.result.pb',result)]:
        (out/n).write_bytes(raw)
    return cp.identity


def main(out):
    os.chdir(ROOT);out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    hosted=os.getenv('GITHUB_ACTIONS')=='true';head=None
    manifest=json.loads((ROOT/'docs/research/cog04i/manifest.json').read_text(encoding='utf8'))
    if hosted:
        head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();require(os.getenv('COG03BC_EXPECTED_SHA')==head,'wrong checkout')
        prior=json.loads((out.parent/'cog04h'/'receipt.json').read_text(encoding='utf8'))
        require(prior['source_sha']==head and prior['totals']==dict(tests=37,failures=0,errors=0,skipped=0) and prior['hosted_predecessor_checked'] is True and prior['checkpoint_replay_verified'] is True and prior['production_enabled'] is False,'missing same-head H acceptance')
    check(manifest,head=head)
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1');xml=out/'tests.xml'
    with (out/'tests.log').open('w',encoding='utf8') as log:
        subprocess.run([sys.executable,'-m','pytest','-q','research_tests/cog04i','--junitxml',str(xml)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180,check=True)
    totals={k:sum(int(t.get(k,0)) for t in ET.parse(xml).getroot().findall('.//testsuite')) for k in EXPECTED};require(totals==EXPECTED,str(totals))
    benchmarks=run(out/'benchmark');require(len(benchmarks)==3 and all(v['accepted'] and v['conditions_exact'] for v in benchmarks),'incomplete benchmark')
    checkpoint=checkpoint_gate(out);check(manifest,head=head)
    artifacts={a.relative_to(out).as_posix():hashlib.sha256(a.read_bytes()).hexdigest() for a in sorted(out.rglob('*')) if a.is_file() and not a.is_symlink() and a.name!='receipt.json'}
    (out/'receipt.json').write_text(json.dumps(dict(source_sha=head,reference_parent=manifest['base'],totals=totals,source_pins=len(manifest['git_blobs']),hosted_predecessor_checked=hosted,actual_worker_calls=1,checkpoint_sha256=checkpoint,checkpoint_replay_verified=True,certified_full_domain_error=True,hard_conditions=True,profile='scalar-stable-linear-unit-interval',production_enabled=False,native_lu_accepted=False,artifacts=artifacts),indent=2)+'\n',encoding='utf8')
    print(totals,'adaptive residual-trained KAN, continuous certificate and actual MEL worker')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);main(p.parse_args().out)
