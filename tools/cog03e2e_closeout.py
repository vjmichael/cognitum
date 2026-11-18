"""Mandatory hosted real-data/weights gate and offline synthetic fixture.
Dataset and checkpoint acquisition only with explicit --acquire.
"""
import argparse,hashlib,io,json,time,urllib.request,zipfile
from pathlib import Path
import numpy as np
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split
from sklearn.metrics import adjusted_rand_score,normalized_mutual_info_score,roc_auc_score
from cognitum.research.hdc_visual_closeout import *
from cognitum.research.hdc_uncertain_visual import VisualBank
from tools.cog03e2e_pilot import EuclideanBank

HAR_URL='https://archive.ics.uci.edu/static/public/240/human+activity+recognition+using+smartphones.zip'
WEIGHT_URL='https://download.pytorch.org/models/quantized/mobilenet_v2_qnnpack_37f702c5.pth'
SIGNALS=['body_acc','body_gyro','total_acc']

def acquire(url,path,cap):
    if not path.exists():
        tmp=path.with_suffix('.partial')
        try:
            with urllib.request.urlopen(url,timeout=45) as r,tmp.open('wb') as f:
                n=0
                while True:
                    b=r.read(1<<20)
                    if not b:break
                    n+=len(b)
                    if n>cap:raise ValueError('download size limit')
                    f.write(b)
            tmp.replace(path)
        finally:tmp.unlink(missing_ok=True)
    if not 0<path.stat().st_size<=cap:raise ValueError('asset size limit')
    return hashlib.sha256(path.read_bytes()).hexdigest()

def har_arrays(path):
    with zipfile.ZipFile(path) as outer:
        nested=[n for n in outer.namelist() if n.endswith('UCI HAR Dataset.zip')]
        handle=io.BytesIO(outer.read(nested[0])) if nested else path
    with zipfile.ZipFile(handle) as z:
        def read(suffix,dtype):
            paths=[n for n in z.namelist() if n.endswith('/'+suffix) or n==suffix]
            if len(paths)!=1:raise ValueError('missing or duplicate '+suffix)
            return np.loadtxt(io.BytesIO(z.read(paths[0])),dtype=dtype)
        out=[]
        for split,n,ng in [('train',7352,21),('test',2947,9)]:
            y=read(f'{split}/y_{split}.txt',int)-1;g=read(f'{split}/subject_{split}.txt',int)
            x=np.stack([read(f'{split}/Inertial Signals/{s}_{axis}_{split}.txt',np.float32) for s in SIGNALS for axis in 'xyz'],axis=-1)
            assert x.shape==(n,128,9) and y.shape==g.shape==(n,) and len(np.unique(g))==ng and set(y)==set(range(6)) and np.isfinite(x).all()
            out.append((x,y,g))
    assert not set(out[0][2])&set(out[1][2]);return out

def fixture(seed):
    rng=np.random.default_rng(seed);p=rng.normal(size=(6,128,9))*.5
    def make(groups):
        g=np.repeat(groups,12);y=np.tile(np.repeat(np.arange(6),2),len(groups));x=p[y]+rng.normal(size=(len(y),128,9))*.2+g[:,None,None]*.003
        return x,y,g
    return [make(np.arange(1,22)),make(np.arange(22,31))]

