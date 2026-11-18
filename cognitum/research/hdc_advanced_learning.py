"""Bounded CPU research candidate; no production routing.
RefineHD follows the misclassification branch of Algorithm 3 (C80, 2024).
Correct-class branch uses the prose interpretation, not the ambiguous printed
multiplicative assignment. No claim of full paper reproduction.
"""
import numpy as np
from .hdc_learning import _matrix, _labels, cosine_scores, MAX_ELEMENTS


def budget_dimension(features, classes, slots, budget, *, count_bytes=4):
    if any(type(v) is not int or v < 1 for v in (features, classes, slots, budget)) or count_bytes not in (4,8):
        raise ValueError('invalid budget')
    # float32 projection + bias + prototype bank, uint32 counts + float64 scaling
    available = budget - count_bytes*classes*slots - 16*features
    dim = min(65536, available//(4*(features+1+classes*slots)), MAX_ELEMENTS//max(features,classes*slots))
    if dim < 1: raise ValueError('budget too small')
    return dim


class MultiPrototype:
    def __init__(self, classes, dimensions, slots=1):
        if any(type(v) is not int or v < 1 for v in (classes, dimensions, slots)) or classes<2 or classes*dimensions*slots>MAX_ELEMENTS:
            raise ValueError('invalid shape')
        self.w=np.zeros((classes, slots, dimensions),np.float32)
        self.count=np.zeros((classes,slots),np.uint32)

    @property
    def numeric_bytes(self): return self.w.nbytes+self.count.nbytes

    def scores(self,x):
        x=_matrix(x,complex_ok=False)
        if x.dtype!=self.w.dtype: raise ValueError('dtype mismatch')
        c,k,d=self.w.shape
        s=cosine_scores(x,self.w.reshape(c*k,d)).reshape(len(x),c,k)
        active=(self.count>0)&(np.linalg.norm(self.w.astype(np.float64),axis=2)>0)
        s=np.where(active[None,:,:],s,-np.inf)
        return s.max(2)

    def predict(self,x):
        s=self.scores(x);p=s.argmax(1);best=s[np.arange(len(s)),p]
        tie=(s==best[:,None]).sum(1)>1
        return np.where(np.isfinite(best)&(~tie)&(np.linalg.norm(x,axis=1)>0),p,-1)

    def update(self,x,y,*,novelty=.6):
        x=_matrix(x,complex_ok=False); c,k,d=self.w.shape
        y=_labels(y,len(x),c)
        if x.dtype!=self.w.dtype or x.shape[1]!=d or not np.isfinite(novelty) or not -1<=novelty<=1 or np.any(np.linalg.norm(x.astype(np.float64),axis=1)==0):raise ValueError('invalid update')
        # Full batch validation and commit: an invalid or overflowing batch does not mutate.
        w=self.w.copy();n=self.count.copy()
        for h,t in zip(x,y):
            active=n[t]>0
            if active.any():
                s=cosine_scores(h[None,:],w[t])[0];s[~active]=-np.inf;j=int(s.argmax())
                if (~active).any() and s[j]<novelty:j=int(np.flatnonzero(~active)[0])
            else:j=0
            if n[t,j]==np.iinfo(np.uint32).max: raise OverflowError('count exhausted')
            with np.errstate(over='raise',invalid='raise'):w[t,j]+=h
            n[t,j]+=1
        if not np.isfinite(w).all():raise ValueError('invalid state')
        self.w,self.count=w,n


def refine_step(weights, h, label, error_sum, error_count, *, correct_rule='additive', initial_threshold=0.):
    """One sequential step; raw signed cosine; stable low-index ties.
    Algorithm 3 top-two rule can yield negative multipliers; preserve it.
    Correct branch explicitly chooses additive prose or literal assignment.
    Error statistic is mean mistaken winner similarity, zero before first error.
    Empty true row receives first nonzero sample (explicit cold-start policy).
    """
    w=_matrix(weights,complex_ok=False);h=_matrix(h,complex_ok=False)
    if len(h)!=1 or len(w)<2 or h.dtype!=w.dtype or type(label) is not int or not 0<=label<len(w) or type(error_count) is not int or error_count<0 or not np.isfinite(error_sum) or abs(error_sum)>error_count+1e-10 or not -1<=initial_threshold<=1 or correct_rule not in ('additive','literal') or not np.linalg.norm(h.astype(np.float64)):
        raise ValueError('invalid RefineHD state')
    s=cosine_scores(h,w)[0];order=np.argsort(-s,kind='stable');p=int(order[0]);g=1-s[order[0]]-s[order[1]];out=w.copy();kind='skip'
    if not np.any(w[label]):out[label]=h[0];kind='cold'
    elif p!=label:
        out[label]+=(1-s[label])*g*h[0];out[p]-=(1-s[p])*g*h[0]
        error_sum+=float(s[p]);error_count+=1;kind='error'
    elif s[p]<=(error_sum/error_count if error_count else initial_threshold):
        if correct_rule=='additive':out[label]+=g*h[0]
        else:out[label]=out[label]*g*h[0]
        kind='correct'
    if not np.isfinite(out).all():raise ValueError('nonfinite refine')
    return out,error_sum,error_count,kind


def _projection_grad(x,y,p,b,w):
    """Sinusoid HDC features with a supervised softmax readout; cross entropy.
    Independent NumPy gradient; no claim of a pure single-pass HDC trainer.
    """
    z=x@p.T;h=np.cos(z+b)*np.sin(z);logits=h@w.T
    logits-=logits.max(1,keepdims=True);q=np.exp(logits);q/=q.sum(1,keepdims=True)
    loss=-np.log(np.maximum(q[np.arange(len(y)),y],1e-30)).mean()
    q[np.arange(len(y)),y]-=1;q/=len(y)
    dh=q@w;dz=dh*(np.cos(z+b)*np.cos(z)-np.sin(z+b)*np.sin(z))
    return float(loss),dz.T@x,(-dh*np.sin(z+b)*np.sin(z)).sum(0),q.T@h


def train_projection(x,y,projection,bias,head,*,epochs=5,lr=.05,learn=True,batch=32):
    x,p,w=(_matrix(a,complex_ok=False) for a in (x,projection,head));b=np.asarray(bias);y=_labels(y,len(x),len(w))
    if len(w)<2 or x.shape[1]!=p.shape[1] or w.shape[1]!=len(p) or b.shape!=(len(p),) or any(a.dtype!=np.float32 for a in (x,p,b,w)) or not np.isfinite(b).all() or type(epochs) is not int or not 1<=epochs<=100 or type(batch) is not int or not 1<=batch<=4096 or batch*max(len(p),len(w))>MAX_ELEMENTS or not np.isfinite(lr) or not 0<lr<=1:raise ValueError('invalid projection training')
    p,b,w=p.copy(),b.copy(),w.copy();losses=[]
    with np.errstate(over='raise',invalid='raise'):
        for _ in range(epochs):
            ls=[]
            for i in range(0,len(x),batch):
                loss,dp,db,dw=_projection_grad(x[i:i+batch],y[i:i+batch],p,b,w);w-=lr*dw
                if learn:p-=lr*dp;b-=lr*db
                ls.append(loss)
            losses.append(float(np.mean(ls)))
    if not all(np.isfinite(a).all() for a in (p,b,w)):raise ValueError('nonfinite learned state')
    return p,b,w,losses


def lehdc_dropout_reference(x,y,classes,*,epochs=4,seed=1,rate=.3,lr=.01,batch=32,weight_decay=.003):
    """Independent preencoded native-compatible dropout and shadow Adam.
    Explicit RNG isolation; DataLoader iterator uses the same torch RNG
    consumption as the pinned native nonshuffled loader. No external state mutation.
    """
    import torch
    from torch.utils.data import DataLoader,TensorDataset
    a=_matrix(x,complex_ok=False)
    if a.dtype!=np.float32 or not np.isin(a,[-1,0,1]).all() or type(classes) is not int or not 2<=classes<=4096 or classes*a.shape[1]>MAX_ELEMENTS or type(epochs) is not int or not 1<=epochs<=100 or type(batch) is not int or not 1<=batch<=4096 or batch*max(a.shape[1],classes)>MAX_ELEMENTS or not 0<=rate<1 or not 0<lr<=1 or not 0<=weight_decay<=1:raise ValueError('invalid LeHDC policy')
    y=_labels(y,len(a),classes)
    tx=torch.tensor(a);ty=torch.tensor(y);loader=DataLoader(TensorDataset(tx,ty),batch_size=batch,shuffle=False)
    shadow=torch.nn.Parameter(torch.zeros((classes,a.shape[1]),dtype=tx.dtype));opt=torch.optim.Adam([shadow],lr=lr,weight_decay=weight_decay);scheduler=torch.optim.lr_scheduler.ReduceLROnPlateau(opt,patience=2)
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        for _ in range(epochs):
            total=0.
            for z,t in loader:
                w=shadow.detach().sign().requires_grad_();masked=torch.nn.functional.dropout(z,p=rate,training=True)
                loss=torch.nn.functional.cross_entropy(masked@w.T,t);total+=loss.detach().item();opt.zero_grad();loss.backward();shadow.grad=w.grad;opt.step()
            scheduler.step(total)
    state=opt.state[shadow];numeric=sum(v.numel()*v.element_size() for v in state.values() if torch.is_tensor(v))
    return shadow.detach().numpy().copy(),shadow.detach().sign().numpy().copy(),numeric
