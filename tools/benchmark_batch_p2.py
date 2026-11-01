"""Matched one-process vs per-operation Cognitum Python worker wall-time study."""
from __future__ import annotations
import json,platform,statistics,sys,time
from pathlib import Path
from cognitum.contracts import HostContext, Request
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.plugins.calculator import Calculator

OUT=Path(__file__).resolve().parents[1]/'research'/'component_quality_p2'/'results'/'generic_runtime_benchmark.json'


def runtime():
    r=Registry();r.install(Calculator,enabled=True);r.nominate('calc','reference_calc')
    return Runtime(r)


def quantile(data,p):
    xs=sorted(data); return xs[min(len(xs)-1,max(0,int((len(xs)-1)*p+.5)))]


def main():
    ctx=HostContext('local','local-user')
    r=runtime()
    output={'title':'P2 generic Cognitum trusted worker batching reference benchmark',
            'platform':platform.platform(),'python':platform.python_version(),
            'note':'Local Linux process latency; effect-free Calculator only; no OS sandbox or installed app; same formal tasks',
            'samples':[]}
    # Trigger first import/spawn to reduce transient cold-cache influence.
    assert r.call(Request('warm','warm','calc.rational',{'expression':'1/3*3'},timeout_ms=5000),ctx).result=={'value':'1'}
    for n in (1,4,8,16):
        separate=[];batched=[]
        for trial in range(3):
            reqs=[Request(f'N{n}-T{trial}-Q{i}',f'N{n}-T{trial}',
                 'calc.rational',{'expression':'(1/7)*7'},timeout_ms=5000) for i in range(n)]
            def many():
                st=time.perf_counter()
                vals=[r.call(x,ctx) for x in reqs]
                return (time.perf_counter()-st)*1000,vals
            def one():
                st=time.perf_counter()
                vals=r.call_batch(reqs,ctx,trusted_batch_opt_in=True)
                return (time.perf_counter()-st)*1000,vals
            if trial%2:
                b,bv=one();s,sv=many()
            else:
                s,sv=many();b,bv=one()
            if not (all(x.execution_status=='completed' and x.result=={'value':'1'} for x in sv+bv)
                    and all(a.result==z.result for a,z in zip(sv,bv))):
                raise RuntimeError('batch calculation mismatch')
            separate.append(s);batched.append(b)
        a=statistics.median(separate);b=statistics.median(batched)
        output['samples'].append({'operations':n,'trials':3,
                                  'separate_ms':separate,'batch_ms':batched,
                                  'separate_median_ms':a,'batch_median_ms':b,
                                  'separate_max_of_three_ms':max(separate),
                                  'batch_max_of_three_ms':max(batched),
                                  'median_speedup':a/b,'batch_per_op_amortized_ms':b/n})
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps(output,indent=2))

if __name__=='__main__':main()
