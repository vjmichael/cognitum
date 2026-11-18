"""Paired local-only learning pilot; no network and no environment authority."""
import argparse,json,time,hashlib
from pathlib import Path
import numpy as np
from cognitum.research.hdc_cooperative_learning import *

def digest(*a):return hashlib.sha256(b''.join(np.asarray(x).astype('<i8').tobytes() for x in a)).hexdigest()

def rl(seed,quick):
    rng=np.random.default_rng(seed);side=5;N=side**2;goal=N-1;A=4
    delta=np.array([[-1,0],[1,0],[0,-1],[0,1]])
    def step(s,a):
        p=np.clip(np.array(divmod(s,side))+delta[a],0,side-1);n=int(p[0]*side+p[1]);return n,1. if n==goal else -.04,n==goal
    # Fixed uniform offline replay; no online collection by learned policy.
    n=1800 if quick else 9000;ss=rng.integers(N-1,size=n);aa=rng.integers(A,size=n);start=rng.integers(N-1,size=20 if quick else 80)
    replay=[(int(s),int(a),*step(s,a)) for s,a in zip(ss,aa)]
    rows=[]
    features={'tabular':np.eye(N)}
    for dim in (64,256):features[f'iid_{dim}']=codebook(N,dim,seed);features[f'bound_{dim}']=grid_features(side,dim,seed)
    for name,f in features.items():
        t=time.perf_counter();q=OfflineQ(f,A,alpha=.2,gamma=.95)
        for s,a,n,r,done in replay:q.update(s,a,r,n,done)
        fit=time.perf_counter()-t;returns=[];wins=0
        for s in start:
            total=0.;discount=1.
            for _ in range(40):
                a=int(q.q(s).argmax());s,r,done=step(s,a);total+=discount*r;discount*=.95
                if done:wins+=1;break
            returns.append(total)
        mat=unit(f);g=mat@mat.T;np.fill_diagonal(g,0)
        rows.append(dict(task='rl',seed=seed,method=name,replay_sha256=digest(ss,aa,start),n=len(start),success=wins,mean_return=float(np.mean(returns)),return_p10=float(np.quantile(returns,.1)),max_abs_cross_state_similarity=float(abs(g).max()),fit_seconds=fit,numeric_bytes=q.numeric_bytes,weight_bytes=q.w.nbytes))
    return rows

