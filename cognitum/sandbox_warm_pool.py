"""P8 opt-in 1/2/4 prewarmed workers INSIDE P7 Linux namespaces.

All worker processes are created using LinuxNamespaceExecutor._launch_contained,
never the legacy unsandboxed multiprocessing pool. One sandbox handles one
request then its PID namespace is destroyed. Overflow goes ONLY through the
P7 cold namespace executor. Requires an explicit trusted-host opt-in.

Limitations: no cgroup pids/memory proof, no seccomp profile, no Windows
support, and not a general untrusted-code plugin sandbox.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
import selectors
import shutil
import threading
import time

from .sandbox_linux import LinuxNamespaceExecutor, MAX_FRAME_BYTES
from .warm_pool import (_GLOBAL_WARM_BUDGET, MAX_WARM_WORKERS,
                        MIN_WARM_WORKERS, DEFAULT_WARM_WORKERS)
from .plugins.calculator import Calculator
from .plugins.specialists import Specialists


@dataclass
class _WarmSlot:
    process: object
    root: str
    ready_at: float


def _reap(slot: _WarmSlot):
    try:
        LinuxNamespaceExecutor._terminate_group(slot.process)
    finally:
        for stream in (slot.process.stdin, slot.process.stdout, slot.process.stderr):
            if stream is not None:
                try:
                    stream.close()
                except (OSError, ValueError):
                    pass
        shutil.rmtree(slot.root, ignore_errors=True)


def _read_ready(proc, timeout_s: float):
    """Bounded readiness line; never trust an arbitrary stdout token as READY."""
    stdout = bytearray()
    stderr = bytearray()
    deadline = time.monotonic() + timeout_s
    with selectors.DefaultSelector() as poller:
        for name, stream in (('out', proc.stdout),('err', proc.stderr)):
            os.set_blocking(stream.fileno(), False)
            poller.register(stream, selectors.EVENT_READ, name)
        while time.monotonic() < deadline:
            events = poller.select(min(0.25,deadline-time.monotonic()))
            for key, _ in events:
                try:
                    data = os.read(key.fileobj.fileno(), 1024)
                except (OSError, ValueError):
                    return False
                if not data:
                    poller.unregister(key.fileobj)
                    continue
                if key.data == 'out':
                    stdout.extend(data)
                    if len(stdout) > 2048:
                        return False
                    if b'\n' in stdout:
                        if stdout.count(b'\n') != 1 or not stdout.endswith(b'\n'):
                            return False
                        try:
                            msg = json.loads(stdout)
                        except (ValueError, UnicodeDecodeError):
                            return False
                        # These fields must have been emitted AFTER P7's
                        # kernel-backed preflight inside the chroot.
                        return (type(msg) is dict and set(msg) == {'status','result'}
                                and msg['status'] == 'ready'
                                and type(msg['result']) is dict
                                and msg['result'] == {
                                    'isolation_preflight': True,
                                    'inside_pid': 1,
                                    'read_only_code': True,
                                } and proc.poll() is None)
                else:
                    stderr.extend(data)
                    if len(stderr) > 4096:
                        return False
            if proc.poll() is not None:
                return False
    return False


class LinuxSandboxWarmPool:
    """Per-provider pool with a process-WIDE cap of four warm P7 sandboxes."""

    def __init__(self, executor, factory, *, target_ready=DEFAULT_WARM_WORKERS,
                 min_ready=MIN_WARM_WORKERS, max_warm=MAX_WARM_WORKERS,
                 adaptive=True, idle_downshift_s=60.0,
                 warmup_timeout_s=10.0, max_idle_s=120.0):
        if type(executor) is not LinuxNamespaceExecutor:
            raise TypeError('P7_EXECUTOR_REQUIRED')
        if factory is Calculator:
            provider = 'calculator'
            ops = ('calc.rational',)
        elif factory is Specialists:
            provider = 'specialists'
            ops = ('specialist.hdc','specialist.ssm','specialist.kan')
        else:
            raise PermissionError('UNREVIEWED_WARM_FACTORY')
        if (any(type(v) is not int for v in (target_ready,min_ready,max_warm))
                or not 1 <= min_ready <= target_ready <= max_warm <= MAX_WARM_WORKERS):
            raise ValueError('WARM_WORKER_LIMIT_MUST_BE_1_TO_4')
        if type(adaptive) is not bool:
            raise ValueError('INVALID_ADAPTIVE_SETTING')
        if not 1 <= idle_downshift_s <= 3600 or not 0.2 <= warmup_timeout_s <= 30 or not 1 <= max_idle_s <= 3600:
            raise ValueError('INVALID_POOL_INTERVAL')
        plugin = factory()
        manifest = plugin.manifest()
        if (plugin.health() is not True or plugin.self_test() is not True or
                any(op.effects or not op.deterministic for op in manifest.operations)):
            raise PermissionError('WARM_REQUIRES_TRUSTED_PURE_FACTORY')
        self.executor = executor
        self.factory = factory
        self.provider = provider
        self.operations = frozenset(ops)
        self.target_ready = target_ready
        self.baseline_ready = target_ready
        self.min_ready = min_ready
        self.max_warm = max_warm
        self.host_ceiling = max_warm
        self.adaptive = adaptive
        self.idle_downshift_s = float(idle_downshift_s)
        self.warmup_timeout_s = float(warmup_timeout_s)
        self.max_idle_s = float(max_idle_s)
        self._last_request = time.monotonic()
        self._last_downshift = self._last_request
        self._cv = threading.Condition(threading.RLock())
        self._idle: list[_WarmSlot] = []
        self._busy: dict[object,_WarmSlot] = {}
        self._warming = 0
        self._warming_slots: set[int] = set()
        self._active_prepares: dict[int,_WarmSlot] = {}
        self._threads: set[threading.Thread] = set()
        self._started = False
        self._closed = False
        self.hits = 0
        self.misses = 0
        self.warmup_failures = 0
        self.upshifts = 0
        self.downshifts = 0
        self.peak_warm = 0
        self.expired_reaped = 0
        self.crashed_reaped = 0

    def _total(self):
        return len(self._idle) + len(self._busy) + self._warming

    def _fill_locked(self):
        while (self._started and not self._closed
               and len(self._idle)+self._warming < self.target_ready
               and self._total() < self.max_warm
               and self._total() < self.host_ceiling):
            if not _GLOBAL_WARM_BUDGET.reserve():
                break
            self._warming += 1
            self.peak_warm = max(self.peak_warm, self._total())
            thread = threading.Thread(target=self._prepare, daemon=True,
                                      name='cognitum-sandbox-prewarm')
            self._threads.add(thread)
            try:
                thread.start()
            except RuntimeError:
                self._threads.remove(thread)
                self._warming -= 1
                _GLOBAL_WARM_BUDGET.release()
                self.warmup_failures += 1
                break

    def _prepare(self):
        slot = None
        acquired = False
        try:
            with self._cv:
                if self._closed:
                    return
            proc, root = self.executor._launch_contained(
                warm_provider=self.provider,
                allow_kan=(self.provider == 'specialists'))
            slot = _WarmSlot(proc,root,time.monotonic())
            with self._cv:
                self._warming_slots.add(id(slot))  # id avoids mutable slot hashing
                # Track concrete slots for shutdown separately.
                self._active_prepares[id(slot)] = slot
            acquired = _read_ready(proc,self.warmup_timeout_s)
        except BaseException:
            acquired = False
        finally:
            with self._cv:
                self._warming -= 1
                if slot is not None:
                    self._warming_slots.discard(id(slot))
                    self._active_prepares.pop(id(slot),None)
                if (acquired and not self._closed and
                        len(self._idle) < self.target_ready and
                        self._total() < self.host_ceiling):
                    slot.ready_at=time.monotonic()
                    self._idle.append(slot)
                    slot=None
                elif not self._closed:
                    self.warmup_failures += 1
                self._threads.discard(threading.current_thread())
                self._cv.notify_all()
            # NEVER release the global reservation before the OS process dies.
            if slot is not None:
                _reap(slot)
            if slot is not None or not acquired:
                _GLOBAL_WARM_BUDGET.release()
                with self._cv:
                    # Never spin-spawn endlessly if namespace setup or
                    # resource limits are unavailable. A trusted later
                    # maintenance tick or next request may retry.
                    if acquired and not self._closed:
                        self._fill_locked()
                    self._cv.notify_all()

    def start(self):
        with self._cv:
            if self._closed:
                raise RuntimeError('POOL_CLOSED')
            self._started=True
            self._fill_locked()

    def wait_ready(self, seconds=12.0, *, minimum=None):
        if minimum is None:
            minimum=self.target_ready
        if type(minimum) is not int or minimum < 1 or minimum > self.max_warm:
            raise ValueError('INVALID_READY_TARGET')
        deadline=time.monotonic()+seconds
        with self._cv:
            while not self._closed and len(self._idle)<minimum:
                remaining=deadline-time.monotonic()
                if remaining<=0:
                    break
                self._cv.wait(remaining)
            return not self._closed and len(self._idle)>=minimum

    def _approved(self,factory,operation):
        return (factory is self.factory and operation in self.operations and
                not (operation=='specialist.kan' and self.executor.approved_kan_sha256 is None))

    def execute(self,factory,operation,payload,timeout_ms):
        """One contained standby, else P7 contained cold fallback; never unsandboxed."""
        if not self._approved(factory,operation):
            return 'unavailable',None
        with self._cv:
            if self._closed:
                return 'unavailable',None
            # A caller that explicitly injected a pool may arrive before the
            # trusted host's explicit prewarm; cold fallback must still seed
            # replacement standbys, without waiting on the request path.
            self._started=True
            slot = self._idle.pop() if self._idle else None
            if slot is not None:
                self._busy[slot.process]=slot
                self.hits+=1
            else:
                self.misses+=1
            self._last_request=time.monotonic()
            if self.target_ready<min(self.baseline_ready,self.host_ceiling):
                self.target_ready=min(self.baseline_ready,self.host_ceiling)
            if (self.adaptive and slot is None and self.target_ready < self.host_ceiling):
                self.target_ready+=1
                self.upshifts+=1
            self._fill_locked()
        if slot is None:
            # Cold overflow must remain inside P7 namespaces and cold budget.
            return self.executor.execute(factory,operation,payload,timeout_ms)
        try:
            if time.monotonic()-slot.ready_at > self.max_idle_s or slot.process.poll() is not None:
                # A stale/crashed standby is not reusable. Fail over ONLY to
                # the already verified P7 contained cold launcher.
                return self.executor.execute(factory,operation,payload,timeout_ms)
            try:
                raw=json.dumps({'kind':'cognitum','operation':operation,'payload':payload},
                               separators=(',',':'),allow_nan=False).encode('ascii')+b'\n'
            except (ValueError,TypeError,OverflowError):
                return 'invalid_input',None
            if len(raw)>MAX_FRAME_BYTES:
                return 'invalid_input',None
            status,result=self.executor._exchange(slot.process,raw,timeout_ms/1000)
            with self._cv:
                if self._closed:
                    return 'unavailable',None
            return status,result
        except (OSError,ValueError,TypeError):
            return 'unavailable',None
        finally:
            _reap(slot)
            with self._cv:
                self._busy.pop(slot.process,None)
                _GLOBAL_WARM_BUDGET.release()
                self._fill_locked()
                self._cv.notify_all()

    def snapshot(self):
        with self._cv:
            return {'idle':len(self._idle),'warming':self._warming,
                    'busy':len(self._busy),'warm_total':self._total(),
                    'target_ready':self.target_ready,'baseline_ready':self.baseline_ready,
                    'min_ready':self.min_ready,'max_warm':self.max_warm,
                    'host_ceiling':self.host_ceiling,'hits':self.hits,'misses':self.misses,
                    'upshifts':self.upshifts,'downshifts':self.downshifts,
                    'peak_warm':self.peak_warm,
                    'expired_reaped':self.expired_reaped,
                    'crashed_reaped':self.crashed_reaped,
                    'global_warm_budget':_GLOBAL_WARM_BUDGET.snapshot(),
                    'closed':self._closed}

    def set_target_ready(self,value,*,host_override=True):
        """Trusted-host target; reap before reallocation of global reservations.

        Removed idle slots still count globally until their OS process exits.
        A concurrent close never launches replacements after shutdown.
        """
        if type(value) is not int or not self.min_ready<=value<=self.max_warm:
            raise ValueError('INVALID_READY_TARGET')
        to_reap=[]
        with self._cv:
            if self._closed:
                raise RuntimeError('POOL_CLOSED')
            if host_override:
                self.host_ceiling=value
            if value>self.host_ceiling:
                raise ValueError('TARGET_EXCEEDS_HOST_CEILING')
            self.target_ready=value
            while self._idle and len(self._idle)+self._warming>value:
                to_reap.append(self._idle.pop())
            self._cv.notify_all()
        for slot in to_reap:
            _reap(slot)
            _GLOBAL_WARM_BUDGET.release()
        with self._cv:
            if not self._closed:
                self._fill_locked()
            self._cv.notify_all()
        return self.snapshot()

    def maintain(self):
        """Reap stale idle namespaces, then refill without exceeding cap.

        P8 checked expiry only when dispatching a request. That let old idle
        processes occupy the warm budget forever and made the first request
        after long inactivity unnecessarily cold. The trusted host owns this
        periodic lifecycle action; there is no hidden scheduler.
        """
        to_reap=[]
        with self._cv:
            if self._closed:
                return self.snapshot()
            now=time.monotonic()
            quiet=now-max(self._last_request,self._last_downshift)
            if (self.adaptive and quiet>=self.idle_downshift_s and
                    not self._busy and self.target_ready>self.min_ready):
                self.target_ready-=1
                self.downshifts+=1
                self._last_downshift=now
            retained=[]
            for slot in self._idle:
                if slot.process.poll() is not None:
                    self.crashed_reaped+=1
                    to_reap.append(slot)
                elif now-slot.ready_at>=self.max_idle_s:
                    self.expired_reaped+=1
                    to_reap.append(slot)
                else:
                    retained.append(slot)
            self._idle=retained
            while len(self._idle)>self.target_ready:
                to_reap.append(self._idle.pop())
            # No refill yet: reservations from to_reap remain held until
            # their actual namespace process trees have been killed/reaped.
            self._cv.notify_all()
        for slot in to_reap:
            _reap(slot)
            _GLOBAL_WARM_BUDGET.release()
        with self._cv:
            if not self._closed:
                self._fill_locked()
            self._cv.notify_all()
        return self.snapshot()

    def close(self):
        with self._cv:
            if self._closed:
                return
            self._closed=True
            idle=self._idle
            self._idle=[]
            active=list(self._busy.values())+list(self._active_prepares.values())
            threads=list(self._threads)
            self._cv.notify_all()
        for slot in idle:
            _reap(slot)
            _GLOBAL_WARM_BUDGET.release()
        # Terminate but let each operating/prewarming thread perform the
        # single final reap and reservation release to avoid double-close.
        for slot in active:
            try:
                LinuxNamespaceExecutor._terminate_group(slot.process)
            except (OSError,ValueError):
                pass
        for thread in threads:
            if thread is not threading.current_thread():
                thread.join(timeout=self.warmup_timeout_s+3)
        with self._cv:
            deadline=time.monotonic()+3.0
            while self._busy and time.monotonic()<deadline:
                self._cv.wait(deadline-time.monotonic())

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.close()
