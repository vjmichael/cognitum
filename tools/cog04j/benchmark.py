"""Independent Fourier-series and manufactured benchmarks, not training labels."""
from dataclasses import asdict
import json
from pathlib import Path
import time
import numpy as np
from cognitum.research import kan_elliptic_learning as s, kan_elliptic_certificate as v

F=((1,1,1),(1,2,-1),(2,1,-1),(2,2,1))


def analytic_series(p,points,N=255):
    # For x(1-x)y(1-y): odd sine coefficients 8/(n*pi)^3;
    # solve each y mode exactly with the two zero Dirichlet conditions.
    x,y=points.T;out=np.zeros(len(x))
    for n in range(1,N+1,2):
        k=n*np.pi;lam=p.ax*k*k+p.reaction;mu=np.sqrt(lam/p.ay)
        ratio=(np.exp(-mu*y)+np.exp(-mu*(1-y)))/(1+np.exp(-mu))
        out+=8/k**3*np.sin(k*x)*(y*(1-y)/lam+2*p.ay/lam**2*(ratio-1))
    # Bound sum of all omitted n (not only odd) by monotone integrals.
    tail=2/(p.ax*np.pi**5)/(4*N**4)+16*p.ay/(p.ax**2*np.pi**7)/(6*N**6)
    return out,tail


def cases():
    return [('poisson',v.Problem(1,1,0,((0,1,2),(0,2,-2),(1,0,2),(2,0,-2))),1e-12),('reaction_diffusion',v.Problem(1,1,4,F),.00031),('anisotropic',v.Problem(.125,1,10,F),.001),('asymmetric',v.Problem(.125,1,0,((1,1,-.75),(1,2,.75),(2,1,1.5),(2,2,-1.5),(3,0,2),(4,0,-2))),.003648)]


def run(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    x=(np.arange(65)+.37)/65;y=(np.arange(67)+.61)/67;pts=np.array(np.meshgrid(x,y,indexing='ij')).reshape(2,-1).T
    rows=[]
    for name,p,t in cases():
        start=time.perf_counter();f=s.fit(p,t);seconds=time.perf_counter()-start;c=v.require_accuracy(p,f.model,f.certificate,t)
        if name=='poisson':expected=pts[:,0]*(1-pts[:,0])*pts[:,1]*(1-pts[:,1]);tail=0.
        elif name=='asymmetric':expected=pts[:,0]**3*(1-pts[:,0])*pts[:,1]*(1-pts[:,1]);tail=0.
        else:expected,tail=analytic_series(p,pts)
        measured=float(np.max(abs(s.evaluate(f.model,pts)-expected)))
        # Numerical reference comparison is diagnostic, not the rigorous proof.
        v.need(measured<=float(c.solution_error_upper)+tail+1e-12,'holdout contradicted certificate')
        m=f.model;uniform=lambda n: tuple(round(64*i/(n+1))/64 for i in range(1,n+1));uc=v.assess(p,s._fit(p,uniform(len(m.xcuts)),uniform(len(m.ycuts))))
        raw=m.checkpoint();v.replay(p,v.restore(raw),c)
        (out/(name+'.checkpoint.json')).write_bytes(raw)
        (out/(name+'.certificate.json')).write_text(json.dumps(asdict(c),default=str,indent=2)+'\n')
        rows.append(dict(name=name,problem=asdict(p),problem_sha256=p.identity,model_sha256=m.identity,accepted=f.converged,tolerance=t,fit_seconds=seconds,stages=[float(r.solution_error_upper) for r in f.history],xcuts=m.xcuts,ycuts=m.ycuts,parameters=len(m.coefficients),cells=len(c.cells),full_domain_error_upper=float(c.solution_error_upper),exact_bound=str(c.solution_error_upper),sampled_max_error=measured,analytic_series_tail_bound=tail,heldout_points=len(pts),uniform_matched_bound=float(uc.solution_error_upper),conditions_exact=c.hard_conditions,c2=c.c2_interfaces))
    (out/'benchmark.json').write_text(json.dumps(rows,indent=2)+'\n');return rows

if __name__=='__main__':
    import argparse
    a=argparse.ArgumentParser();a.add_argument('--out',required=True);run(a.parse_args().out)
