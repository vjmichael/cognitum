"""Matched CPU cached-feature projection benchmark; research only."""
import argparse,json,platform,tempfile,time,os
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
from tools.h12_projection.projection import Plan,Sparse,Hadamard,words,unpack
from tools.h12_projection.symbolic import trial
from tools.cog03f_dispatch_pilot import build

def measure(fn):
    result=fn();ts=[]
    for _ in range(3):
        t=time.perf_counter_ns();result=fn();ts.append(time.perf_counter_ns()-t)
    return result,dict(median_ms=float(np.median(ts)/1e6),samples_ns=ts)
def workload(x,t,y,truth,ds,name,native,cal=None):
    cal=x if cal is None else cal;mu=cal.mean(0);sig=np.maximum(cal.std(0),.05);x,t=(np.clip((a-mu)/sig,-5,5).astype(np.float32) for a in (x,t));rows=[];f=x.shape[1]
    for d in ds:
        p=Plan(f,d);w=p.dense();packed=p.packed();s=Sparse(f,d,min(f,16),1201);h=Hadamard(f,d,1201)
        arms={'dense':lambda a:p.reference(a,w),'packed_weights':lambda a:p.encode(a,packed),'seed_regenerate':lambda a:p.encode(a),'sparse16':s.encode,'hadamard':h.encode}
        b=min(128,len(t));ref=p.reference(t,w);tr=p.reference(x,w);base=1-2*unpack(ref,d)[:b].astype(np.float64);base_sim=base@base.T/d
        for k,e in arms.items():
            tq=e(x);q=e(t);labels,ix=np.unique(y,return_inverse=True);st=np.zeros((len(labels),d),np.int32);np.add.at(st,ix,1-2*unpack(tq,d).astype(np.int32));proto=words(st<0)
            score=native.scores(q,proto,d);dense_score=(1-2*unpack(q,d).astype(np.int32))@(1-2*unpack(proto,d).astype(np.int32)).T;assert np.array_equal(score,dense_score)
            same=bool(np.array_equal(q,ref) and np.array_equal(tq,tr));assert same if k in ('dense','packed_weights','seed_regenerate') else True
            bits=1-2*unpack(q,d)[:b].astype(np.float64);sim=bits@bits.T/d;timings=[]
            for batch in sorted({1,min(16,len(t)),b}):
                _,enc=measure(lambda:e(t[:batch]));_,total=measure(lambda:labels[native.scores(e(t[:batch]),proto,d).argmax(1)]);timings.append(dict(batch=batch,projection=enc,feature_to_class=total))
            rows.append(dict(workload=name,f=f,d=d,arm=k,train=len(x),test=len(t),classes=len(labels),accuracy=float(np.mean(labels[score.argmax(1)]==truth)),same_codebook_parity=same,score_parity=True,similarity_rmse=float(np.sqrt(np.mean((sim-base_sim)**2))),retained_projection_array_bytes={'dense':w.nbytes,'packed_weights':packed.nbytes,'seed_regenerate':0,'sparse16':s.indices.nbytes+s.signs.nbytes,'hadamard':0}[k],head_bytes=proto.nbytes,timings=timings))
        print(name,d,'complete',flush=True)
    return rows

def run(data=None,checkpoint=None,quick=False):
    from sklearn.datasets import load_digits
    from sklearn.model_selection import train_test_split
    r=load_digits();x,t,y,z=train_test_split(r.data.astype(np.float32),r.target,test_size=.25,stratify=r.target,random_state=1201);rows=[];mathrows=[];assets={}
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=os.name=='nt') as td,threadpool_limits(limits=1):
        native,meta=build(td);rows+=workload(x,t,y,z,[256,1024] if quick else [256,1024,4096],'digits',native)
        if not quick:
            rng=np.random.default_rng(1201);yy=np.repeat(np.arange(50),4);centers=rng.normal(size=(50,1280)).astype(np.float32);xx=centers[yy]+rng.normal(size=(len(yy),1280)).astype(np.float32);zz=np.repeat(np.arange(50),2);tt=centers[zz]+rng.normal(size=(len(zz),1280)).astype(np.float32);rows+=workload(xx,tt,yy,zz,[1024,4096],'synthetic_1280',native)
        for d in ([256,1024] if quick else [256,1024,4096]):
            for k in ([1,9] if quick else [1,5,17,33,65]):mathrows.append(trial(d,k,128,12 if quick else 100,1201+d+k))
        if data or checkpoint:
            if not data or not checkpoint:raise ValueError('both paths required')
            import torch
            from tools.cog03f2_core50 import read_sample,digest
            from tools.cog03e2g_cifar import RGBMobileNet,WEIGHT_SHA
            assert digest(checkpoint)==WEIGHT_SHA
            samples,assets=read_sample(data);assets['checkpoint_sha256']=WEIGHT_SHA
            tr=[(k,v[1]) for k,v in sorted(samples.items()) if k[0]=='train' and k[1]=='C'];te=[(k,v[1]) for k,v in sorted(samples.items()) if k[0]=='test' and k[1]=='C'];train=np.stack([v for _,v in tr]).transpose(0,3,1,2);test=np.stack([v for _,v in te]).transpose(0,3,1,2);yy=np.array([k[3] for k,_ in tr]);zz=np.array([k[3] for k,_ in te]);session=np.array([k[2] for k,_ in tr]);torch.set_num_threads(1)
            m=RGBMobileNet(checkpoint,'fp32',train[session==session.min()]);f,q=m.batch(train);g,q2=m.batch(test);assert q is None and q2 is None;rows+=workload(f.astype(np.float32),g.astype(np.float32),yy,zz,[1024,4096],'core50_fp32',native,f[session==session.min()])
        return dict(scope='warm normalized cached feature-to-class; normalization fitted train-only but excluded from timed loop; no hardware or energy claims; retained arrays exclude transient workspace/metadata; independent encoders are not exact substitutes; IID symbolic pilot only',platform=platform.platform(),numpy=np.__version__,build=meta,assets=assets,rows=rows,symbolic=mathrows)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--quick',action='store_true');p.add_argument('--data');p.add_argument('--checkpoint');p.add_argument('--out',required=True);a=p.parse_args();r=run(a.data,a.checkpoint,a.quick);Path(a.out).write_text(json.dumps(r,indent=2)+'\n');print('rows',len(r['rows']),'symbolic',len(r['symbolic']))
