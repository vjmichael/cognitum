"""Independent six-node direct spline assembly and whitened eigenspectrum."""
from fractions import Fraction as Q
from math import pi
import numpy as np
from scipy.interpolate import BSpline
from cognitum.research import kan_continuum_ritz as q

def verify(raw,result):
    cuts=tuple(Q(x) for x in result['cuts'])
    q.need(q.replay(cuts,raw),'exact matrix replay')
    edges=(Q(0),*cuts,Q(1))
    knots=np.array([0.]*3+list(map(float,edges))+[1.]*3)
    basis=BSpline(knots,np.eye(len(cuts)+4),3)
    n=len(cuts)+2;m=np.zeros((n,n));s=np.zeros((n,n))
    x,w=np.polynomial.legendre.leggauss(8)
    for a,b in zip(edges,edges[1:]):
        lo,hi=float(a),float(b);pts=(lo+hi)/2+(hi-lo)*x/2;wt=(hi-lo)*w/2
        v=basis(pts)[:,1:-1];d=basis(pts,nu=1)[:,1:-1]
        m+=v.T@(wt[:,None]*v);s+=d.T@(wt[:,None]*d)
    em,es=q.numeric(raw)
    q.need(np.allclose(m,em,atol=1e-10,rtol=1e-10) and np.allclose(s,es,atol=1e-10,rtol=1e-10),'independent matrix agreement')
    l=np.linalg.cholesky(m);a=np.linalg.solve(l,s);h=np.linalg.solve(l,a.T).T
    q.need(np.allclose(h,h.T,atol=1e-9,rtol=1e-9),'independent symmetry')
    primary=np.asarray(result['values']);values=np.linalg.eigvalsh((h+h.T)/2)[:len(primary)]
    q.need(np.allclose(primary,values,atol=1e-8,rtol=1e-9),'independent eigenspectrum')
    exact=(pi*np.arange(1,len(primary)+1))**2
    q.need(np.all(primary>=exact-1e-8*exact),'continuum min-max check')
    # Not a rigorous enclosure of pi or the float64 Ritz values.
    return dict(independent_values=values.tolist(),analytic_values=exact.tolist(),
        relative_errors=(abs(primary-exact)/exact).tolist(),quadrature_points=8*(len(cuts)+1),
        max_mass_difference=float(np.max(abs(m-em))),max_stiffness_difference=float(np.max(abs(s-es))),
        max_eigenvalue_difference=float(np.max(abs(primary-values))))
