"""Expanded deterministic E2G comparisons; no network, external controller or hidden label use."""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
from cognitum.research.hdc_cooperative_closeout import *
from cognitum.research.hdc_cooperative_learning import local_update,scores
from tools.cog03e2g_pilot import digest

def maze(seed,quick):
    rng=np.random.default_rng(seed);side=15;N=side**2;goal=N-1;actions=4
    wall=np.zeros((side,side),bool)
    for j in (3,7,11):wall[:,j]=True;wall[[1,6,13],j]=False
    wall=wall.ravel();allowed=np.flatnonzero(~wall);start=allowed[allowed!=goal];delta=np.array([[-1,0],[1,0],[0,-1],[0,1]])
    trans=np.empty((N,actions),int)
    for s in range(N):
        for a in range(actions):
            p=np.clip(np.array(divmod(s,side))+delta[a],0,side-1);z=int(p[0]*side+p[1]);trans[s,a]=s if wall[z] or s==goal else z
    rows=[];gamma=.95
    for slip in (.0,.2):
        def step(s,a,u,alt):
            n=trans[s,alt if u<slip else a];return int(n),1. if n==goal else -.04,n==goal
        # Dynamic programming oracle, explicitly given the known transition model.
        v=np.zeros(N)
        for _ in range(300):
            nv=np.where(trans==goal,1.,-.04+gamma*v[trans]);q=(1-slip)*nv+slip*nv.mean(axis=1,keepdims=True);v=q.max(1);v[goal]=0
        opt=q.argmax(1)
        n=1000 if quick else 24000;ss=rng.choice(start,n);aa=rng.integers(actions,size=n);u=rng.random(n);alt=rng.integers(actions,size=n);replay=[(int(s),int(a),*step(s,a,t,int(b))) for s,a,t,b in zip(ss,aa,u,alt)]
        starts=rng.choice(start,12 if quick else 60);uu=rng.random((len(starts),100));bb=rng.integers(actions,size=uu.shape);rd=hashlib.sha256(ss.tobytes()+aa.tobytes()+u.tobytes()+alt.tobytes()+starts.tobytes()+uu.tobytes()+bb.tobytes()).hexdigest()
        for budget in (4096,16384):
            for kind in ('tabular','fourier','seeded','bound','oracle'):
                d=128 if budget==4096 else 512
                if kind=='bound':d=64 if budget==4096 else 256
                model=None if kind=='oracle' else GridQ(side,kind,d,seed)
                if model and model.numeric_bytes>budget:raise AssertionError('budget')
                t=time.perf_counter()
                if model:
                    for s,a,n,r,done in replay:model.update(s,a,r,n,done)
                elapsed=time.perf_counter()-t;policy=opt if model is None else np.array([model.q(s).argmax() for s in range(N)])
                returns=[];wins=0
                for i,s in enumerate(starts):
                    total=0.;factor=1.
                    for j in range(100):
                        s,r,done=step(s,policy[s],uu[i,j],bb[i,j]);total+=factor*r;factor*=gamma
                        if done:wins+=1;break
                    returns.append(total)
                # Explicit sampled state-interference diagnostic (no persistent cache).
                if model and kind!='tabular':
                    f=unit(np.stack([model.feature(int(s)) for s in allowed[:32]]));g=f@f.T;np.fill_diagonal(g,0);interference=float(abs(g).max())
                else:interference=0.
                rows.append(dict(task='rl',seed=seed,slip=slip,budget=budget,method=kind,d=d,replay_sha256=rd,n=len(starts),success=wins,mean_return=float(np.mean(returns)),p10=float(np.quantile(returns,.1)),numeric_bytes=int(model.numeric_bytes) if model else None,fit_seconds=elapsed,interference=interference,returns=returns))
    return rows

def dataset(seed,ds):
    from sklearn.datasets import load_digits,load_wine,make_blobs
    from sklearn.model_selection import train_test_split
    if ds=='digits':X,y=load_digits(return_X_y=True)
    elif ds=='wine':X,y=load_wine(return_X_y=True)
    else:X,y=make_blobs(n_samples=180,centers=3,n_features=8,random_state=seed,cluster_std=2.5)
    tr,te=train_test_split(np.arange(len(y)),test_size=.25,stratify=y,random_state=seed);fit,cal=train_test_split(tr,test_size=.2,stratify=y[tr],random_state=seed+1)
    return np.asarray(X,dtype=np.float32),y,fit,cal,te

