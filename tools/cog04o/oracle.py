"""Independent SciPy/Gauss reference, separate from exact Gram computation."""
from itertools import product
from math import prod
import numpy as np
from scipy.interpolate import BSpline
from cognitum.mel import tensor_field as f


def _numeric(mod,p,m,points,order):
    cuts,shape,coef=f._tensor(mod,m)
    arrays=[]
    for axis,(c,n) in enumerate(zip(cuts,shape)):
        knot=np.array([0.]*4+list(c)+[1.]*4,dtype=np.float64)
        arrays.append(BSpline(knot,np.eye(n),3)(points[:,axis],nu=order[axis]))
    subs='ni,nj,ij->n' if len(shape)==2 else 'ni,nj,nk,ijk->n'
    result=np.einsum(subs,*arrays,np.array(coef,dtype=float).reshape(shape),optimize=True)
    for term in f._initial(mod,p):
        val=np.ones(len(points))*term[-1]
        for i,(degree,d) in enumerate(zip(term[:-1],order)):
            if degree<d:val*=0.
            else:val*=prod(range(degree-d+1,degree+1))*points[:,i]**(degree-d)
        result+=val
    return result


def reference(left,right):
    lm,lp,la,_=f.restore(left);rm,rp,ra,_=f.restore(right)
    f.need(lm is rm,'reference profile')
    lc,ls,_=f._tensor(lm,la);rc,_,_=f._tensor(rm,ra)
    x,w=np.polynomial.legendre.leggauss(5);axes=[]
    for a,b in zip(lc,rc):
        edge=sorted({0.,1.,*a,*b})
        axes.append([(float((lo+hi)/2+(hi-lo)*z/2),float((hi-lo)*v/2))
                     for lo,hi in zip(edge,edge[1:]) for z,v in zip(x,w)])
    grid=list(product(*axes));pts=np.array([[u for u,v in r] for r in grid])
    weight=np.array([prod(v for u,v in r) for r in grid])
    rows=[]
    for axis in range(-1,len(ls)):
        order=tuple(int(i==axis) for i in range(len(ls)))
        a,b=_numeric(lm,lp,la,pts,order),_numeric(rm,rp,ra,pts,order)
        rows.append(dict(left_squared=float(np.dot(weight,a*a)),right_squared=float(np.dot(weight,b*b)),
            inner=float(np.dot(weight,a*b)),distance_squared=float(np.dot(weight,(a-b)**2))))
    return rows,len(pts)
