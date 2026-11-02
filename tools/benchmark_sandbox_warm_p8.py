"""P8 real namespace warm/cold tool time only; no model tokens involved."""
from __future__ import annotations
import json
from statistics import median
from time import perf_counter

from cognitum.contracts import Request,HostContext
from cognitum.registry import Registry
from cognitum.plugins.calculator import Calculator
from cognitum.sandbox_linux import LinuxNamespaceExecutor
from cognitum.sandbox_warm_pool import LinuxSandboxWarmPool
from cognitum.runtime import Runtime


def quantile(seq,q):
    a=sorted(seq)
    k=(len(a)-1)*q
    i=int(k)
    return round(a[i]*(1-(k-i))+a[min(i+1,len(a)-1)]*(k-i),3)


def main():
    reg=Registry();reg.install(Calculator,enabled=True);reg.nominate('calc','reference_calc')
    ctx=HostContext('local','local-user')
    executor=LinuxNamespaceExecutor()
    cold=Runtime(reg,sandbox_executor=executor)
    cold_ms=[]
    for i in range(12):
        response=cold.call(Request(f'cold-{i}','c','calc.rational',{'expression':'17/3+7/3'},timeout_ms=7000),ctx)
        assert response.execution_status=='completed' and response.result=={'value':'8'}
        cold_ms.append(response.latency_ms)
    pool=LinuxSandboxWarmPool(executor,Calculator)
    warm=Runtime(reg,sandbox_executor=executor,warm_pool=pool)
    warm_ms=[];startup=0;refill=[]
    try:
        t=perf_counter();pool.start();assert pool.wait_ready(15)
        startup=(perf_counter()-t)*1000
        for i in range(12):
            t=perf_counter();assert pool.wait_ready(15,minimum=2)
            refill.append((perf_counter()-t)*1000)
            out=warm.call(Request(f'warm-{i}','c','calc.rational',{'expression':'17/3+7/3'},timeout_ms=7000),ctx)
            assert out.execution_status=='completed' and out.result=={'value':'8'}
            warm_ms.append(out.latency_ms)
        state=pool.snapshot()
    finally:pool.close()
    report={
        'n':12,'unit':'milliseconds','model_inference_included':False,
        'worker_type':'Linux user/mount/PID/net/IPC/UTS namespaces, P7 chroot/rlimits',
        'cold_p50':round(median(cold_ms),3),'warm_p50':round(median(warm_ms),3),
        'cold_p95':quantile(cold_ms,.95),'warm_p95':quantile(warm_ms,.95),
        'warm_initial_preload_ms':round(startup,3),
        'warm_refill_wait_p50_ms':round(median(refill),3),
        'warm_hits':state['hits'],'warm_misses':state['misses'],
        'warm_peak':state['peak_warm'],
        'cold_samples_ms':cold_ms,'warm_samples_ms':warm_ms,
        'note':'CPU/resource contention, memory and p99 require independent acceptance.',
    }
    print(json.dumps(report,indent=2))
    return report

if __name__=='__main__':main()
