"""Two-component convection-diffusion eigenproblem on the unit interval.

L u = -u'' + b u' + C u, homogeneous Dirichlet for both components.
Exact rational weak forms; numerical complex left/right eigenpairs.
Only bounded constant coefficients and simple isolated low modes.
"""
from dataclasses import dataclass
from fractions import Fraction as Q
import json
import numpy as np
from scipy.linalg import eig
from cognitum.research import kan_sturm_liouville as r

PROFILE='cognitum.kan.coupled_ritz_constant.v1'
MAX_RECEIPT=262144
need=r.need
AXIS=r.Problem((1,0),(0,0),(1,0),('D',0),('D',0))

@dataclass(frozen=True,slots=True)
class Problem:
    drift:Q
    coupling:tuple
    def __post_init__(self):
        b=r.rational(self.drift)
        need(abs(b)<=4,'drift budget')
        need(type(self.coupling) is tuple and len(self.coupling)==2 and all(type(row) is tuple and len(row)==2 for row in self.coupling),'two component matrix')
        c=tuple(tuple(r.rational(x) for x in row) for row in self.coupling)
        need(all(abs(x)<=4 for row in c for x in row),'coupling budget')
        disc=(c[0][0]-c[1][1])**2+4*c[0][1]*c[1][0]
        need(abs(disc)>=Q(1,4),'repeated or near-defective component spectrum excluded')
        object.__setattr__(self,'drift',b);object.__setattr__(self,'coupling',c)

def assemble(problem,cuts):
    need(type(problem) is Problem,'typed problem')
    r.validate(cuts)
    axis=json.loads(r.assemble(AXIS,cuts));n=axis['dof']
    g=[[Q(0)]*n for _ in range(n)]
    for a,b,polys in r.o.f.j._basis(cuts):
        h=b-a;v=polys[1:-1];d=[r.o._derivative(x,1,h) for x in v]
        for i in range(n):
            for j in range(n):
                g[i][j]=r.o._bounded(g[i][j]+r.o._poly_inner(v[i],d[j],h))
    # Integration by parts with zero endpoint traces: exact skew derivative.
    need(all(g[i][j]==-g[j][i] for i in range(n) for j in range(n)),'exact skew drift form')
    m=[[Q(x) for x in row] for row in axis['mass']]
    k=[[Q(x) for x in row] for row in axis['stiffness']]
    A=[];M=[]
    for a in range(2):
        for i in range(n):
            A.append([r.o._bounded((k[i][j]+problem.drift*g[i][j] if a==b else Q(0))+problem.coupling[a][b]*m[i][j]) for b in range(2) for j in range(n)])
            M.append([m[i][j] if a==b else Q(0) for b in range(2) for j in range(n)])
    raw=r.o.f.canonical(dict(profile=PROFILE,problem=problem,cuts=cuts,axis=axis,drift_form=g,
        mass=M,operator=A,dof=2*n,ordering='component_then_spline',adjoint='transpose_operator_same_mass',
        execution_authorized=False))
    need(len(raw)<=MAX_RECEIPT,'coupled receipt budget')
    return raw

def replay(problem,cuts,raw):
    need(type(raw) is bytes and 0<len(raw)<=MAX_RECEIPT,'receipt size')
    need(assemble(problem,cuts)==raw,'coupled replay mismatch')
    return True

def numeric(raw):
    a=json.loads(raw)
    return tuple(np.asarray([[float(Q(x)) for x in row] for row in a[key]]) for key in ('mass','operator'))

def pack(a):
    a=np.asarray(a)
    return np.stack((a.real,a.imag),axis=-1).tolist()

def unpack(data):
    a=np.asarray(data,dtype=float)
    return a[...,0]+1j*a[...,1]

def solve(problem,cuts):
    raw=assemble(problem,cuts);m,a=numeric(raw)
    cond=float(np.linalg.cond(m));need(np.isfinite(cond) and cond<=r.p.MAX_CONDITION,'mass condition')
    z,l,v=eig(a,m,left=True,right=True)
    need(np.isfinite(z).all() and np.isfinite(l).all() and np.isfinite(v).all(),'finite coupled spectrum')
    idx=sorted(range(len(z)),key=lambda i:(z[i].real,z[i].imag))[:4]
    vals=z[idx];left=l[:,idx];right=v[:,idx]
    need(len(idx)==4 and min(abs(z[i]-z[j]) for i in idx for j in range(len(z)) if i!=j)>1e-6,'isolated simple low modes')
    for mat in (left,right):
        for i in range(4):
            x=mat[:,i];norm=float(np.vdot(x,m@x).real)
            need(np.isfinite(norm) and norm>0,'mass normalization')
            mat[:,i]/=np.sqrt(norm)
    def residual(B,x,lam):
        den=(np.linalg.norm(B,ord=np.inf)+abs(lam)*np.linalg.norm(m,ord=np.inf))*np.linalg.norm(x,ord=np.inf)
        return float(np.linalg.norm(B@x-lam*(m@x),ord=np.inf)/max(den,1e-300))
    rr=[residual(a,right[:,i],vals[i]) for i in range(4)]
    lr=[residual(a.T,left[:,i],vals[i].conjugate()) for i in range(4)]
    overlap=left.conj().T@m@right
    diag=np.abs(np.diag(overlap))
    off=float(np.max(abs(overlap-np.diag(np.diag(overlap)))))
    need(max(rr+lr)<=1e-9 and off<=1e-8 and np.min(diag)>=1e-4,'left/right residual or biorthogonality/conditioning')
    need(all(min(abs(x-y.conjugate()) for y in vals)<=1e-8*max(1.,abs(x)) for x in vals),'conjugate closure')
    return raw,dict(cuts=list(map(str,cuts)),dof=len(m),values=pack(vals),left_columns=pack(left),right_columns=pack(right),
        right_residuals=rr,left_residuals=lr,biorthogonal_overlap=pack(overlap),max_off_diagonal=off,
        reciprocal_overlap_condition=(1/diag).tolist(),mass_condition=cond,certified_eigenvalue_enclosure=False)

def history(problem,levels=4):
    need(type(levels) is int and 1<=levels<=4,'level budget')
    rows=[]
    for k in range(1,levels+1):
        n=2**k;c=tuple(Q(i,n) for i in range(1,n));rows.append(solve(problem,c))
    # No self-adjoint min-max monotonicity asserted for nonnormal problems.
    return rows
