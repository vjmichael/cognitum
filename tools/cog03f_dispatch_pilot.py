"""One binary, exact modes, dimension/batch sweeps; virtualized CPU only."""
import argparse,hashlib,json,platform,shutil,subprocess,tempfile,time,os,contextlib
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits,threadpool_info
from cognitum.research.hdc_hardware import Native,pack
ROOT=Path(__file__).resolve().parents[1]

def build(directory):
    cc=shutil.which('gcc') or shutil.which('clang')
    if not cc:raise RuntimeError('compiler missing')
    dll=Path(directory)/('dispatch.dll' if os.name=='nt' else 'dispatch.so')
    cmd=[cc,'-std=c11','-O3','-Wall','-Wextra','-Werror','-shared',*(['-fPIC'] if os.name!='nt' else []),str(ROOT/'hardware/hdc/packed.c'),'-o',str(dll)]
    subprocess.run(cmd,check=True)
    return Native(dll),dict(command=cmd,compiler=subprocess.check_output([cc,'--version'],text=True).splitlines()[0],binary_sha256=hashlib.sha256(dll.read_bytes()).hexdigest())

def measure(func,n=7):
    result=func();measurements=[]
    for _ in range(n):
        start=time.perf_counter_ns();func();measurements.append(time.perf_counter_ns()-start)
    return result,float(np.median(measurements)/1e6),measurements

def run(quick=False,build_dir=None):
    context=tempfile.TemporaryDirectory(ignore_cleanup_errors=os.name=='nt') if build_dir is None else contextlib.nullcontext(build_dir)
    with context as td,threadpool_limits(limits=1):
        Path(td).mkdir(parents=True,exist_ok=True)
        native,build_meta=build(td);rows=[]
        ds=[65,256,2048,4097] if quick else [64,128,256,512,1024,2048,4096,10000,20001,65536]
        shapes=[(1,8),(16,32)] if quick else [(1,1),(1,64),(128,64)]
        for d in ds:
            for nq,np_ in shapes:
                rng=np.random.default_rng(d+nq+np_);a=rng.integers(0,2,(nq,d),dtype=np.uint8);b=rng.integers(0,2,(np_,d),dtype=np.uint8)
                q,p=pack(a),pack(b);aa=1-2*a.astype(np.float32);bb=1-2*b.astype(np.float32);ref=aa@bb.T
                for mode,name in [(0,'swar'),(1,'popcnt'),(2,'avx512'),(3,'auto'),(None,'dense_blas')]:
                    if mode is not None and native.selected(d,mode)<0:continue
                    fn=(lambda:aa@bb.T) if mode is None else (lambda:native.scores(q,p,d,mode))
                    pred,ms,samples=measure(fn);assert np.array_equal(pred,ref)
                    rows.append(dict(d=d,queries=nq,prototypes=np_,method=name,selected=native.selected(d,mode) if mode is not None else None,ms=ms,samples_ns=samples,operand_bytes=q.nbytes+p.nbytes if mode is not None else aa.nbytes+bb.nbytes,parity=True))
                pred,ms,samples=measure(lambda:native.scores(pack(a),pack(b),d));assert np.array_equal(pred,ref)
                rows.append(dict(d=d,queries=nq,prototypes=np_,method='auto_including_pack',selected=native.selected(d),ms=ms,samples_ns=samples,parity=True,operand_bytes=q.nbytes+p.nbytes,unpacked_input_bytes=a.nbytes+b.nbytes))
        return dict(rows=rows,capabilities=native.capabilities,build=build_meta,platform=platform.platform(),threadpools=threadpool_info(),scope='One CPU thread; warm resident operands except explicit pack path; no end-to-end speed, physical device or energy claim')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--quick',action='store_true');p.add_argument('--out',required=True);a=p.parse_args();Path(a.out).write_text(json.dumps(run(a.quick,Path(a.out).parent/'f-dispatch-build'),indent=2)+'\n',encoding='utf8')
