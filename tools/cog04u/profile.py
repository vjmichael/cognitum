"""Matched exact assembly benchmark. One fresh native process per route/case."""
import argparse,hashlib,json,time
from fractions import Fraction as Q
from cognitum.research import kan_certified_spectrum as u
from tools.cog04r.fixtures import CASES
from tools.cog04p.profile import memory

def main(case,route):
    p=CASES[case];fn=u.r.assemble if route=='baseline' else u.assemble_supported
    meshes=[tuple(Q(i,n) for i in range(1,n)) for n in (2,4,8,16)]
    baseline,method=memory();samples=[];expected=None
    for repeat in range(3):
        before,check=memory();cpu=time.process_time_ns();start=time.perf_counter_ns()
        data=[fn(p,c) for c in meshes]
        elapsed=time.perf_counter_ns()-start;cpu=time.process_time_ns()-cpu;peak,check2=memory()
        hashes=[hashlib.sha256(x).hexdigest() for x in data]
        if expected is None:expected=hashes
        u.need(hashes==expected and method==check==check2 and peak>=before>=baseline>0 and elapsed>0 and cpu>0,'profile repeat')
        samples.append(dict(elapsed_ns=elapsed,process_cpu_ns=cpu,before_peak_bytes=before,peak_bytes=peak))
    print(json.dumps(dict(case=case,route=route,baseline_peak_bytes=baseline,memory_method=method,
        samples=samples,matrix_hashes=expected,scope='four meshes exact assembly, no eigensolve or oracle; lifetime peak includes imports'),allow_nan=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',choices=CASES,required=True);p.add_argument('--route',choices=('baseline','optimized'),required=True)
    a=p.parse_args();main(a.case,a.route)
