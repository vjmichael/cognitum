"""Independent matched encoder, prequential drift and isolated memory research."""
import argparse,hashlib,json,os,subprocess,sys,time
import numpy as np
from cognitum.research.hdc_learning import RandomFeatures,Prototype,cosine_scores
from cognitum.research.hdc_advanced_learning import MultiPrototype,budget_dimension,refine_step,train_projection
from cognitum.research.hdc_learning_closeout import FloatWindow,DriftPrototype,refine_stabilized


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
    return np.clip((x[tr]-lo)/scale,0,1).astype('float32'),y[tr].astype('int64'),np.clip((x[te]-lo)/scale,0,1).astype('float32'),y[te].astype('int64'),lo,scale,hashlib.sha256(np.concatenate((tr,[-1],te)).astype('<i8').tobytes()).hexdigest()


def refine_study(name,seed,d):
    a,y,b,t,*_,split=dataset(name,seed);c=int(y.max())+1;f=a.shape[1];r=np.random.default_rng(seed);rows=[]
    for enc in ('float_window','sinusoid'):
        e=FloatWindow(r.choice(np.array([-1,1],np.float32),(f,d))) if enc=='float_window' else RandomFeatures.seeded(f,d,seed)
        h=e.encode(a);g=e.encode(b);nz=np.any(h,axis=1)
        for arm in ('vanilla','online','paper_additive','paper_literal','stabilized_winner','stabilized_true'):
            w=np.zeros((c,d),np.float32);es=0.;n=0;counts={};negative=0;failure=None;processed=0
            if arm in ('vanilla','online'):
                m=Prototype(c,d)
                for v,label in zip(h[nz],y[nz]):m.update(v[None],np.array([label]),rule=arm)
                w=m.weights
            else:
                for v,label in zip(h[nz],y[nz]):
                    s=np.sort(cosine_scores(v[None],w)[0]);negative+=int(1-s[-1]-s[-2]<0)
                    try:
                        with np.errstate(over='raise',invalid='raise'):
                            if arm.startswith('paper'):w,es,n,k=refine_step(w,v[None],int(label),es,n,correct_rule=arm.split('_')[-1])
                            else:w,es,n,k=refine_stabilized(w,v[None],int(label),es,n,threshold=arm.split('_')[-1])
                    except (FloatingPointError,ValueError) as exc:
                        if arm!='paper_literal' or not ('nonfinite' in str(exc) or 'overflow' in str(exc)):raise
                        failure=str(exc);break
                    processed+=1;counts[k]=counts.get(k,0)+1
            p=cosine_scores(g,w).argmax(1);p[~np.any(g,axis=1)]=-1
            rows.append(dict(dataset=name,seed=seed,split=split,dimension=d,encoder=enc,arm=arm,n=len(t),correct=int((p==t).sum()) if failure is None else None,zero_train=int((~nz).sum()),zero_test=int((~np.any(g,axis=1)).sum()),branches=counts,negative_candidate_factors=negative,processed=int(nz.sum()) if arm in ('vanilla','online') else processed,fit_failure=failure))
    return rows


