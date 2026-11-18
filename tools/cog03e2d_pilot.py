"""Paired bounded research pilot; labels used only for evaluation."""
import argparse,json,time
from pathlib import Path
import numpy as np
from sklearn.datasets import load_wine,load_breast_cancer,make_blobs
from sklearn.metrics import adjusted_rand_score,normalized_mutual_info_score,roc_auc_score,average_precision_score
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import MiniBatchKMeans
from sklearn.ensemble import IsolationForest
from sklearn.svm import OneClassSVM
from sklearn.neighbors import NearestNeighbors
from cognitum.research.hdc_stream_discovery import *

def cluster(seed,quick):
    rng=np.random.default_rng(seed);x,y=make_blobs(n_samples=300 if quick else 600,centers=4,n_features=8,cluster_std=1.5,random_state=seed)
    # Fourth mode held out of bootstrap; no labels used by learners.
    first=np.flatnonzero(y!=3);rng.shuffle(first);n=len(first)//2;one=first[:n];other=np.concatenate([first[n:],np.flatnonzero(y==3)]);rng.shuffle(other)
    rows=[]
    for kind,x,y,one,other in [('novel_blobs',x,y,one,other),('wine',*wine(seed))]:
        z=StandardScaler().fit(x[one]);a=z.transform(x[one]);b=z.transform(x[other]);truth=y[other];enc=ThermometerProjection(a.shape[1],64,8,seed).fit(a);ha=enc.encode(a);hb=enc.encode(b)
        def add(name,p,bytes_,dt,extra={}):rows.append(dict(dataset=kind,seed=seed,arm=name,n=len(truth),ari=adjusted_rand_score(truth,p),nmi=normalized_mutual_info_score(truth,p),clusters=len(set(p)-{-1}),refused=int(np.sum(np.asarray(p)==-1)),numeric_bytes=int(bytes_),seconds=dt,**extra))
        t=time.perf_counter();m=IncrementalLouvain(k=8,threshold=.13,capacity=128,seed=seed);boot=m.fit(ha);p=np.array([m.assign(h) for h in hb]);elapsed=time.perf_counter()-t;add('hd_louvain',p,m.nbytes+enc.nbytes,elapsed,{'bootstrap_clusters':len(set(boot))})
        t=time.perf_counter();d=np.linalg.norm(a[:,None,:]-a[None,:,:],axis=2);g=nx.Graph();g.add_nodes_from(range(len(a)))
        for i,rr in enumerate(d):
            for j in [j for j in np.argsort(rr,kind='stable') if j!=i][:8]:g.add_edge(i,int(j),weight=1/(1+rr[j]))
        groups=nx.community.louvain_communities(g,seed=seed);labels=np.empty(len(a),int)
        for j,gp in enumerate(groups):labels[list(gp)]=j
        nn=NearestNeighbors(n_neighbors=1).fit(a);p=labels[nn.kneighbors(b,return_distance=False)[:,0]];add('raw_louvain_knn',p,a.nbytes+labels.nbytes,time.perf_counter()-t)
        t=time.perf_counter();k=MiniBatchKMeans(n_clusters=len(groups),random_state=seed,n_init=3).fit(a);p=[]
        for r in b:p.append(k.predict(r[None])[0]);k.partial_fit(r[None])
        add('online_kmeans',np.array(p),k.cluster_centers_.nbytes+k._counts.nbytes,time.perf_counter()-t)
    return rows

def wine(seed):
    x,y=load_wine(return_X_y=True);idx=np.random.default_rng(seed).permutation(len(x));n=len(idx)//2;return x,y,idx[:n],idx[n:]

