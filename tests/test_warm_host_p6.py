"""P6 trusted-host periodic warm-pool maintenance (no Lu dependency)."""
from __future__ import annotations

import time

import pytest

from cognitum.warm_host import TrustedWarmMaintenance
from cognitum.warm_pool import WarmCappedPool, global_warm_budget_snapshot
from cognitum.worker_budget import global_cold_budget_snapshot
from cognitum.plugins.calculator import Calculator
from cognitum.contracts import HostContext
from tests.test_warm_pool_p4 import setup,calc_req
from tests.test_warm_worker_edge_p3 import SlowPure


def test_host_maintenance_automatically_downshifts_and_restores_two_after_request():
    runtime, pool=setup(target=2)
    pool.idle_downshift_s=1.0
    host=TrustedWarmMaintenance([pool],interval_s=0.1)
    try:
        host.start()
        assert pool.wait_ready(12)
        assert pool.snapshot()['target_ready']==2
        end=time.monotonic()+4
        while time.monotonic()<end and pool.snapshot()['target_ready']!=1:
            time.sleep(.05)
        assert pool.snapshot()['target_ready']==1, host.snapshot()
        assert host.snapshot()['ticks']>=1
        result=runtime.call(calc_req(11,'2+2'),HostContext('local','local-user'))
        assert result.result=={'value':'4'}
        assert pool.snapshot()['target_ready']==2
        assert pool.wait_ready(12)
        assert host.snapshot()['failures']==0
    finally:host.close()
    assert not host.snapshot()['running']
    assert global_warm_budget_snapshot()['reserved']==0
    assert global_cold_budget_snapshot()['active']==0


def test_explicit_host_opt_in_not_scheduled_by_default():
    pool=WarmCappedPool(Calculator)
    host=TrustedWarmMaintenance([pool],interval_s=.1)
    try:
        assert not host.snapshot()['running']
        assert pool.snapshot()['warm_total']==0
        host.start(); assert pool.wait_ready(12)
        host.start()  # idempotent
        assert host.snapshot()['running']
    finally:host.close()
    with pytest.raises(RuntimeError,match='HOST_MAINTENANCE_CLOSED'):
        host.start()
    assert not host.snapshot()['running']
    assert global_warm_budget_snapshot()['reserved']==0


def test_host_maintains_multiple_pools_without_exceeding_four_warm():
    p1=WarmCappedPool(Calculator)
    p2=WarmCappedPool(SlowPure)
    host=TrustedWarmMaintenance([p1,p2],interval_s=.1)
    try:
        host.start()
        assert p1.wait_ready(12) and p2.wait_ready(12)
        snap=host.snapshot()
        assert snap['warm']['reserved']==4
        assert snap['warm']['peak']<=4
        assert p1.snapshot()['target_ready']==2 and p2.snapshot()['target_ready']==2
    finally:host.close()
    assert global_warm_budget_snapshot()['reserved']==0


@pytest.mark.parametrize('period',[0,.01,True,61,'0.2',None])
def test_host_rejects_invalid_maintenance_period(period):
    p=WarmCappedPool(Calculator)
    try:
        with pytest.raises(ValueError,match='INVALID_MAINTENANCE_PERIOD'):
            TrustedWarmMaintenance([p],interval_s=period)
    finally:p.close()


def test_host_rejects_duplicate_and_unknown_pools():
    p=WarmCappedPool(Calculator)
    try:
        with pytest.raises(ValueError,match='DUPLICATE_POOL'):
            TrustedWarmMaintenance([p,p])
        with pytest.raises(TypeError,match='TRUSTED_WARM_POOL_REQUIRED'):
            TrustedWarmMaintenance([object()])
    finally:p.close()
