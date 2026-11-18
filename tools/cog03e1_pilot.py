"""E1A matched learning pilot. Full local experiments use sklearn public
bundled digits/wine; quick CI fixture requires only inherited dependencies.
Fixed splits, train-only scaler, shared batch order, no test-set tuning.
Native results are preserved even when adaptive regeneration is a no-op.
"""
import argparse,hashlib,io,json,time
from pathlib import Path
import numpy as np
import torch
from torchhd import classifiers
from torch.utils.data import DataLoader,TensorDataset
from cognitum.research.hdc_learning import Prototype,RandomFeatures,neural_regeneration_scores,dist_regeneration_scores,density_ridge


def dataset(name,seed):
    rng=np.random.default_rng(seed)
    if name=='synthetic':
        y=np.repeat(np.arange(3),48);x=rng.normal(size=(len(y),8))*.22+rng.normal(size=(3,8))[y]
    else:
        from sklearn.datasets import load_digits,load_wine
        data=load_digits() if name=='digits' else load_wine();x,y=data.data,data.target
    train=[];test=[]
    for c in np.unique(y):
        ix=rng.permutation(np.flatnonzero(y==c));k=max(1,len(ix)//4);test.extend(ix[:k]);train.extend(ix[k:])
    tr=rng.permutation(train);te=rng.permutation(test);assert not set(tr)&set(te)
    lo=x[tr].min(0);scale=np.maximum(x[tr].max(0)-lo,1e-8)
    a=np.clip((x[tr]-lo)/scale,0,1).astype('float32');b=np.clip((x[te]-lo)/scale,0,1).astype('float32')
    return a,y[tr].astype('int64'),b,y[te].astype('int64'),lo,scale,hashlib.sha256(np.concatenate((tr,[-1],te)).astype('<i8').tobytes()).hexdigest()


def payload(arrays):
    arrays={k:np.asarray(v) for k,v in arrays.items()};buf=io.BytesIO();np.savez(buf,**arrays)
    return sum(v.nbytes for v in arrays.values()),len(buf.getvalue())


def state_native(m):
    # Deduplicate aliases (intRVFL exposes same encoding via two paths).
    seen=set();out={}
    for k,v in m.state_dict().items():
        identity=(v.untyped_storage().data_ptr(),v.storage_offset(),v.numel())
        if identity not in seen:out[k]=v.detach().cpu().numpy();seen.add(identity)
    return out


def evaluate(name,seed,d,epochs):
    torch.set_num_threads(1)
    a,y,b,t,lo,scale,split=dataset(name,seed);c=int(y.max())+1;f=a.shape[1];data=DataLoader(TensorDataset(torch.tensor(a),torch.tensor(y)),batch_size=32,shuffle=False)
    at,bt=torch.tensor(a),torch.tensor(b);rows=[]
    def record(arm,p,arrays,train,infer,**extra):
        assert p.shape==t.shape and np.isin(p,np.arange(-1,c)).all()
        total,serialized=payload({**arrays,'scale_min':lo,'scale_span':scale});cm=np.zeros((c,c+1),int);np.add.at(cm,(t,np.where(p==-1,c,p)),1)
        rows.append(dict(dataset=name,seed=seed,dimension=d,split=split,arm=arm,n=len(t),correct=int((p==t).sum()),abstain=int((p==-1).sum()),numeric_bytes=total,snapshot_bytes=serialized,train_seconds=train,infer_seconds=infer,confusion=cm.tolist(),prediction_digest=hashlib.sha256(p.astype('<i8').tobytes()).hexdigest(),**extra))
    for label,cls,kw in [('vanilla',classifiers.Vanilla,{'n_levels':16,'min_level':0.,'max_level':1.}),('adapt',classifiers.AdaptHD,{'n_levels':16,'min_level':0.,'max_level':1.,'epochs':epochs,'lr':.1}),('online',classifiers.OnlineHD,{'epochs':epochs,'lr':.1}),('neural',classifiers.NeuralHD,{'epochs':epochs,'lr':.1,'regen_freq':2,'regen_rate':.1}),('dist',classifiers.DistHD,{'epochs':epochs,'lr':.1,'regen_freq':2,'regen_rate':.1}),('rvfl',classifiers.IntRVFL,{'alpha':1.})]:
        torch.manual_seed(seed);n=cls(f,d,c,**kw);initial=state_native(n);enc0=None if label not in ('neural','dist') else n.encoder.weight.detach().numpy().copy();bias0=n.encoder.bias.detach().numpy().ravel().copy() if label=='neural' else None
        # Before training, export the native fixed feature states only for parity controls.
        if label in ('vanilla','adapt','online','rvfl'):
            h=(n.model.encode(at) if label=='rvfl' else n.encoder(at)).detach().numpy();g=(n.model.encode(bt) if label=='rvfl' else n.encoder(bt)).detach().numpy()
            enc_state={k:v.copy() for k,v in initial.items() if k!='model.weight'}
        start=time.perf_counter();failure=None
        try:n.fit(data)
        except TypeError as exc:
            if label!='dist' or 'topk()' not in str(exc) or 'not int' not in str(exc):raise
            failure=str(exc)
        elapsed=time.perf_counter()-start
        changed=None if enc0 is None else int(np.any(n.encoder.weight.detach().numpy()!=enc0,axis=1).sum())
        if failure is None:
            start=time.perf_counter();s=n(bt).detach().numpy();infer=time.perf_counter()-start;p=s.argmax(1)
            record('native_'+label,p,state_native(n),elapsed,infer,changed_projection_rows=changed,fit_epochs=1 if label in ('vanilla','rvfl') else epochs)
        else:
            rows.append(dict(dataset=name,seed=seed,dimension=d,split=split,arm='native_'+label,n=len(t),correct=None,fit_failed=True,error=failure,changed_projection_rows=changed,train_seconds=elapsed))
        if label in ('vanilla','adapt','online'):
            m=Prototype(c,d);start=time.perf_counter();steps=1 if label=='vanilla' else epochs
            for _ in range(steps):
                for j in range(0,len(y),32):m.update(h[j:j+32],y[j:j+32],rule=label,lr=1. if label=='vanilla' else .1)
            elapsed=time.perf_counter()-start;start=time.perf_counter();cs=m.scores(g);cp=cs.argmax(1);infer=time.perf_counter()-start
            # Timings exclude native encoding for shared-operand comparisons; explicitly labeled.
            record('custom_'+label,cp,{**enc_state,'weight':m.weights},elapsed,infer,scope='preencoded update/score only; native includes encoding',native_prediction_disagreements=int((cp!=p).sum()),max_weight_error=float(np.max(np.abs(m.weights-n.model.weight.detach().numpy()))),updates=m.updates)
        elif label=='rvfl':
            for policy,arm in [('native_rank','custom_rvfl'),('full_rank','custom_rvfl_full_rank')]:
                start=time.perf_counter();w=density_ridge(h,y,c,cutoff=policy);elapsed=time.perf_counter()-start;start=time.perf_counter();cp=(g@w.T).argmax(1);infer=time.perf_counter()-start;record(arm,cp,{**enc_state,'weight':w},elapsed,infer,scope='preencoded readout only',cutoff=policy,native_prediction_disagreements=int((cp!=p).sum()),max_weight_error=float(np.max(np.abs(w-n.model.weight.detach().numpy()))))
        else:
            e=RandomFeatures(enc0,bias0,kind='sinusoid' if label=='neural' else 'linear');m=Prototype(c,d);r=np.random.default_rng(seed+79);events=0;start=time.perf_counter()
            for epoch in range(epochs):
                for j in range(0,len(y),32):
                    h=e.encode(a[j:j+32]);m.update(h,y[j:j+32],rule=('vanilla' if epoch==0 else 'adapt') if label=='neural' else 'online',lr=(1. if epoch==0 and label=='neural' else .1))
                if (epoch+1)%2==0:
                    w=m.weights
                    if label=='neural':scores=neural_regeneration_scores(w)
                    else:scores=sum((dist_regeneration_scores(e.encode(a[j:j+32]),y[j:j+32],w) for j in range(0,len(y),32)),np.zeros(d))
                    ix=np.argsort(scores,kind='stable')[:int(np.ceil(.1*d))];e.regenerate(ix,r,m);events+=len(ix)
            elapsed=time.perf_counter()-start;w,bias=e.state();start=time.perf_counter();cp=m.scores(e.encode(b)).argmax(1);infer=time.perf_counter()-start;record('custom_regen_'+label,cp,{'projection':w,'bias':bias,'weight':m.weights},elapsed,infer,changed_projection_rows=int(np.any(w!=enc0,axis=1).sum()),regeneration_events=events,scope='explicit independent regeneration; no native behavioral parity claim')
    for kind in ('sinusoid','phase'):
        e=RandomFeatures.seeded(f,d,seed,kind=kind);h=e.encode(a[:1]);m=Prototype(c,d,h.dtype);start=time.perf_counter()
        for epoch in range(epochs):
            for j in range(0,len(y),32):m.update(e.encode(a[j:j+32]),y[j:j+32],rule='vanilla' if epoch==0 else 'margin',lr=1. if epoch==0 else .1)
        elapsed=time.perf_counter()-start;start=time.perf_counter();cp=m.predict(e.encode(b),min_margin=0.);infer=time.perf_counter()-start;w,bias=e.state();record('custom_margin_'+kind,cp,{'projection':w,'bias':bias,'weight':m.weights},elapsed,infer,scope='same dimension, not equal bytes; no RefineHD replication')
    if name!='synthetic':
        from sklearn.linear_model import LogisticRegression
        from sklearn.svm import SVC
        for label,n in [('logistic',LogisticRegression(max_iter=1000,random_state=seed)),('rbf_svm',SVC(C=1.,gamma='scale'))]:
            start=time.perf_counter();n.fit(a,y);elapsed=time.perf_counter()-start;start=time.perf_counter();p=n.predict(b);infer=time.perf_counter()-start
            arrays={k:v for k,v in vars(n).items() if isinstance(v,np.ndarray)}
            record(label,p,arrays,elapsed,infer,scope='numerical ndarray state, not serialized estimator API')
    return rows


def main():
    p=argparse.ArgumentParser();p.add_argument('--quick',action='store_true');p.add_argument('--out',required=True);p.add_argument('--dataset',choices=['digits','wine']);p.add_argument('--seed',type=int,default=711);p.add_argument('--dimension',type=int,default=128);a=p.parse_args()
    rows=evaluate('synthetic' if a.quick else (a.dataset or 'digits'),a.seed,32 if a.quick else a.dimension,3 if a.quick else 8)
    Path(a.out).write_text(json.dumps({'rows':rows,'scope':'fixed held-out pilot; numerical/snapshot arrays not whole process memory; fixed settings not tuned; native and custom preencoded timing incomparable directly'},indent=2)+'\n',encoding='utf8')
if __name__=='__main__':main()