def anomalies(seed,quick):
    rng=np.random.default_rng(seed);x,y=load_breast_cancer(return_X_y=True);normal=x[y==1];bad=x[y==0];rng.shuffle(normal);rng.shuffle(bad)
    a,c,b=normal[:180],normal[180:240],np.vstack([normal[240:],bad[:100]]);truth=np.r_[np.zeros(len(normal[240:])),np.ones(100)]
    if quick:a,c,b,truth=a[:60],c[:20],np.vstack([normal[240:260],bad[:20]]),np.r_[np.zeros(20),np.ones(20)]
    rows=[]
    for ds,a,c,b,truth in [('breast_cancer',a,c,b,truth),('synthetic',*synthetic(seed,quick))]:
        scaler=StandardScaler().fit(a);a,c,b=[scaler.transform(v) for v in (a,c,b)];enc=IDLevel(a.shape[1],512,16,seed).fit(a);ha,hc,hb=[enc.encode(v) for v in (a,c,b)]
        for arm in ('raw_density','hd_density','isolation_forest','ocsvm','hd_prototype'):
            t=time.perf_counter()
            if arm.endswith('density'):
                ishd=arm.startswith('hd');m=DensityDistance(ishd).fit(ha if ishd else a);fn=m.score;cal,test=(hc,hb) if ishd else (c,b);bytes_=m.ref.nbytes+m.rho.nbytes+(enc.nbytes if ishd else 0)
            elif arm=='hd_prototype':
                p=(ha.mean(0)>=.5).astype(np.uint8)[None];fn=lambda v:hamming(v,p)[:,0];cal,test=hc,hb;bytes_=p.nbytes+enc.nbytes
            else:
                m=(IsolationForest(n_estimators=50,random_state=seed,n_jobs=1) if arm=='isolation_forest' else OneClassSVM(nu=.05)).fit(a);fn=lambda v:-m.decision_function(v);cal,test=c,b;bytes_=None
            fit=time.perf_counter()-t;threshold=float(np.quantile(fn(cal),.95));t=time.perf_counter();s=fn(test);lat=time.perf_counter()-t;pred=s>threshold
            rows.append(dict(dataset=ds,seed=seed,arm=arm,n=len(test),roc_auc=roc_auc_score(truth,s),pr_auc=average_precision_score(truth,s),fpr=float(pred[truth==0].mean()),tpr=float(pred[truth==1].mean()),fit_seconds=fit,score_seconds=lat,numeric_bytes=bytes_))
    return rows

def synthetic(seed,quick):
    r=np.random.default_rng(seed);n=60 if quick else 180;normal=lambda k:r.normal(size=(k,8));a=normal(n);c=normal(30);b=np.vstack([normal(100),r.normal(2.2,.7,(40,8))]);return a,c,b,np.r_[np.zeros(100),np.ones(40)]

def wafer(seed,quick):
    r=np.random.default_rng(seed);yy,xx=np.indices((20,20));radius=np.hypot(xx-9.5,yy-9.5);disk=radius<9.5
    def make(mode,n):
        out=[]
        for _ in range(n):
            prob=np.full((20,20),.025)
            if mode==1:prob[radius<3]=.8
            if mode==2:prob[(radius>7)&disk]=.65
            if mode==3:prob[(abs(xx-yy)<2)&disk]=.8
            if mode==4:prob[(xx<7)&(yy<7)&disk]=.9
            a=(r.random((20,20))<prob)&disk
            out.append(np.array([a.mean(),*(a[yy//5==i].mean() for i in range(4)),*(a[xx//5==i].mean() for i in range(4)),*(a[(radius>=i)&(radius<i+2)].mean() for i in range(0,10,2)),a[abs(xx-yy)<2].mean()]))
        return np.asarray(out)
    normal=make(0,100);cal=make(0,40);stream=[];labels=[]
    for phase in ([0,1,2],[0,3],[0,1,2,4]):
        x=np.vstack([make(k,15 if quick else 40) for k in phase]);y=np.repeat(phase,15 if quick else 40);ii=r.permutation(len(y));stream.extend(x[ii]);labels.extend(y[ii])
    x=np.asarray(stream);y=np.asarray(labels);enc=ThermometerProjection(normal.shape[1],64,8,seed).fit(normal);a,b,c=[enc.encode(v) for v in (normal,cal,x)];rows=[]
    for capacity in (8,32):
        m=OpenWorld(a,b,capacity=capacity,match=.13,coherence=.18,seed=seed);t=time.perf_counter();p=[];persist=[]
        for v in c:
            i,ok,score=m.observe(v);p.append(i);persist.append(ok)
        p=np.asarray(p);persist=np.asarray(persist);det=p!=0;rows.append(dict(seed=seed,capacity=capacity,n=len(y),ari=adjusted_rand_score(y[y!=0],p[y!=0]),nmi=normalized_mutual_info_score(y[y!=0],p[y!=0]),fpr=float(det[y==0].mean()),tpr=float(det[y!=0].mean()),persistent_modes=sum(m.persistent),refused=int(sum(p==-1)),numeric_bytes=m.nbytes+enc.nbytes,seconds=time.perf_counter()-t,defect_assignment_coverage=float((p[y!=0]>0).mean()),defect_promotion_coverage=float(persist[y!=0].mean()),old_mode_recovery=float(persist[(np.arange(len(y))>=len(y)*5/9)&(y==1)].mean())))
    return rows

def main():
    p=argparse.ArgumentParser();p.add_argument('--quick',action='store_true');p.add_argument('--out',required=True);a=p.parse_args();seeds=[601] if a.quick else [601,607,613];result={'scope':'bounded independent CPU references; not paper benchmarks; labels only evaluation; HDC anomaly density is inductive adaptation; storage excludes allocator and conventional detector state unmeasured','clustering':[],'anomaly':[],'wafer':[]}
    for s in seeds:
        result['clustering']+=cluster(s,a.quick);result['anomaly']+=anomalies(s,a.quick);result['wafer']+=wafer(s,a.quick)
    Path(a.out).write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
