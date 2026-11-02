"""P9 trusted-host fleet policy for one Cognitum Linux warm-worker budget.

A host with calculator and specialist pools receives TWO total standbys by
DEFAULT, rather than two per provider. On actual demand it can grow to FOUR
across the providers, never bypassing P7 containment or the existing global
warm budget. Pool selection and resizing are host-owned; model calls cannot
change the allocation. This is NOT a new sandbox security boundary.
"""
from __future__ import annotations

import threading
import time

from .sandbox_warm_pool import LinuxSandboxWarmPool
from .warm_pool import MAX_WARM_WORKERS, global_warm_budget_snapshot


class ContainedWarmFleet:
    """Explicit, synchronous host allocator; call maintain() from host service.

    Supports one calculator pool, one specialists pool, or both. Each provider
    retains one standby while enabled. Misses from actual authorized requests
    grow the respective share by at most one per tick until the host-wide four
    ceiling. Pressure or sustained inactivity reclaims surplus reservations.
    Cold overflow continues through the P7 executor's separate bounded gate.
    """

    def __init__(self, pools, *, quiet_s=60.0):
        if type(pools) not in (tuple, list) or not 1 <= len(pools) <= 2:
            raise ValueError('FLEET_REQUIRES_ONE_OR_TWO_PROVIDERS')
        if any(type(p) is not LinuxSandboxWarmPool for p in pools):
            raise TypeError('FLEET_REQUIRES_P7_CONTAINED_POOLS')
        providers=[p.provider for p in pools]
        if len(set(providers)) != len(providers):
            raise ValueError('DUPLICATE_FLEET_PROVIDER')
        if type(quiet_s) not in (float,int) or not 1<=quiet_s<=3600:
            raise ValueError('INVALID_FLEET_QUIET_PERIOD')
        self._pools=tuple(pools)
        self._lock=threading.RLock()
        self.quiet_s=float(quiet_s)
        self._started=False
        self._closed=False
        self._alloc={p.provider:(2 if len(pools)==1 else 1) for p in pools}
        if any(p.min_ready>self._alloc[p.provider] or p.max_warm<self._alloc[p.provider]
               for p in pools):
            raise ValueError('INCOMPATIBLE_POOL_STANDBY_MINIMUM')
        self._last_misses={p.provider:0 for p in pools}
        self._last_hits={p.provider:0 for p in pools}
        self._last_demand=time.monotonic()
        self._last_trim=self._last_demand
        self.expansions=0
        self.trims=0
        self.pressure_trims=0

    def start(self):
        with self._lock:
            if self._closed:
                raise RuntimeError('FLEET_CLOSED')
            if self._started:
                return
            # Authoritatively cap each independent pool BEFORE it can spawn.
            try:
                for p in self._pools:
                    p.adaptive=False  # fleet replaces the P8 local autoscaler
                    p.set_target_ready(self._alloc[p.provider])
                for p in self._pools:
                    p.start()
            except BaseException:
                self._closed=True
                for p in self._pools:
                    p.close()
                raise
            self._started=True

    def maintain(self, *, pressure=False):
        """Rebalance one step per tick; pressure=True is trusted-host input."""
        if type(pressure) is not bool:
            raise TypeError('HOST_PRESSURE_MUST_BE_BOOLEAN')
        with self._lock:
            if self._closed:
                return self.snapshot()
            if not self._started:
                raise RuntimeError('FLEET_NOT_STARTED')
            now=time.monotonic()
            snapshots={p.provider:p.snapshot() for p in self._pools}
            misses={name:s['misses'] for name,s in snapshots.items()}
            hits={name:s['hits'] for name,s in snapshots.items()}
            deltas={name:max(0,count-self._last_misses[name])
                    for name,count in misses.items()}
            self._last_misses=misses
            new_hits=any(hits[name]>self._last_hits[name] for name in hits)
            self._last_hits=hits
            if any(deltas.values()) or new_hits:
                self._last_demand=now
            baseline=2
            used=sum(self._alloc.values())
            if pressure:
                # Under pressure, return to minimum reserved footprint.
                for p in self._pools:
                    floor=1
                    if self._alloc[p.provider]>floor:
                        self._alloc[p.provider]=floor
                        self.pressure_trims+=1
                        p.set_target_ready(floor)
                self._last_demand=now  # avoid immediate reacquire
                self._last_trim=now
            elif now-max(self._last_demand,self._last_trim)>=self.quiet_s and used>baseline:
                # Round down the largest share, retaining one per provider.
                eligible=[p for p in self._pools if self._alloc[p.provider]>
                          (2 if len(self._pools)==1 else 1)]
                if eligible:
                    selected=max(eligible,key=lambda p:(self._alloc[p.provider],p.provider))
                    self._alloc[selected.provider]-=1
                    selected.set_target_ready(self._alloc[selected.provider])
                    self.trims+=1
                    self._last_trim=now
            elif used<baseline:
                # Restore the ordinary two-standby policy when pressure clears.
                selected=self._pools[0]
                if self._alloc[selected.provider]<selected.max_warm:
                    self._alloc[selected.provider]+=1
                    selected.set_target_ready(self._alloc[selected.provider])
            elif used<MAX_WARM_WORKERS and any(deltas.values()):
                eligible=[p for p in self._pools if deltas[p.provider] and
                          self._alloc[p.provider]<p.max_warm]
                if eligible:
                    selected=max(eligible,key=lambda p:(deltas[p.provider],
                                                       -self._alloc[p.provider]))
                    self._alloc[selected.provider]+=1
                    selected.set_target_ready(self._alloc[selected.provider])
                    self.expansions+=1
            for p in self._pools:
                p.maintain()
            return self.snapshot()

    def snapshot(self):
        with self._lock:
            return {'started':self._started,'closed':self._closed,
                    'default_standbys':2,'maximum_standbys':MAX_WARM_WORKERS,
                    'allocation':dict(self._alloc),
                    'expansions':self.expansions,'trims':self.trims,
                    'pressure_trims':self.pressure_trims,
                    'warm_budget':global_warm_budget_snapshot(),
                    'pools':{p.provider:p.snapshot() for p in self._pools}}

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed=True
            for p in self._pools:
                p.close()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.close()
