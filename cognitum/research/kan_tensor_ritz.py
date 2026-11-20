"""Exact factorized weak forms for separable weighted rectangular 2D/3D operators.

On the normalized box, mass = tensor product of axis masses;
stiffness = sum of axis stiffness terms times transverse masses and 1/L_i^2.
No dense multidimensional matrix is required. Research-only.
"""
from dataclasses import dataclass
from fractions import Fraction as Q
from itertools import product
from math import prod
import json
import numpy as np
from cognitum.research import kan_sturm_liouville as r

PROFILE='cognitum.kan.tensor_ritz_separable.v1'
MAX_DOF=7000
MAX_RECEIPT=524288
need=r.need

@dataclass(frozen=True,slots=True)
class Problem:
    axes:tuple
    lengths:tuple
    def __post_init__(self):
        need(type(self.axes) is tuple and len(self.axes) in (2,3) and all(type(a) is r.Problem for a in self.axes),'axis profiles')
        need(type(self.lengths) is tuple and len(self.lengths)==len(self.axes),'length count')
        lengths=tuple(r.rational(x) for x in self.lengths)
        need(all(Q(1,2)<=v<=4 for v in lengths),'length budget')
        object.__setattr__(self,'lengths',lengths)
    @property
    def scales(self):return tuple(1/x**2 for x in self.lengths)

def validate(problem,cuts):
    need(type(problem) is Problem and type(cuts) is tuple and len(cuts)==len(problem.axes),'tensor rank')
    for c in cuts:r.validate(c)
    shape=tuple(len(r.indices(a,c)) for a,c in zip(problem.axes,cuts))
    need(prod(shape)<=MAX_DOF,'tensor degree-of-freedom budget')
    return shape

def _receipt(problem,cuts,axis_receipts):
    shape=validate(problem,cuts)
    raw=r.o.f.canonical(dict(profile=PROFILE,problem=problem,cuts=cuts,shape=shape,dof=prod(shape),
        scales=problem.scales,factors=[json.loads(x) for x in axis_receipts],
        mass='kronecker_product',stiffness='sum_scaled_axis_stiffness_transverse_mass',
        order='last_axis_fastest',constant_null_mode=all(a.null_mode for a in problem.axes),
        execution_authorized=False))
    need(len(raw)<=MAX_RECEIPT,'tensor receipt budget')
    return raw

def assemble(problem,cuts):
    validate(problem,cuts)
    return _receipt(problem,cuts,[r.assemble(a,c) for a,c in zip(problem.axes,cuts)])

def replay(problem,cuts,raw):
    need(type(raw) is bytes and 0<len(raw)<=MAX_RECEIPT,'receipt size')
    need(assemble(problem,cuts)==raw,'tensor replay mismatch')
    return True

def entry(raw,left,right):
    """Exact entry in factorized represented weak forms, no global dense expansion."""
    d=json.loads(raw);shape=d['shape'];rank=len(shape)
    need(type(left) is tuple and type(right) is tuple and len(left)==len(right)==rank
        and all(type(i) is int and 0<=i<n for idx in (left,right) for i,n in zip(idx,shape)),'tensor index')
    m=[Q(f['mass'][i][j]) for f,i,j in zip(d['factors'],left,right)]
    s=[Q(f['stiffness'][i][j]) for f,i,j in zip(d['factors'],left,right)]
    return r.o._bounded(prod(m)),r.o._bounded(sum((Q(d['scales'][k])*s[k]*prod(m[:k]+m[k+1:]) for k in range(rank)),Q(0)))

def combine(values,scales,modes):
    # For lowest k values, the first k eigenvalues along every axis suffice.
    # Ties retain multiplicity within the returned window, not the complete eigenspace.
    ranked=sorted((sum(float(s)*values[j][i] for j,(s,i) in enumerate(zip(scales,idx))),idx)
        for idx in product(*(range(len(a)) for a in values)))
    return ranked[:modes]

def _outer(vectors):
    a=vectors[0]
    for b in vectors[1:]:a=np.multiply.outer(a,b)
    return a

def _apply(array,mats):
    u=array
    for axis,m in enumerate(mats):u=np.moveaxis(np.tensordot(m,u,axes=(1,axis)),0,axis)
    return u

def solve(problem,cuts,modes=3):
    shape=validate(problem,cuts)
    need(type(modes) is int and 1<=modes<=3,'mode budget')
    data=[r.solve(a,c,modes) for a,c in zip(problem.axes,cuts)]
    raw=_receipt(problem,cuts,[a for a,b in data])
    axis=[b for a,b in data];pairs=combine([b['values'] for b in axis],problem.scales,modes)
    matrices=[r.numeric(a) for a,b in data];ms=[a for a,b in matrices];ss=[b for a,b in matrices]
    basis=[np.asarray(a['vectors_columns']) for a in axis]
    cond=prod(a['mass_condition'] for a in axis)
    need(np.isfinite(cond) and cond<=1e8,'tensor mass condition')
    vectors=[];residuals=[]
    for lam,idx in pairs:
        u=_outer([v[:,i] for v,i in zip(basis,idx)])
        mu=_apply(u,ms);su=np.zeros(shape)
        for j,scale in enumerate(problem.scales):
            mats=list(ms);mats[j]=ss[j];su+=float(scale)*_apply(u,mats)
        norm_s=sum(float(scale)*np.linalg.norm(ss[j],ord=np.inf)*prod(np.linalg.norm(ms[k],ord=np.inf) for k in range(len(ms)) if k!=j)
            for j,scale in enumerate(problem.scales))
        den=(norm_s+abs(lam)*prod(np.linalg.norm(m,ord=np.inf) for m in ms))*np.max(abs(u))
        err=float(np.max(abs(su-lam*mu))/max(den,1e-300))
        need(np.isfinite(err) and err<=1e-9,'tensor residual')
        residuals.append(err);vectors.append((u,mu))
    orth=max(abs(float(np.sum(u*mv))-int(i==j)) for i,(u,mu) in enumerate(vectors) for j,(v,mv) in enumerate(vectors))
    need(orth<=1e-8,'tensor mass orthogonality')
    return raw,dict(cuts=[list(map(str,c)) for c in cuts],shape=shape,dof=prod(shape),axis=axis,
        values=[v for v,i in pairs],mode_indices=[i for v,i in pairs],scaled_residuals=residuals,
        mass_orthogonality=orth,mass_condition=cond,certified_eigenvalue_enclosure=False,
        dense_global_matrix_allocated=False)

def history(problem,levels=4,modes=3):
    need(type(levels) is int and 1<=levels<=4,'level budget')
    rows=[]
    for k in range(1,levels+1):
        n=2**k;c=tuple(Q(i,n) for i in range(1,n))
        raw,row=solve(problem,(c,)*len(problem.axes),modes)
        if rows:
            need(all(v<=u+1e-9*max(1.,abs(u)) for u,v in zip(rows[-1][1]['values'],row['values'])),'nested tensor Ritz monotonicity')
        rows.append((raw,row))
    return rows
