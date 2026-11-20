"""MEL-07A-R3 fresh same-head R2 calibration and held-out partition qualification."""
from tools.mel07a_r2 import config,prepare,values,cases
from tools.mel07a_cpu import require,sha
from cognitum.mel import cpu_batching as b, admission as a, native as n
from cognitum.mel import polynomial_kan as p,model_reference as r,engines as e
from cognitum.runtime import Runtime
from cognitum.worker_metrics import observe_one
from dataclasses import replace,asdict
import argparse,hashlib,json,math,os,platform,statistics,subprocess,sys,time
from pathlib import Path


def refuse(fn):
    try:fn()
    except ValueError:return
    raise RuntimeError('expected refusal')


def calibrate(report,report_digest,op,key,head,folder):
    """Trusted benchmark ingestion only; use observed maxima + 25% margin.

    Singleton estimates use worst per-worker latency+verification or amortized
    serial total, whichever is greater. Other sizes use full observed arm
    duration. No percentile/confidence or hard resource bound is claimed.
    """
    require(report['status']=='PASS' and report['source_commit']==head
            and report['profile']=='mel07a-r2.v1' and report['actual_worker_calls']==214
            and len(report['rows'])==52 and len(report['comparisons'])==26
            and report['platform']==platform.platform() and report['python']==sys.version,
            'unqualified calibration')
    rows=[x for x in report['rows'] if x['operation']==op]
    obs=[]
    for size in b.SIZES[op]:
        selected=[x for x in rows if x['arm']==('serial' if size==1 else 'batch')
                  and (size==1 or x['count']==size)]
        require(len(selected)==(2*(len(b.SIZES[op])-1) if size==1 else 2),'incomplete calibration size')
        times=[];cpus=[];peaks=[]
        for row in selected:
            require(row['worker_calls']==len(row['calls'])==(row['count'] if size==1 else 1),'calibration worker count')
            times.append(row['elapsed_ms']/len(row['calls']))
            for index,c in enumerate(row['calls']):
                rid=f'{op.replace(chr(46),chr(45))}-{row["count"]}-{row["repeat"]}-{row["arm"]}-{index}'
                material=(folder/(rid+'.request.pb')).read_bytes()
                result=(folder/(rid+'.result.pb')).read_bytes()
                require(len(material)==c['request_bytes'] and sha(material)==c['request_sha256']
                        and len(result)==c['result_bytes'] and sha(result)==c['result_sha256'],
                        'calibration wire hash or size mismatch')
                typed=n.decode_request(material,op) if op in n.OP else p.Call(op,material) if op==p.OP else e.Call(op,material)
                actual_key,actual_count,actual_id,_,_=b.describe(typed)
                require(actual_key==key and actual_count==size and actual_id==rid,'calibration workload mismatch')
                q=c['telemetry']
                require(q['status']=='measured' and q['observed_workers']==1 and q['samples']>0
                        and q['cpu_final']==(sys.platform=='win32')
                        and q['peak_resident_bytes_observed']>0 and q['cpu_seconds']>=0,
                        'invalid calibration telemetry')
                times.append(q['observed_call_ms']+c['verification_ms'])
                cpus.append(q['cpu_seconds']);peaks.append(q['peak_resident_bytes_observed'])
        obs.append(b.Estimate(size,max(times)*1.25,max(cpus)*1.25,math.ceil(max(peaks)*1.25)))
    return b.Calibration(op,key,report_digest,head,platform.platform()+' '+sys.version.split()[0],tuple(obs))


def full_budget(limits):
    return b.Budget(16*limits.request_bytes,16*limits.result_bytes,120000.,120.,1<<40)