def drift_study(seed,d=128,phase_n=300):
    r=np.random.default_rng(seed);f=8;c=3;centers=r.uniform(.2,.8,(c,f)).astype('float32');enc=RandomFeatures.seeded(f,d,seed);rows=[]
    for scenario in ('stationary','abrupt_concept','gradual_concept','domain_shift'):
        streams=[];probes=[]
        for phase in range(3):
            def sample(n,probe=False):
                z=r.integers(c,size=n);x=centers[z]+r.normal(0,.065,(n,f));y=z.copy()
                if scenario=='domain_shift' and phase==1:x=x[:,::-1]
                if scenario=='abrupt_concept' and phase==1:y=(z+1)%c
                if scenario=='gradual_concept' and phase==1:
                    flip=r.random(n)<(np.ones(n) if probe else np.linspace(0,1,n));y[flip]=(z[flip]+1)%c
                return enc.encode(np.clip(x,0,1).astype('float32')),y
            streams.append(sample(phase_n));probes.append(sample(150,True))
        for decay in (1.,.99,.95):
            m=DriftPrototype(c,d,decay);trajectory=[]
            for phase,(x,y) in enumerate(streams):
                pred=[]
                for h,t in zip(x,y):pred.append(int(m.predict(h[None])[0]));m.update(h[None],np.array([t]))
                p=np.array(pred);trajectory.append(dict(phase=phase,n=len(y),correct=int((p==y).sum()),first50=int((p[:50]==y[:50]).sum()),last50=int((p[-50:]==y[-50:]).sum()),abstain=int((p==-1).sum()),probe_accuracy=[float((m.predict(g)==v).mean()) for g,v in probes]))
            rows.append(dict(seed=seed,scenario=scenario,decay=decay,dimension=d,model_bytes=m.w.nbytes,trajectory=trajectory))
    return rows


def peak_bytes():
    if sys.platform=='win32':
        import ctypes as ct
        from ctypes import wintypes as wt
        class Counters(ct.Structure):
            _fields_=[('cb',wt.DWORD),('faults',wt.DWORD)]+[(x,ct.c_size_t) for x in ('peak','current','quota_peak_paged','quota_paged','quota_peak_nonpaged','quota_nonpaged','pagefile','peak_pagefile')]
        data=Counters();data.cb=ct.sizeof(data);kernel=ct.WinDLL('kernel32');kernel.GetCurrentProcess.restype=wt.HANDLE;get=ct.WinDLL('psapi').GetProcessMemoryInfo;get.argtypes=[wt.HANDLE,ct.POINTER(Counters),wt.DWORD];get.restype=wt.BOOL
        if not get(kernel.GetCurrentProcess(),ct.byref(data),data.cb):raise OSError('GetProcessMemoryInfo')
        return int(data.peak)
    import resource
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*(1 if sys.platform=='darwin' else 1024)

ARMS=('online','multi2','fixed_projection','learned_projection','native_linear','native_lehdc')
PROCESS_CAP=1024*1024*1024

