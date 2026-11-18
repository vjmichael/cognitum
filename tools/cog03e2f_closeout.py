"""Paired duration/retained-budget pilots and mandatory original HAR gate.
No data acquisition unless --acquire. Synthetic fixture is never real evidence.
"""
import argparse,hashlib,json,sys,time,subprocess
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.cluster import KMeans
from tools.cog03e2f_pilot import waveform_data,hmm_data,count_ngram,digest
from tools.cog03e2e_closeout import HAR_URL,acquire,har_arrays,fixture,group_partition
from cognitum.research.hdc_temporal import CategoricalHMM, LDNSummary
from cognitum.research.hdc_temporal_closeout import duration_hmm,duration_tokens,adaptive_summary,batched_summary,SeededPackedHead
HAR_SHA='c00b803081a5c797cd5e4b83700a9810b38d53d9d84e01917e090e1fdbc81031'
BUDGETS=(4096,16384)

def peak_rss():
    if sys.platform=='win32':
        import ctypes as c
        from ctypes import wintypes as w
        class Counters(c.Structure):
            _fields_=[('cb',w.DWORD),('PageFaultCount',w.DWORD)]+[(k,c.c_size_t) for k in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
        a=Counters();a.cb=c.sizeof(a);k=c.windll.kernel32;k.GetCurrentProcess.restype=w.HANDLE
        fn=c.windll.psapi.GetProcessMemoryInfo;fn.argtypes=[w.HANDLE,c.POINTER(Counters),w.DWORD];fn.restype=w.BOOL
        if not fn(k.GetCurrentProcess(),c.byref(a),a.cb):raise OSError('GetProcessMemoryInfo')
        return a.PeakWorkingSetSize
    if sys.platform.startswith('linux'):
        # VmHWM is per current executable, unlike inherited ru_maxrss across fork/exec.
        return int(next(l for l in Path('/proc/self/status').read_text().splitlines() if l.startswith('VmHWM:')).split()[1])*1024
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)

def dwell_data(seed,quick):
    r=np.random.default_rng(seed);counts=(8,4) if quick else (30,20)
    def batch(n,length,warp=1.):
        x=[];y=[]
        for c in range(3):
            for _ in range(n):
                a=[];s=int(r.integers(3))
                while len(a)<length:
                    d=max(1,round(warp*max(1,int(r.normal([2,5,10][c],.8)))));a.extend([s]*d);s=(s+1)%3
                a=np.array(a[:length]);err=r.random(length)<.07;a[err]=r.integers(3,size=err.sum());x.append(a);y.append(c)
        return x,np.array(y)
    x,y=batch(counts[0],48);return x,y,{'clean':batch(counts[1],48),'longer':batch(counts[1],96),'slower':batch(counts[1],64,1.3)}

def cat_feature(s,mode):
    if mode=='bigram':return count_ngram(s,3,2)
    t=duration_tokens(s,3);return np.r_[np.bincount(t,minlength=15)/max(1,len(t)),count_ngram(t,15,2)]

