"""Reproducible scoped pilot; real Digits, simulated subject-disjoint HAR.
No source paper dataset, quantized pretrained CNN or FPGA replication claim.
"""
import argparse,json,time
from pathlib import Path
import numpy as np
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split
from sklearn.metrics import adjusted_rand_score,normalized_mutual_info_score,roc_auc_score
from cognitum.research.hdc_uncertain_visual import LevelEncoder,VisualBank,Mondrian,scores,nonconformity


def har(seed):
    rng=np.random.default_rng(seed); C=4; D=256; T=8; grams=6
    proto=rng.choice([-1,1],(C,D)).astype(np.int8)
    def sample(groups,shift=0.):
        xs=[];ys=[];gs=[]
        for g in groups:
            common=rng.random(D)<.10
            for k in range(C):
                for _ in range(T):
                    err=rng.random((grams,D))<(.23+shift)
                    xs.append(np.where(err^common, -proto[k],proto[k]));ys.append(k);gs.append(g)
        return np.asarray(xs),np.asarray(ys),np.asarray(gs)
    x,y,g=sample(range(20));p=np.stack([np.where(x[y==k].sum((0,1))>=0,1,-1) for k in range(C)])
    cal,cy,cg=sample(range(20,40));test,ty,tg=sample(range(40,60));shift,sy,sg=sample(range(60,80),.22)
    assert len(set(g)&set(cg))==len(set(g)&set(tg))==len(set(cg)&set(tg))==0
    a=scores(cal,p);b=scores(test,p);s=scores(shift,p);out=[]
    for name,w in [('distance',(1,0,0)),('gap',(0,1,0)),('dispersion',(0,0,1)),('combined',(1,1,1))]:
        ca=nonconformity(a,w); ta=nonconformity(b,w); sh=nonconformity(s,w)
        ood=roc_auc_score(np.r_[np.zeros(len(ta)),np.ones(len(sh))],np.r_[ta.min(1),sh.min(1)])
        for mode in ['window','subject_max']:
            m=Mondrian(.1).fit(ca,cy,cg if mode=='subject_max' else None)
            for condition,xx,yy,gg in [('clean',ta,ty,tg),('shift',sh,sy,sg)]:
                mask=m.predict(xx);hit=mask[np.arange(len(yy)),yy];singleton=mask.sum(1)==1
                group_class=[bool(hit[(gg==g)&(yy==k)].all()) for g in np.unique(gg) for k in range(C)]
                out.append(dict(seed=seed,score=name,calibration=mode,condition=condition,coverage=float(hit.mean()),group_class_coverage=float(np.mean(group_class)),mean_set_size=float(mask.sum(1).mean()),singleton_rate=float(singleton.mean()),singleton_error=float(1-hit[singleton].mean()) if singleton.any() else None,ood_auc=float(ood),n=len(yy),cal_counts=m.counts.tolist()))
    return out

class EuclideanBank:
    """Fixed-slot conventional online centroid control, labels never passed."""
    def __init__(self,f,budget):
        self.cap=budget//(4*f+8);self.n=0
        self.a=np.zeros((self.cap,f),np.float32);self.count=np.zeros(self.cap,np.int64)
    @property
    def numeric_bytes(self):return self.a.nbytes+self.count.nbytes
    def predict(self,q):return (int(np.argmin(np.sum((self.a[:self.n]-q)**2,axis=1))) if self.n else -1)
    def observe(self,q):
        j=self.predict(q)
        if self.n<self.cap and (j<0 or np.mean((self.a[j]-q)**2)>.025):self.a[self.n]=q;self.count[self.n]=1;self.n+=1
        else:self.count[j]+=1;self.a[j]+=(q-self.a[j])/self.count[j]
        return j

def visual(seed,d,budget,threshold=.68):
    rng=np.random.default_rng(seed); X,y=load_digits(return_X_y=True);X=np.rint(X*15/16).astype(np.uint8)
    ix,tx=train_test_split(np.arange(len(y)),test_size=.3,stratify=y,random_state=seed)
    order=rng.permutation(10); phases=np.array_split(order,5); enc=LevelEncoder(64,d,16,seed)
    cap=min(128,(budget-enc.numeric_bytes)//((d+7)//8+24))
    if cap<2: return []
    rows=[]
    # Fixed sequential classes, with training labels scheduling only, not passed to learner.
    for name in ['merge','replace','fixed','euclidean']:
        bank=EuclideanBank(64,budget) if name=='euclidean' else VisualBank(d,cap,seed=seed,novelty_floor=threshold,mode=name)
        feat=lambda i:X[i].astype(np.float32)/15 if name=='euclidean' else enc.encode(X[i])
        pred=lambda i:bank.predict(feat(i)) if name=='euclidean' else bank.predict(feat(i))[0]
        seen=[];prev={}; phase_rows=[];start=time.perf_counter()
        for phase,classes in enumerate(phases):
            ids=ix[np.isin(y[ix],classes)];ids=np.random.default_rng(seed+phase+100).permutation(ids)
            for i in ids:bank.observe(feat(i))
            seen.extend(classes.tolist()); eval_ids=tx[np.isin(y[tx],seen)];preds=np.array([pred(i) for i in eval_ids]);truth=y[eval_ids]
            # Score cluster validity, not supervised accuracy. A separate fixed mapping would need validation labels.
            ari=adjusted_rand_score(truth,preds);nmi=normalized_mutual_info_score(truth,preds)
            pair_ari={}
            for k,oldclasses in enumerate(phases[:phase+1]):
                mask=np.isin(truth,oldclasses);pair_ari[k]=float(adjusted_rand_score(truth[mask],preds[mask]))
                prev[k]=max(prev.get(k,-1.),pair_ari[k])
            phase_rows.append(dict(phase=phase,ari=float(ari),nmi=float(nmi),n_test=len(truth),new_pair_ari=pair_ari[phase],old_pair_forgetting=float(np.mean([prev[k]-pair_ari[k] for k in range(phase)])) if phase else 0.,clusters=bank.n))
        rows.append(dict(seed=seed,dimension=d,budget=budget,novelty_floor=threshold,method=name,numeric_bytes=bank.numeric_bytes+(0 if name=='euclidean' else enc.numeric_bytes),seconds=time.perf_counter()-start,merges=getattr(bank,'merges',0),phases=phase_rows))
    return rows

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--quick',action='store_true');ap.add_argument('--out',required=True);a=ap.parse_args()
    seeds=[1103] if a.quick else [1103,1109,1151];u=[];v=[]
    for seed in seeds:
        u.extend(har(seed))
        for d in ([128] if a.quick else [128,256]):
            for budget in ([8192] if a.quick else [4096,8192,16384]):v.extend(visual(seed,d,budget))
        v.extend(visual(seed,256,4096,.85))
    assert all(r['numeric_bytes']<=r['budget'] for r in v)
    Path(a.out).write_text(json.dumps({'uncertainty':u,'visual':v,'scope':'Simulated subjects/window HVs, Digits fixed quantized pixels, unsupervised cluster metrics; numeric retained state only; no paper dataset or hardware replication.'},indent=2)+'\n')
if __name__=='__main__':main()