def memory_worker(name,seed,budget,arm):
    if arm not in ARMS:raise ValueError('unknown arm')
    a,y,b,t,lo,scale,split=dataset(name,seed);c=int(y.max())+1;f=a.shape[1];k=2 if arm=='multi2' else 1
    if arm.startswith('native_'):
        import torch
        from torchhd import embeddings,classifiers
        from torch.utils.data import DataLoader,TensorDataset
        torch.set_num_threads(1);torch.manual_seed(seed)
    before=peak_bytes();start=time.perf_counter();d=budget_dimension(f,c,k,budget)
    if arm=='native_lehdc':
        d=(budget-lo.nbytes-scale.nbytes-4)//(4*(f+16+5*c));assert d>0
        model=classifiers.LeHDC(f,d,c,n_levels=16,min_level=0.,max_level=1.,epochs=4,dropout_rate=.3);train=DataLoader(TensorDataset(torch.tensor(a),torch.tensor(y)),batch_size=32,shuffle=False);model.fit(train);model.eval();train_peak=peak_bytes();elapsed=time.perf_counter()-start
        with torch.no_grad():p=model(torch.tensor(b)).numpy().argmax(1)
        seen=set();persistent=0
        for v in model.state_dict().values():
            key=v.untyped_storage().data_ptr()
            if key not in seen:persistent+=v.untyped_storage().nbytes();seen.add(key)
    else:
        e=RandomFeatures.seeded(f,d,seed);proj,bias=e.state()
        if arm=='native_linear':
            model=embeddings.Projection(f,d,requires_grad=True);head=torch.nn.Linear(d,c,bias=False);opt=torch.optim.SGD([*model.parameters(),*head.parameters()],lr=.05);init=np.random.default_rng(seed+3).normal(0,.03,(c,d)).astype('float32')
            with torch.no_grad():model.weight.copy_(torch.tensor(proj));head.weight.copy_(torch.tensor(init))
            at=torch.tensor(a);yt=torch.tensor(y)
            for _ in range(10):
                for i in range(0,len(y),32):opt.zero_grad();loss=torch.nn.functional.cross_entropy(head(model(at[i:i+32])),yt[i:i+32]);loss.backward();opt.step()
            train_peak=peak_bytes();elapsed=time.perf_counter()-start
            with torch.no_grad():p=head(model(torch.tensor(b))).numpy().argmax(1)
            persistent=sum(v.numel()*v.element_size() for v in [*model.parameters(),*head.parameters()])
        elif arm in ('learned_projection','fixed_projection'):
            init=np.random.default_rng(seed+3).normal(0,.03,(c,d)).astype('float32');pp,bb,hh,_=train_projection(a,y,proj,bias,init,epochs=10,learn=arm=='learned_projection');train_peak=peak_bytes();elapsed=time.perf_counter()-start;p=(RandomFeatures(pp,bb).encode(b)@hh.T).argmax(1);persistent=pp.nbytes+bb.nbytes+hh.nbytes
        else:
            m=MultiPrototype(c,d,k) if k==2 else Prototype(c,d)
            for i in range(0,len(y),32):
                h=e.encode(a[i:i+32]);m.update(h,y[i:i+32],**({} if k==2 else {'rule':'online'}))
            train_peak=peak_bytes();elapsed=time.perf_counter()-start;p=m.predict(e.encode(b));persistent=proj.nbytes+bias.nbytes+(m.numeric_bytes if k==2 else m.weights.nbytes)
    persistent+=lo.nbytes+scale.nbytes
    assert persistent<=budget and train_peak<=PROCESS_CAP and p.shape==t.shape
    return dict(dataset=name,seed=seed,split=split,arm=arm,dimension=d,budget=budget,persistent_bytes=persistent,input_bytes=sum(v.nbytes for v in (a,y,b,t,lo,scale)),baseline_peak_bytes=before,training_peak_process_bytes=train_peak,training_peak_growth_bytes=max(0,train_peak-before),process_cap_bytes=PROCESS_CAP,final_peak_process_bytes=peak_bytes(),n=len(t),correct=int((p==t).sum()),train_seconds=elapsed)


def main():
    p=argparse.ArgumentParser();p.add_argument('--out');p.add_argument('--quick',action='store_true');p.add_argument('--worker',nargs=4);p.add_argument('--only',choices=['refine','drift','memory']);a=p.parse_args()
    if a.worker:
        name,seed,budget,arm=a.worker;print(json.dumps(memory_worker(name,int(seed),int(budget),arm)));return
    if not a.out:p.error('--out required')
    seeds=[811] if a.quick else [811,823];names=['synthetic'] if a.quick else ['digits','wine'];dims=[64] if a.quick else [128,512];budgets=[8192] if a.quick else [8192,32768]
    result={'refine':[],'drift':[],'memory':[],'memory_scope':'isolated OS peak RSS/working set from process start through training; equal observed 1 GiB ceiling and matched retained numeric ceilings, not exclusive tensor/allocator attribution or hard limit'}
    if a.only in (None,'refine'):
        for name in names:
            for seed in seeds:
                for d in dims:result['refine']+=refine_study(name,seed,d)
    if a.only in (None,'drift'):
        for seed in seeds:result['drift']+=drift_study(seed,64 if a.quick else 128,120 if a.quick else 300)
    if a.only in (None,'memory'):
        for name in names:
            for budget in budgets:
                for arm in ARMS:
                    child=subprocess.run([sys.executable,'-m','tools.cog03e2a_closeout','--worker',name,str(seeds[0]),str(budget),arm],capture_output=True,text=True,check=True,timeout=120,env={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'});result['memory'].append(json.loads(child.stdout.strip().splitlines()[-1]))
    with open(a.out,'w',encoding='utf8') as f:json.dump(result,f,indent=2,allow_nan=False)
if __name__=='__main__':main()