def fed(seed,ds,quick):
    X,y,fit,cal,te=dataset(seed,ds);rng=np.random.default_rng(seed);classes=len(np.unique(y));clients=[[] for _ in range(5)]
    for c in range(classes):
        idx=fit[y[fit]==c];rng.shuffle(idx);ass=rng.choice(5,len(idx),p=rng.dirichlet(np.ones(5)*.4))
        for j in range(5):clients[j].extend(idx[ass==j])
    clients=[np.asarray(c,int) for c in clients if c];assert len(clients)>=3
    part=digest(*[np.r_[len(c),c] for c in clients]);rows=[]
    # Client-only sufficient statistics, transmitted by the same explicit frame format.
    moment=[];initial_wire=0
    for idx in clients:
        v=X[idx].astype(np.float64);frame=encode_frame(np.stack([v.sum(0),(v*v).sum(0)]),len(idx),False)
        decoded,count=decode_frame(frame,(2,X.shape[1]),False);moment.append(decoded.astype(np.float64));initial_wire+=len(frame)
    moments=np.sum(moment,axis=0)/len(fit);mean=moments[0].astype(np.float32);std=np.sqrt(np.maximum(moments[1]-moments[0]**2,1.e-6)).astype(np.float32)
    normalizer=np.stack([mean,std]);initial_wire+=sum(len(encode_frame(normalizer,len(idx),False)) for idx in clients)
    scaler_bytes=normalizer.nbytes
    X=np.clip((X-mean)/std,-6,6).astype(np.float32)
    for budget in (8192,32768):
        # Model + active local model/delta + one gradient, excluding input and queued communication packets.
        for kind in ('raw','hdc'):
            d=X.shape[1] if kind=='raw' else min(256,(budget-scaler_bytes)//(classes*4*4))
            # Public deterministic generator: no retained projection matrix; one transient float32 matrix.
            if kind=='hdc':
                proj=codebook(X.shape[1],d,seed+42);features=unit(np.where(X@proj>=0,1.,-1.)).astype(np.float32);del proj
            else:features=unit(X).astype(np.float32)
            numeric=classes*d*4;workspace=4*numeric+scaler_bytes
            if workspace>budget:
                rows.append(dict(task='fed',seed=seed,dataset=ds,budget=budget,kind=kind,method='over_budget',condition='all',estimated_client_model_workspace=workspace,partition_sha256=part));continue
            for condition in ('clean','label_flip','model_poison','dropout'):
                for method in ('weighted','median','packed_weighted','packed_median'):
                    w=np.zeros((classes,d),np.float32);wire=initial_wire;t=time.perf_counter();active_n=[]
                    for nr in range(2 if quick else 8):
                        updates=[];counts=[]
                        for j,idx in enumerate(clients):
                            if condition=='dropout' and j==nr%len(clients):continue
                            # Count real serialized downlink + uplink for each participating client; no external networking.
                            down=encode_frame(w,len(idx),False);local,_=decode_frame(down,w.shape,False);wire+=len(down)
                            labels=y[idx].copy()
                            if condition=='label_flip' and j==0:labels=(labels+1)%classes
                            update=softmax_update(features[idx],labels,local,lr=.08) if kind=='raw' else hdc_local_update(features[idx],labels,local,lr=.08)
                            if condition=='model_poison' and j==0:update=-update*8+2
                            up=encode_frame(update,len(idx),method.startswith('packed_'));a,c=decode_frame(up,w.shape,method.startswith('packed_'));wire+=len(up);updates.append(a);counts.append(c)
                        active_n.append(len(updates));w+=aggregate(np.stack(updates),counts,method.replace('packed_','')).astype(np.float32)
                    pred=(features[te]@w.T).argmax(1) if kind=='raw' else scores(features[te],w).argmax(1)
                    rows.append(dict(task='fed',seed=seed,dataset=ds,budget=budget,kind=kind,d=d,method=method,condition=condition,partition_sha256=part,split_sha256=digest(fit,cal,te),n=len(te),correct=int((pred==y[te]).sum()),wire_bytes=wire,model_bytes=numeric+scaler_bytes,initial_wire_bytes=initial_wire,estimated_client_model_workspace=workspace,server_aggregate_array_bytes=len(clients)*numeric,elapsed=time.perf_counter()-t,active_clients=active_n))
    return rows

def visual(seed,ds,quick):
    from sklearn.linear_model import LogisticRegression
    X,y,fit,cal,te=dataset(seed,ds);rng=np.random.default_rng(seed);C=len(np.unique(y));rows=[];split=digest(fit,cal,te);lo=X[fit].min(0);span=np.maximum(X[fit].max(0)-lo,1e-8);X=np.clip((X-lo)/span,0,1);scaler_bytes=lo.nbytes+span.nbytes
    # Streaming binary training: retained heads + packed codebook, bounded scratch per record. Raw input corpus external.
    def train(enc,pairs,k,repel=False):
        init_rng=np.random.default_rng(seed+enc.d);ix=np.concatenate([init_rng.choice(fit[y[fit]==c],min(k,np.sum(y[fit]==c)),replace=False) for c in range(C)]);h=enc.batch(X[ix],pairs);m=PackedSearch(h,y[ix],enc.d,k,seed+5)
        for j in fit:m.update(enc.encode(X[j],pairs),int(y[j]),.5,repel)
        return m
    for budget in (4096,16384):
        d=128 if budget==4096 else 512;coarse=RecordEncoder(X.shape[1],d//2,8,seed);fine=RecordEncoder(X.shape[1],d,8,seed+1);a=train(coarse,False,3);b=train(fine,True,3);rep=train(fine,True,3,True)
        def row(method,p,bytes_,**kw):rows.append(dict(task='binary',seed=seed,dataset=ds,budget=budget,method=method,split_sha256=split,n=len(te),correct=int((p==y[te]).sum()),numeric_bytes=int(bytes_+scaler_bytes),**kw))
        ca=a.predict(coarse.batch(X[cal]));fb=b.predict(fine.batch(X[cal],True));gs=np.array([a.decision(coarse.encode(x))[1] for x in X[cal]])
        # Calibration only: maximize accuracy penalizing routing; fixed candidate thresholds.
        t=max((0.,.02,.05,.10,.20),key=lambda v:np.mean(np.where(gs<v,fb,ca)==y[cal])-.025*np.mean(gs<v))
        lazy=LazyCascade(coarse,fine,a,b,t);assert lazy.numeric_bytes+scaler_bytes<=budget
        tick=time.perf_counter();lp=lazy.predict(X[te]);lat=time.perf_counter()-tick
        ah=coarse.batch(X[te]);bh=fine.batch(X[te],True);pa=a.predict(ah);pb=b.predict(bh);g=np.array([a.decision(q)[1] for q in ah]);assert np.array_equal(lp,np.where(g<t,pb,pa));assert lazy.fine_calls==int((g<t).sum())
        row('record',pa,coarse.numeric_bytes+a.numeric_bytes,route_fraction=0.)
        row('record_pair',pb,fine.numeric_bytes+b.numeric_bytes,route_fraction=1.)
        row('repel_experiment',rep.predict(bh),fine.numeric_bytes+rep.numeric_bytes,route_fraction=1.)
        row('lazy',lp,lazy.numeric_bytes,route_fraction=lazy.fine_calls/len(te),threshold=t,prediction_parity=True,inference_seconds=lat,fine_calls=lazy.fine_calls)
        raw=LogisticRegression(max_iter=300).fit(X[fit],y[fit]);nb=raw.coef_.nbytes+raw.intercept_.nbytes
        if nb+scaler_bytes<=budget:row('raw_logistic',raw.predict(X[te]),nb,route_fraction=0.)
        else:rows.append(dict(task='binary',seed=seed,dataset=ds,budget=budget,method='raw_logistic_over_budget',numeric_bytes=nb+scaler_bytes,split_sha256=split))
    return rows

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--quick',action='store_true');ap.add_argument('--seed',type=int);ap.add_argument('--out',required=True);args=ap.parse_args();rows=[]
    for seed in ([args.seed] if args.seed else ([1701] if args.quick else [1723,1733,1741])):
        rows+=maze(seed,args.quick)
        for ds in (['synthetic'] if args.quick else ['digits','wine']):rows+=fed(seed,ds,args.quick)+visual(seed,ds,args.quick)
    Path(args.out).write_text(json.dumps(dict(schema='cognitum.e2g.closeout.v1',rows=rows,production_enabled=False,scope='matched retained RL/visual bytes; federated estimated active client model workspace, excludes input caches, encoding temporaries, server aggregate and framework memory; frame payload both directions, not authenticated network traffic; offline simulation'),indent=2)+'\n');print(len(rows),'rows')
if __name__=='__main__':main()
