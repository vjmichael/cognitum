"""Manufactured and Fourier-series references (diagnostic, no training labels)."""
from dataclasses import asdict
import json,time
from pathlib import Path
import numpy as np
from cognitum.research import kan_transient_certificate as v,kan_transient_learning as s

F=((1,0,1),(2,0,-1))
def cases():
    return [('manufactured',v.Problem(1,0,((0,1,2),*F),(0,)),1e-12),
            ('forced_heat',v.Problem(.125,0,F,(0,)),.009),
            ('reaction_diffusion',v.Problem(.25,2,F,(0,)),.0055),
            ('initial_decay',v.Problem(.125,0,(),(0,1,0,-2,1)),.013)]

def analytic(name,p,pts,N=255):
    x,t=pts.T
    if name=='manufactured':return x*(1-x)*t,0.
    out=np.zeros(len(x))
    for n in range(1,N+1,2):
        k=n*np.pi;lam=p.diffusion*k*k+p.reaction
        factor=96/k**5*np.exp(-lam*t) if name=='initial_decay' else 8/k**3*(-np.expm1(-lam*t))/lam
        out+=factor*np.sin(k*x)
    # sum_{n>N} n^-5 <= 1/(4 N^4), including omitted even modes.
    tail=(96 if name=='initial_decay' else 8/p.diffusion)/(4*np.pi**5*N**4)
    return out,tail

def run(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    # Include exact initial and final time, and a shifted independent interior grid.
    x=np.r_[0,(np.arange(65)+.37)/65,1];t=np.r_[0,(np.arange(67)+.61)/67,1]
    pts=np.array(np.meshgrid(x,t,indexing='ij')).reshape(2,-1).T;rows=[]
    for name,p,tol in cases():
        start=time.perf_counter();f=s.fit(p,tol);seconds=time.perf_counter()-start
        c=v.require_accuracy(p,f.model,f.certificate,tol);expected,tail=analytic(name,p,pts);pred=s.evaluate(p,f.model,pts)
        measured=float(np.max(abs(pred-expected)));v.need(measured<=float(c.solution_error_upper)+tail+1e-12,'reference contradicts certificate')
        for slab in c.slabs:
            mask=(pts[:,1]>=float(slab.interval[0]))&(pts[:,1]<=float(slab.interval[1]));v.need(max(abs(pred[mask]-expected[mask]))<=float(slab.solution_error_upper)+tail+1e-12,'slab reference contradicts certificate')
        m=f.model.spline;uniform=lambda n:tuple(round(64*i/(n+1))/64 for i in range(1,n+1))
        uc=v.assess(p,s._fit(p,uniform(len(m.xcuts)),uniform(len(m.ycuts))))
        raw=f.model.checkpoint();v.replay(p,v.restore(raw),c)
        (out/(name+'.checkpoint.json')).write_bytes(raw);(out/(name+'.certificate.json')).write_text(json.dumps(asdict(c),default=str,indent=2)+'\n')
        rows.append(dict(name=name,problem=asdict(p),problem_sha256=p.identity,model_sha256=f.model.identity,accepted=f.converged,tolerance=tol,fit_seconds=seconds,stages=[float(z.solution_error_upper) for z in f.history],xcuts=m.xcuts,tcuts=m.ycuts,parameters=len(m.coefficients),cells=len(c.cells),slab_bounds=[float(z.solution_error_upper) for z in c.slabs],full_domain_error_upper=float(c.solution_error_upper),exact_bound=str(c.solution_error_upper),sampled_max_error=measured,analytic_series_tail_bound=tail,heldout_points=len(pts),uniform_matched_bound=float(uc.solution_error_upper),initial_exact=c.initial_exact,boundary_exact=c.boundary_exact,c2=c.interfaces_exact))
    (out/'benchmark.json').write_text(json.dumps(rows,indent=2)+'\n');return rows

if __name__=='__main__':
    import argparse
    a=argparse.ArgumentParser();a.add_argument('--out',required=True);run(a.parse_args().out)
