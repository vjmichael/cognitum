"""P7 local developer-only latency comparison; no model or GPU timings."""
from __future__ import annotations
import json
from statistics import median

from cognitum.contracts import Request, HostContext
from cognitum.plugins.calculator import Calculator
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.sandbox_linux import LinuxNamespaceExecutor


def run(n=12):
    registry=Registry()
    registry.install(Calculator,enabled=True)
    registry.nominate('calc','reference_calc')
    context=HostContext('local','local-user')
    modes={'legacy_disposable_trusted':Runtime(registry),
           'namespace_isolated_cold':Runtime(registry,sandbox_executor=LinuxNamespaceExecutor())}
    values={}
    for name,runtime in modes.items():
        samples=[]
        for i in range(n):
            request=Request(f'p7bench-{name}-{i}',f'cor-{i}',
                            'calc.rational',{'expression':'17/3+7/3'},timeout_ms=5000)
            r=runtime.call(request,context)
            assert r.execution_status=='completed' and r.result=={'value':'8'},r.to_dict()
            samples.append(r.latency_ms)
        ordered=sorted(samples)
        values[name]={'n':n,'median_ms':median(samples),
                      'p95_nearest_rank_ms':ordered[max(0,(95*n+99)//100-1)],
                      'samples_ms':samples}
    out={'environment':'Linux namespace-capable local host',
         'model_included':False,'os_containment':'user/mount/net/PID/IPC/UTS namespaces; no cgroups',
         'warm_standby_in_sandbox':False,'results':values}
    print(json.dumps(out,indent=2))
    return out

if __name__=='__main__':run()
