"""Independent research references: stochastic binary HMM and LDN-HDC.
No production routing; no author-code parity claim for L24. CPU only.
"""
from dataclasses import dataclass
import numpy as np
from scipy.linalg import expm


def _obs(seq, alphabet):
    x=np.asarray(seq)
    if x.ndim!=1 or len(x)==0 or x.dtype.kind not in 'iu' or np.any(x<0) or np.any(x>=alphabet):
        raise ValueError('nonempty categorical sequence required')
    return x.astype(np.int64,copy=False)

@dataclass
class CategoricalHMM:
    initial:np.ndarray
    transition:np.ndarray
    emission:np.ndarray
    def __post_init__(self):
        self.initial=np.asarray(self.initial,dtype=np.float64).copy();self.transition=np.asarray(self.transition,dtype=np.float64).copy();self.emission=np.asarray(self.emission,dtype=np.float64).copy()
        k=len(self.initial)
        if k<1 or self.initial.shape!=(k,) or self.transition.shape!=(k,k) or self.emission.ndim!=2 or self.emission.shape[0]!=k or self.emission.shape[1]<1:raise ValueError('shape')
        for a in (self.initial,self.transition,self.emission):
            if not np.isfinite(a).all() or (a<0).any() or not np.allclose(a.sum(axis=-1),1,rtol=0,atol=1e-10):raise ValueError('nonstochastic parameters')
    @property
    def nbytes(self):return sum(a.nbytes for a in (self.initial,self.transition,self.emission))
    def forward(self,seq):
        x=_obs(seq,self.emission.shape[1]);a=np.empty((len(x),len(self.initial)));s=np.empty(len(x))
        p=self.initial.copy()
        for i,o in enumerate(x):
            p=p*self.emission[:,o];s[i]=p.sum()
            if s[i]<=0: return -np.inf,None,None
            a[i]=p/s[i];p=a[i]@self.transition
        return float(np.log(s).sum()),a,s
    def score(self,seq):
        # Inference need not retain the training forward/backward trace.
        x=_obs(seq,self.emission.shape[1]);p=self.initial.copy();loglik=0.
        for o in x:
            p=p*self.emission[:,o];mass=p.sum()
            if mass<=0:return -np.inf
            loglik+=np.log(mass);p=(p/mass)@self.transition
        return float(loglik)
    @classmethod
    def fit(cls,sequences,alphabet,states,seed=0,iterations=8,prior=.1):
        if not 1<=states<=16 or not 1<=alphabet<=256 or iterations<1 or prior<=0:raise ValueError('fit parameters')
        x=[_obs(s,alphabet) for s in sequences]
        if not x:raise ValueError('no sequences')
        rng=np.random.default_rng(seed);m=cls(rng.dirichlet(np.ones(states)),rng.dirichlet(np.ones(states),states),rng.dirichlet(np.ones(alphabet),states))
        for _ in range(iterations):
            pi=np.full(states,prior);t=np.full((states,states),prior);e=np.full((states,alphabet),prior)
            for seq in x:
                _,a,s=m.forward(seq);b=np.ones(states);g=a[-1]*b;g/=g.sum();e[:,seq[-1]]+=g
                for i in range(len(seq)-2,-1,-1):
                    z=m.emission[:,seq[i+1]]*b;xi=a[i,:,None]*m.transition*z[None,:];xi/=xi.sum();t+=xi
                    b=(m.transition@z)/s[i+1];g=a[i]*b;g/=g.sum();e[:,seq[i]]+=g
                pi+=g
            m=cls(pi/pi.sum(),t/t.sum(1,keepdims=True),e/e.sum(1,keepdims=True))
        return m

# Binary population hypervectors: one disjoint bit mask per hidden state.
# Probability mass is lane occupancy; AND filters emissions, OR combines
# mutually exclusive origin/transition lanes. Resampling is numerical, not
# an assertion of paper's all-bitwise pipeline. Normalization prevents decay.
class BinaryForward:
    def __init__(self,model,dimension,seed=0):
        if dimension<8 or dimension>65536:raise ValueError('dimension')
        self.model=model;self.dimension=int(dimension);self.rng=np.random.default_rng(seed);self.reset()
    def reset(self):
        self.state=self._sample(self.model.initial);self.steps=0;self.loglik=0.;self.depleted=False
    def _sample(self,p):
        d=self.dimension
        z=np.searchsorted(np.cumsum(p),self.rng.random(d),side='right').clip(max=len(p)-1)
        return np.packbits(np.arange(len(p))[:,None]==z,axis=1,bitorder='little')
    def _counts(self,a):return np.unpackbits(a,axis=1,count=self.dimension,bitorder='little').sum(1)
    @property
    def state_bytes(self):return self.state.nbytes
    def step(self,obs):
        if not isinstance(obs,(int,np.integer)) or not 0<=obs<self.model.emission.shape[1]:raise ValueError('symbol')
        if self.depleted:return -np.inf
        m=self.model;d=self.dimension
        if self.steps:
            nxt=np.zeros_like(self.state)
            for i,p in enumerate(m.transition):nxt|=(self.state[i]&self._sample(p))
            self.state=nxt
        mask=np.packbits(self.rng.random((len(m.initial),d))<m.emission[:,obs,None],axis=1,bitorder='little')
        count=self._counts(self.state&mask);total=int(count.sum());self.steps+=1
        if not total:
            self.state[:]=0;self.loglik=-np.inf;self.depleted=True;return self.loglik
        self.loglik+=np.log(total/d);self.state=self._sample(count/total)
        return self.loglik
    def consume(self,seq):
        for o in _obs(seq,self.model.emission.shape[1]):self.step(o)
        return self.loglik

