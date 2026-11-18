"""Local CPU measurements only; no physical device or synthesis claims."""
import argparse, subprocess, json, time, platform, os, tempfile, shutil, hashlib
from pathlib import Path
import numpy as np
from sklearn.datasets import load_digits,load_wine
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits, threadpool_info
from cognitum.research.hdc_hardware import *
from cognitum.research.hdc_shared import Shared
ROOT=Path(__file__).resolve().parents[1]

def timing(fn,repeats=5):
    first=fn();samples=[]
    for _ in range(repeats):
        s=time.perf_counter_ns();fn();samples.append(time.perf_counter_ns()-s)
    return first,float(np.median(samples)/1e6),samples

def compile_native(root,flag):
    out=root/('packed'+flag.replace('-','_')+'.so');cmd=['gcc','-std=c11','-O3','-Wall','-Wextra','-Werror','-fPIC','-shared',str(ROOT/'hardware/hdc/packed.c'),'-o',str(out)]
    subprocess.run(cmd,check=True);asm=subprocess.check_output(['objdump','-d',str(out)],text=True)
    return Native(out),dict(command=cmd,popcnt_instruction=any('popcnt' in line and '\t' in line and ('popcnt ' in line or 'popcnt\t' in line) for line in asm.splitlines()))

def primitive(root):
    portable,pm=compile_native(root,'');rows=[];fm={'runtime_dispatch':True,'caps':portable.capabilities}
    for d in [256,512,1024,2048,4096,10000,20001]:
        r=np.random.default_rng(d);a=r.integers(0,2,(128,d),dtype=np.uint8);b=r.integers(0,2,(64,d),dtype=np.uint8);q,p=pack(a),pack(b)
        af,bf=(1-2*a.astype(np.float32)),(1-2*b.astype(np.float32));oracle=af@bf.T
        for name,fn,nb in [('dense_float32_blas',lambda:af@bf.T,af.nbytes+bf.nbytes),('packed_numpy',lambda:scores(q,p,d),q.nbytes+p.nbytes),('portable_c',lambda:portable.scores(q,p,d,0),q.nbytes+p.nbytes),('auto_c',lambda:portable.scores(q,p,d,3),q.nbytes+p.nbytes)]:
            got,ms,samples=timing(fn);assert np.array_equal(got,oracle)
            rows.append(dict(d=d,method=name,queries=len(a),classes=len(b),median_ms=ms,repetitions_ns=samples,operand_bytes=nb,output_bytes=got.nbytes,parity=True))
    return rows,dict(portable=pm,popcnt=fm)