def execute(reg,scope,route,parts,limits,approval,out,label):
    rt=Runtime(reg);host=a.Admission(rt,scope.session,enable_engines=True,
        enable_model_codecs=True,enable_polynomial_kan=True)
    op=route.operation
    try:
        kw={}
        if op=='kan.evaluate':
            host.approve_checkpoint(scope,approval.checkpoint.wire,expected_sha256=approval.checkpoint.identity,review_id=approval.review_id)
            kw=dict(model_codec=True,checkpoint_sha256=approval.checkpoint.identity)
        elif op==p.OP:
            host.approve_polynomial_checkpoint(scope,approval.checkpoint.wire,expected_sha256=approval.checkpoint.identity,review_id=approval.review_id)
            kw=dict(checkpoint_sha256=approval.checkpoint.identity)
        elif op=='hdc.query':kw=dict(model_codec=True)
        # Exactly one existing grant budget shared by the entire partition.
        token=host.issue(scope,route,limits,ttl_ms=60000,**kw)
        observed=[];rows=[];start=time.perf_counter_ns()
        for part in parts:
            call=part.request
            _,count,rid,turn,_=b.describe(call);raw=b.wire(call)
            require(b.digest(raw)==part.request_sha256 and count==part.stop-part.start and turn==scope.turn,'child identity drift')
            rec,metrics=observe_one(lambda:host.execute(scope,token,rid,raw,timeout_ms=limits.timeout_ms))
            require(rec.status=='completed' and rec.request_sha256==part.request_sha256
                    and rec.result_sha256==sha(rec.result_frame),'partition admission failed')
            require(metrics['status']=='measured' and metrics['observed_workers']==1,'measurement missing')
            tol=1e-6 if op==p.OP else 1e-5 if op=='kan.evaluate' else 0. if op=='hdc.query' else 1e-10
            before=time.perf_counter_ns()
            feedback,audit=r.verified_feedback(scope,call,rec,(tol,),approval)
            verify_ms=(time.perf_counter_ns()-before)/1e6
            require(feedback['ok'],'verification refused')
            result=feedback['result']
            if op=='hdc.query':
                v=result['hamming_distance']
                require(result['best_index']==[i for i,x in enumerate(v) if x==min(v)],'chunk tie mismatch')
            elif op==p.OP:
                v=result['values'];require(len(v)==3*count,'polynomial layout')
                v=[list(z) for z in zip(v[:count],v[count:2*count],v[2*count:])]
            else:v=result['values']
            require(len(v)==count,'result length');observed.extend(v)
            rows.append(dict(start=part.start,stop=part.stop,work=part.work,request_sha256=rec.request_sha256,
                result_sha256=rec.result_sha256,metrics=metrics,verification_ms=verify_ms))
            (out/(label+'-'+str(part.start)+'.request.pb')).write_bytes(raw)
            (out/(label+'-'+str(part.start)+'.result.pb')).write_bytes(rec.result_frame)
        elapsed=(time.perf_counter_ns()-start)/1e6
        require(len(rt.trace.events)==len(parts) and all(x['execution_status']=='completed' for x in rt.trace.events),'trace mismatch')
        return dict(values=observed,elapsed_ms=elapsed,calls=rows,
            cpu_seconds=sum(x['metrics']['cpu_seconds'] for x in rows),
            largest_observed_worker_peak_bytes=max(x['metrics']['peak_resident_bytes_observed'] for x in rows),
            global_ties=[i for i,x in enumerate(observed) if x==min(observed)] if op=='hdc.query' else [])
    finally:host.close()