def classify_features(x,y,test,budget,method,seed,overhead=0):
    if method=='logistic':
        mu=x.mean(0);sd=np.maximum(x.std(0),1e-8);m=LogisticRegression(max_iter=400).fit((x-mu)/sd,y);size=mu.nbytes+sd.nbytes+m.coef_.nbytes+m.intercept_.nbytes+m.classes_.nbytes+overhead
        if size>budget:return None,size,None
        return m.predict((test-mu)/sd),size,None
    # Budget includes explicit retained scaling, labels, seed, packed prototype and encoder arrays.
    k=len(np.unique(y));base=2*x.shape[1]*8+k*8+24+overhead;d=min(4096,8*((budget-base)//k))
    if d<8:return None,base,None
    m=SeededPackedHead(int(d),seed).fit(x,y);size=m.numeric_bytes+overhead
    assert size<=budget
    return m.predict(test),size,d

def append(rows,task,arm,seed,budget,condition,y,pred,bytes_,seconds,split,dim=None,**kw):
    rows.append(dict(task=task,method=arm,seed=seed,budget=budget,condition=condition,n=len(y),correct=None if pred is None else int(np.sum(y==pred)),accuracy=None if pred is None else float(np.mean(y==pred)),retained_bytes=int(bytes_),eligible=pred is not None,dimension=dim,seconds=seconds,split_sha256=split,**kw))

def categorical(rows,seed,quick):
    x,y,tests=dwell_data(seed,quick);base=[];expanded=[];chosen=[]
    for c in range(3):
        seq=[s for s,j in zip(x,y) if c==j];m=CategoricalHMM.fit(seq[:-3],3,3,seed+c,iterations=4 if quick else 8)
        d=max((1,2,3,4),key=lambda a:np.mean([duration_hmm(m,a).score(s)/len(s) for s in seq[-3:]]));base.append(m);expanded.append(duration_hmm(m,d));chosen.append(d)
    xx={k:np.array([cat_feature(s,k) for s in x]) for k in ['bigram','dwell']}
    for cond,(tx,ty) in tests.items():
        split=digest(x,[y],tx,[ty]);t=time.perf_counter();p0=np.array([[m.score(s) for m in base] for s in tx]).argmax(1);dt=time.perf_counter()-t
        t=time.perf_counter();p1=np.array([[m.score(s) for m in expanded] for s in tx]).argmax(1);dt1=time.perf_counter()-t
        for b in BUDGETS:
            for name,models,p,elapsed in [('hmm',base,p0,dt),('minimum_dwell_hmm',expanded,p1,dt1)]:
                z=sum(m.nbytes for m in models);append(rows,'dwell',name,seed,b,cond,ty,p if z<=b else None,z,elapsed,split,min_dwell=chosen if name!='hmm' else [1]*3)
            for feat in xx:
                f=np.array([cat_feature(s,feat) for s in tx])
                for method in ['logistic','packed']:
                    t=time.perf_counter();p,z,d=classify_features(xx[feat],y,f,b,method,seed);append(rows,'dwell',feat+'_'+method,seed,b,cond,ty,p,z,time.perf_counter()-t,split,d)

def wave_features(x,mode):
    return np.array([adaptive_summary(s,normalized=mode=='normalized') for s in x])

def waveform(rows,seed,quick,only=None):
    x,y,tests=waveform_data(seed,quick);overhead=LDNSummary(4,.3,1/64).numeric_bytes
    for mode in ['fixed','normalized']:
        if only and not only.startswith(mode):continue
        f=wave_features(x,mode)
        for cond,(tx,ty) in tests.items():
            z=wave_features(tx,mode);split=digest(x,[y],tx,[ty]);
            for b in BUDGETS:
                if only and b!=BUDGETS[0]:continue
                for method in ['logistic','packed']:
                    if only and only!=mode+'_'+method:continue
                    t=time.perf_counter();p,size,d=classify_features(f,y,z,b,method,seed,overhead);append(rows,'waveform',mode+'_'+method,seed,b,cond,ty,p,size,time.perf_counter()-t,split,d)

def har_features(x,mode):
    if mode=='raw':return np.c_[x[:,-1,:],x.mean(1),x.std(1)]
    return np.concatenate([batched_summary(x[i:i+64],4,.6,.02) for i in range(0,len(x),64)])

def har(data,seed):
    (x,y,g),(t,ty,tg)=data;fg,cg,sg=group_partition(g,tg,seed);fi=np.isin(g,fg);ci=np.isin(g,cg);rows=[]
    for mode in ['raw','ldn']:
        st=time.perf_counter();f=har_features(x[fi],mode);ca=har_features(x[ci],mode);test=har_features(t,mode);extra=LDNSummary(4,.6,.02,9).numeric_bytes if mode=='ldn' else 0;extract=time.perf_counter()-st
        for b in BUDGETS:
            for method in ['logistic','packed']:
                for condition,z,l,groups in [('calibration',ca,y[ci],g[ci]),('official_test',test,ty,tg)]:
                    start=time.perf_counter();p,n,d=classify_features(f,y[fi],z,b,method,seed,extra);split=digest([g[fi],y[fi],groups,l]);append(rows,'har',mode+'_'+method,seed,b,condition,l,p,n,time.perf_counter()-start,split,d,extract_seconds=extract,subjects=np.unique(groups).tolist())
    # Same raw windows; tokenize train-only standardized 8-sample blocks.
    # Separate windows, no invented continuity across overlapping observations.
    start=time.perf_counter()
    def frames(v):return v.reshape(len(v),16,8,9).mean(2)
    ft=frames(x[fi]);fc=frames(x[ci]);fs=frames(t);mu=ft.mean((0,1));sd=np.maximum(ft.std((0,1)),1e-8)
    q=KMeans(n_clusters=8,n_init=3,random_state=seed).fit(((ft-mu)/sd).reshape(-1,9)[::4]);overhead=mu.nbytes+sd.nbytes+q.cluster_centers_.nbytes
    def tokens(v):return q.predict(((v-mu)/sd).reshape(-1,9)).reshape(len(v),16)
    a,c,s=map(tokens,(ft,fc,fs));extract=time.perf_counter()-start;models=[];ys=y[fi];groups=g[fi];rng=np.random.default_rng(seed)
    for lab in range(6):
        idx=[]
        for subject in fg:
            pool=np.flatnonzero((ys==lab)&(groups==subject));idx.extend(rng.permutation(pool)[:4])
        models.append(CategoricalHMM.fit(a[idx],8,3,seed+lab,iterations=5))
    expand=[duration_hmm(m,2) for m in models]
    ax=np.array([count_ngram(v,8,2) for v in a]);
    for condition,z,l,group in [('calibration',c,y[ci],g[ci]),('official_test',s,ty,tg)]:
        split=digest([groups,ys,group,l]);fx=np.array([count_ngram(v,8,2) for v in z]);
        for name,ms in [('token_hmm',models),('token_duration_hmm',expand)]:
            st=time.perf_counter();pred=np.array([[m.score(v) for m in ms] for v in z]).argmax(1);elapsed=time.perf_counter()-st;size=overhead+sum(m.nbytes for m in ms)
            for b in BUDGETS:append(rows,'har',name,seed,b,condition,l,pred if size<=b else None,size,elapsed,split,extract_seconds=extract,subjects=np.unique(group).tolist())
        for b in BUDGETS:
            for method in ['logistic','packed']:
                st=time.perf_counter();p,n,d=classify_features(ax,ys,fx,b,method,seed,overhead);append(rows,'har','token_bigram_'+method,seed,b,condition,l,p,n,time.perf_counter()-st,split,d,extract_seconds=extract,subjects=np.unique(group).tolist())
    return dict(fit_subjects=fg.tolist(),cal_subjects=cg.tolist(),test_subjects=sg.tolist(),rows=rows)

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);p.add_argument('--quick',action='store_true');p.add_argument('--data',type=Path);p.add_argument('--acquire',action='store_true');p.add_argument('--worker',choices=['fixed_logistic','fixed_packed','normalized_logistic','normalized_packed']);p.add_argument('--resource',action='store_true');a=p.parse_args();rows=[];resources=[]
    if a.worker:
        start=time.perf_counter();before=peak_rss();waveform(rows,1411,a.quick,a.worker);payload=dict(arm=a.worker,peak_before_bytes=before,peak_process_bytes=peak_rss(),seconds=time.perf_counter()-start,rows=rows);a.out.write_text(json.dumps(payload,indent=2)+'\n');return
    for seed in ([1411] if a.quick else [1411,1423,1447]):categorical(rows,seed,a.quick);waveform(rows,seed,a.quick)
    if a.acquire:
        if a.data is None:raise ValueError('data directory required')
        a.data.mkdir(exist_ok=True,parents=True);f=a.data/'uci-har.zip';sha=acquire(HAR_URL,f,100<<20)
        if sha!=HAR_SHA:raise ValueError('HAR archive differs from E2E accepted bytes: '+sha)
        ds=har_arrays(f)
    else:sha=None;ds=fixture(43)
    h=[har(ds,s) for s in ([1201] if a.quick else [1201,1207,1213])]
    if a.resource:
        for method in ['fixed_logistic','fixed_packed','normalized_logistic','normalized_packed']:
            dst=a.out.with_name(a.out.stem+'-'+method+'.json');cmd=[sys.executable,'-m','tools.cog03e2f_closeout','--worker',method,'--out',str(dst)]+(['--quick'] if a.quick else []);subprocess.run(cmd,check=True,timeout=180);resources.append(json.loads(dst.read_text()))
    allrows=rows+[r for item in h for r in item['rows']];assert all(r['retained_bytes']<=r['budget'] for r in allrows if r['eligible'])
    a.out.write_text(json.dumps(dict(schema='cognitum.e2f.closeout.v1',fixture=not a.acquire,har_sha256=sha,rows=rows,har=h,resources=resources,scope='retained explicit numeric arrays, not hard total process memory; isolated resource measurements include import/data overhead and fit plus predict; known-window duration normalization is not future-blind streaming; HAR does not concatenate overlapping windows.',production_enabled=False),indent=2)+'\n');print(len(rows),sum(len(v['rows']) for v in h),'rows')
if __name__=='__main__':main()
