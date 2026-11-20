"""MEL-07A-R1: batch amortization, polynomial derivative and tensor CPU evidence.

Real reference worker executions only. Reuse established scoped Admission,
Runtime, mathematical replay and the prior COG-04N benchmark. No host, GPU,
or permission changes. Direct timings are research controls.
"""
# Import the baseline harness first to set requested BLAS thread environment.
from tools.mel07a_cpu import resources, delta, sha, require, registry
import argparse
from dataclasses import asdict, replace
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.mel import admission as a, native as n
from cognitum.mel import polynomial_kan as p, polynomial_model as pm
from cognitum.mel import cpu_routing as routing, tensor_cooperation as tc
from cognitum.research.kan_trainable import Layer, Network
from tools.cog04n.benchmark import run as tensor_benchmark


def denied(fn):
    try:
        fn()
    except ValueError:
        return
    raise RuntimeError('expected route refusal')


def measure(fn):
    before=resources();start=time.perf_counter_ns()
    value=fn()
    elapsed=(time.perf_counter_ns()-start)/1e6
    after=resources()
    return value,{'elapsed_ms':elapsed,'cpu_delta':delta(before,after),
                  'process_high_water':after}


def byte_pair(call,rec,raw):
    require(rec.status=='completed' and len(raw)>0 and
            rec.request_sha256==sha(call.wire if isinstance(call,p.Call) else call.wire()) and
            rec.result_sha256==sha(raw) and rec.result_frame==raw,
            'request/result binding or direct-worker mismatch')


def polynomial(out):
    reg=Registry()
    reg.install(p.PolynomialPlugin,enabled=True);reg.nominate(p.OP,p.NAME)
    route=next(x for x in a.routes(include_engines=True,include_polynomial_kan=True)
               if x.operation==p.OP)
    denied(lambda:routing.select_cpu(reg,route,allow_research=True))
    denied(lambda:routing.select_cpu(reg,route,allow_research=True,
                                     allow_polynomial=True,preference='gpu'))
    denied(lambda:routing.select_cpu(reg,replace(route,descriptor_sha256='0'*64),
                                     allow_research=True,allow_polynomial=True))
    selected=routing.select_cpu(reg,route,allow_research=True,allow_polynomial=True)
    require(not selected.execution_authorized,'proposal may not authorize')
    # On [-1,1], (T0+T2)/2 = x^2; independent analytic derivatives 2x, 2.
    cp=p.export_checkpoint(Network((Layer('chebyshev',2,[[-1.,1.]],
        [[[.5,0.,.5]]],[[1.]],[0.]),)))
    approval=p.Approval(cp,'cpu-poly-review');rows=[]
    (out/'polynomial.checkpoint.pb').write_bytes(cp.wire)
    for size,points in [('small',[[.5]]),('larger',[[-1.],[-.25],[.5],[1.]])]:
        for order in (0,1,2):
            for rep in range(3):
                scope=a.Scope('poly-session','cpu','reviewer','turn')
                rid=f'poly-{size}-{order}-{rep}'
                call=p.make_call(cp,points,order,1e-6,rid,scope.turn)
                host=a.Admission(Runtime(reg),scope.session,
                    enable_engines=True,enable_polynomial_kan=True)
                try:
                    host.approve_polynomial_checkpoint(scope,cp.wire,
                        expected_sha256=cp.identity,review_id=approval.review_id)
                    token=host.issue(scope,route,p.Limits(timeout_ms=10000),
                        ttl_ms=60000,checkpoint_sha256=cp.identity)
                    plugin=p.PolynomialPlugin()
                    direct,_=measure(lambda:plugin.handle(p.OP,call.payload()))
                    direct_raw=n.decode_carrier(direct['frame'],p.MAX_RESULT)
                    samples=[];plugin.handle(p.OP,call.payload())
                    for _ in range(7):
                        start=time.perf_counter_ns()
                        frame=n.decode_carrier(plugin.handle(p.OP,call.payload())['frame'],p.MAX_RESULT)
                        samples.append((time.perf_counter_ns()-start)/1e6)
                        require(frame==direct_raw,'unstable polynomial bytes')
                    rec,timing=measure(lambda:host.execute(scope,token,rid,call.wire,timeout_ms=10000))
                    byte_pair(call,rec,direct_raw)
                    (feedback,audit),verification=measure(lambda:pm.feedback(scope,call,rec,approval,1e-6))
                    require(feedback['ok'] and audit['verdict']=='within_represented_input_tolerance',
                            'polynomial replay')
                    actual=feedback['result']['values']
                    ref=[q[0]**2 for q in points]+([2*q[0] for q in points] if order else [])+(
                        [2.]*len(points) if order==2 else [])
                    require(len(actual)==len(ref),'polynomial shape')
                    error=max(abs(x-y) for x,y in zip(actual,ref))
                    require(error<=1e-12,'analytic polynomial mismatch')
                    require(all(v['lower']<=x<=v['upper'] for v,x in zip(feedback['result']['intervals'],ref)),
                            'analytic value not enclosed')
                    (out/(rid+'.request.pb')).write_bytes(call.wire)
                    (out/(rid+'.result.pb')).write_bytes(rec.result_frame)
                    rows.append(dict(case=rid,size=size,order=order,repeat=rep,
                        components=len(ref),max_abs_error=error,request_sha256=rec.request_sha256,
                        result_sha256=rec.result_sha256,request_bytes=len(call.wire),
                        result_bytes=len(rec.result_frame),logical_work_units=p.account(call,p.Limits()),
                        direct_ms_samples=samples,direct_median_ms=statistics.median(samples),
                        admission_worker=timing,verification=verification,matched_native_bytes=True,
                        checkpoint_sha256=cp.identity,independent_replay=True))
                finally:host.close()
    require(len(rows)==18,'polynomial matrix')
    return {'selection':asdict(selected),'rows':rows}