def controls():
    reg,legacy,poly=config();scope=a.Scope('r3-controls','w','u','turn')
    route=next(x for x in a.routes() if x.operation=='vfa.evaluate')
    parent,_,limits,_,_,_=prepare(route.operation,[[0.],[.5]],route,'control',scope,legacy,poly)
    limits=replace(limits,calls=2)
    key,*_=b.describe(parent)
    cal=b.Calibration(route.operation,key,'f'*64,'a'*40,'synthetic-policy-unit-test',
        tuple(b.Estimate(k,100.+k,.1,1000*k) for k in b.SIZES[route.operation]))
    opt=dict(allow_research=True)
    budget=full_budget(limits)
    plan=b.plan_cpu(reg,scope,route,parent,limits,budget,cal,**opt)
    require(len(plan.parts)==1 and not plan.execution_authorized,'default measured partition')
    small=b.plan_cpu(reg,scope,route,parent,replace(limits,points=1),budget,cal,**opt)
    require([q.stop-q.start for q in small.parts]==[1,1],'hard points limit not enforced')
    mem=b.plan_cpu(reg,scope,route,parent,limits,replace(budget,estimated_peak_bytes=1000),cal,**opt)
    require(len(mem.parts)==2,'estimated peak adaptation')
    refuse(lambda:b.plan_cpu(reg,scope,route,parent,limits,budget,cal))
    refuse(lambda:b.plan_cpu(reg,scope,route,parent,limits,budget,cal,preference='gpu',**opt))
    refuse(lambda:b.plan_cpu(reg,replace(scope,turn='other'),route,parent,limits,budget,cal,**opt))
    refuse(lambda:b.plan_cpu(reg,scope,route,parent,limits,budget,replace(cal,workload_key='0'*64),**opt))
    refuse(lambda:b.plan_cpu(reg,scope,route,parent,replace(limits,points=1,calls=1),budget,cal,**opt))
    refuse(lambda:b.plan_cpu(reg,scope,route,parent,replace(limits,work=1),budget,cal,**opt))
    refuse(lambda:b.plan_cpu(reg,scope,route,parent,replace(limits,request_bytes=1),budget,cal,**opt))
    refuse(lambda:b.plan_cpu(reg,scope,route,parent,limits,replace(budget,total_result_reserve_bytes=1),cal,**opt))
    refuse(lambda:b.plan_cpu(reg,scope,route,parent,limits,replace(budget,estimated_elapsed_ms=1.),cal,**opt))
    refuse(lambda:b.plan_cpu(reg,scope,route,parent,limits,replace(budget,estimated_cpu_s=0.),cal,**opt))
    refuse(lambda:b.plan_cpu(reg,scope,route,parent,limits,replace(budget,estimated_peak_bytes=1),cal,**opt))
    require(plan.parts[0].request.request_id!=parent.request_id,'request identity reuse')
    cap=b.plan_cpu(reg,scope,route,parent,limits,replace(budget,max_items_per_call=1),cal,**opt)
    require(len(cap.parts)==2,'explicit planning cap')
    require(plan==b.plan_cpu(reg,scope,route,parent,limits,budget,cal,**opt),'nondeterministic selection')
    return 17


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--calibration',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    require(not os.getenv('GITHUB_SHA') or head==os.getenv('GITHUB_SHA'),'wrong source')
    require(not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True).strip(),'modified tracked source')
    raw=args.calibration.read_bytes();prior=json.loads(raw);source_digest=sha(raw)
    folder=args.calibration.resolve().parent
    manifests=prior['artifact_sha256']
    require(type(manifests) is dict and len(manifests)==428 and set(manifests)=={f.name for f in folder.glob('*.pb')},'calibration manifest coverage')
    for file,digest in manifests.items():
        require(Path(file).name==file and sha((folder/file).read_bytes())==digest,'calibration manifest hash mismatch')
    report=dict(status='OPEN',profile='mel07a-r3.v1',source_commit=head,
        calibration_sha256=source_digest,platform=platform.platform(),python=sys.version,rows=[])
    try:
        report['control_count']=controls()
        reg,legacy,poly=config()
        for op,count in [('vfa.evaluate',13),('vfa.gradient',11),('kan.evaluate',15),(p.OP,3),('hdc.query',7)]:
            route=next(x for x in a.routes(include_engines=True,include_polynomial_kan=True) if x.operation==op)
            scope=a.Scope('r3-session','reviewed','owner','turn')
            # Held-out represented coordinates and altered candidate ordering.
            items=([('0'*64 if i%3==0 else '10110010'*8 if i%3==1 else '1'*64)
                    for i in range(count)] if op=='hdc.query' else [[(2*i+1-count)/16] for i in range(count)])
            parent,_,limits,_,approval,_=prepare(op,items,route,'heldout',scope,legacy,poly)
            limits=replace(limits,calls=16)
            key,*_=b.describe(parent);cal=calibrate(prior,source_digest,op,key,head,folder)
            budget=full_budget(limits);options=dict(allow_research=True,allow_polynomial=op==p.OP)
            # Pick the measured adaptive partition, a constrained partition
            # (max 2 items per worker), and a singleton fixed control. All
            # are the SAME original request and independently granted.
            field='points' if op in n.OP else 'rows' if op=='kan.evaluate' else 'candidates' if op=='hdc.query' else None
            constrained=replace(limits,**{field:2}) if field else limits
            fixed=replace(limits,**{field:1}) if field else limits
            adaptive=b.plan_cpu(reg,scope,route,parent,limits,budget,cal,**options)
            # The planning cap is explicit even where polynomial's native
            # Limits type has no per-call row field; actual grants still apply.
            def fixed_plan(grain):
                parts=[]
                for start in range(0,count,grain):
                    stop=min(start+grain,count)
                    child=b._slice(parent,start,stop,'fixed-'+str(grain)+':b'+str(start)+'-'+str(stop))
                    raw=b.wire(child);work=b._work(child,limits)
                    require(work is not None and len(raw)<=limits.request_bytes,'fixed control budget')
                    est=next(x for x in cal.estimates if x.count==stop-start)
                    parts.append(b.Part(start,stop,child,sha(raw),work,len(raw),limits.result_bytes,est))
                require(sum(x.work for x in parts)<=limits.work and len(parts)<=limits.calls,'aggregate fixed control')
                return tuple(parts)
            constrained_parts=b.plan_cpu(reg,scope,route,parent,constrained,
                    replace(budget,max_items_per_call=2),cal,**options).parts
            require(all(q.stop-q.start<=2 for q in constrained_parts),'constrained planner cap')
            serial=fixed_plan(1)
            label=op.replace('.','-')
            matched={}
            for tag,parts,cap in [('adaptive',adaptive.parts,limits),('constrained',constrained_parts,constrained),('serial',serial,fixed)]:
                rec=execute(reg,scope,route,parts,cap,approval,out,label+'-'+tag)
                rec['partition']=[x.stop-x.start for x in parts]
                matched[tag]=rec
            oracle=values(op,items)
            # Existing R2 HDC oracle uses identical probe; numeric oracle
            # computes all components independent of partition selection.
            for rec in matched.values():
                x,y=rec['values'],oracle
                require(len(x)==len(y)==count,'aggregate layout')
                err=max((abs(v-w) for q,z in zip(x,y) for v,w in zip(q,z)) if op==p.OP else (abs(v-w) for v,w in zip(x,y)))
                require(err<=(1e-5 if op=='kan.evaluate' else 1e-10 if op in n.OP else 0.),'held-out analytic oracle')
                rec['max_abs_error']=err
                if op=='hdc.query':require(rec['global_ties']==[i for i,v in enumerate(oracle) if v==min(oracle)],'global tie reconstruction')
            # Compare every returned component; no performance threshold.
            for other in ('constrained','serial'):
                x,y=matched['adaptive']['values'],matched[other]['values']
                err=max((abs(v-w) for q,z in zip(x,y) for v,w in zip(q,z)) if op==p.OP else (abs(v-w) for v,w in zip(x,y)))
                require(err<=(1e-5 if op=='kan.evaluate' else 1e-10 if op in n.OP else 0.),'partition numerical drift')
            rec=matched['adaptive']
            rec['estimate_comparison']=dict(elapsed_actual_minus_estimated_ms=rec['elapsed_ms']-adaptive.estimated_elapsed_ms,
                observed_cpu_minus_estimated_s=rec['cpu_seconds']-adaptive.estimated_cpu_s,
                observed_peak_minus_estimated_bytes=rec['largest_observed_worker_peak_bytes']-adaptive.estimated_peak_bytes)
            report['rows'].append(dict(operation=op,count=count,profile=asdict(cal),
                parent_sha256=adaptive.parent_sha256,estimated_elapsed_ms=adaptive.estimated_elapsed_ms,
                estimated_cpu_s=adaptive.estimated_cpu_s,estimated_peak_bytes=adaptive.estimated_peak_bytes,
                reserved_work=adaptive.total_work,reserved_request_bytes=adaptive.total_request_bytes,
                reserved_result_bytes=adaptive.total_result_reserve_bytes,arms=matched))
        require(len(report['rows'])==5,'incomplete held-out matrix')
        report['actual_worker_calls']=sum(len(a['calls']) for z in report['rows'] for a in z['arms'].values())
        report['status']='PASS'
    finally:
        report['artifact_sha256']={f.name:sha(f.read_bytes()) for f in sorted(out.glob('*.pb'))}
        (out/'qualification.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')


if __name__=='__main__':main()
