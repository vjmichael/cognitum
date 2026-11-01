"""P6 matched local timings: P5 manually maintained vs trusted maintenance host.

No LLM clock included. This is NOT a production throughput benchmark.
"""
from __future__ import annotations

import json
import os
import statistics
import time

from cognitum.contracts import Request, HostContext
from cognitum.plugins.calculator import Calculator
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.warm_pool import WarmCappedPool, global_warm_budget_snapshot
from cognitum.warm_host import TrustedWarmMaintenance
from cognitum.worker_budget import global_cold_budget_snapshot


def runtime(pool=None):
    reg=Registry()
    reg.install(Calculator,enabled=True)
    reg.nominate('calc','reference_calc')
    return Runtime(reg,warm_pool=pool)


def ready_calls(use_host):
    pool=WarmCappedPool(Calculator,target_ready=2,idle_downshift_s=60)
    host=TrustedWarmMaintenance([pool],interval_s=.1) if use_host else None
    try:
        started=time.perf_counter()
        if host: host.start()
        else: pool.start()
        assert pool.wait_ready(12)
        startup_ms=1000*(time.perf_counter()-started)
        rt=runtime(pool)
        latencies=[]
        for i in range(8):
            assert pool.wait_ready(12,minimum=2)
            out=rt.call(Request(f'p6-yes-{i}-{use_host}','c','calc.rational',
                                {'expression':'4/3+2/3'},timeout_ms=4000),HostContext('local','local-user'))
            assert out.execution_status=='completed' and out.result=={'value':'2'}
            latencies.append(out.latency_ms)
        return {'maintenance_enabled':bool(host),
                'startup_ms':round(startup_ms,3),
                'median_ready_request_ms':round(statistics.median(latencies),3),
                'p90_ready_request_ms':round(sorted(latencies)[-2],3),
                'samples':latencies,'host_ticks':host.ticks if host else 0,
                'warm_hits':pool.hits,'warm_misses':pool.misses}
    finally:
        if host:host.close()
        else: pool.close()


def cold_calls():
    rt=runtime()
    latencies=[]
    for i in range(5):
        out=rt.call(Request(f'p6-cold-{i}','c','calc.rational',
                            {'expression':'4/3+2/3'},timeout_ms=4000),HostContext('local','local-user'))
        assert out.result=={'value':'2'}
        latencies.append(out.latency_ms)
    return {'median_ms':round(statistics.median(latencies),3), 'samples':latencies}


def main():
    cold=cold_calls()
    manual=ready_calls(False)
    automatic=ready_calls(True)
    result={'schema':'cognitum-p6-developer-host-microbenchmark-v1',
            'clock':'Cognitum tool request only, no model generation',
            'platform':os.name,
            'one_worker_startup_per_preload':True,
            'cold':cold,'p5_manual_maintenance':manual,'p6_trusted_auto_maintenance':automatic,
            'global_cold_budget':global_cold_budget_snapshot(),
            'global_warm_budget':global_warm_budget_snapshot(),
            'warning':'Only trusted deterministic pure operations. No OS sandbox; single host process; not p95/p99.'}
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
