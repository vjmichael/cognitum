"""Fresh subprocess measurement: process CPU and OS lifetime peak resident/working-set bytes."""
import argparse,hashlib,json,os,sys,time
from pathlib import Path

def memory():
    if sys.platform.startswith('linux'):
        import resource
        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*1024,'linux ru_maxrss lifetime peak RSS'
    if sys.platform=='win32':
        import ctypes as c
        from ctypes import wintypes as w
        class Counters(c.Structure):
            _fields_=[('cb',w.DWORD),('PageFaultCount',w.DWORD)]+[(k,c.c_size_t) for k in
                ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage',
                 'QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
        kernel=c.WinDLL('kernel32',use_last_error=True);psapi=c.WinDLL('psapi',use_last_error=True)
        kernel.GetCurrentProcess.restype=w.HANDLE
        psapi.GetProcessMemoryInfo.argtypes=(w.HANDLE,c.POINTER(Counters),w.DWORD)
        psapi.GetProcessMemoryInfo.restype=w.BOOL
        v=Counters();v.cb=c.sizeof(v)
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),c.byref(v),v.cb):
            raise OSError(c.get_last_error(),'GetProcessMemoryInfo failed')
        return int(v.PeakWorkingSetSize),'windows lifetime peak working set'
    raise ValueError('unqualified native memory backend')

def main(kind,left,right,out):
    # Identical import baseline for both operation classes, single BLAS thread configured by parent.
    from cognitum.research import kan_function_metrics as o,kan_weak_form as p
    a,b=Path(left).read_bytes(),Path(right).read_bytes()
    before,method=memory();cpu=time.process_time_ns();start=time.perf_counter_ns()
    if kind=='O':
        raw=o.compare(a,b);extra={}
    elif kind=='P':
        raw,extra=p.spectrum((a,b))
    else:raise ValueError('unknown operation')
    elapsed=time.perf_counter_ns()-start;cpu=time.process_time_ns()-cpu
    peak,check=memory()
    if method!=check or not (peak>=before>0 and elapsed>0 and cpu>0):
        raise ValueError('invalid native resource counters')
    out=Path(out);out.write_bytes(raw)
    print(json.dumps(dict(kind=kind,elapsed_ns=elapsed,process_cpu_ns=cpu,peak_bytes=peak,
        before_peak_bytes=before,memory_method=method,peak_scope='whole fresh process including imports',
        source_left_sha256=hashlib.sha256(a).hexdigest(),source_right_sha256=hashlib.sha256(b).hexdigest(),
        result_sha256=hashlib.sha256(raw).hexdigest(),spectrum=extra),allow_nan=False))

if __name__=='__main__':
    q=argparse.ArgumentParser()
    for name in ('kind','left','right','out'):q.add_argument('--'+name,required=True)
    a=q.parse_args();main(a.kind,a.left,a.right,a.out)
