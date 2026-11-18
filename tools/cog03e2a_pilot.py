"""Paired retained numeric byte ceilings; not equal total peak working memory.
No held-out examples used for projection training, support selection or updates.
"""
import json, time, hashlib, argparse
import numpy as np
import torch
from torchhd import embeddings, classifiers
from torch.utils.data import DataLoader,TensorDataset
from tools.cog03e1_pilot import dataset, state_native
from cognitum.research.hdc_advanced_learning import MultiPrototype, budget_dimension, refine_step, train_projection, lehdc_dropout_reference
from cognitum.research.hdc_learning import RandomFeatures, Prototype, cosine_scores


def run(name,seed,budget):
    a,y,b,t,lo,scale,split=dataset(name,seed);c=int(y.max())+1;f=a.shape[1];rows=[]
    def record(arm,p,dim,arrays,train,infer,**extra):
        size=sum(v.nbytes for v in arrays)+lo.nbytes+scale.nbytes
        assert size<=budget and p.shape==t.shape
        rows.append(dict(dataset=name,seed=seed,split=split,budget=budget,arm=arm,d=dim,bytes=size,n=len(t),correct=int((p==t).sum()),abstain=int((p==-1).sum()),train_seconds=train,infer_seconds=infer,prediction_digest=hashlib.sha256(p.astype('<i8').tobytes()).hexdigest(),**extra))
    for k in (1,2,4):
        d=budget_dimension(f,c,k,budget);e=RandomFeatures.seeded(f,d,seed);p,w=e.state();h=e.encode(a);g=e.encode(b);m=MultiPrototype(c,d,k)
        start=time.perf_counter();m.update(h,y);elapsed=time.perf_counter()-start;start=time.perf_counter();pred=m.predict(g);infer=time.perf_counter()-start;record(f'multi_{k}',pred,d,[p,w,m.w,m.count],elapsed,infer,active_slots=int((m.count>0).sum()),scope='preencoded training and readout')
        # Class incremental: first k-shot per class, then rest of class. Evaluate seen classes only, all future classes masked.
        for shots in (1,5,None):
            m=MultiPrototype(c,d,k);trajectory=[];history=[];start=time.perf_counter()
            for label in range(c):
                ix=np.flatnonzero(y==label)[:shots];m.update(h[ix],y[ix]);pred=m.predict(g);acc=[float((pred[t==j]==j).mean()) for j in range(label+1)]
                history.append(acc);trajectory.append(dict(seen=label+1,accuracy=float((pred[t<=label]==t[t<=label]).mean()),unseen_false_accept=int(np.sum(pred[t>label]>=0))))
            elapsed=time.perf_counter()-start;start=time.perf_counter();pred=m.predict(g);infer=time.perf_counter()-start
            forgetting=float(np.mean([max(q[j] for q in history[j:])-history[-1][j] for j in range(c-1)]))
            record(f'multi_{k}_continual' if shots is None else f'multi_{k}_{shots}shot',pred,d,[p,w,m.w,m.count],elapsed,infer,trajectory=trajectory,forgetting=forgetting,scope='class-incremental all examples' if shots is None else 'class-incremental few-shot; no replay')
    d=budget_dimension(f,c,1,budget-16);e=RandomFeatures.seeded(f,d,seed);p,w=e.state();h=e.encode(a);g=e.encode(b)
    for arm in ('vanilla','online','refine_additive','refine_literal'):
        start=time.perf_counter();err=0.;n=0
        if arm.startswith('refine'):
            weights=np.zeros((c,d),np.float32);counts={}
            for v,label in zip(h,y):weights,err,n,kind=refine_step(weights,v[None,:],int(label),err,n,correct_rule=arm.split('_')[1]);counts[kind]=counts.get(kind,0)+1
        else:
            m=Prototype(c,d)
            for v,label in zip(h,y):m.update(v[None,:],np.array([label]),rule=arm)
            weights=m.weights;counts={}
        elapsed=time.perf_counter()-start;start=time.perf_counter();pred=cosine_scores(g,weights).argmax(1);infer=time.perf_counter()-start;record(arm,pred,d,[p,w,weights,np.array([err,n],np.float64)] if arm.startswith('refine') else [p,w,weights],elapsed,infer,branches=counts,scope='preencoded single-pass, not Flocet reproduction')
    rng=np.random.default_rng(seed+3);head=rng.normal(0,.03,(c,d)).astype('float32')
    for learn in (False,True):
        start=time.perf_counter();pp,bb,hh,loss=train_projection(a,y,p,w,head,epochs=10,learn=learn);elapsed=time.perf_counter()-start;start=time.perf_counter();pred=(RandomFeatures(pp,bb).encode(b)@hh.T).argmax(1);infer=time.perf_counter()-start;record('learned_projection' if learn else 'fixed_projection',pred,d,[pp,bb,hh],elapsed,infer,loss=loss,changed_rows=int(np.any(pp!=p,axis=1).sum()),scope='same initialization, softmax readout, 10 epochs')
    # Actual maintained native encoder, same linear initial weights and same readout, not sinusoid parity.
    torch.set_num_threads(1);torch.manual_seed(seed);enc=embeddings.Projection(f,d,requires_grad=True);readout=torch.nn.Linear(d,c,bias=False)
    with torch.no_grad():enc.weight.copy_(torch.tensor(p));readout.weight.copy_(torch.tensor(head))
    opt=torch.optim.SGD([*enc.parameters(),*readout.parameters()],lr=.05);at=torch.tensor(a);yt=torch.tensor(y);start=time.perf_counter()
    for epoch in range(10):
        for i in range(0,len(y),32):
            opt.zero_grad();loss=torch.nn.functional.cross_entropy(readout(enc(at[i:i+32])),yt[i:i+32]);loss.backward();opt.step()
    elapsed=time.perf_counter()-start;start=time.perf_counter();pred=readout(enc(torch.tensor(b))).detach().numpy().argmax(1);infer=time.perf_counter()-start;record('native_learned_linear',pred,d,[enc.weight.detach().numpy(),readout.weight.detach().numpy()],elapsed,infer,changed_rows=int(np.any(enc.weight.detach().numpy()!=p,axis=1).sum()),scope='actual TorchHD trainable Projection; different feature map')
    # Equal ceiling for retained training arrays: keys, levels, ternary and shadow,
    # two Adam moments, one shared gradient, Adam step scalar, and scaler.
    # Native optimizer is local to fit; reference audits the actual moment sizes.
    dd=(budget-lo.nbytes-scale.nbytes-4)//(4*(f+16+5*c))
    assert dd>0
    loader=DataLoader(TensorDataset(at,yt),batch_size=32,shuffle=False)
    for rate in (0.,.3):
        torch.manual_seed(seed);m=classifiers.LeHDC(f,dd,c,n_levels=16,min_level=0.,max_level=1.,epochs=4,dropout_rate=rate)
        h=m.encoder(at).detach().numpy();g=m.encoder(torch.tensor(b)).detach().numpy()
        torch.manual_seed(seed+30);start=time.perf_counter();m.fit(loader);elapsed=time.perf_counter()-start;m.eval();start=time.perf_counter();pred=m(torch.tensor(b)).detach().numpy().argmax(1);infer=time.perf_counter()-start
        start=time.perf_counter();shadow,weight,optim=lehdc_dropout_reference(h,y,c,seed=seed+30,rate=rate);custom_time=time.perf_counter()-start
        assert np.allclose(shadow,m.grad_model.weight.detach().numpy(),atol=1e-6)
        assert np.array_equal(weight,m.model.weight.detach().numpy()) and np.array_equal((g@weight.T).argmax(1),pred)
        arrays=list(state_native(m).values());state_bytes=sum(v.nbytes for v in arrays);training_bytes=state_bytes+optim+weight.nbytes+lo.nbytes+scale.nbytes
        assert training_bytes<=budget
        record(f'native_lehdc_dropout_{rate}',pred,dd,arrays,elapsed,infer,training_array_bytes=training_bytes,optimizer_bytes=optim,reference_train_seconds=custom_time,weight_disagreements=0,prediction_disagreements=0,scope='actual native and preencoded reference; retained training arrays plus optimizer and gradient, excluding input, activation and temporary arrays')
    return rows

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--quick',action='store_true');args=p.parse_args();rows=[]
    configs=[('synthetic',811,8192)] if args.quick else [(name,seed,budget) for name in ('digits','wine') for seed in (811,823) for budget in (8192,32768)]
    for cfg in configs:rows.extend(run(*cfg))
    with open(args.out,'w') as f:json.dump(dict(rows=rows,scope='retained numeric arrays only; preencoded times identified; no FPGA or production claims'),f,indent=2)
