"""P5 matched burst benchmark: cold, 1, 2, 4 standbys, no LLM involved."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
from statistics import median
import threading
import time

from cognitum.contracts import HostContext, Request
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.warm_pool import WarmCappedPool
from tests.test_warm_worker_edge_p3 import SlowPure


def _rss(pid):
    try:
        for line in Path(f'/proc/{pid}/status').read_text().splitlines():
            if line.startswith('VmRSS:'):
                return int(line.split()[1])*1024
    except (FileNotFoundError, PermissionError, ValueError):
        pass
    return None


def group(runtime, n, label, trial):
    barrier=threading.Barrier(n+1)
    ctx=HostContext('local','local-user')
    def once(i):
        barrier.wait(timeout=10)
        return runtime.call(Request(f'{label}-{n}-{trial}-{i}',f'prompt-{trial}',
                                    'slow.wait',{'duration_ms':'400'},timeout_ms=7000),ctx)
    with ThreadPoolExecutor(max_workers=n) as executor:
        futures=[executor.submit(once,i) for i in range(n)]
        start=time.perf_counter()
        barrier.wait(timeout=10)
        results=[f.result(timeout=12) for f in futures]
        elapsed=(time.perf_counter()-start)*1000
    assert len(results)==n
    assert all(r.execution_status=='completed' and r.result=={'value':'done'} for r in results),[r.to_dict() for r in results]
    return {'wall_ms':round(elapsed,3),'median_request_ms':round(median(r.latency_ms for r in results),3),
            'min_request_ms':round(min(r.latency_ms for r in results),3),
            'max_request_ms':round(max(r.latency_ms for r in results),3)}


def run():
    report={'label':'P5 two-default standby capacity, independent local Linux benchmark',
            'unit':'ms','worker_delay_ms':400,'runs_per_burst':2,
            'llm_included':False,'os_sandbox':False,
            'settings':{'max_warm_hard_limit':4,'single_use':True,'overflow':'cold immediately'},
            'conditions':{}}
    for condition,target in [('cold',None),('warm_1',1),('warm_2',2),('warm_4',4)]:
        reg=Registry();reg.install(SlowPure,enabled=True);reg.nominate('slow','slow_pure')
        pool=WarmCappedPool(SlowPure,target_ready=target,max_warm=4,adaptive=False) if target else None
        rt=Runtime(reg,warm_pool=pool)
        stats={'runs':{},'memory':{},'warmup_ms':None,'final_pool':None}
        try:
            if pool:
                t0=time.perf_counter()
                pool.start()
                assert pool.wait_ready(15)
                stats['warmup_ms']=round((time.perf_counter()-t0)*1000,3)
                with pool._cv:
                    rss=[_rss(s.process.pid) for s in pool._idle]
                    stats['memory']={'worker_rss_bytes':rss,'sum_worker_rss_bytes':sum(x for x in rss if x is not None)}
            for n in (4,8):
                results=[]
                for trial in range(2):
                    if pool:
                        assert pool.wait_ready(15)
                    results.append(group(rt,n,condition,trial))
                stats['runs'][str(n)]=results
                stats[f'{n}_median_wall_ms']=round(median(z['wall_ms'] for z in results),3)
                stats[f'{n}_median_request_ms']=round(median(z['median_request_ms'] for z in results),3)
            if pool:
                assert pool.snapshot()['max_observed_warm']<=4
                stats['final_pool']=pool.snapshot()
        finally:
            if pool:pool.close()
        report['conditions'][condition]=stats
    for n in (4,8):
        cold=report['conditions']['cold'][f'{n}_median_wall_ms']
        for condition in ('warm_1','warm_2','warm_4'):
            warm=report['conditions'][condition][f'{n}_median_wall_ms']
            report[f'{n}_{condition}_wall_speedup']=round(cold/warm,3)
    return report


if __name__=='__main__':
    result=run()
    print(json.dumps(result,indent=2))
