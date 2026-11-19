"""Residual-only anisotropic 2+1D tensor KAN learning, no analytical labels."""
from dataclasses import dataclass
import numpy as np
from . import kan_elliptic_learning as s,kan_spacetime_certificate as v


def _initial(p,x,y,dx=0,dy=0):
    from math import prod
    out=np.zeros(np.broadcast_shapes(x.shape,y.shape))
    for i,j,c in p.initial:
        if i>=dx and j>=dy:out+=c*prod(range(i-dx+1,i+1))*prod(range(j-dy+1,j+1))*x**(i-dx)*y**(j-dy)
    return out


def _fit(p,cuts):
    # Validate knots/resource bounds before allocation.
    shape=tuple(len(k)+4 for k in cuts);v.Model(cuts,(0,)*int(np.prod(shape)))
    (x,wx),(y,wy),(t,wt)=map(s._nodes,cuts);bx,by,bt=[s._basis(k,z)[:,slice(1,-1) if a<2 else slice(1,None)] for a,(k,z) in enumerate(zip(cuts,(x,y,t)))];dx=s._basis(cuts[0],x,2)[:,1:-1];dy=s._basis(cuts[1],y,2)[:,1:-1];dt=s._basis(cuts[2],t,1)[:,1:]
    ten=lambda a,b,c:np.einsum('xi,yj,tk->xytijk',a,b,c,optimize=True)
    A=(ten(bx,by,dt)-p.ax*ten(dx,by,bt)-p.ay*ten(bx,dy,bt)+p.reaction*ten(bx,by,bt)).reshape(len(x)*len(y)*len(t),-1)
    X=x[:,None,None];Y=y[None,:,None];T=t[None,None,:]
    rhs=np.broadcast_to(p.ax*_initial(p,X,Y,2,0)+p.ay*_initial(p,X,Y,0,2)-p.reaction*_initial(p,X,Y), (len(x),len(y),len(t))).copy()
    for i,j,k,c in p.forcing:rhs+=c*X**i*Y**j*T**k
    w=np.sqrt((wx[:,None,None]*wy[None,:,None]*wt[None,None,:]).ravel());coef,_,rank,_=np.linalg.lstsq(A*w[:,None],rhs.ravel()*w,rcond=None)
    v.need(rank==A.shape[1] and np.isfinite(coef).all(),'rank deficient/nonfinite fit');C=np.zeros(shape);C[1:-1,1:-1,1:]=coef.reshape(shape[0]-2,shape[1]-2,shape[2]-1)
    return v.Model(cuts,tuple(map(float,C.ravel())))


def evaluate(problem,model,points,derivative=(0,0,0)):
    v.need(type(problem) is v.Problem and type(model) is v.Model and type(derivative) is tuple and len(derivative)==3 and all(type(d) is int and 0<=d<=2 for d in derivative) and sum(derivative)<=2,'evaluation profile')
    a=np.asarray(points);v.need(a.dtype.kind in 'fiu' and a.ndim==2 and a.shape[1]==3 and 1<=len(a)<=32768,'point shape')
    v.need(np.isfinite(a).all() and (a>=0).all() and (a<=1).all(),'point domain')
    bs=[s._basis(k,a[:,i],derivative[i]) for i,k in enumerate(model.cuts)]
    out=np.einsum('ni,nj,nk,ijk->n',*bs,np.asarray(model.coefficients).reshape(model.shape),optimize=True)
    if derivative[2]==0:out+=_initial(problem,a[:,0],a[:,1],*derivative[:2])
    return out

@dataclass(frozen=True,slots=True)
class Fit:
    model:v.Model
    certificate:v.Certificate
    history:tuple
    converged:bool


def fit(problem,tolerance=.01,max_refinements=v.MAX_SPLITS):
    v.need(type(problem) is v.Problem and type(max_refinements) is int and 0<=max_refinements<=v.MAX_SPLITS,'refinement budget')
    tol=v.number(tolerance);v.need(tol>0,'positive tolerance');m=_fit(problem,((),(),()));c=v.assess(problem,m);history=[c]
    v.need(c.solution_error_upper is not None,'hard conditions failed')
    for _ in range(max_refinements):
        if c.solution_error_upper<=tol:break
        seen=set();best=None
        for cell in sorted(c.cells,key=lambda cell:(-cell.residual_upper,cell.box)):
            for axis,(lo,hi) in enumerate(cell.box):
                if hi-lo<v.Q(1,32):continue
                mid=float((lo+hi)/2);key=(axis,mid)
                if key in seen:continue
                seen.add(key);cuts=list(m.cuts);cuts[axis]=tuple(sorted((*cuts[axis],mid)))
                trial=_fit(problem,tuple(cuts));cert=v.assess(problem,trial)
                if cert.solution_error_upper is not None and cert.solution_error_upper<c.solution_error_upper and (best is None or cert.solution_error_upper<best[1].solution_error_upper):best=trial,cert
            if best is not None:break
        if best is None:break
        m,c=best;history.append(c)
    return Fit(m,c,tuple(history),c.solution_error_upper<=tol)
