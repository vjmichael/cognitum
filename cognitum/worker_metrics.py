"""Opt-in reference-worker native observer; no execution or authority changes.

Observe the exact multiprocessing child created by the frozen worker.execute
on the calling thread. No global monkeypatch, process-list guessing, payload
inspection, or change to the result/trace protocol. Profiling overhead applies
only to instrumented calls. Never use this telemetry for admission or proof
of OS containment.
"""
import multiprocessing.process
import os
import sys
import math
import time
import threading
from . import worker


class _Linux:
    kind = 'linux_proc_sampled_lower_bound'
    def __init__(self, process):
        self.fd = os.open('/proc/'+str(process.pid), os.O_RDONLY | os.O_DIRECTORY)
        self.hz = os.sysconf('SC_CLK_TCK')

    def _read(self, name):
        with os.fdopen(os.open(name, os.O_RDONLY, dir_fd=self.fd), 'r', encoding='ascii') as f:
            return f.read()

    def sample(self):
        cpu = peak = None
        try:
            fields = self._read('stat').rsplit(')', 1)[1].split()
            cpu = (int(fields[11])+int(fields[12]))/self.hz
        except (OSError, ValueError, IndexError):
            pass
        try:
            for line in self._read('status').splitlines():
                if line.startswith('VmHWM:'):
                    peak = int(line.split()[1])*1024
                    break
        except (OSError, ValueError, IndexError):
            pass
        return cpu, peak, False

    def close(self):
        os.close(self.fd)


class _Windows:
    kind = 'windows_retained_handle_peak_working_set'
    def __init__(self, process):
        import ctypes as c
        from ctypes import wintypes as w
        self.c, self.w = c, w
        self.k = k = c.WinDLL('kernel32', use_last_error=True)
        self.p = p = c.WinDLL('psapi', use_last_error=True)
        class Counters(c.Structure):
            _fields_ = [('cb', w.DWORD), ('PageFaultCount', w.DWORD)] + [
                (name, c.c_size_t) for name in ('PeakWorkingSetSize','WorkingSetSize',
                'QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage',
                'QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
        self.Counters = Counters
        k.GetCurrentProcess.restype = w.HANDLE
        k.DuplicateHandle.argtypes = [w.HANDLE,w.HANDLE,w.HANDLE,c.POINTER(w.HANDLE),w.DWORD,w.BOOL,w.DWORD]
        k.DuplicateHandle.restype = w.BOOL
        k.CloseHandle.argtypes = [w.HANDLE]; k.CloseHandle.restype = w.BOOL
        k.GetProcessTimes.argtypes = [w.HANDLE]+[c.POINTER(w.FILETIME)]*4
        k.GetProcessTimes.restype = w.BOOL
        k.WaitForSingleObject.argtypes = [w.HANDLE,w.DWORD]; k.WaitForSingleObject.restype = w.DWORD
        p.GetProcessMemoryInfo.argtypes = [w.HANDLE,c.POINTER(Counters),w.DWORD]
        p.GetProcessMemoryInfo.restype = w.BOOL
        # The actual Process.sentinel is the native child HANDLE on Windows;
        # copy it before multiprocessing closes its own handle.
        handle = w.HANDLE(); own = k.GetCurrentProcess()
        if not k.DuplicateHandle(own, w.HANDLE(int(process.sentinel)), own,
                                 c.byref(handle), 0, False, 2):
            raise c.WinError(c.get_last_error())
        self.handle = handle

    def sample(self):
        c,w,k = self.c,self.w,self.k
        creation,exit,kernel,user = (w.FILETIME() for _ in range(4))
        ended = k.WaitForSingleObject(self.handle,0)==0
        cpu = peak = None
        if k.GetProcessTimes(self.handle,*[c.byref(v) for v in (creation,exit,kernel,user)]):
            ticks = lambda v: (v.dwHighDateTime<<32)|v.dwLowDateTime
            cpu = (ticks(kernel)+ticks(user))/10_000_000
        counter = self.Counters(); counter.cb = c.sizeof(counter)
        if self.p.GetProcessMemoryInfo(self.handle,c.byref(counter),counter.cb):
            peak = int(counter.PeakWorkingSetSize)
        return cpu,peak,ended and cpu is not None

    def close(self):
        self.k.CloseHandle(self.handle)


class _Monitor:
    def __init__(self, process):
        self.pid = process.pid
        self.source = _Linux(process) if sys.platform.startswith('linux') else _Windows(process)
        self.stop = threading.Event()
        self.cpu = self.peak = None
        self.complete = False
        self.samples = 0
        self.thread = threading.Thread(target=self._loop,daemon=True)
        try:
            self._sample(); self.thread.start()
        except BaseException:
            self.source.close(); raise

    def _sample(self):
        cpu,peak,final = self.source.sample()
        if cpu is not None and math.isfinite(cpu) and cpu>=0:
            self.cpu = cpu if self.cpu is None else max(self.cpu,cpu)
            self.complete |= final
        if peak is not None and peak>0:
            self.peak = peak if self.peak is None else max(self.peak,peak)
        if cpu is not None or peak is not None:
            self.samples += 1

    def _loop(self):
        while not self.stop.wait(.005):
            self._sample()

    def finish(self):
        self.stop.set();self.thread.join()
        try:
            self._sample()
            return {'status':'measured' if self.cpu is not None and self.peak is not None else 'partial',
                    'method':self.source.kind,'pid':self.pid,'samples':self.samples,
                    'cpu_seconds':self.cpu,'cpu_final':self.complete,
                    'peak_resident_bytes_observed':self.peak,'peak_is_lower_bound':True}
        finally:
            self.source.close()


def observe_one(fn):
    """Execute one synchronous trusted call unchanged; return result, telemetry.

    Explicit unsupported/absent/ambiguous metrics never imply zero usage.
    A failed call still propagates its original exception. An unrelated or
    nested profiling session is not modified. This observer is intended for
    one-worker-at-a-time research trials on native Windows/Linux.
    """
    if sys.getprofile() is not None:
        raise ValueError('existing profiler; observer not installed')
    if not (sys.platform.startswith('linux') or sys.platform=='win32'):
        raise ValueError('native observation unsupported')
    monitors=[]; missed=0
    start_code=multiprocessing.process.BaseProcess.start.__code__
    worker_code=worker.execute.__code__
    def profile(frame,event,arg):
        nonlocal missed
        if event!='return' or frame.f_code is not start_code:
            return
        parent=frame.f_back;process=frame.f_locals.get('self')
        if parent is None or parent.f_code is not worker_code or parent.f_locals.get('process') is not process:
            return
        try:
            if process.pid is None:
                missed+=1;return
            # Limit resource consumption even if the caller violates single-call scope.
            if len(monitors)>=2:
                missed+=1;return
            monitors.append(_Monitor(process))
        except (OSError, ValueError, RuntimeError, AttributeError):
            missed+=1
    started=time.perf_counter_ns();records=[]
    sys.setprofile(profile)
    try:
        result=fn()
    finally:
        sys.setprofile(None)
        for monitor in monitors:
            records.append(monitor.finish())
    elapsed=(time.perf_counter_ns()-started)/1e6
    if len(records)!=1 or missed:
        return result,{'status':'unavailable' if not records else 'ambiguous',
                       'observed_workers':len(records),'missed_workers':missed,'observed_call_ms':elapsed}
    return result,dict(records[0],observed_workers=1,missed_workers=0,observed_call_ms=elapsed)
