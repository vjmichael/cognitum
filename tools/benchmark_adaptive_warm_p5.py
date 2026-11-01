"""P5 trusted adaptive two-to-four warm-worker burst benchmark, no model."""
from __future__ import annotations
import json
from time import perf_counter
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.warm_pool import WarmCappedPool, global_warm_budget_snapshot
from tests.test_warm_worker_edge_p3 import SlowPure
from tools.benchmark_warm_pool_p5 import group, _rss


def run():
    reg=Registry()
    reg.install(SlowPure,enabled=True)
    reg.nominate('slow','slow_pure')
    pool=WarmCappedPool(SlowPure)  # default two, min one, maximum four, adaptive
    rt=Runtime(reg,warm_pool=pool)
    record={'mode':'adaptive_two_to_four','llm_included':False,'os_sandbox':False,'bursts':[]}
    try:
        pool.start()
        assert pool.wait_ready(15)
        record['initial']=pool.snapshot()
        for trial in range(3):
            # For steady-state measurement, allow planned replacement to be ready.
            assert pool.wait_ready(15,minimum=pool.target_ready)
            before=pool.snapshot()
            stat=group(rt,4,'adaptive',trial)
            after=pool.snapshot()
            record['bursts'].append({'index':trial+1,'before_target':before['target_ready'],
                'after_target':after['target_ready'],'wall_ms':stat['wall_ms'],
                'before_hits':before['hits'],'after_hits':after['hits'],
                'before_misses':before['misses'],'after_misses':after['misses']})
        record['final']=pool.snapshot()
        record['rss_bytes_idle']=[]
        assert pool.wait_ready(15)
        with pool._cv:
            record['rss_bytes_idle']=[_rss(s.process.pid) for s in pool._idle]
        assert record['final']['max_observed_warm']<=4
    finally:
        pool.close()
    record['global_after_close']=global_warm_budget_snapshot()
    assert record['global_after_close']['reserved']==0
    return record

if __name__=='__main__':
    print(json.dumps(run(),indent=2))
