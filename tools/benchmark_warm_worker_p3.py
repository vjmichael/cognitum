"""Non-production P3 warm-worker timing with explicit startup and task clocks."""
from __future__ import annotations
import json
from pathlib import Path
from statistics import median
from time import perf_counter

from cognitum.contracts import HostContext, Request
from cognitum.plugins.calculator import Calculator
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.warm_worker import WarmSingleUsePool


def main():
    reg=Registry();reg.install(Calculator,enabled=True);reg.nominate('calc','reference_calc')
    ctx=HostContext('local','local-user')
    baseline=Runtime(reg)
    cold=[]
    for i in range(8):
        out=baseline.call(Request(f'cold-{i}','c','calc.rational',{'expression':'17/3+7/3'},timeout_ms=4500),ctx)
        assert out.result=={'value':'8'}
        cold.append(out.latency_ms)
    pool=WarmSingleUsePool(Calculator)
    warmed=[];waits=[]
    try:
        started=perf_counter()
        pool.start()
        assert pool.wait_ready(10)
        initial_preload=(perf_counter()-started)*1000
        for i in range(8):
            t0=perf_counter()
            assert pool.wait_ready(10)
            waits.append((perf_counter()-t0)*1000)
            out=Runtime(reg,warm_pool=pool).call(Request(f'warm-{i}','c','calc.rational',{'expression':'17/3+7/3'},timeout_ms=4500),ctx)
            assert out.result=={'value':'8'}
            warmed.append(out.latency_ms)
        # Burst exposes when a 1-standby pool is depleted. No artificial
        # readiness wait between requests: cold fallback is the control.
        assert pool.wait_ready(10)
        burst=[]
        for i in range(8):
            out=Runtime(reg,warm_pool=pool).call(Request(f'burst-{i}','c','calc.rational',{'expression':'17/3+7/3'},timeout_ms=4500),ctx)
            assert out.result=={'value':'8'}
            burst.append(out.latency_ms)
        result={
            'kind':'p3_warm_worker_linux_development_only',
            'n_per_class':8,
            'cold_call_ms':cold,'prewarmed_call_ms':warmed,'no_wait_burst_ms':burst,
            'median_cold_ms':round(median(cold),3),
            'median_warm_ms':round(median(warmed),3),
            'prewarmed_speedup':round(median(cold)/median(warmed),2),
            'initial_preload_ms':round(initial_preload,3),
            'refill_wait_ms':waits,
            'warm_hits_total':pool.hits,'warm_misses_total':pool.misses,
            'max_idle_workers':1,
            'protocol':'one-shot Python multiprocessing.Pipe, trusted pure factory',
            'os_sandbox':False,
            'model_time_included':False,
            'note':'Warmup and refill time measured separately from Cognitum request latency.'
        }
    finally:pool.close()
    print(json.dumps(result,indent=2))
    return result

if __name__=='__main__':main()
