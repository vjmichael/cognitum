"""MEL-07A-R2: bounded in-request batching and opt-in actual worker telemetry.

No automatic inter-request batching: each arm uses a single reviewed scope,
checkpoint, route and independent trusted grant for each existing typed call.
"""
from tools.mel07a_cpu import registry, require, sha, scalar_oracle, fidelity
import argparse,json,math,os,statistics,sys,time,subprocess,platform
from pathlib import Path
from cognitum.worker_metrics import observe_one
from cognitum.runtime import Runtime
from cognitum.mel import admission as a,native as n,engines as e,engines_pb2 as ep
from cognitum.mel import model_engines as m,model_reference as r
from cognitum.mel import polynomial_kan as p,polynomial_model as pm
from cognitum.mel.engine_limits import HdcLimits,KanLimits
from cognitum.research.kan_trainable import Layer,Network


def config():
    reg=registry()
    reg.install(p.PolynomialPlugin,enabled=True);reg.nominate(p.OP,p.NAME)
    legacy=m.Approval(m.Checkpoint(m.checkpoint_wire([ep.KanLayer(
        inputs=1,outputs=1,knots=3,basis=ep.RBF,grid=[-1.,0.,1.],
        coefficients=[0.,2.,0.],mask=[1.])])),'batch-review')
    poly=p.Approval(p.export_checkpoint(Network((Layer('chebyshev',2,
        [[-1.,1.]],[[[.5,0.,.5]]],[[1.]],[0.]),))),'poly-review')
    return reg,legacy,poly


def cases():
    for op in ('vfa.evaluate','vfa.gradient','kan.evaluate'):
        for count in (2,8,16):
            yield op,count
    for count in (2,4):yield p.OP,count
    for count in (2,8):yield 'hdc.query',count


def prepare(op,items,route,rid,scope,legacy,poly):
    if op in n.OP:
        f=n.gaussian([[0.]],[[1.]],[2.],constant=0.,axes=[('x','1')],
                     domain=[(-1.,1.)],output_unit='1')
        c=n.make_call(route.public_name,f,n.points(f,items),rid,scope.turn)
        return c,c.wire(),a.Limits(timeout_ms=10000),{},None,1e-10
    if op==p.OP:
        c=p.make_call(poly.checkpoint,items,2,1e-6,rid,scope.turn)
        return c,c.wire,p.Limits(timeout_ms=10000),{'checkpoint_sha256':poly.checkpoint.identity},poly,1e-6
    if op=='kan.evaluate':
        c=m.bind(op,legacy,r.canonical({'points':items}),rid,scope.turn)
        return c,c.wire,KanLimits(timeout_ms=10000),dict(model_codec=True,checkpoint_sha256=legacy.checkpoint.identity),legacy,1e-5
    c=m.bind(op,None,r.canonical({'probe':'10110010'*8,'candidates':items}),rid,scope.turn)
    return c,c.wire,HdcLimits(timeout_ms=10000),{'model_codec':True},None,0.


def values(op,items):
    if op=='hdc.query':
        probe='10110010'*8
        return [sum(x!=y for x,y in zip(probe,v)) for v in items]
    if op=='vfa.evaluate':return [2*math.exp(-x[0]**2/2) for x in items]
    if op=='vfa.gradient':return [-2*x[0]*math.exp(-x[0]**2/2) for x in items]
    if op=='kan.evaluate':return [2*math.exp(-x[0]**2) for x in items]
    return [[x[0]**2,2*x[0],2.] for x in items]