def batching(out):
    from cognitum.mel import model_reference as r
    reg=registry();route=next(x for x in a.routes() if x.operation=='vfa.evaluate')
    selected=routing.select_cpu(reg,route,allow_research=True)
    f=n.gaussian([[0.]],[[1.]],[2.],constant=0.,axes=[('x','1')],
                 domain=[(-1.,1.)],output_unit='1')
    points=[[-.5],[0.],[.25],[.5]]
    oracle=[2*math.exp(-x[0]*x[0]/2) for x in points]
    runs=[]
    for rep in range(3):
        # Alternate arm order to reduce fixed warm/cold ordering bias.
        for arm in (('batch','serial') if rep%2==0 else ('serial','batch')):
            scope=a.Scope('batch-session','cpu','reviewer','turn')
            rt=Runtime(reg);host=a.Admission(rt,scope.session)
            try:
                chunks=[points] if arm=='batch' else [[x] for x in points]
                values=[];calls=[];start=time.perf_counter_ns();before=resources()
                for index,chunk in enumerate(chunks):
                    rid=f'{arm}-{rep}-{index}'
                    call=n.make_call(route.public_name,f,n.points(f,chunk),rid,scope.turn)
                    token=host.issue(scope,route,a.Limits(timeout_ms=10000),
                                     ttl_ms=60000)
                    rec,timing=measure(lambda:host.execute(scope,token,rid,call.wire(),timeout_ms=10000))
                    require(rec.status=='completed','batch worker not completed')
                    (feedback,audit),verify=measure(lambda:r.verified_feedback(scope,call,rec,(1e-10,)))
                    require(feedback['ok'],'batch certificate verification')
                    results=feedback['result']['values'];values.extend(results)
                    (out/(rid+'.request.pb')).write_bytes(call.wire())
                    (out/(rid+'.result.pb')).write_bytes(rec.result_frame)
                    calls.append(dict(request_sha256=audit['request_sha256'],result_sha256=audit['result_sha256'],
                                      worker=timing,verification=verify,points=len(chunk)))
                after=resources();elapsed=(time.perf_counter_ns()-start)/1e6
                require(len(values)==4 and max(abs(x-y) for x,y in zip(values,oracle))<=1e-10,
                        'batch analytic mismatch')
                require(len(rt.trace.events)==len(chunks) and all(x['execution_status']=='completed'
                        for x in rt.trace.events),'worker trace mismatch')
                runs.append(dict(repeat=rep,arm=arm,values=values,worker_calls=len(chunks),
                                 elapsed_ms=elapsed,cpu_delta=delta(before,after),
                                 process_high_water=after,calls=calls))
            finally:host.close()
    comparisons=[]
    for rep in range(3):
        b=next(x for x in runs if x['repeat']==rep and x['arm']=='batch')
        s=next(x for x in runs if x['repeat']==rep and x['arm']=='serial')
        err=max(abs(x-y) for x,y in zip(b['values'],s['values']))
        require(err<=1e-10,'batch/serial numerical drift')
        comparisons.append(dict(repeat=rep,batch_ms=b['elapsed_ms'],serial_ms=s['elapsed_ms'],
                                serial_over_batch=s['elapsed_ms']/b['elapsed_ms'],max_abs_difference=err))
    return dict(selection=asdict(selected),runs=runs,comparisons=comparisons,
                median_serial_over_batch=statistics.median(x['serial_over_batch'] for x in comparisons),
                actual_worker_calls=sum(x['worker_calls'] for x in runs))


