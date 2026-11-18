"""Matched numeric training state incl gradients; separate observed RSS process peaks.
No test-tuned hyperparameters, no hardware inference claims. sklearn only full mode.
"""
import argparse,hashlib,json,time,subprocess,sys,os,platform
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F
from cognitum.research.hdc_frontier_learning import TrainableItems,PhaseMemory,channel_bind,informative,expanded_dot
from cognitum.research.hdc_frontier_closeout import PackedPhaseAdam,class_union,packed_expanded_dot
from cognitum.research.hdc_advanced_learning import lehdc_dropout_reference
from tools.cog03e2b_pilot import datasets,sign

ARMS=('threshold','adam','packed6','dense6','thdc','lehdc','mlp')
def rss():
    if sys.platform=='win32':
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD)]+[(n,ctypes.c_size_t) for n in ('peak','working','qp','q','qnp','qn','page','peakpage')]
        c=Counters();c.cb=ctypes.sizeof(c);h=ctypes.windll.kernel32.GetCurrentProcess();ctypes.windll.kernel32.GetCurrentProcess.restype=wintypes.HANDLE;h=ctypes.windll.kernel32.GetCurrentProcess();ctypes.windll.psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD]
        if not ctypes.windll.psapi.GetProcessMemoryInfo(h,ctypes.byref(c),c.cb):raise OSError('GetProcessMemoryInfo')
        return int(c.peak)
    import resource
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*(1 if sys.platform=='darwin' else 1024)

