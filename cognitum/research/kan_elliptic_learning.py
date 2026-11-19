"""Residual-trained tensor-product KAN PDE approximation; no label fitting."""
from dataclasses import dataclass
import numpy as np
from scipy.interpolate import BSpline
from . import kan_elliptic_certificate as v


def _grid(cuts):return [0.]*4+list(cuts)+[1.]*4


def _basis(cuts,x,order=0):
    n=len(cuts)+4
    return BSpline(_grid(cuts),np.eye(n),3,extrapolate=False)(x,nu=order)


def _nodes(cuts):
    z,w=np.polynomial.legendre.leggauss(6);points=[];weights=[]
    for a,b in zip((0.,*cuts),(*cuts,1.)):
        points.extend(a+(z+1)*(b-a)/2);weights.extend(w*(b-a)/2)
    return np.array(points),np.array(weights)


def _fit(p,xc,yc):
    x,wx=_nodes(xc);y,wy=_nodes(yc);nx,ny=len(xc)+4,len(yc)+4
    # All outer rows/columns fixed to exactly zero before solving.
    bx=_basis(xc,x)[:,1:-1];by=_basis(yc,y)[:,1:-1]
    dx=_basis(xc,x,2)[:,1:-1];dy=_basis(yc,y,2)[:,1:-1]
    A=(-p.ax*np.einsum('xi,yj->xyij',dx,by)-p.ay*np.einsum('xi,yj->xyij',bx,dy)+p.reaction*np.einsum('xi,yj->xyij',bx,by)).reshape(len(x)*len(y),-1)
    f=np.zeros((len(x),len(y)))
    for i,j,c in p.forcing:f+=c*x[:,None]**i*y[None,:]**j
    w=np.sqrt((wx[:,None]*wy[None,:]).ravel());sol,_,rank,_=np.linalg.lstsq(A*w[:,None],f.ravel()*w,rcond=None)
    v.need(rank==A.shape[1] and np.isfinite(sol).all(),'rank deficient/nonfinite fit')
    c=np.zeros((nx,ny));c[1:-1,1:-1]=sol.reshape(nx-2,ny-2)
    return v.Model(xc,yc,tuple(map(float,c.ravel())))


def evaluate(model,points,derivative=(0,0)):
    v.need(type(model) is v.Model and type(derivative) is tuple and len(derivative)==2 and all(type(d) is int and 0<=d<=2 for d in derivative) and sum(derivative)<=2,'evaluation profile')
    a=np.asarray(points);v.need(a.dtype.kind in 'fiu' and a.ndim==2 and a.shape[1]==2 and 1<=len(a)<=16384,'point shape')
    v.need(np.isfinite(a).all() and (a>=0).all() and (a<=1).all(),'point domain')
    return np.einsum('ni,ij,nj->n',_basis(model.xcuts,a[:,0],derivative[0]),np.asarray(model.coefficients).reshape(model.shape),_basis(model.ycuts,a[:,1],derivative[1]))


@dataclass(frozen=True,slots=True)
class Fit:
    model:v.Model
    certificate:v.Certificate
    history:tuple
    converged:bool


def fit(problem,tolerance=0.01,max_refinements=v.MAX_SPLITS):
    v.need(type(problem) is v.Problem and type(max_refinements) is int and 0<=max_refinements<=v.MAX_SPLITS,'refinement budget')
    t=v.number(tolerance);v.need(t>0,'positive tolerance')
    model=_fit(problem,(),());cert=v.assess(problem,model);history=[cert]
    v.need(cert.solution_error_upper is not None,'hard conditions failed')
    for _ in range(max_refinements):
        if cert.solution_error_upper<=t:break
        # Highest certified error cell first. Try splitting its x or y strip;
        # retain only strict full-domain certified improvement. No labels.
        seen=set();best=None
        for cell in sorted(cert.cells,key=lambda c:(-c.residual_upper,c.box)):
            x0,x1,y0,y1=cell.box
            for axis,lo,hi in [(0,x0,x1),(1,y0,y1)]:
                if hi-lo<v.Q(1,32):continue
                mid=float((lo+hi)/2);key=(axis,mid)
                if key in seen:continue
                seen.add(key)
                xc=tuple(sorted((*model.xcuts,mid))) if axis==0 else model.xcuts
                yc=tuple(sorted((*model.ycuts,mid))) if axis==1 else model.ycuts
                m=_fit(problem,xc,yc);c=v.assess(problem,m)
                if c.solution_error_upper is not None and c.solution_error_upper<cert.solution_error_upper and (best is None or c.solution_error_upper<best[1].solution_error_upper):best=(m,c)
            if best is not None:break
        if best is None:break
        model,cert=best;history.append(cert)
    return Fit(model,cert,tuple(history),cert.solution_error_upper<=t)