class LDN:
    """Exact ZOH discretization of continuous Legendre delay equations.
    Fixed step, bounded q x channels state; reset required across sequences.
    """
    def __init__(self,order,theta,dt,channels=1):
        if not 1<=order<=64 or not 1<=channels<=64 or not np.isfinite([theta,dt]).all() or min(theta,dt)<=0:raise ValueError('LDN parameters')
        self.order=int(order);self.channels=int(channels);self.theta=float(theta);self.dt=float(dt)
        i,j=np.indices((order,order));self.A=(2*i+1)/theta*np.where(i<j,-1,(-1.)**(i-j+1));self.B=(2*np.arange(order)+1)/theta*(-1.)**np.arange(order)
        aug=np.zeros((order+1,order+1));aug[:order,:order]=self.A;aug[:order,order]=self.B
        disc=expm(aug*dt);self.Ad=disc[:order,:order].copy();self.Bd=disc[:order,order].copy();self.reset()
    def reset(self):self.state=np.zeros((self.order,self.channels),dtype=np.float64)
    @property
    def numeric_bytes(self):return sum(a.nbytes for a in (self.A,self.B,self.Ad,self.Bd,self.state))
    def step(self,x):
        x=np.asarray(x,dtype=np.float64)
        if x.shape!=(self.channels,) or not np.isfinite(x).all():raise ValueError('one finite sample required')
        self.state=self.Ad@self.state+self.Bd[:,None]*x
        return self.state.copy()
    def consume(self,x):
        x=np.asarray(x,dtype=float)
        if x.ndim!=2 or x.shape[1]!=self.channels or not np.isfinite(x).all():raise ValueError('sequence shape')
        return np.array([self.step(u) for u in x]).reshape(-1,self.order,self.channels)

class LIF:
    """Discrete rate encoder corresponding to the LDN paper's LIF equations."""
    def __init__(self,channels,alpha=.6,beta=.6,threshold=1.):
        if channels<1 or not 0<=alpha<1 or not 0<=beta<1 or not np.isfinite(threshold) or threshold<=0:raise ValueError('LIF parameters')
        self.channels=channels;self.alpha=alpha;self.beta=beta;self.threshold=threshold;self.reset()
    def reset(self):self.current=np.zeros(self.channels);self.voltage=np.zeros(self.channels)
    def step(self,x):
        x=np.asarray(x,dtype=float)
        if x.shape!=(self.channels,) or not np.isfinite(x).all() or (x<0).any():raise ValueError('nonnegative finite input required')
        self.current=(1-self.alpha)*self.current+x;self.voltage=(1-self.beta)*self.voltage+self.current
        spike=self.voltage>=self.threshold;self.voltage[spike]=0.;return spike

class BinaryNgram:
    """Streaming XOR role shift, majority bundle; fixed-width ring + counters."""
    def __init__(self,codebook,n):
        c=np.asarray(codebook)
        if c.ndim!=2 or n<1 or n>16 or c.shape[1]<8 or not np.isin(c,[0,1]).all():raise ValueError('codebook')
        self.codebook=c.astype(bool);self.n=n;self.reset()
    def reset(self):self.ring=[];self.counts=np.zeros(self.codebook.shape[1],np.int64);self.windows=0
    def step(self,token):
        if not isinstance(token,(int,np.integer)) or not 0<=token<len(self.codebook):raise ValueError('token')
        self.ring.append(int(token));self.ring=self.ring[-self.n:]
        if len(self.ring)==self.n:
            v=np.zeros(self.codebook.shape[1],bool)
            for i,s in enumerate(self.ring):v^=np.roll(self.codebook[s],self.n-1-i)
            self.counts+=v.astype(np.int64)*2-1;self.windows+=1
    def consume(self,seq):
        for t in _obs(seq,len(self.codebook)):self.step(t)
        return self.counts/max(1,self.windows)
    @property
    def numeric_bytes(self):return self.codebook.nbytes+self.counts.nbytes+8*self.n


class LDNSummary:
    """Final, mean and population standard deviation without a state-history buffer."""
    def __init__(self,order,theta,dt,channels=1):
        self.ldn=LDN(order,theta,dt,channels);self.reset()
    def reset(self):
        self.ldn.reset();self.n=0;self.mean=np.zeros_like(self.ldn.state);self.m2=np.zeros_like(self.mean)
    def step(self,x):
        z=self.ldn.step(x);self.n+=1;delta=z-self.mean;self.mean+=delta/self.n;self.m2+=delta*(z-self.mean)
    def feature(self):
        if not self.n:raise ValueError('empty stream')
        return np.concatenate((self.ldn.state.ravel(),self.mean.ravel(),np.sqrt(np.maximum(self.m2/self.n,0)).ravel()))
    @property
    def numeric_bytes(self):return self.ldn.numeric_bytes+self.mean.nbytes+self.m2.nbytes+8

class PackedPrototype:
    """Bipolar majority prototype with exact Hamming scores on true bit arrays."""
    def __init__(self,prototypes):
        z=np.asarray(prototypes)
        if z.ndim!=2 or not z.shape[0] or z.shape[1]<1 or not np.isfinite(z).all():raise ValueError('prototypes')
        self.dimension=z.shape[1];self.bits=np.packbits(z>=0,axis=1,bitorder='little')
    def distances(self,vector):
        v=np.asarray(vector)
        if v.shape!=(self.dimension,) or not np.isfinite(v).all():raise ValueError('query')
        q=np.packbits(v>=0,bitorder='little');return np.bitwise_count(self.bits^q).sum(axis=1,dtype=np.int64)
    def predict(self,vector):return int(self.distances(vector).argmin())
    @property
    def numeric_bytes(self):return self.bits.nbytes
