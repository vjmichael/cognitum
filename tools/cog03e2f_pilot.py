"""Matched synthetic sequence benchmark. Frozen splits; negative results retained."""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression
from cognitum.research.hdc_temporal import CategoricalHMM,BinaryForward,LDN,LIF,BinaryNgram,LDNSummary,PackedPrototype


def digest(*parts):
    h=hashlib.sha256()
    for p in parts:
        for x in p:
            a=np.asarray(x);h.update(str(a.shape).encode());h.update(a.tobytes())
    return h.hexdigest()

def hmm_data(seed,quick):
    rng=np.random.default_rng(seed)
    # Same emissions; transition patterns differ, with hidden state (not supplied to learners).
    p=[1/3]*3;B=np.array([[.8,.1,.07,.03],[.1,.8,.03,.07],[.08,.07,.75,.1]])
    T=[np.array([[.12,.82,.06],[.06,.12,.82],[.82,.06,.12]]),np.array([[.12,.06,.82],[.82,.12,.06],[.06,.82,.12]]),np.full((3,3),1/3)]
    def batch(n,length):
        X=[];Y=[]
        for c,t in enumerate(T):
            for _ in range(n):
                z=rng.choice(3,p=p);x=[]
                for _ in range(length):x.append(rng.choice(4,p=B[z]));z=rng.choice(3,p=t[z])
                X.append(np.array(x,dtype=np.int64));Y.append(c)
        return X,np.array(Y)
    x,y=batch(8 if quick else 24,24);tx,ty=batch(4 if quick else 10,24);lx,ly=batch(4 if quick else 10,72)
    edited=[]
    for seq in tx:
        out=[]
        for o in seq:
            if rng.random()<.12:continue
            out.append(o)
            if rng.random()<.12:out.append(rng.integers(4))
            if rng.random()<.08:out.append(o)
        edited.append(np.array(out or [0],dtype=np.int64))
    return x,y,{'clean':(tx,ty),'unseen_length':(lx,ly),'insert_delete_repeat':(edited,ty)}

def count_ngram(seq,alphabet=4,n=2):
    a=np.zeros(alphabet**n)
    for i in range(len(seq)-n+1):
        k=0
        for o in seq[i:i+n]:k=k*alphabet+int(o)
        a[k]+=1
    return a/max(1,a.sum())

def score_proto(x,p):
    return (x@p.T)/(np.maximum(np.linalg.norm(x,axis=1),1e-12)[:,None]*np.maximum(np.linalg.norm(p,axis=1),1e-12)[None,:])

def proto(x,y):return np.array([x[y==i].mean(0) for i in sorted(set(y))])

def row(rows,task,method,seed,condition,y,pred,seconds,retained,workspace,split,**kw):
    rows.append(dict(task=task,method=method,seed=seed,condition=condition,n=len(y),correct=int(np.sum(pred==y)),accuracy=float(np.mean(pred==y)),predict_seconds=seconds,retained_numeric_bytes=int(retained),estimated_explicit_workspace_bytes=int(workspace),split_sha256=split,**kw))

def gru_fit(x,y,seed,continuous=False,epochs=20):
    import torch
    from torch import nn
    torch.manual_seed(seed);torch.set_num_threads(1)
    def batch(s):
        a=np.stack(s);a=a.astype(np.float32) if continuous else np.eye(4,dtype=np.float32)[a];return torch.from_numpy(a)
    class Net(nn.Module):
        def __init__(self):super().__init__();self.r=nn.GRU(1 if continuous else 4,12,batch_first=True);self.head=nn.Linear(12,3)
        def forward(self,x):return self.head(self.r(x)[1][0])
    m=Net();opt=torch.optim.Adam(m.parameters(),lr=.03);X=batch(x);Y=torch.tensor(y,dtype=torch.long)
    for _ in range(epochs):
        opt.zero_grad();loss=nn.functional.cross_entropy(m(X),Y);loss.backward();opt.step()
    def pred(s):
        with torch.inference_mode():return np.array([int(m(batch([a])).argmax(1)[0]) for a in s])
    return pred,sum(p.numel()*p.element_size() for p in m.parameters())

