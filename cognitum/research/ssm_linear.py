"""Bounded mathematical research profiles; no host or control authority."""
from dataclasses import dataclass, fields
from fractions import Fraction as Q
from hashlib import sha256
import json, re

DIM=8
STEPS=64
BITS=4096
FRAME=262144
CLOCK=1000000

def need(ok,msg):
    if not ok: raise ValueError(msg)

def bounded(x):
    need(type(x) is Q and max(x.numerator.bit_length(),x.denominator.bit_length())<=BITS,'rational budget')
    return x

def rat(x):
    need(type(x) in (int,Q),'exact rational required')
    x=bounded(Q(x));need(abs(x)<=32 and x.denominator<=1024,'coefficient/input budget');return x

def vector(v,n,convert=rat):
    need(type(v) is tuple and len(v)==n,'vector shape')
    return tuple(convert(x) for x in v)

def matrix(a,n,m,convert=rat):
    need(type(a) is tuple and len(a)==n,'matrix shape')
    return tuple(vector(row,m,convert) for row in a)

def _matmul(a,b):
    return tuple(tuple(bounded(sum((bounded(x*y) for x,y in zip(row,col)),Q(0))) for col in zip(*b)) for row in a)

def _add(a,b):return tuple(tuple(bounded(x+y) for x,y in zip(r,s)) for r,s in zip(a,b))
def mv(a,x):return tuple(row[0] for row in _matmul(a,tuple((v,) for v in x)))
def va(a,b):return tuple(bounded(x+y) for x,y in zip(a,b))
def eye(n):return tuple(tuple(Q(i==j) for j in range(n)) for i in range(n))
def outercol(x):return tuple((v,) for v in x)
def canonical(x):
    def conv(v):
        if type(v) is Q:return str(v)
        if isinstance(v,(Model,State)) :return {f.name:conv(getattr(v,f.name)) for f in fields(v)}
        if type(v) is dict:return {k:conv(w) for k,w in v.items()}
        if type(v) in (tuple,list):return [conv(w) for w in v]
        return v
    raw=json.dumps(conv(x),sort_keys=True,separators=(',',':'),allow_nan=False).encode('ascii')
    need(len(raw)<=FRAME,'receipt budget');return raw