def arm(reg,legacy,poly,op,count,rep,kind,out):
    route=next(x for x in a.routes(include_engines=True,include_polynomial_kan=True) if x.operation==op)
    scope=a.Scope('batch-cpu','reviewed','owner','turn')
    rt=Runtime(reg);host=a.Admission(rt,scope.session,enable_engines=True,
        enable_model_codecs=True,enable_polynomial_kan=True)
    try:
        if op=='kan.evaluate':
            host.approve_checkpoint(scope,legacy.checkpoint.wire,
                expected_sha256=legacy.checkpoint.identity,review_id=legacy.review_id)
        if op==p.OP:
            host.approve_polynomial_checkpoint(scope,poly.checkpoint.wire,
                expected_sha256=poly.checkpoint.identity,review_id=poly.review_id)
        items=([('10110010'*8 if i%3==0 else '01011100'*8 if i%3==1 else '0'*64)
                for i in range(count)] if op=='hdc.query' else [[(i-8)/16] for i in range(count)])
        chunks=[items] if kind=='batch' else [[v] for v in items]
        all_values=[];rows=[];files=[];begin=time.perf_counter_ns()
        for i,chunk in enumerate(chunks):
            rid=f'{op.replace(".","-")}-{count}-{rep}-{kind}-{i}'
            call,wire,limits,kw,approval,tol=prepare(op,chunk,route,rid,scope,legacy,poly)
            token=host.issue(scope,route,limits,ttl_ms=60000,**kw)
            rec,metrics=observe_one(lambda:host.execute(scope,token,rid,wire,timeout_ms=10000))
            require(rec.status=='completed' and rec.request_sha256==sha(wire) and
                    rec.result_sha256==sha(rec.result_frame),'worker receipt')
            require(metrics['status']=='measured' and metrics['observed_workers']==1
                    and metrics['samples']>0 and metrics['peak_resident_bytes_observed']>0
                    and metrics['cpu_seconds']>=0 and metrics['cpu_final']==(sys.platform=='win32'),
                    'native per-worker counters missing')
            start=time.perf_counter_ns()
            feedback,audit=r.verified_feedback(scope,call,rec,(tol,),approval)
            verify_ms=(time.perf_counter_ns()-start)/1e6
            require(feedback['ok'],'independent verification')
            result=feedback['result']
            if op=='hdc.query':
                found=result['hamming_distance']
                require(result['best_index']==[j for j,v in enumerate(found) if v==min(found)],'tie ranking')
            elif op==p.OP:
                flat=result['values'];k=len(chunk)
                require(len(flat)==3*k,'polynomial component count')
                found=[list(v) for v in zip(flat[:k],flat[k:2*k],flat[2*k:])]
            else:found=result['values']
            require(len(found)==len(chunk),'result shape')
            all_values.extend(found)
            files.append((rid,wire,rec.result_frame))
            rows.append({'request_sha256':rec.request_sha256,'result_sha256':rec.result_sha256,
                         'request_bytes':len(wire),'result_bytes':len(rec.result_frame),
                         'verification_ms':verify_ms,'telemetry':metrics})
        elapsed=(time.perf_counter_ns()-begin)/1e6
        expected=values(op,items)
        if op==p.OP:errors=[abs(x-y) for u,v in zip(all_values,expected) for x,y in zip(u,v)]
        else:errors=[abs(x-y) for x,y in zip(all_values,expected)]
        tolerance=1e-5 if op=='kan.evaluate' else 1e-10 if op in n.OP else 0
        require(max(errors)<=tolerance,'analytic oracle mismatch')
        require(len(rt.trace.events)==len(chunks) and all(x['execution_status']=='completed' for x in rt.trace.events),'runtime trace')
        for rid,wire,raw in files:
            (out/(rid+'.request.pb')).write_bytes(wire)
            (out/(rid+'.result.pb')).write_bytes(raw)
        return dict(operation=op,count=count,repeat=rep,arm=kind,values=all_values,
                    elapsed_ms=elapsed,worker_calls=len(rows),max_abs_error=max(errors),
                    total_observed_worker_cpu_s=sum(x['telemetry']['cpu_seconds'] for x in rows),
                    largest_observed_worker_peak_bytes=max(x['telemetry']['peak_resident_bytes_observed'] for x in rows),calls=rows)
    finally:host.close()


def refusals(reg,legacy,poly):
    route=next(x for x in a.routes() if x.operation=='vfa.evaluate')
    scope=a.Scope('refusal','reviewed','owner','turn')
    host=a.Admission(Runtime(reg),scope.session)
    try:
        c,raw,_,_,_,_=prepare(route.operation,[[0.],[.5]],route,'over-budget',scope,legacy,poly)
        token=host.issue(scope,route,a.Limits(points=1,timeout_ms=10000),ttl_ms=60000)
        rec,met=observe_one(lambda:host.execute(scope,token,'over-budget',raw,timeout_ms=10000))
        require(rec.status=='resource_denied' and rec.result_frame is None and
                met['status']=='unavailable' and met['observed_workers']==0,'budget denial spawned child')
        other=a.Scope(scope.session,'different','owner','turn')
        try:host.execute(other,token,'over-budget',raw,timeout_ms=10000)
        except ValueError:pass
        else:raise RuntimeError('cross-scope grant not refused')
        require(not host._runtime.trace.events,'denied request dispatched')
        return ['oversized_for_grant_no_worker','cross_scope_denied']
    finally:host.close()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    require(not os.getenv('GITHUB_SHA') or head==os.getenv('GITHUB_SHA'),'wrong source checkout')
    report=dict(status='OPEN',source_commit=head,profile='mel07a-r2.v1',platform=platform.platform(),
                python=sys.version,rows=[],comparisons=[],memory='largest observed single child, not whole tree')
    try:
        reg,legacy,poly=config();report['refusals']=refusals(reg,legacy,poly)
        for op,count in cases():
            for rep in range(2):
                pair={}
                for kind in (('batch','serial') if rep==0 else ('serial','batch')):
                    pair[kind]=arm(reg,legacy,poly,op,count,rep,kind,out);report['rows'].append(pair[kind])
                b,s=pair['batch'],pair['serial']
                av,bv=b['values'],s['values']
                diff=max((abs(x-y) for u,v in zip(av,bv) for x,y in zip(u,v)) if op==p.OP else
                         (abs(x-y) for x,y in zip(av,bv)))
                require(diff<=(1e-5 if op=='kan.evaluate' else 1e-10 if op in n.OP else 0),'batch serial drift')
                report['comparisons'].append(dict(operation=op,count=count,repeat=rep,
                    batch_ms=b['elapsed_ms'],serial_ms=s['elapsed_ms'],
                    speedup=s['elapsed_ms']/b['elapsed_ms'],max_abs_difference=diff))
        report['actual_worker_calls']=sum(x['worker_calls'] for x in report['rows'])
        require(len(report['comparisons'])==26 and report['actual_worker_calls']==214,'incomplete sweep')
        report['status']='PASS'
    finally:
        report['artifact_sha256']={f.name:sha(f.read_bytes()) for f in sorted(out.glob('*.pb'))}
        (out/'qualification.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf8')


if __name__=='__main__':main()