def discrete(rows,seed,quick):
    x,y,tests=hmm_data(seed,quick);models=[CategoricalHMM.fit([s for s,c in zip(x,y) if c==i],4,3,seed+i,iterations=4 if quick else 8) for i in range(3)];ret=sum(m.nbytes for m in models)
    conv=LogisticRegression(max_iter=300).fit(np.array([count_ngram(s) for s in x]),y)
    book=np.random.default_rng(seed+1).integers(0,2,(4,256),dtype=np.uint8);encode=lambda s:BinaryNgram(book,2).consume(s)
    hp=proto(np.array([encode(s) for s in x]),y);packed=PackedPrototype(hp);gru,gb=gru_fit(x,y,seed,epochs=8 if quick else 40)
    for cond,(tx,ty) in tests.items():
        sp=digest(x,[y],tx,[ty]);t=time.perf_counter();exact=np.array([[m.score(s)/len(s) for m in models] for s in tx]);dt=time.perf_counter()-t;best=exact.argmax(1)
        row(rows,'categorical','exact_hmm',seed,cond,ty,best,dt,ret,3*3*8,sp)
        for d in ([128] if quick else [128,512,2048]):
            t=time.perf_counter();scores=np.array([[BinaryForward(m,d,seed+q*97+i*10009).consume(s)/len(s) for i,m in enumerate(models)] for q,s in enumerate(tx)]);dt=time.perf_counter()-t;valid=np.isfinite(scores);p=scores.argmax(1);p[~valid.any(1)]=-1
            row(rows,'categorical',f'binary_forward_{d}',seed,cond,ty,p,dt,ret+3*((d+7)//8),3*d*24,sp,rank1_agreement=float(np.mean(p==best)),mean_abs_logscore_error=float(np.mean(np.abs(scores[valid]-exact[valid]))) if valid.any() else None,depleted_scores=int((~valid).sum()),dimension=d)
        for name,fn,b,w in [('conventional_bigram',lambda z:conv.predict(np.array([count_ngram(s) for s in z])),conv.coef_.nbytes+conv.intercept_.nbytes,16*8),('hdc_bigram',lambda z:score_proto(np.array([encode(s) for s in z]),hp).argmax(1),hp.nbytes+book.nbytes,256*8+16),('hdc_bigram_packed_majority',lambda z:np.array([packed.predict(encode(s)) for s in z]),packed.numeric_bytes+book.nbytes,256*8+16),('gru',gru,gb,0)]:
            t=time.perf_counter();p=fn(tx);row(rows,'categorical',name,seed,cond,ty,p,time.perf_counter()-t,b,w,sp)

def waveform_data(seed,quick):
    r=np.random.default_rng(seed+723)
    def batch(n,length):
        X=[];Y=[]
        for c in range(3):
            for _ in range(n):
                t=np.arange(length)/length;phase=r.uniform(-.3,.3);v=[np.sin(2*np.pi*(t+3*t*t)+phase),np.sin(2*np.pi*(7*t-3*t*t)+phase),np.sin(2*np.pi*4*t+phase)][c];v*=r.uniform(.8,1.2);v+=r.normal(0,.18,length)+r.uniform(-.15,.15);X.append(v[:,None]);Y.append(c)
        return X,np.array(Y)
    x,y=batch(12 if quick else 60,64);tx,ty=batch(5 if quick else 24,64);lx,ly=batch(5 if quick else 24,96)
    jitter=[]
    for s in tx:
        # Monotonic time warp, same sample count, additive noise.
        u=np.linspace(0,1,len(s));warp=u+.10*np.sin(2*np.pi*u);jitter.append((np.interp(warp,u,s[:,0])+r.normal(0,.12,len(s)))[:,None])
    return x,y,{'clean':(tx,ty),'longer':(lx,ly),'time_warp':(jitter,ty)}

def ldn_feature(seq,q):
    l=LDNSummary(q,.30,1/64)
    for u in seq:l.step(u)
    return l.feature()

def continuous(rows,seed,quick):
    x,y,tests=waveform_data(seed,quick);gs,gb=gru_fit(x,y,seed,continuous=True,epochs=8 if quick else 40)
    def raw(s):return np.r_[s[-1],s.mean(0),s.std(0)]
    for order in ([4] if quick else [4,8]):
        # LDN same operands across classifiers; no held-out fitting; train-only scaling.
        f=np.array([ldn_feature(s,order) for s in x]);mu=f.mean(0);sd=np.maximum(f.std(0),1e-8);z=(f-mu)/sd
        r=np.random.default_rng(seed+order);proj=r.normal(size=(z.shape[1],256));h=lambda v:np.where(v@proj>=0,1.,-1.)
        hp=proto(h(z),y);clf=LogisticRegression(max_iter=300).fit(z,y)
        rp=r.normal(size=(3,256));rf=np.array([raw(s) for s in x]);rm=rf.mean(0);rs=np.maximum(rf.std(0),1e-8);rproto=proto(np.where(((rf-rm)/rs)@rp>=0,1.,-1.),y)
        # Paper-style LIF -> binary state symbol -> order-sensitive XOR/majority.
        states=[LDN(order,.30,1/64).consume(s)[:,:,0] for s in x];offset=np.maximum(0,-np.min(np.concatenate(states),axis=0));book=r.integers(0,2,(2**order,256),dtype=np.uint8)
        def spike_ngram(s):
            l=LDN(order,.30,1/64);lif=LIF(order,threshold=1.0);ng=BinaryNgram(book,3)
            for u in s:
                spikes=lif.step(np.maximum(l.step(u)[:,0]+offset,0));token=int(spikes.astype(int)@(2**np.arange(order)));ng.step(token)
            return ng.counts/max(1,ng.windows)
        sp=proto(np.array([spike_ngram(s) for s in x]),y);pack=PackedPrototype(sp);raw_clf=LogisticRegression(max_iter=300).fit((rf-rm)/rs,y)
        for condition,(tx,ty) in tests.items():
            split=digest(x,[y],tx,[ty]);ldnb=LDNSummary(order,.30,1/64).numeric_bytes
            def ftest(v):return (np.array([ldn_feature(s,order) for s in v])-mu)/sd
            arms=[('ldn_logistic',lambda v:clf.predict(ftest(v)),clf.coef_.nbytes+clf.intercept_.nbytes+mu.nbytes+sd.nbytes+ldnb,0),('ldn_hdc_projection',lambda v:score_proto(h(ftest(v)),hp).argmax(1),proj.nbytes+hp.nbytes+mu.nbytes+sd.nbytes+ldnb,256*8),('ldn_lif_hdc_ngram',lambda v:score_proto(np.array([spike_ngram(s) for s in v]),sp).argmax(1),book.nbytes+sp.nbytes+offset.nbytes+ldnb,256*8+order*16+24),('ldn_lif_packed_majority',lambda v:np.array([pack.predict(spike_ngram(s)) for s in v]),book.nbytes+pack.numeric_bytes+offset.nbytes+ldnb,256*8+order*16+24),('raw_logistic',lambda v:raw_clf.predict((np.array([raw(s) for s in v])-rm)/rs),raw_clf.coef_.nbytes+raw_clf.intercept_.nbytes+rm.nbytes+rs.nbytes,0),('raw_hdc',lambda v:score_proto(np.where(((np.array([raw(s) for s in v])-rm)/rs)@rp>=0,1.,-1.),rproto).argmax(1),rp.nbytes+rproto.nbytes+rm.nbytes+rs.nbytes,256*8),('gru',gs,gb,0)]
            for name,fun,b,w in arms:
                t=time.perf_counter();prediction=fun(tx);row(rows,'waveform',name,seed,condition,ty,prediction,time.perf_counter()-t,b,w,split,order=order)

def run(quick=False,seed=None):
    rows=[]
    for s in ([seed] if seed is not None else ([1301] if quick else [1301,1307,1319])):
        discrete(rows,s,quick);continuous(rows,s,quick)
    return dict(schema='cognitum.cog03e2f.temporal.pilot.v1',rows=rows,quick=quick,scope='synthetic hidden-state and waveform streams; no source paper replication; retained numeric arrays only, explicit workspace estimate incomplete; GRU workspace not measured; CPU timings include extraction, no hardware inference',production_enabled=False)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--quick',action='store_true');p.add_argument('--seed',type=int);p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=run(a.quick,a.seed);a.out.write_text(json.dumps(r,indent=2)+'\n');print(len(r['rows']),'rows')