def uncertainty(data,seed):
    (x,y,g),(t,ty,tg)=data;fg,cg,sg=group_partition(g,tg,seed);fi=np.isin(g,fg);ci=np.isin(g,cg)
    e=IMUEncoder(256,seed).fit(x[fi]);rows=[]
    conditions=['clean','gain','offset','unseen'];known=conditions[:3]
    cs={k:e.encode(perturb(x[ci],k)) for k in known};ts={k:e.encode(perturb(t,k)) for k in conditions}
    for name in ['clean','augmented']:
        tr=np.concatenate([e.encode(perturb(x[fi],k)) for k in (known if name=='augmented' else ['clean'])]);yl=np.tile(y[fi],3 if name=='augmented' else 1)
        p=np.array([np.where(tr[yl==k].sum((0,1))>=0,1,-1) for k in range(6)])
        ca={k:nonconformity(scores(v,p)) for k,v in cs.items()};ta={k:nonconformity(scores(v,p)) for k,v in ts.items()}
        for method in ['window','subject','envelope']:
            m=robust_calibration(np.stack([ca[k] for k in known]),y[ci],g[ci]) if method=='envelope' else Mondrian(.1).fit(ca['clean'],y[ci],g[ci] if method=='subject' else None)
            for k,a in ta.items():
                mask=m.predict(a);hit=mask[np.arange(len(ty)),ty];sing=mask.sum(1)==1;gc=[hit[(tg==q)&(ty==j)].all() for q in sg for j in range(6) if ((tg==q)&(ty==j)).any()]
                rows.append(dict(seed=seed,fit=name,method=method,condition=k,n=len(ty),coverage=float(hit.mean()),group_class_coverage=float(np.mean(gc)),mean_set_size=float(mask.sum(1).mean()),empty=float((mask.sum(1)==0).mean()),singleton=float(sing.mean()),singleton_error=float(1-hit[sing].mean()) if sing.any() else None,top1=float((a.argmin(1)==ty).mean()),ood_auc=(float(roc_auc_score(np.r_[np.zeros(len(ty)),np.ones(len(ty))],np.r_[ta['clean'].min(1),a.min(1)])) if k!='clean' else None),cal_counts=m.counts.tolist()))
    return {'fit_subjects':fg.tolist(),'cal_subjects':cg.tolist(),'test_subjects':sg.tolist(),'rows':rows}

class ExemplarBank:
    def __init__(self,f,budget):
        self.cap=budget//(f+8);self.a=np.zeros((self.cap,f),np.uint8);self.count=np.zeros(self.cap,np.int64);self.n=0
    @property
    def numeric_bytes(self):return self.a.nbytes+self.count.nbytes
    def predict(self,q):return int(np.argmin(np.sum((self.a[:self.n].astype(np.int32)-q)**2,axis=1))) if self.n else -1
    def observe(self,q):
        j=self.predict(q)
        if self.n<self.cap and (j<0 or np.mean((self.a[j].astype(np.int32)-q)**2)>5):self.a[self.n]=q;self.count[self.n]=1;self.n+=1
        elif j>=0:self.count[j]+=1

