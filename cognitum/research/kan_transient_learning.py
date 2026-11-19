"""Residual-only least squares for the parabolic tensor profile."""
from dataclasses import dataclass
import numpy as np
from . import kan_elliptic_learning as s,kan_elliptic_certificate as v,kan_transient_certificate as q

def _fit(p,xc,tc):
    x,wx=s._nodes(xc);t,wt=s._nodes(tc);nx,nt=len(xc)+4,len(tc)+4
    bx=s._basis(xc,x)[:,1:-1];bt=s._basis(tc,t)[:,1:]
    dx=s._basis(xc,x,2)[:,1:-1];dt=s._basis(tc,t,1)[:,1:]
    A=(np.einsum('xi,tj->xtij',bx,dt)-p.diffusion*np.einsum('xi,tj->xtij',dx,bt)+p.reaction*np.einsum('xi,tj->xtij',bx,bt)).reshape(len(x)*len(t),-1)
    g=np.polynomial.Polynomial(p.initial);rhs=np.broadcast_to((p.diffusion*g.deriv(2)(x)-p.reaction*g(x))[:,None],(len(x),len(t))).copy()
    for i,j,c in p.forcing:rhs+=c*x[:,None]**i*t[None,:]**j
    w=np.sqrt((wx[:,None]*wt[None,:]).ravel());sol,_,rank,_=np.linalg.lstsq(A*w[:,None],rhs.ravel()*w,rcond=None)
    v.need(rank==A.shape[1] and np.isfinite(sol).all(),'rank deficient/nonfinite fit')
    c=np.zeros((nx,nt));c[1:-1,1:]=sol.reshape(nx-2,nt-1)
    return q.Model(v.Model(xc,tc,tuple(map(float,c.ravel()))))

def evaluate(problem,model,points,derivative=(0,0)):
    v.need(type(problem) is q.Problem and type(model) is q.Model,'typed problem/model')
    a=np.asarray(points);out=s.evaluate(model.spline,a,derivative)
    if derivative[1]==0:out+=np.polynomial.Polynomial(problem.initial).deriv(derivative[0])(a[:,0])
    return out

@dataclass(frozen=True,slots=True)
class Fit:
    model:q.Model
    certificate:q.Certificate
    history:tuple
    converged:bool

def fit(problem,tolerance=.01,max_refinements=v.MAX_SPLITS):
    v.need(type(problem) is q.Problem and type(max_refinements) is int and 0<=max_refinements<=v.MAX_SPLITS,'refinement budget')
    t=v.number(tolerance);v.need(t>0,'positive tolerance');m=_fit(problem,(),());c=q.assess(problem,m);history=[c]
    v.need(c.solution_error_upper is not None,'hard conditions failed')
    while len(m.spline.xcuts)+len(m.spline.ycuts)<max_refinements:
        if c.solution_error_upper<=t:break
        seen=set();best=None
        # Rank by certified local residual; evaluate candidate strip splits by global bound.
        for cell in sorted(c.cells,key=lambda a:(-a.residual_upper,a.box)):
            x0,x1,t0,t1=cell.box
            for axis,lo,hi in [(0,x0,x1),(1,t0,t1)]:
                if hi-lo<v.Q(1,32):continue
                mid=float((lo+hi)/2);key=(axis,mid)
                if key in seen:continue
                seen.add(key);xc=m.spline.xcuts;tc=m.spline.ycuts
                candidate=(tuple(sorted((*xc,mid))),tc) if axis==0 else (xc,tuple(sorted((*tc,mid))))
                candidates=[candidate]
                # A symmetric pair can escape a one-knot local minimum.
                if axis==0 and 1-mid!=mid and 1-mid not in xc and len(xc)+len(tc)+2<=max_refinements:
                    pair=tuple(sorted((*xc,mid,1-mid)))
                    if min(b-a for a,b in zip((0.,*pair),(*pair,1.)))>=1/64:candidates.append((pair,tc))
                for cx,ct in candidates:
                    trial=_fit(problem,cx,ct);cert=q.assess(problem,trial)
                    if cert.solution_error_upper is not None and cert.solution_error_upper<c.solution_error_upper and (best is None or cert.solution_error_upper<best[1].solution_error_upper):best=(trial,cert)
        if best is None:break
        m,c=best;history.append(c)
    return Fit(m,c,tuple(history),c.solution_error_upper<=t)