def units(v,n):
    need(type(v) is tuple and len(v)==n and all(type(x) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./*^+-]{0,23}',x,re.ASCII) for x in v),'unit labels')
    return v

@dataclass(frozen=True,slots=True)
class Model:
    a:tuple; b:tuple; c:tuple; d:tuple
    state_units:tuple; input_units:tuple; output_units:tuple
    domain:str='discrete'; step:Q=Q(1)
    def __post_init__(self):
        need(all(type(x) is tuple and 1<=len(x)<=DIM for x in (self.a,self.input_units,self.output_units)),'dimension budget')
        n,m,p=len(self.a),len(self.input_units),len(self.output_units)
        for k,r,s in [('a',n,n),('b',n,m),('c',p,n),('d',p,m)]:object.__setattr__(self,k,matrix(getattr(self,k),r,s))
        for k,s in [('state_units',n),('input_units',m),('output_units',p)]:units(getattr(self,k),s)
        need(type(self.domain) is str and self.domain in ('discrete','continuous'),'time domain')
        h=rat(self.step);need(h>0,'positive step');object.__setattr__(self,'step',h)
    @property
    def digest(self):return sha256(canonical(self)).hexdigest()

@dataclass(frozen=True,slots=True)
class State:
    model_sha256:str; index:int; x:tuple

def state(model,x,index=0):
    need(type(model) is Model and model.domain=='discrete','discrete model required')
    need(type(index) is int and 0<=index<=CLOCK,'state clock')
    return State(model.digest,index,vector(x,len(model.a),bounded))

def scan(model,start,inputs):
    need(type(model) is Model and model.domain=='discrete','discrete model required')
    need(type(start) is State and start.model_sha256==model.digest,'state model binding')
    s=state(model,start.x,start.index);need(type(inputs) is tuple and 1<=len(inputs)<=STEPS and s.index+len(inputs)<=CLOCK,'sequence budget')
    x=s.x;ys=[]
    for u in inputs:
        u=vector(u,len(model.input_units));ys.append(va(mv(model.c,x),mv(model.d,u)));x=va(mv(model.a,x),mv(model.b,u))
    end=state(model,x,s.index+len(inputs))
    raw=canonical(dict(profile='cognitum.ssm.linear.exact.v1',model_sha256=model.digest,initial=s,inputs=tuple(tuple(Q(v) for v in u) for u in inputs),outputs=tuple(ys),final=end,output_convention='pre_update',execution_authorized=False))
    return end,tuple(ys),raw

def replay(model,start,inputs,receipt):
    need(type(receipt) is bytes and 0<len(receipt)<=FRAME,'receipt size');need(scan(model,start,inputs)[2]==receipt,'replay mismatch');return True

def compose(first,second):
    """Affine maps (A,b); later map second after first. Exact ordered composition."""
    need(type(first) is tuple and type(second) is tuple and len(first)==len(second)==2,'affine shape')
    a,b=first;c,d=second;need(type(a) is tuple and 1<=len(a)<=DIM,'dimension budget');n=len(a)
    a=matrix(a,n,n,bounded);c=matrix(c,n,n,bounded);b=vector(b,n,bounded);d=vector(d,n,bounded)
    return _matmul(c,a),va(mv(c,b),d)

def transition(model,inputs):
    need(type(model) is Model and model.domain=='discrete','discrete model required');need(type(inputs) is tuple and 1<=len(inputs)<=STEPS,'sequence budget')
    n=len(model.a);t=(eye(n),(Q(0),)*n)
    for u in inputs:t=compose(t,(model.a,mv(model.b,vector(u,len(model.input_units)))))
    return t

def markov(model,count):
    need(type(model) is Model and model.domain=='discrete' and type(count) is int and 1<=count<=STEPS,'Markov budget')
    out=[model.d];a=model.b
    for _ in range(count-1):out.append(_matmul(model.c,a));a=_matmul(model.a,a)
    return tuple(out)

def _solve(a,b):
    n=len(a);z=[list(r)+list(s) for r,s in zip(a,b)]
    for j in range(n):
        pivot=next((i for i in range(j,n) if z[i][j]),None);need(pivot is not None,'singular resolvent')
        z[j],z[pivot]=z[pivot],z[j];p=z[j][j];z[j]=[bounded(x/p) for x in z[j]]
        for i in range(n):
            if i!=j:
                p=z[i][j];z[i]=[bounded(x-bounded(p*y)) for x,y in zip(z[i],z[j])]
    return tuple(tuple(r[n:]) for r in z)

def transfer(model,z):
    need(type(model) is Model,'typed model');z=rat(z);n=len(model.a)
    a=tuple(tuple(bounded(z*int(i==j)-model.a[i][j]) for j in range(n)) for i in range(n))
    return _add(model.d,_matmul(model.c,_solve(a,model.b)))

def discretize(model,h):
    """Numerical ZOH with independent scaled Taylor cross-check; not a certified enclosure."""
    need(type(model) is Model and model.domain=='continuous','continuous model required');h=rat(h);need(h>0,'positive interval')
    import numpy as np
    from scipy.linalg import expm
    n,m=len(model.a),len(model.input_units)
    block=np.zeros((n+m,n+m));block[:n,:n]=np.array(model.a,dtype=float);block[:n,n:]=np.array(model.b,dtype=float);block*=float(h)
    norm=float(np.linalg.norm(block,np.inf));need(norm<=8,'exponential norm budget')
    k=0
    while norm/(2**k)>0.5:k+=1
    z=block/(2**k);series=np.eye(n+m);term=series.copy()
    for j in range(1,33):term=term@z/j;series+=term
    for _ in range(k):series=series@series
    direct=expm(block);err=float(np.linalg.norm(direct-series,np.inf)/max(1.,np.linalg.norm(direct,np.inf)))
    need(np.isfinite(direct).all() and np.isfinite(series).all() and err<=2e-12,'exponential cross-check')
    return dict(a=direct[:n,:n],b=direct[:n,n:],c=np.array(model.c,dtype=float),d=np.array(model.d,dtype=float),step=str(h),scaled_crosscheck=err,method='scipy_expm_zoh_checked_taylor',certified=False,execution_authorized=False)
