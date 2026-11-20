"""MEL-07A scoped CPU worker benchmark; genuine reference paths, not Lu.

Compare exact same requests through direct plugin computation and existing
Admission/Runtime/spawned worker plus independent verification. Direct calls
are benchmark controls only, never a new runtime routing shortcut.
"""
import argparse
import ctypes
import hashlib
import json
import math
import os
import platform
import statistics
import sys
import time
from pathlib import Path
from dataclasses import asdict, replace

# Constrain common native math libraries before importing NumPy.
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS',
            'BLIS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key] = '1'

import numpy as np
import google.protobuf
from cognitum.mel import admission as a, native as n, engines as e
from cognitum.mel import engines_pb2 as ep, model_engines as m
from cognitum.mel import model_reference as r, intent_reference as ir
from cognitum.mel import lu_adapter as adapter, cpu_routing as routing
from cognitum.mel.engine_limits import HdcLimits, KanLimits, account
from cognitum.registry import Registry
from cognitum.runtime import Runtime


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def resources():
    """Process high water and CPU counters; not summed simultaneous tree RSS."""
    if sys.platform.startswith('linux'):
        import resource
        own=resource.getrusage(resource.RUSAGE_SELF)
        child=resource.getrusage(resource.RUSAGE_CHILDREN)
        return dict(self_cpu_s=own.ru_utime+own.ru_stime,
                    reaped_child_cpu_s=child.ru_utime+child.ru_stime,
                    self_peak_rss_bytes=own.ru_maxrss*1024,
                    largest_reaped_child_peak_rss_bytes=child.ru_maxrss*1024,
                    memory_scope='process_lifetime_high_water_not_tree_sum')
    if sys.platform=='win32':
        from ctypes import wintypes as w
        class Counters(ctypes.Structure):
            _fields_=[('cb',w.DWORD),('PageFaultCount',w.DWORD)]+[
                (key,ctypes.c_size_t) for key in (
                'PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage',
                'QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage',
                'QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
        k=ctypes.WinDLL('kernel32',use_last_error=True)
        k.GetCurrentProcess.restype=w.HANDLE
        p=ctypes.WinDLL('psapi',use_last_error=True)
        p.GetProcessMemoryInfo.argtypes=[w.HANDLE,ctypes.POINTER(Counters),w.DWORD]
        p.GetProcessMemoryInfo.restype=w.BOOL
        c=Counters();c.cb=ctypes.sizeof(c)
        if not p.GetProcessMemoryInfo(k.GetCurrentProcess(),ctypes.byref(c),c.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return dict(self_cpu_s=time.process_time(),reaped_child_cpu_s=None,
                    self_peak_rss_bytes=c.PeakWorkingSetSize,
                    largest_reaped_child_peak_rss_bytes=None,
                    memory_scope='process_lifetime_high_water_child_unmeasured')
    raise RuntimeError('native resource measurement unsupported on this platform')


def delta(before,after):
    return {key:after[key]-before[key] if before[key] is not None else None
            for key in ('self_cpu_s','reaped_child_cpu_s')}


def sha(raw):return hashlib.sha256(raw).hexdigest()


def registry():
    reg=Registry()
    reg.install(n.NativeVFAPlugin,enabled=True)
    reg.install(e.EnginePlugin,enabled=True)
    for op in adapter.OPERATIONS:
        reg.nominate(op,n.NAME if op in n.OP else e.NAME)
    return reg


def instances():
    for large in (False,True):
        d=2 if large else 1
        rows=4 if large else 1
        vfa={'axes':[{'name':'x'+str(i),'unit':'1'} for i in range(d)],
             'domain':[{'lower':-1,'upper':1} for _ in range(d)],
             'terms':[{'center':[0]*d,'width':[1]*d,'weight':2}],
             'constant':0,'output_unit':'1',
             'points':[[.5]*d for _ in range(rows)]}
        if large:
            vfa['terms'] += [{'center':[.25]*d,'width':[.5]*d,'weight':-.5},
                             {'center':[-.25]*d,'width':[1]*d,'weight':.25}]
            vfa['points']=[[i/8,-i/8] for i in range(rows)]
        yield 'vfa.evaluate',large,vfa,None
        yield 'vfa.gradient',large,vfa,None
        dim=768 if large else 8  # keep eight candidates inside the model's 8192-byte envelope
        left=('10110010'*((dim+7)//8))[:dim]
        right=('01011100'*((dim+7)//8))[:dim]
        yield 'hdc.bind',large,{'left':left,'right':right},None
        candidates=[left,right,left,'0'*dim]
        if large:candidates += ['1'*dim,right,left,right]
        yield 'hdc.query',large,{'probe':left,'candidates':candidates},None
        cp=m.Approval(m.Checkpoint(m.checkpoint_wire([ep.KanLayer(
            inputs=1,outputs=1,knots=3,basis=ep.RBF,grid=[-1.,0.,1.],
            coefficients=[0.,2.,0.],mask=[1.])])), 'cpu-qualification')
        yield 'kan.evaluate',large,{'points':[[i/8] for i in range(8)] if large else [[.5]]},cp


def scalar_oracle(op,args):
    if op=='hdc.bind':
        return ''.join(str(int(x)^int(y)) for x,y in zip(args['left'],args['right']))
    if op=='hdc.query':
        d=[sum(a!=b for a,b in zip(args['probe'],x)) for x in args['candidates']]
        return {'distances':d,'indices':[i for i,v in enumerate(d) if v==min(d)]}
    if op=='kan.evaluate':
        # Exact simple reviewed fixture: 2 exp(-x^2), binary32 coordinates.
        return [2*math.exp(-row[0]**2) for row in args['points']]
    values=[]
    for row in args['points']:
        terms=[t['weight']*math.exp(-.5*math.fsum(
            ((x-c)/w)**2 for x,c,w in zip(row,t['center'],t['width'])))
            for t in args['terms']]
        if op=='vfa.evaluate':values.append(math.fsum([args['constant'],*terms]))
        else:
            values.extend(math.fsum(-y*(row[j]-t['center'][j])/t['width'][j]**2
                           for y,t in zip(terms,args['terms']))
                          for j in range(len(row)))
    return values


def observed(op,frame):
    if op in n.OP:
        b=n.pb.VfaResult.FromString(frame).result.body
        return list(b.values.values if op=='vfa.evaluate' else b.gradient.values)
    x=ep.EngineResult.FromString(frame)
    if op=='hdc.bind':return m._unpack(x.bound)
    if op=='hdc.query':return {'distances':list(x.query.hamming_distance),'indices':list(x.query.best_index)}
    return list(x.kan.values)


def fidelity(op,actual,expected):
    if op.startswith('hdc.'):
        require(actual==expected,'independent exact HDC oracle disagreement')
        return {'exact':True,'max_abs_error':0.0}
    require(len(actual)==len(expected) and all(math.isfinite(x) for x in actual),
            'numeric result shape or finiteness')
    error=max(abs(x-y) for x,y in zip(actual,expected))
    tolerance=1e-5 if op=='kan.evaluate' else 1e-10
    require(error<=tolerance,'independent numerical oracle disagreement')
    return {'exact':False,'max_abs_error':error,'absolute_tolerance':tolerance}


def sample(reg,op,large,args,approval,repetition):
    scope=a.Scope('cpu-session','cpu-bench','reviewer','turn')
    route=next(x for x in a.routes(include_engines=True) if x.operation==op)
    proposed=routing.select_cpu(reg,route,preference='cpu',allow_research=True)
    require(proposed.backend=='cpu' and not proposed.execution_authorized,'route proposal')
    meta=next(x for x in adapter.proposal()['routes'] if x['operation']==op)
    allowed=r.Allowed((op,),approval)
    intent=ir.Intent(scope,op,r.canonical(args),None if op.startswith('hdc.') else .25,
                     approval.checkpoint.identity if approval else None)
    raw=r.canonical({'tool':route.public_name,'arguments':args})
    start=time.perf_counter_ns()
    p=adapter.prepare(reg,intent,allowed,route,meta['codec_sha256'],raw,
                      request_id='cpu-call')
    prepare_ms=(time.perf_counter_ns()-start)/1e6
    factory=n.NativeVFAPlugin if op in n.OP else e.EnginePlugin
    direct=[]
    plugin=factory()
    # Warmup outside the samples, same encoded input and same kernel.
    plugin.handle(op,p.call.payload())
    direct_before=resources()
    frames=[]
    for _ in range(7):
        start=time.perf_counter_ns()
        output=plugin.handle(op,p.call.payload())
        direct.append((time.perf_counter_ns()-start)/1e6)
        frames.append(n.decode_carrier(output['frame'],n.MAX_RESULT if op in n.OP else e.MAX_RESULT))
    direct_after=resources()
    require(all(x==frames[0] for x in frames),'unstable direct result bytes')
    limits=a.Limits(timeout_ms=10000) if op in n.OP else (
        KanLimits(timeout_ms=10000) if op=='kan.evaluate' else HdcLimits(timeout_ms=10000))
    if op in n.OP:
        f,q=n.pair(p.call.function,p.call.points);t,d=f.body.shape
        work=(t+1)*d*q.body.shape[0]
    else:work=account(p.call,limits)
    require(work is not None and 0<work<=limits.work,'work accounting')
    host=a.Admission(Runtime(reg),scope.session,enable_engines=True,enable_model_codecs=True)
    try:
        if approval:
            host.approve_checkpoint(scope,approval.checkpoint.wire,
                expected_sha256=approval.checkpoint.identity,review_id=approval.review_id)
        token=host.issue(scope,route,limits,ttl_ms=60000,model_codec=op not in n.OP,
                         checkpoint_sha256=approval.checkpoint.identity if approval else None)
        before=resources();start=time.perf_counter_ns()
        receipt=host.execute(scope,token,'cpu-call',p.wire,timeout_ms=10000)
        admitted_ms=(time.perf_counter_ns()-start)/1e6;after=resources()
        require(receipt.status=='completed','worker did not complete: '+receipt.status)
        require(receipt.result_frame==frames[0],'direct/admitted result bytes differ')
        verify_before=resources();start=time.perf_counter_ns()
        verified=adapter.verify_host_retained_receipt(p,receipt)
        verify_ms=(time.perf_counter_ns()-start)/1e6;verify_after=resources()
        require(verified['ok'] and not verified['publication_authorized'],'independent verification failed')
        oracle=scalar_oracle(op,args)
        check=fidelity(op,observed(op,receipt.result_frame),oracle)
        return {'operation':op,'size':'larger' if large else 'small','repeat':repetition,
                'selection':asdict(proposed),'request_sha256':sha(p.wire),
                'result_sha256':sha(receipt.result_frame),'request_bytes':len(p.wire),
                'result_bytes':len(receipt.result_frame),'logical_work_units':work,
                'prepare_ms':prepare_ms,'direct_ms_samples':direct,
                'direct_median_ms':statistics.median(direct),'admission_worker_ms':admitted_ms,
                'verification_ms':verify_ms,'admitted_cpu_delta':delta(before,after),
                'direct_seven_samples_cpu_delta':delta(direct_before,direct_after),
                'verification_cpu_delta':delta(verify_before,verify_after),
                'process_high_water_after_worker':after,
                'process_high_water_after_verification':verify_after,'fidelity':check,
                'verification':'PASS','matched_native_bytes':True}
    finally:host.close()


def refusals(reg):
    route=next(x for x in a.routes(include_engines=True) if x.operation=='hdc.bind')
    def denied(fn):
        try:fn()
        except ValueError:return
        raise RuntimeError('expected refusal')
    for choice in ('gpu','vulkan','cuda','rocm','fpga','distributed','unknown'):
        denied(lambda:routing.select_cpu(reg,route,preference=choice,allow_research=True))
    denied(lambda:routing.select_cpu(reg,route,allow_research=False))
    denied(lambda:routing.select_cpu(reg,replace(route,descriptor_sha256='0'*64),allow_research=True))
    require(routing.select_cpu(reg,route,allow_research=True).backend=='cpu','auto CPU')
    reg.enable(e.NAME,False)
    try:denied(lambda:routing.select_cpu(reg,route,allow_research=True))
    finally:reg.enable(e.NAME,True)
    # Resource denial, one-shot replay and revoked grant.
    scope=a.Scope('neg-session','w','u','negative')
    args={'left':'1010','right':'0011'}
    call=m.bind('hdc.bind',None,r.canonical(args),'negative-call',scope.turn)
    host=a.Admission(Runtime(reg),scope.session,enable_engines=True,enable_model_codecs=True)
    try:
        tiny=host.issue(scope,route,HdcLimits(dimensions=1),ttl_ms=60000,model_codec=True)
        q=host.execute(scope,tiny,'negative-call',call.wire,timeout_ms=3000)
        require(q.status=='resource_denied' and q.result_frame is None,'resource denial')
        full=host.issue(scope,route,HdcLimits(timeout_ms=10000),ttl_ms=60000,model_codec=True)
        q=host.execute(scope,full,'negative-call',call.wire,timeout_ms=10000)
        require(q.status=='completed','positive replay control')
        q=host.execute(scope,full,'negative-call',call.wire,timeout_ms=10000)
        require(q.status=='replay_denied' and q.result_frame is None,'replay denied')
        host.revoke(scope,full)
        denied(lambda: host.execute(scope,full,'negative-call',call.wire,timeout_ms=10000))
    finally:host.close()
    return ['explicit_non_cpu_refused','research_disabled','stale_descriptor',
            'automatic_cpu','disabled_plugin','resource_denied','replay_denied','revoked_grant']


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    p.add_argument('--repeats',type=int,default=3);args=p.parse_args()
    require(1<=args.repeats<=5,'repeat budget')
    out=args.out;out.parent.mkdir(parents=True,exist_ok=True)
    report={'profile':'cognitum.mel.cpu_qualification.v1','status':'OPEN',
            'source_commit':os.environ.get('GITHUB_SHA'),'platform':platform.platform(),
            'machine':platform.machine(),'python':sys.version,'numpy':np.__version__,
            'protobuf':google.protobuf.__version__,'visible_cpus':os.cpu_count(),
            'thread_env':{k:os.environ[k] for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')},
            'scope':'five existing CPU operations, bounded representative fixtures; not hardware certification',
            'rows':[]}
    try:
        reg=registry()
        report['negative_controls']=refusals(reg)
        for op,large,inputs,approval in instances():
            for i in range(args.repeats):
                report['rows'].append(sample(reg,op,large,inputs,approval,i))
        require(len(report['rows'])==10*args.repeats,'incomplete matrix')
        report['summaries']=[]
        for op in adapter.OPERATIONS:
            for size in ('small','larger'):
                rows=[x for x in report['rows'] if x['operation']==op and x['size']==size]
                report['summaries'].append({'operation':op,'size':size,'repeats':len(rows),
                    'direct_median_ms':statistics.median(v for x in rows for v in x['direct_ms_samples']),
                    'admitted_median_ms':statistics.median(x['admission_worker_ms'] for x in rows),
                    'verification_median_ms':statistics.median(x['verification_ms'] for x in rows),
                    'max_abs_error':max(x['fidelity']['max_abs_error'] for x in rows)})
        report['terminal_resources']=resources()
        report['status']='PASS'
    finally:
        out.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')


if __name__=='__main__':main()
