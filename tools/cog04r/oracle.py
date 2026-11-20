"""Independent continuum Prüfer ODE shooting and direct spline quadrature."""
from fractions import Fraction as Q
from math import pi,atan2,sin,cos
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq
from scipy.interpolate import BSpline
from cognitum.research import kan_sturm_liouville as r

def reference(problem,modes=3,rtol=2e-11):
    """Phase of (u, p*u'), independent of spline basis, matrix and eigenvectors."""
    d,v,w=tuple(tuple(map(float,c)) for c in (problem.diffusion,problem.potential,problem.weight))
    start=0. if problem.left[0]=='D' else atan2(1.,float(problem.left[1]))
    end=pi if problem.right[0]=='D' else pi-atan2(1.,float(problem.right[1]))
    evaluations=0
    def phase(lam):
        nonlocal evaluations
        def rhs(x,t):
            return [cos(t[0])**2/(d[0]+d[1]*x)+(lam*(w[0]+w[1]*x)-(v[0]+v[1]*x))*sin(t[0])**2]
        z=solve_ivp(rhs,(0.,1.),[start],rtol=rtol,atol=rtol*.05,method='DOP853',max_step=1/64)
        r.need(z.success and np.isfinite(z.y[0,-1]),'continuum shooting integration')
        evaluations+=z.nfev
        return z.y[0,-1]
    origin=phase(0.);values=[];errors=[]
    for j in range(modes):
        target=end+j*pi
        if j==0 and problem.null_mode:
            r.need(abs(origin-target)<1e-9,'zero-mode phase');values.append(0.);errors.append(abs(origin-target));continue
        r.need(origin<target,'positive mode bracket')
        hi=16.
        while phase(hi)<target:
            hi*=2
            r.need(hi<=16384,'reference bracket budget')
        root=brentq(lambda l:phase(l)-target,0.,hi,xtol=1e-10,rtol=1e-12)
        err=abs(phase(root)-target);r.need(err<2e-7,'phase root residual')
        values.append(root);errors.append(err)
    return dict(values=values,phase_residuals=errors,rhs_evaluations=evaluations,rtol=rtol)

def verify(problem,raw,result,continuum):
    cuts=tuple(Q(x) for x in result['cuts'])
    r.need(r.replay(problem,cuts,raw),'exact replay')
    edges=(0.,*map(float,cuts),1.);nfull=len(cuts)+4
    spline=BSpline(np.array([0.]*3+list(edges)+[1.]*3),np.eye(nfull),3)
    ids=list(range(int(problem.left[0]=='D'),nfull-int(problem.right[0]=='D')))
    n=len(ids);m=np.zeros((n,n));s=np.zeros((n,n));x,w=np.polynomial.legendre.leggauss(8)
    def coef(c,x):return float(c[0])+float(c[1])*x
    for a,b in zip(edges,edges[1:]):
        pts=(a+b)/2+(b-a)*x/2;wt=(b-a)*w/2
        V=spline(pts)[:,ids];D=spline(pts,nu=1)[:,ids]
        m+=V.T@((wt*coef(problem.weight,pts))[:,None]*V)
        s+=D.T@((wt*coef(problem.diffusion,pts))[:,None]*D)+V.T@((wt*coef(problem.potential,pts))[:,None]*V)
    for i,bc in enumerate((problem.left,problem.right)):
        trace=spline(float(i))[ids]
        if bc[0]=='D':r.need(np.max(abs(trace))==0,'Dirichlet trace')
        if bc[0]=='R':s+=float(bc[1])*np.outer(trace,trace)
    em,es=r.numeric(raw)
    r.need(np.allclose(em,m,atol=1e-10,rtol=1e-10) and np.allclose(es,s,atol=1e-10,rtol=1e-10),'independent matrix agreement')
    l=np.linalg.cholesky(m);a=np.linalg.solve(l,s);h=np.linalg.solve(l,a.T).T
    r.need(np.allclose(h,h.T,atol=1e-9,rtol=1e-9),'whitened symmetry')
    primary=np.asarray(result['values']);ref=np.linalg.eigvalsh((h+h.T)/2)[:len(primary)]
    r.need(np.allclose(primary,ref,atol=1e-8,rtol=1e-9),'independent Ritz spectrum')
    exact=np.asarray(continuum['values']);scale=np.maximum(1.,abs(exact))
    r.need(np.all(primary>=exact-2e-8*scale),'continuum minmax numerical check')
    vec=np.array(result['vectors_columns']);bc_errors=[]
    for i,bc in enumerate((problem.left,problem.right)):
        u=spline(float(i))[ids]@vec
        flux=(-1 if i==0 else 1)*coef(problem.diffusion,float(i))*(spline(float(i),nu=1)[ids]@vec)
        bc_errors.append(abs(u if bc[0]=='D' else flux+float(bc[1])*u).tolist())
    return dict(independent_values=ref.tolist(),continuum_values=exact.tolist(),
        scaled_errors=(abs(primary-exact)/scale).tolist(),endpoint_strong_residuals=bc_errors,
        quadrature_points=8*(len(cuts)+1),max_mass_difference=float(np.max(abs(m-em))),
        max_stiffness_difference=float(np.max(abs(s-es))),max_eigenvalue_difference=float(np.max(abs(primary-ref))))
