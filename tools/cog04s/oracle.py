"""Independent axis continuum shooting, direct quadrature and small global dense reference."""
from fractions import Fraction as Q
from itertools import product
from functools import reduce
from math import prod
import json
import numpy as np
from scipy.interpolate import BSpline
from scipy.linalg import eigh
from tools.cog04r.oracle import reference,verify as axis_verify
from cognitum.research import kan_tensor_ritz as s

def sums(values,lengths,k):
    # Full Cartesian enumeration of the available independently computed axis spectra.
    return sorted(sum(v/float(L)**2 for v,L in zip(combo,lengths)) for combo in product(*values))[:k]

def continuum(problem):
    refs=[reference(a,rtol=2e-12) for a in problem.axes]
    coarse=[reference(a) for a in problem.axes]
    s.need(all(np.allclose(x['values'],y['values'],atol=2e-8,rtol=2e-9) for x,y in zip(refs,coarse)),'axis continuum stability')
    return dict(axes=refs,values=sums([a['values'] for a in refs],problem.lengths,3))

def direct_axis(a,cuts):
    edges=(0.,*map(float,cuts),1.)
    n=len(cuts)+4;ids=list(range(int(a.left[0]=='D'),n-int(a.right[0]=='D')))
    b=BSpline([0.]*3+list(edges)+[1.]*3,np.eye(n),3)
    m=np.zeros((len(ids),len(ids)));k=m.copy();x,w=np.polynomial.legendre.leggauss(10)
    def f(c,z):return float(c[0])+float(c[1])*z
    for lo,hi in zip(edges,edges[1:]):
        z=(lo+hi)/2+(hi-lo)*x/2;wt=(hi-lo)*w/2
        v=b(z)[:,ids];d=b(z,nu=1)[:,ids]
        m+=v.T@((wt*f(a.weight,z))[:,None]*v)
        k+=d.T@((wt*f(a.diffusion,z))[:,None]*d)+v.T@((wt*f(a.potential,z))[:,None]*v)
    for i,bc in enumerate((a.left,a.right)):
        if bc[0]=='R':v=b(float(i))[ids];k+=float(bc[1])*np.outer(v,v)
    return m,k

def verify(problem,raw,row,ref):
    cuts=tuple(tuple(Q(x) for x in c) for c in row['cuts'])
    s.need(s.replay(problem,cuts,raw),'exact factor replay')
    receipt=json.loads(raw);axis=[];ms=[];ks=[];vals=[];k=len(row['values'])
    for a,c,f,v,t in zip(problem.axes,cuts,receipt['factors'],row['axis'],ref['axes']):
        a_raw=s.r.o.f.canonical(f);axis.append(axis_verify(a,a_raw,v,t))
        m,z=direct_axis(a,c);ms.append(m);ks.append(z)
        em,ez=s.r.numeric(a_raw)
        s.need(np.allclose(m,em,rtol=1e-10,atol=1e-10) and np.allclose(z,ez,rtol=1e-10,atol=1e-10),'independent factor matrix')
        L=np.linalg.cholesky(m);h=np.linalg.solve(L,z);h=np.linalg.solve(L,h.T).T
        vals.append(np.linalg.eigvalsh((h+h.T)/2).tolist())
    independent=sums(vals,problem.lengths,k);primary=np.asarray(row['values'])
    s.need(np.allclose(primary,independent,atol=1e-8,rtol=1e-9),'independent tensor spectrum')
    dense=None
    if row['dof']<=160:
        M=reduce(np.kron,ms);K=np.zeros_like(M)
        for j,L in enumerate(problem.lengths):
            ff=list(ms);ff[j]=ks[j];K+=reduce(np.kron,ff)/float(L)**2
        dense=eigh(K,M,subset_by_index=(0,k-1),eigvals_only=True)
        s.need(np.allclose(primary,dense,atol=1e-8,rtol=1e-9),'global dense reference')
    exact=np.asarray(ref['values'][:k]);scale=np.maximum(1.,abs(exact))
    s.need(np.all(primary>=exact-2e-8*scale),'continuum min-max check')
    return dict(axis=axis,independent_values=independent,continuum_values=exact.tolist(),
        scaled_errors=(abs(primary-exact)/scale).tolist(),
        max_eigenvalue_difference=float(np.max(abs(primary-independent))),
        dense_reference=None if dense is None else dense.tolist(),
        dense_difference=None if dense is None else float(np.max(abs(primary-dense))),
        quadrature_points=sum(x['quadrature_points']+10*(len(c)+1) for x,c in zip(axis,cuts)))
