"""Independent manufactured and Fourier reference; no solution labels in fit."""
from dataclasses import asdict
from itertools import product
from pathlib import Path
import json,time
import numpy as np
from cognitum.research import kan_spacetime_certificate as v,kan_spacetime_learning as s
G=tuple((i,j,(-1)**(i+j)) for i,j in product((1,2),repeat=2))
F=tuple((i,j,0,c) for i,j,c in G)
H=tuple((i,j,a*b) for (i,a),(j,b) in product(((1,1),(3,-2),(4,1)),repeat=2))
M=tuple(sorted([*F,(0,1,1,2),(0,2,1,-2),(1,0,1,2),(2,0,1,-2)]))

def cases():
    # Fixed profile thresholds following initial exploratory pilot; not blind holdout.
    return [('manufactured',v.Problem(1,1,0,M,()),1e-12),('forced',v.Problem(.125,.25,0,F,()),.0045),('reaction',v.Problem(.25,.125,1,F,()),.005),('initial_decay',v.Problem(.125,.25,0,(),H),.028)]


def reference(name,p,x,y,t,N=127):
    if name=='manufactured':return (x*(1-x))[:,None,None]*(y*(1-y))[None,:,None]*t[None,None,:],0.
    k=np.arange(1,N+1,2)*np.pi;lam=p.ax*k[:,None]**2+p.ay*k[None,:]**2+p.reaction
    dec=name=='initial_decay';power=5 if dec else 3;scale=96 if dec else 8
    a=scale/k**power
    weights=a[:,None,None]*a[None,:,None]*(np.exp(-lam[:,:,None]*t) if dec else -np.expm1(-lam[:,:,None]*t)/lam[:,:,None])
    pred=np.einsum('im,jn,mnt->ijt',np.sin(x[:,None]*k),np.sin(y[:,None]*k),weights,optimize=True)
    # Union bound on omitted positive mode absolute coefficients. t<=1 implies
    # both exp(-lambda*t) and (1-exp(-lambda*t))/lambda <= 1.
    # Sum all integer n^-p <= 1+1/(p-1), tail <= N^(1-p)/(p-1).
    tail=2*(scale/np.pi**power)**2*(1+1/(power-1))*N**(1-power)/(power-1)
    return pred,tail


def run(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    x=np.r_[0,(np.arange(17)+.31)/17,1];y=np.r_[0,(np.arange(19)+.57)/19,1];t=np.r_[0,(np.arange(21)+.71)/21,1]
    pts=np.array(np.meshgrid(x,y,t,indexing='ij')).reshape(3,-1).T;rows=[]
    for name,p,tol in cases():
        start=time.perf_counter();f=s.fit(p,tol);sec=time.perf_counter()-start;c=v.require_accuracy(p,f.model,f.certificate,tol)
        exact,tail=reference(name,p,x,y,t);pred=s.evaluate(p,f.model,pts).reshape(exact.shape);err=abs(pred-exact);measured=float(err.max())
        v.need(measured<=float(c.solution_error_upper)+tail+1e-12,'analytical reference contradicts cert')
        for z in c.slabs:
            mask=(t>=float(z.interval[0]))&(t<=float(z.interval[1]));v.need(not mask.any() or err[:,:,mask].max()<=float(z.solution_error_upper)+tail+1e-12,'prefix contradiction')
        uniform=lambda n:tuple(round(64*i/(n+1))/64 for i in range(1,n+1));u=v.assess(p,s._fit(p,tuple(uniform(len(k)) for k in f.model.cuts)))
        raw=f.model.checkpoint();v.replay(p,v.restore(raw),c);(out/(name+'.checkpoint.json')).write_bytes(raw);(out/(name+'.certificate.json')).write_text(json.dumps(asdict(c),default=str,indent=2)+'\n')
        rows.append(dict(name=name,problem=asdict(p),problem_sha256=p.identity,model_sha256=f.model.identity,accepted=f.converged,tolerance=tol,seconds=sec,cuts=f.model.cuts,shape=f.model.shape,parameters=len(f.model.coefficients),cells=len(c.cells),stages=[float(z.solution_error_upper) for z in f.history],full_domain_error_upper=float(c.solution_error_upper),exact_bound=str(c.solution_error_upper),sampled_max_error=measured,series_tail_bound=tail,heldout_points=len(pts),uniform_matched_bound=float(u.solution_error_upper),initial_exact=c.initial_exact,boundary_exact=c.boundary_exact,c2=c.interfaces_exact))
    (out/'benchmark.json').write_text(json.dumps(rows,indent=2)+'\n');return rows

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);run(p.parse_args().out)
