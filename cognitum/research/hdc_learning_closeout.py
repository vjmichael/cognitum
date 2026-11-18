"""Research-only float window encoding and bounded streaming adaptation."""
import numpy as np
from .hdc_learning import _matrix, _labels, cosine_scores, MAX_ELEMENTS

class FloatWindow:
    """Independent balanced sliding-window MAP key/value encoding.

    This discretization is explicit, not author-code fidelity. Values 0..1
    map to a contiguous positive half-window moving without wraparound.
    """
    def __init__(self, keys):
        k=_matrix(keys, complex_ok=False)
        if k.dtype!=np.float32 or k.shape[1]%2 or k.shape[1]<2 or not np.isin(k,[-1,1]).all(): raise ValueError('invalid keys')
        self.keys=k.copy()
    def encode(self,x):
        x=_matrix(x,complex_ok=False)
        f,d=self.keys.shape
        if x.dtype!=np.float32 or x.shape[1]!=f or np.any((x<0)|(x>1)) or len(x)*d>MAX_ELEMENTS: raise ValueError('invalid input')
        out=np.zeros((len(x),d),np.float32)
        # Stream feature contributions rather than allocating N*F*D.
        pos=np.arange(d);half=d//2
        for j in range(f):
            s=np.rint(x[:,j]*half).astype(np.int64)[:,None]
            out+=np.where((pos>=s)&(pos<s+half),self.keys[j],-self.keys[j])
        return out

class DriftPrototype:
    """Fixed storage exponentially decayed class bank, prequential use.

    A global per-event decay gives newer observations more influence; no
    replay buffer. Scores for empty classes are masked. Update is atomic.
    """
    def __init__(self,classes,dimensions,decay=1.):
        if type(classes) is not int or type(dimensions) is not int or classes<2 or dimensions<1 or classes*dimensions>MAX_ELEMENTS or not np.isfinite(decay) or not 0<decay<=1: raise ValueError('invalid drift policy')
        self.w=np.zeros((classes,dimensions),np.float32);self.decay=float(decay)
    def predict(self,x,*,margin=0.):
        x=_matrix(x,complex_ok=False)
        if x.dtype!=np.float32 or not np.isfinite(margin) or not 0<=margin<=2:raise ValueError('invalid score policy')
        s=cosine_scores(x,self.w);s[:,~np.any(self.w,axis=1)]=-np.inf;p=s.argmax(1);ix=np.arange(len(s));best=s[ix,p].copy();s[ix,p]=-np.inf;second=s.max(1)
        gap=np.full(len(s),-np.inf);use=np.isfinite(best);gap[use]=best[use]-second[use]
        return np.where(use&(gap>margin)&np.any(x,axis=1),p,-1)
    def update(self,x,y):
        x=_matrix(x,complex_ok=False);y=_labels(y,len(x),len(self.w))
        if x.dtype!=np.float32 or x.shape[1]!=self.w.shape[1] or not np.all(np.any(x,axis=1)):raise ValueError('invalid update')
        w=self.w.copy()
        with np.errstate(over='raise',invalid='raise'):
            for h,t in zip(x,y):w*=self.decay;w[t]+=h
        if not np.isfinite(w).all():raise ValueError('nonfinite state')
        self.w=w


def refine_stabilized(weights,h,label,error_sum,error_count,*,threshold='winner'):
    """Independent ablation, NOT RefineHD: nonnegative confidence multiplier.

    True/winner error reference and additive correct branch explicit; cold
    start and no-error threshold 0 are implementation policies.
    """
    w=_matrix(weights,complex_ok=False);h=_matrix(h,complex_ok=False)
    if len(h)!=1 or len(w)<2 or type(label) is not int or not 0<=label<len(w) or h.dtype!=w.dtype or threshold not in ('winner','true') or type(error_count) is not int or error_count<0 or not np.isfinite(error_sum) or abs(error_sum)>error_count+1e-10 or not np.any(h):raise ValueError('invalid refine state')
    s=cosine_scores(h,w)[0];order=np.argsort(-s,kind='stable');p=int(order[0]);g=max(0.,1-float(s[order[0]])-float(s[order[1]]));out=w.copy()
    if not np.any(w[label]):out[label]=h[0];kind='cold'
    elif p!=label:
        out[label]+=(1-s[label])*g*h[0];out[p]-=(1-s[p])*g*h[0];error_sum+=float(s[p if threshold=='winner' else label]);error_count+=1;kind='error'
    elif s[p]<=(error_sum/error_count if error_count else 0.):out[label]+=g*h[0];kind='correct'
    else:kind='skip'
    if not np.isfinite(out).all():raise ValueError('nonfinite refine')
    return out,error_sum,error_count,kind
