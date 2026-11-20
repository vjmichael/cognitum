"""Fresh process per case; measurements exclude independent reference."""
import argparse,json,time,hashlib
from pathlib import Path
from cognitum.research import kan_tensor_ritz as s
from tools.cog04s.fixtures import CASES
from tools.cog04p.profile import memory

def main(case,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    before,method=memory();cpu=time.process_time_ns();start=time.perf_counter_ns()
    rows=s.history(CASES[case])
    elapsed=time.perf_counter_ns()-start;cpu=time.process_time_ns()-cpu;peak,check=memory()
    s.need(peak>=before>0 and method==check and cpu>0 and elapsed>0,'native counters')
    history=[]
    for i,(raw,row) in enumerate(rows):
        name=f'level-{i}.exact.json';(out/name).write_bytes(raw)
        history.append(dict(**row,matrix_file=name,matrix_sha256=hashlib.sha256(raw).hexdigest()))
    print(json.dumps(dict(case=case,rows=history,elapsed_ns=elapsed,process_cpu_ns=cpu,peak_bytes=peak,
        before_peak_bytes=before,memory_method=method,resource_scope='four-level solve, peak lifetime includes imports, oracle excluded'),allow_nan=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',choices=CASES,required=True);p.add_argument('--out',required=True)
    a=p.parse_args();main(a.case,a.out)
