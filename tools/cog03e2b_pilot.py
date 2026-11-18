"""Fixed-seed matched-dimension pilots. Quick fixture needs no scikit-learn."""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F
from cognitum.research.hdc_frontier_learning import (TrainableItems,PhaseMemory,exported_scores,margin_fit,hinge,informative,expanded_dot,channel_bind)

def sign(x):return np.where(x>=0,1,-1)
def datasets(quick,seed):
    rng=np.random.default_rng(seed)
    if quick:
        y=np.repeat(np.arange(3),48);centers=rng.uniform(.1,.9,(3,8));x=np.clip(centers[y]+rng.normal(0,.12,(len(y),8)),0,1);order=rng.permutation(len(y));i,j=order[:108],order[108:];return [('synthetic',x[i],y[i],x[j],y[j])]
    from sklearn.datasets import load_digits,load_wine
    from sklearn.model_selection import train_test_split
    data=[]
    for name,loader in [('digits',load_digits),('wine',load_wine)]:
        t=loader();x=t.data;y=t.target;i,j=train_test_split(np.arange(len(y)),test_size=.25,stratify=y,random_state=seed);lo=x[i].min(0);hi=x[i].max(0);z=np.clip((x-lo)/np.maximum(hi-lo,1e-12),0,1);data.append((name,z[i],y[i],z[j],y[j]))
    return data

def run(quick=False):
    torch.set_num_threads(1);rows=[]
    for seed in ([811] if quick else [811,823]):
      for name,x,y,z,t in datasets(quick,seed):
       x=np.minimum((x*8).astype(int),7);z=np.minimum((z*8).astype(int),7);c=int(y.max()+1);f=x.shape[1];n=len(t)
       split=hashlib.sha256(x.tobytes()+y.tobytes()+z.tobytes()+t.tobytes()).hexdigest()
       for d in [32]:
        rng=np.random.default_rng(seed);epochs=3;orders=[rng.permutation(len(x)) for _ in range(epochs)];batches=[ix[j:j+32] for ix in orders for j in range(0,len(ix),32)]
        def record(arm,p,**kw):
            rows.append(dict(dataset=name,seed=seed,d=d,arm=arm,split=split,n=n,correct=int(np.sum(p==t)),**kw))
        for arm,learn in [('thdc_joint',True),('thdc_static',False)]:
            a=TrainableItems(f,8,c,d,seed,learn_items=learn);opt=torch.optim.Adam([p for p in a.parameters() if p.requires_grad],lr=.01);start=time.perf_counter()
            for i in batches:
                opt.zero_grad();loss=F.cross_entropy(a(x[i]),torch.tensor(y[i]));loss.backward();opt.step()
            p,v,w=a.exported();scores=exported_scores(z,p,v,w);native=a(z).detach().numpy();assert np.argmax(scores,1).tolist()==np.argmax(native,1).tolist()
            arr=sum(p.numel()*p.element_size() for p in a.parameters());mom=sum(v.numel()*v.element_size() for state in opt.state.values() for v in state.values() if isinstance(v,torch.Tensor));grad=sum(p.grad.numel()*p.grad.element_size() for p in a.parameters() if p.grad is not None)
            record(arm,scores.argmax(1),inference_logical_bytes=a.logical_inference_bytes(),training_array_bytes=arr+mom,gradient_bytes=grad,optimizer_bytes=mom,seconds=time.perf_counter()-start)
        for rule,lr in [('threshold',1),('sgd',10),('adam',.75),('adam6',.75)]:
            a=PhaseMemory(f,8,c,d,seed=seed,rule=rule,lr=lr);start=time.perf_counter();writes=0
            for i in batches:
                _,w=a.update(x[i],y[i]);writes+=w
            record('phase_'+rule,a.scores(z).argmax(1),inference_logical_bytes=a.ideal_grid_bytes(),training_array_bytes=a.persistent_array_bytes(),optimizer_bytes=a.persistent_array_bytes()-sum(q.nbytes for q in a.tables),writes=writes,seconds=time.perf_counter()-start)
        # Same bipolar encoded input, universal mask and matched random controls.
        p=rng.choice([-1,1],(f,d));v=rng.choice([-1,1],(8,d));a=sign(channel_bind(x[:,None,:],p,v));b=sign(channel_bind(z[:,None,:],p,v));w=np.array([a[y==k].sum(0) for k in range(c)]);full=sign(w);record('bipolar_full',(b@full.T).argmax(1),classifier_bits=c*d)
        _,_,delta,sh=informative(a,y,full);count=max(1,d//4);key=np.maximum(delta.max(0),sh.max(0));sel=np.argsort(-key,kind='stable')[:count];rnd=rng.permutation(d)[:count]
        for arm,ix in [('informative',sel),('random',rnd)]:
            aa=a[:,ix];bb=b[:,ix];model=full[:,ix];record(arm+'_pruned',(bb@model.T).argmax(1),classifier_bits=c*count)
            model=w[:,ix].astype(float)/np.maximum(1,np.bincount(y,minlength=c)[:,None]);lr=.05
            for order in orders:
                for i in order:
                    pred=int((model@aa[i]).argmax());truth=y[i]
                    if pred!=truth:model[truth]+=lr*aa[i];model[pred]-=lr*aa[i]
            # Quantize class weights using one common training-only scale.
            scale=max(1e-12,float(np.abs(model).max()));m=12;k=np.clip(np.rint((model/scale+1)*m/2),0,m).astype(int);q=np.ones_like(k);scores=expanded_dot(bb,k,q,m);assert np.array_equal(scores,bb@(2*k-m).T)
            record(arm+'_real',(bb@model.T).argmax(1),classifier_bits=64*c*count)
            record(arm+'_expanded',scores.argmax(1),classifier_bits=m*c*count,exact_quantized_score_parity=True)
        # Binary fixed subset, no bias. Same features for all controls.
        c0,c1=(3,8) if name=='digits' else (0,1);ix=np.isin(y,[c0,c1]);jx=np.isin(t,[c0,c1]);ax=a[ix]/np.sqrt(d);bx=b[jx]/np.sqrt(d);ay=np.where(y[ix]==c1,1,-1);by=np.where(t[jx]==c1,1,-1);lam=.05
        w=margin_fit(ax,ay,lam,epochs=300);cent=ax[ay==1].mean(0)-ax[ay==-1].mean(0)
        for arm,u in [('margin_independent',w),('margin_centroid',cent)]:rows.append(dict(dataset=name,seed=seed,d=d,arm=arm,split=split,n=len(by),correct=int(np.sum(sign(bx@u)==by)),objective=hinge(ax,ay,u,lam)[0]))
        if not quick:
            from sklearn.svm import LinearSVC
            svc=LinearSVC(C=1/(lam*len(ay)),loss='hinge',dual=True,fit_intercept=False,tol=1e-8,max_iter=20000,random_state=seed).fit(ax,ay);u=svc.coef_[0];rows.append(dict(dataset=name,seed=seed,d=d,arm='margin_svm',split=split,n=len(by),correct=int(np.sum(sign(bx@u)==by)),objective=hinge(ax,ay,u,lam)[0],prediction_disagreements=int(np.sum(sign(bx@u)!=sign(bx@w)))))
    return {'schema':'cognitum.cog03e2b.pilot.v1','quick':quick,'rows':rows,'note':'dimension matched; not equal training bytes; actual numpy moment arrays in fake-quant arm; ideal packed inference bytes not hardware measurements'}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--quick',action='store_true');p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(run(a.quick),indent=2)+'\n',encoding='utf8')