def visual(seed,features,y,budget,kind,d=256):
    rng=np.random.default_rng(seed);ix,tx=train_test_split(np.arange(len(y)),test_size=.3,stratify=y,random_state=seed);phases=np.array_split(rng.permutation(10),5)
    first=ix[np.isin(y[ix],phases[0])];prefix=rng.permutation(first)[:max(20,len(first)//3)];ix=ix[~np.isin(ix,prefix)]
    quant=FeatureQuantizer().fit(features[prefix],min(64,features.shape[1]));z=quant.transform(features);enc=LevelEncoder(z.shape[1],d,16,seed);qp=np.array([enc.encode(i) for i in z[prefix]]);ds=hamming(qp[:,None,:],qp[None,:,:],d).astype(float);np.fill_diagonal(ds,np.inf);floor=float(np.clip(1-np.quantile(ds.min(1)/d,.9),.5,.98))
    rows=[]
    for arm in ['merge','fixed','replace','euclidean','exemplar']:
        cap=budget-quant.numeric_bytes
        if arm in ['euclidean','exemplar']:
            bank=EuclideanBank(z.shape[1],cap) if arm=='euclidean' else ExemplarBank(z.shape[1],cap)
            feat=lambda i:z[i].astype(np.float32)/15 if arm=='euclidean' else z[i]
            pred=lambda i:bank.predict(feat(i));storage=quant.numeric_bytes+bank.numeric_bytes
        else:
            bank=VisualBank(d,min(128,(cap-enc.numeric_bytes)//((d+7)//8+24)),seed=seed,novelty_floor=floor,mode=arm)
            feat=lambda i:enc.encode(z[i]);pred=lambda i:bank.predict(feat(i))[0];storage=quant.numeric_bytes+enc.numeric_bytes+bank.numeric_bytes
        assert storage<=budget;seen=[];best={};result=[];start=time.perf_counter()
        for phase,classes in enumerate(phases):
            train=ix[np.isin(y[ix],classes)];train=np.random.default_rng(seed+phase+100).permutation(train)
            for i in train:bank.observe(feat(i))
            seen.extend(classes.tolist());test=tx[np.isin(y[tx],seen)];truth=y[test];p=np.array([pred(i) for i in test]);per={}
            for j,cl in enumerate(phases[:phase+1]):
                mask=np.isin(truth,cl);per[j]=adjusted_rand_score(truth[mask],p[mask]);best[j]=max(best.get(j,-1),per[j])
            result.append(dict(phase=phase,ari=float(adjusted_rand_score(truth,p)),nmi=float(normalized_mutual_info_score(truth,p)),forgetting=float(np.mean([best[j]-per[j] for j in range(phase)])) if phase else 0.,new_pair_ari=float(per[phase]),clusters=bank.n,n=len(test)))
        rows.append(dict(seed=seed,feature=kind,method=arm,budget=budget,numeric_bytes=storage,dimensions=d,novelty_floor=floor,fit_prefix=len(prefix),merges=getattr(bank,'merges',0),seconds=time.perf_counter()-start,phases=result))
    return rows

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--data',required=True);p.add_argument('--acquire',action='store_true');p.add_argument('--fixture',action='store_true');p.add_argument('--pixels-only',action='store_true');a=p.parse_args();root=Path(a.data);root.mkdir(parents=True,exist_ok=True)
    if a.fixture and a.acquire:raise ValueError('fixture cannot acquire')
    if a.pixels_only and not a.fixture:raise ValueError('real gate requires native MobileNet')
    if not a.pixels_only:
        import torch,torchvision
        torch.set_num_threads(1)
    start=time.perf_counter();meta={};data=fixture(41) if a.fixture else None
    if not a.fixture:
        h=root/'uci-har.zip';w=root/'mobilenet_v2_qnnpack_37f702c5.pth'
        if a.acquire:meta['har_sha256']=acquire(HAR_URL,h,100<<20);meta['weights_sha256']=acquire(WEIGHT_URL,w,30<<20)
        else:meta['har_sha256']=hashlib.sha256(h.read_bytes()).hexdigest();meta['weights_sha256']=hashlib.sha256(w.read_bytes()).hexdigest()
        data=har_arrays(h);m=FrozenMobileNet(w)
    elif not a.pixels_only:m=FrozenMobileNet(random_smoke=True)
    u=[uncertainty(data,s) for s in ([1201] if a.fixture else [1201,1207,1213])]
    X,y=load_digits(return_X_y=True);X=np.rint(X*255/16).astype(np.uint8)
    if a.fixture:
        keep=np.concatenate([np.flatnonzero(y==j)[:24] for j in range(10)]);X=X[keep];y=y[keep]
    # Frozen feature extraction only; cached features for controlled head replay are
    # dataset storage, not online learner state. Time extractor separately.
    inputs=[('pixels',X)]
    if not a.pixels_only:
        s=time.perf_counter();f=[];qparams=None
        for i in range(0,len(X),16):
            q,scale,zero=m.features(X[i:i+16].reshape(-1,8,8));f.append(q)
            if qparams is None:qparams=(scale,zero)
            assert qparams==(scale,zero)
        f=np.concatenate(f)
        if not a.fixture:assert np.any(f.var(axis=0)>0),'degenerate pretrained representations'
        meta.update(pretrained=m.pretrained,checkpoint_sha256=m.digest,checkpoint_bytes=m.file_bytes,feature_shape=list(f.shape),feature_dtype=str(f.dtype),extract_seconds=time.perf_counter()-s,feature_scale=scale,feature_zero_point=zero,feature_sha256=hashlib.sha256(f.tobytes()).hexdigest(),torch=torch.__version__,torchvision=torchvision.__version__)
        inputs.append(('mobilenet_int8',f))
    v=[]
    for seed in ([1201] if a.fixture else [1201,1207]):
        for budget in ([8192] if a.fixture else [8192,16384]):
            for name,fe in inputs:v.extend(visual(seed,fe,y,budget,name))
    assert all(x['numeric_bytes']<=x['budget'] for x in v)
    Path(a.out).write_text(json.dumps(dict(fixture=a.fixture,metadata=meta,uncertainty=u,visual=v,seconds=time.perf_counter()-start,scope='Subject-disjoint UCI raw IMU when not fixture; corruptions artificial. Frozen ImageNet QAT features vs pixels; same selected features per HDC/conventional head; retained online numeric cap excludes shared CNN checkpoint, feature cache, workspace and interpreter. Cluster metrics not classification accuracy. No author reproduction.'),indent=2)+'\n')
if __name__=='__main__':main()