def shared_pilot():
    rows=[]
    for ds,load in [('digits',load_digits),('wine',load_wine)]:
        x,y=load(return_X_y=True)
        for seed in [3101,3109]:
            ix,tx=train_test_split(np.arange(len(y)),test_size=.3,stratify=y,random_state=seed);sc=StandardScaler().fit(x[ix]);z=(sc.transform(x)/np.sqrt(x.shape[1])).astype(np.float32)
            # Fixed randomized independent groups. Drop incomplete group, same ordering in each arm.
            for d in [256,1024,4096]:
                for k in [2,4]:
                    rng=np.random.default_rng(seed+k);t=rng.permutation(tx)[:len(tx)//k*k].reshape(-1,k)
                    tr=z[ix];model=Shared(z.shape[1],d,k,len(np.unique(y)),seed,bandwidth=.7).fit(tr,y[ix],seed+1)
                    a=z[t];truth=y[t];split=hashlib.sha256(t.astype('<i8').tobytes()).hexdigest()
                    def predict(mode,f):
                        # Cap each prediction slab at 32 groups, including fallback ranking within group slab.
                        pred=[];n=0
                        for i in range(0,len(a),32):
                            p,c=model.predict(a[i:i+32],mode,f);pred.append(p);n+=c
                        return np.concatenate(pred),n
                    ref,_=predict('batch',0)
                    for name,mode,f in [('sequential','sequential',0),('batched','batch',0),('shared','shared',0),('fallback25','shared',.25),('fallback50','shared',.5),('fallback100','shared',1.)]:
                        (p,c),ms,samples=timing(lambda:predict(mode,f),3)
                        agree=float((p==ref).mean());assert mode=='shared' or agree==1.;assert f!=1 or agree==1.
                        rows.append(dict(dataset=ds,seed=seed,d=d,slots=k,method=name,n=t.size,correct=int((p==truth).sum()),agreement=agree,encoder_calls=int(c),median_ms=ms,repetitions_ns=samples,model_bytes=model.bytes,split_sha256=split))
    return rows

def adaptive_pilot():
    rows=[]
    for ds,load in [('digits',load_digits),('wine',load_wine)]:
        x,y=load(return_X_y=True)
        for seed in [3101,3109]:
            tr,te=train_test_split(np.arange(len(y)),test_size=.3,stratify=y,random_state=seed);tr,ca=train_test_split(tr,test_size=.25,stratify=y[tr],random_state=seed+1)
            a=StandardScaler().fit(x[tr]).transform(x).astype(np.float32)
            for d in [256,1024,4096]:
                rg=np.random.default_rng(seed);w=rg.normal(size=(a.shape[1],d)).astype(np.float32);bits=(a@w>=0).astype(np.uint8);p=pack(np.stack([(bits[tr][y[tr]==k].sum(0)*2>=sum(y[tr]==k)) for k in np.unique(y)]));q=pack(bits)
                exact=scores(q[te],p,d).argmax(1);cal=scores(q[ca],p,d).argmax(1)
                start=time.perf_counter();candidates=[]
                for nw in sorted(set([max(1,d//64//4),max(1,d//64//2),max(1,d//64*3//4),d//64])):
                    partial=scores(q[ca,:nw],p[:,:nw],nw*64);mx=np.sort(partial,axis=1);margin=mx[:,-1]-mx[:,-2]
                    for threshold in [0,4,8,16,32,64,128]:
                        ok=margin>threshold;pred=partial.argmax(1);pred[~ok]=cal[~ok];err=float((pred!=cal).mean());work=nw+(~ok).mean()*(d//64-nw)
                        if err<=.01:candidates.append((work,nw,threshold,err))
                _,nw,threshold,cerr=min(candidates);tune_ms=(time.perf_counter()-start)*1e3
                for name,n in [('certified_half',max(1,d//64//2)),('certified_75',max(1,d//64*3//4)),('calibrated',nw)]:
                    if name=='calibrated':
                        def fn():
                            part=scores(q[te,:n],p[:,:n],n*64);mx=np.sort(part,axis=1);ok=mx[:,-1]-mx[:,-2]>threshold;pred=part.argmax(1);
                            if (~ok).any() and n*64<d:pred[~ok]=(part[~ok]+scores(q[te][~ok,n:],p[:,n:],d-n*64)).argmax(1)
                            return pred,ok
                    else:fn=lambda:safe_prefix(q[te],p,d,n)
                    (pred,ok),ms,_=timing(fn,3);dis=float((pred!=exact).mean());assert name=='calibrated' or dis==0
                    rows.append(dict(dataset=ds,seed=seed,d=d,method=name,words=n,threshold=int(threshold) if name=='calibrated' else 2*(d-n*64),calibration_disagreement=cerr if name=='calibrated' else 0,test_disagreement=dis,correct=int((pred==y[te]).sum()),exact_correct=int((exact==y[te]).sum()),n=len(te),early_fraction=float(ok.mean()),mean_word_steps=float(n+(~ok).mean()*(d//64-n)),median_ms=ms,tune_ms=tune_ms))
    return rows

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--part',choices=['primitive','shared','adaptive','all'],default='all');a=p.parse_args();out={'scope':'single CPU thread; warm resident operands; excludes packing/model fitting except explicit tuning; native kernels locally compiled, no FPGA synthesis, link, power or timing','python':platform.python_version(),'numpy':np.__version__,'platform':platform.platform()}
    with threadpool_limits(limits=1),tempfile.TemporaryDirectory() as td:
        if a.part in ('primitive','all'):out['primitive'],out['native']=primitive(Path(td))
        if a.part in ('shared','all'):out['shared']=shared_pilot()
        if a.part in ('adaptive','all'):out['adaptive']=adaptive_pilot()
        out['threadpools']=threadpool_info()
    out['resources']=[resources(d,c,l) for d in [256,512,1024,2048,4096,10000] for c in [64,256] for l in [1,4,8,16]]
    Path(a.out).write_text(json.dumps(out,indent=2)+'\n')
if __name__=='__main__':main()