def estimate(arm,f,c,d):
    # Model + all persistent optimizer arrays + live parameter gradients.
    # Excludes shared datasets, autograd temporary/activation arrays and runtime.
    n=(f+8+c)*d
    if arm=='threshold':return 9*n
    if arm=='adam':return 17*n
    if arm=='packed6':return 3*sum((6*q*d+7)//8 for q in (f,8,c))+24+8*n
    if arm=='dense6':return 11*n+24
    if arm=='thdc':return 16*n+12
    if arm=='lehdc':return 4*(f+8)*d+20*c*d+4
    if arm=='mlp':return 16*((f+1)*d+(d+1)*c)+16
    raise ValueError(arm)

def dim_for(arm,f,c,budget):
    valid=[d for d in range(8,257,8) if estimate(arm,f,c,d)<=budget]
    if not valid:raise ValueError('insufficient training budget')
    return max(valid)

def experiment(name,x,y,z,t,seed,d,arm,epochs,mode,budget=None):
    c=int(y.max()+1);f=x.shape[1];n=len(t);torch.manual_seed(seed);rng=np.random.default_rng(seed)
    orders=[rng.permutation(len(x))]*epochs;ixs=[i[j:j+32] for i in orders for j in range(0,len(x),32)]
    split=hashlib.sha256(x.astype('<i8').tobytes()+y.astype('<i8').tobytes()+z.astype('<i8').tobytes()+t.astype('<i8').tobytes()).hexdigest();start=time.perf_counter();before=rss();writes=0;decoded=0
    if arm in ('threshold','adam','packed6','dense6'):
        a=PhaseMemory(f,8,c,d,seed=seed,rule=arm,lr=1 if arm=='threshold' else .75) if arm in ('threshold','adam') else PackedPhaseAdam(f,8,c,d,seed=seed,lr=.75,packed=arm=='packed6')
        for i in ixs:_,w=a.update(x[i],y[i]);writes+=w
        p=np.concatenate([a.scores(z[i:i+32]).argmax(1) for i in range(0,len(z),32)]);state=a.persistent_array_bytes();grad=4*(f+8+c)*d;decoded=grad;inference=a.ideal_grid_bytes();extra={'writes':writes,'optimizer_bytes':state-((f+8+c)*d if arm in ('threshold','adam','dense6') else inference)}
    elif arm=='lehdc':
        from torchhd.classifiers import LeHDC
        from torch.utils.data import DataLoader,TensorDataset
        a=LeHDC(f,d,c,n_levels=8,min_level=0,max_level=1,epochs=epochs,dropout_rate=.3);tx=torch.tensor(x/7,dtype=torch.float32);ty=torch.tensor(y);tz=torch.tensor(z/7,dtype=torch.float32)
        # All arms use the same fixed epoch order; native loader is nonshuffled.
        order=orders[0];tx=tx[order];ty=ty[order];h=a.encoder(tx).detach().numpy();torch.manual_seed(seed+100);a.fit(DataLoader(TensorDataset(tx,ty),batch_size=32,shuffle=False));a.eval()
        w,binw,opt=lehdc_dropout_reference(h,ty.numpy(),c,epochs=epochs,seed=seed+100,rate=.3,batch=32);assert np.array_equal(binw,a.model.weight.detach().numpy());np.testing.assert_allclose(w,a.grad_model.weight.detach().numpy(),rtol=1e-5,atol=1e-6)
        with torch.no_grad():p=a(tz).argmax(1).numpy()
        # Native model+shadow weight + native float tables + optimizer state counted from identical reference.
        state=sum(q.numel()*q.element_size() for q in a.parameters())+opt;grad=4*c*d # native shadow.grad aliases model.grad
        inference=4*(f+8)*d+2*c*((d+7)//8);extra={'optimizer_bytes':opt,'native_weight_parity':True,'fixed_epoch_order':True}
    else:
        a=TrainableItems(f,8,c,d,seed) if arm=='thdc' else torch.nn.Sequential(torch.nn.Linear(f,d),torch.nn.ReLU(),torch.nn.Linear(d,c));opt=torch.optim.Adam(a.parameters(),lr=.01)
        def forward(v):return a(v) if arm=='thdc' else a(torch.tensor(v/7,dtype=torch.float32))
        for i in ixs:opt.zero_grad();loss=F.cross_entropy(forward(x[i]),torch.tensor(y[i]));loss.backward();opt.step()
        with torch.no_grad():p=np.concatenate([forward(z[i:i+32]).argmax(1).numpy() for i in range(0,len(z),32)])
        arr=sum(q.numel()*q.element_size() for q in a.parameters());mom=sum(v.numel()*v.element_size() for s in opt.state.values() for v in s.values() if isinstance(v,torch.Tensor));state=arr+mom;grad=sum(q.grad.numel()*q.grad.element_size() for q in a.parameters() if q.grad is not None);inference=a.logical_inference_bytes() if arm=='thdc' else arr;extra={'optimizer_bytes':mom}
    assert state+grad+decoded<=estimate(arm,f,c,d),(arm,state,grad,estimate(arm,f,c,d))
    if budget is not None:assert state+grad+decoded<=budget
    return dict(dataset=name,seed=seed,dimension=d,arm=arm,mode=mode,budget=budget,split=split,n=n,correct=int(np.sum(p==t)),persistent_bytes=state,gradient_bytes=grad,decoded_parameter_bytes=decoded,training_numeric_bytes=state+grad+decoded,inference_logical_bytes=int(inference),baseline_peak_rss_bytes=before,observed_peak_rss_bytes=rss(),prediction_sha256=hashlib.sha256(p.astype('<i8').tobytes()).hexdigest(),seconds=time.perf_counter()-start,**extra)

def structure(name,x,y,z,t,seed,d):
    rng=np.random.default_rng(seed);c=int(y.max()+1);f=x.shape[1];p=rng.choice([-1,1],(f,d));v=rng.choice([-1,1],(8,d));a=np.concatenate([sign(channel_bind(x[i:i+32,None,:],p,v)) for i in range(0,len(x),32)]);b=np.concatenate([sign(channel_bind(z[i:i+32,None,:],p,v)) for i in range(0,len(z),32)]);w=np.array([a[y==i].sum(0) for i in range(c)]);full=sign(w);rows=[]
    for threshold in (.1,.3,.5):
        _,ix=class_union(a,y,full,threshold);count=len(ix)
        if not count:rows.append(dict(dataset=name,seed=seed,dimension=d,threshold=threshold,selected=0,empty=True));continue
        rnd=rng.permutation(d)[:count];orders=[rng.permutation(len(y)) for _ in range(3)]
        for arm,sel in [('union',ix),('random',rnd)]:
            aa=a[:,sel];bb=b[:,sel];model=w[:,sel].astype(float)/np.maximum(1,np.bincount(y,minlength=c)[:,None]);lr=.05
            for order in orders:
                for j in order:
                    pred=int((model@aa[j]).argmax());truth=y[j]
                    if pred!=truth:model[truth]+=lr*aa[j];model[pred]-=lr*aa[j]
            scale=max(1e-12,float(np.abs(model).max()));m=12;k=np.clip(np.rint((model/scale+1)*m/2),0,m).astype(int);q=np.ones_like(k);score,nb=packed_expanded_dot(bb,k,q,m);assert np.array_equal(score,expanded_dot(bb,k,q,m));assert np.array_equal(score,bb@(2*k-m).T)
            rows.append(dict(dataset=name,seed=seed,dimension=d,threshold=threshold,arm=arm,selected=count,n=len(t),correct=int(np.sum(score.argmax(1)==t)),pruned_correct=int(np.sum((bb@full[:,sel].T).argmax(1)==t)),full_correct=int(np.sum((b@full.T).argmax(1)==t)),real_correct=int(np.sum((bb@model.T).argmax(1)==t)),classifier_packed_bytes=nb,exact_score_parity=True,mask_bytes=sel.astype(np.uint16).nbytes))
    return rows

def data(quick,seed):
    return [(name,np.minimum((x*8).astype(int),7),y,np.minimum((z*8).astype(int),7),t) for name,x,y,z,t in datasets(quick,seed)]

def run(quick=False):
    torch.set_num_threads(1);rows=[];st=[];mem=[]
    for seed in ([811] if quick else [811,823]):
      for name,x,y,z,t in data(quick,seed):
        f=x.shape[1];c=int(y.max()+1)
        for d in ([16] if quick else [32,64,128]):
            for arm in ARMS:rows.append(experiment(name,x,y,z,t,seed,d,arm,3,'dimension'))
            st.extend(structure(name,x,y,z,t,seed,d))
        for budget in ([8192] if quick else [16384,32768]):
            for arm in ARMS:rows.append(experiment(name,x,y,z,t,seed,dim_for(arm,f,c,budget),arm,3,'budget',budget))
    return {'schema':'cognitum.cog03e2b.closeout.v1','quick':quick,'rows':rows,'structure':st,'note':'numeric state plus parameter gradients and decoded phase parameter copies matched, model dimension may differ; RSS rows here share process, not per arm. All arms repeat identical seeded epoch order. No activation or allocator ceiling claimed.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--quick',action='store_true');p.add_argument('--out',type=Path,required=True);p.add_argument('--worker',choices=ARMS);a=p.parse_args();torch.set_num_threads(1)
    if a.worker:
        name,x,y,z,t=data(a.quick,811)[0];budget=8192 if a.quick else 32768;d=dim_for(a.worker,x.shape[1],int(y.max()+1),budget);r=experiment(name,x,y,z,t,811,d,a.worker,3,'isolated_budget',budget)
    else:r=run(a.quick)
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8')