def classification(seed,quick,dataset):
    from sklearn.datasets import load_digits,load_wine,make_blobs
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    from sklearn.semi_supervised import SelfTrainingClassifier
    if dataset=='synthetic':X,y=make_blobs(n_samples=240,centers=4,n_features=8,cluster_std=2.5,random_state=seed)
    elif dataset=='digits':X,y=load_digits(return_X_y=True)
    else:X,y=load_wine(return_X_y=True)
    idx=np.arange(len(y));tr,te=train_test_split(idx,test_size=.25,stratify=y,random_state=seed);C=len(np.unique(y));s=StandardScaler().fit(X[tr]);x=s.transform(X[tr]);xt=s.transform(X[te]);yt=y[tr];d=128 if quick else 256
    rng=np.random.default_rng(seed);P=rng.normal(size=(x.shape[1],d));h=bipolar(x@P);ht=bipolar(xt@P);split=digest(tr,te);enc_bytes=P.nbytes+s.mean_.nbytes+s.scale_.nbytes
    rows=[]
    def row(task,method,pred,bytes_,**kw):rows.append(dict(task=task,method=method,dataset=dataset,seed=seed,split_sha256=split,n=len(te),correct=int(np.sum(pred==y[te])),model_bytes=int(bytes_),**kw))
    # Non-IID partition, with Dirichlet class-level proportions including missing classes.
    clients=[[] for _ in range(5)]
    for c in range(C):
        i=np.flatnonzero(yt==c);rng.shuffle(i);a=rng.choice(5,size=len(i),p=rng.dirichlet(np.full(5,.3)))
        for j in range(5):clients[j].extend(i[a==j])
    clients=[np.array(a,dtype=int) for a in clients if len(a)];counts=np.array([len(a) for a in clients]);assert sum(counts)==len(tr)
    partition=digest(*[np.r_[len(a),a] for a in clients]);p=sums(h,yt,C);local=np.stack([sums(h[i],yt[i],C) for i in clients]);assert np.array_equal(local.sum(0),p)
    row('fed','central_sum',scores(ht,p).argmax(1),p.nbytes+enc_bytes,partition_sha256=partition,wire_bytes=0,condition='clean',update_seconds=0.)
    row('fed','federated_sum',scores(ht,local.sum(0)).argmax(1),p.nbytes+enc_bytes,partition_sha256=partition,wire_bytes=local.nbytes,condition='clean',update_seconds=0.)
    for condition in ('clean','poison','bit_noise'):
        for method in ('weighted','median','trimmed','packed_weighted','packed_median'):
            t=time.perf_counter();global_p=local.sum(0)/len(tr);wire=0
            for nround in range(3):
                u=np.stack([local_update(h[i],yt[i],global_p) for i in clients]);
                if condition=='poison':u[0]=-10*u.mean(0)+50
                if method.startswith('packed'):
                    decoded=[pack_update(v,.05 if condition=='bit_noise' else 0.,seed+nround*100+j) for j,v in enumerate(u)];u=np.stack([a[0] for a in decoded]);wire+=sum(a[1] for a in decoded)
                else:
                    # Same per-coordinate sign flips for dense communication control.
                    if condition=='bit_noise':u=np.stack([v*np.where(np.random.default_rng(seed+nround*100+j).random(v.size).reshape(v.shape)<.05,-1,1) for j,v in enumerate(u)])
                    wire+=u.nbytes
                global_p+=aggregate(u,counts,method.replace('packed_',''))
            row('fed',method,scores(ht,global_p).argmax(1),global_p.nbytes+enc_bytes,partition_sha256=partition,wire_bytes=wire,condition=condition,update_seconds=time.perf_counter()-t,clients=counts.tolist())
    # Only two or five labels per class are revealed; other training labels used for retrospective audit only.
    L=np.concatenate([rng.choice(np.flatnonzero(yt==c),size=min(5,np.sum(yt==c)),replace=False) for c in range(C)]);U=np.setdiff1d(np.arange(len(tr)),L);labelsplit=digest(tr[L],tr[U],te)
    p=sums(h[L],yt[L],C);row('semi','hdc_labeled',scores(ht,p).argmax(1),p.nbytes+enc_bytes,label_split=labelsplit,accepted=0,pseudo_correct=0)
    for margin in (.1,.3):
        p,ids,labels=pseudo_train(h[L],yt[L],h[U],C,margin,rounds=5,limit=64);row('semi',f'pseudo_{margin}',scores(ht,p).argmax(1),p.nbytes+enc_bytes,label_split=labelsplit,accepted=len(ids),pseudo_correct=int(np.sum(labels==yt[U[ids]])))
    raw=LogisticRegression(max_iter=300).fit(x[L],yt[L]);row('semi','raw_logistic_labeled',raw.predict(xt),raw.coef_.nbytes+raw.intercept_.nbytes+s.mean_.nbytes+s.scale_.nbytes,label_split=labelsplit,accepted=0,pseudo_correct=0)
    masked=np.full(len(tr),-1);masked[L]=yt[L];clf=SelfTrainingClassifier(LogisticRegression(max_iter=300),threshold=.85,max_iter=5).fit(x,masked);ids=U[clf.transduction_[U]>=0];row('semi','raw_self_training',clf.predict(xt),clf.estimator_.coef_.nbytes+clf.estimator_.intercept_.nbytes+s.mean_.nbytes+s.scale_.nbytes,label_split=labelsplit,accepted=len(ids),pseudo_correct=int(np.sum(clf.transduction_[ids]==yt[ids])))
    for k in (1,3):
        p,l=multiprototype(h,yt,C,k,seed);pred=packed_predict(ht,p,l);oracle=l[(ht.astype(np.int32)@p.astype(np.int32).T).argmax(1)];assert np.array_equal(pred,oracle);row('multi',f'packed_{k}',pred,np.packbits(p>0,axis=1).nbytes+l.nbytes+enc_bytes,prototypes=len(l),parity=True)
    p,l=multiprototype(h,yt,C,3,seed);p=stochastic_binary_train(h,yt,p,l,seed);row('multi','stochastic_binary_3',packed_predict(ht,p,l),np.packbits(p>0,axis=1).nbytes+l.nbytes+enc_bytes,prototypes=len(l))
    # Two declared binary tasks based on known class IDs, fitted on training only.
    target=[yt%2,(yt>=C/2).astype(int)];truth=[y[te]%2,(y[te]>=C/2).astype(int)];models=np.stack([unit(sums(h,v,2)) for v in target]);keys=codebook(2,d,seed+33);merged=task_superpose(models,keys)
    for j in range(2):
        for name,model,nb in [('separate',models[j],models.nbytes),('projected',task_recover(merged,keys[j]),merged.nbytes+keys.nbytes)]:
            rows.append(dict(task='task_projection',method=name,dataset=dataset,seed=seed,split_sha256=split,subtask=j,n=len(te),correct=int(np.sum(scores(ht,model).argmax(1)==truth[j])),model_bytes=nb+enc_bytes))
    # Independent coarse/fine projection control; no claim of reduced compute as both are precomputed here.
    P2=rng.normal(size=(x.shape[1],d));h2=bipolar(x@P2);t2=bipolar(xt@P2);a=scores(ht,sums(h,yt,C));b=scores(t2,sums(h2,yt,C));p,r=cascade_predict(a,b,.15)
    row('cascade','coarse',a.argmax(1),enc_bytes+C*d*8,route_fraction=0.)
    row('cascade','fine',b.argmax(1),enc_bytes+C*d*8,route_fraction=1.)
    row('cascade','hierarchical',p,enc_bytes+P2.nbytes+2*C*d*8,route_fraction=float(r.mean()))
    from sklearn.cluster import KMeans
    from sklearn.metrics import adjusted_rand_score,normalized_mutual_info_score
    for name,labels,nb in [('hdc_hamming',packed_predict(ht,binary_cluster(h,C,seed),np.arange(C)),enc_bytes+C*((d+7)//8)),('raw_kmeans',KMeans(n_clusters=C,n_init=3,random_state=seed).fit(x).predict(xt),C*x.shape[1]*8+s.mean_.nbytes+s.scale_.nbytes)]:
        rows.append(dict(task='cluster',method=name,dataset=dataset,seed=seed,split_sha256=split,n=len(te),ari=float(adjusted_rand_score(y[te],labels)),nmi=float(normalized_mutual_info_score(y[te],labels)),model_bytes=nb))
    full=LogisticRegression(max_iter=300).fit(x,yt);row('multi','raw_logistic',full.predict(xt),full.coef_.nbytes+full.intercept_.nbytes+s.mean_.nbytes+s.scale_.nbytes,prototypes=0)
    return rows

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--quick',action='store_true');ap.add_argument('--out',required=True);args=ap.parse_args();rows=[]
    for seed in ((1601,) if args.quick else (1601,1607,1613)):
        rows+=rl(seed,args.quick)
        for ds in (('synthetic',) if args.quick else ('digits','wine')):rows+=classification(seed,args.quick,ds)
    Path(args.out).write_text(json.dumps(dict(schema='cognitum.e2g.pilot.v1',rows=rows,production_enabled=False,scope='offline local simulated clients; retained numeric state only; no secure aggregation, DP or network; synthetic grid; independent mechanism references'),indent=2)+'\n');print(len(rows),'rows')
if __name__=='__main__':main()