def tensor(out):
    # Review the same factories and descriptor pair used by the established
    # COG-04N benchmark. Selection remains separate from its actual admission.
    reg=Registry()
    for op,plugin in tc.FACTORIES.items():
        manifest=reg.install(plugin,enabled=True);reg.nominate(op,manifest.name)
    selected=routing.select_tensor_cpu(reg,tc.selection(),allow_research=True)
    denied(lambda:routing.select_tensor_cpu(reg,tc.selection()))
    denied(lambda:routing.select_tensor_cpu(reg,tc.selection(),allow_research=True,preference='fpga'))
    denied(lambda:routing.select_tensor_cpu(reg,((tc.TENSOR,'0'*64),),allow_research=True))
    reg.enable(tc.TNAME,False)
    denied(lambda:routing.select_tensor_cpu(reg,tc.selection(),allow_research=True))
    reg.enable(tc.TNAME,True)
    rows,timing=measure(lambda:tensor_benchmark(out))
    require([x['stage'] for x in rows]==['J','K','L'] and
            [x['worker_calls'] for x in rows]==[5,5,6] and
            all(x['receipt_replay'] and x['oracle_difference']<=1e-10 for x in rows),
            'tensor/cooperative benchmark incomplete')
    for row in rows:
        data=json.loads((out/(row['stage']+'.receipts.json')).read_text(encoding='utf8'))
        trace=data['trace']
        require(len(trace)==row['worker_calls'] and all(x['execution_status']=='completed' for x in trace),
                'actual tensor trace')
        row['runtime_worker_latency_ms']=[x['latency_ms'] for x in trace]
        row['runtime_worker_latency_total_ms']=sum(row['runtime_worker_latency_ms'])
    return dict(selection=[asdict(x) for x in selected],rows=rows,
                total_including_fit_and_evidence=timing,actual_worker_calls=sum(x['worker_calls'] for x in rows),
                selection_is_separate_review=True)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    require(not os.getenv('GITHUB_SHA') or head==os.getenv('GITHUB_SHA'),'wrong source checkout')
    require(not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True).strip(),
            'modified tracked source')
    report=dict(profile='cognitum.mel.cpu_qualification_r1.v1',source_commit=head,
                status='OPEN',platform=platform.platform(),python=sys.version,
                notes='reference runtime only; process high-water, not tree memory; Windows child unmeasured')
    try:
        for key,fn in [('polynomial',polynomial),('batching',batching),('tensor',tensor)]:
            folder=out/key;folder.mkdir()
            report[key]=fn(folder)
        require(report['batching']['actual_worker_calls']==15 and report['tensor']['actual_worker_calls']==16,
                'missing worker executions')
        report['actual_worker_calls']=18+15+16
        report['status']='PASS'
    finally:
        report['artifact_sha256']={p.relative_to(out).as_posix():sha(p.read_bytes())
            for p in sorted(out.rglob('*')) if p.is_file() and p.name!='qualification.json'}
        (out/'qualification.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf8')


if __name__=='__main__':main()
