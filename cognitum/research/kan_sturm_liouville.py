"""Bounded affine-coefficient self-adjoint Sturm–Liouville Ritz solver.

Normalized unit interval, homogeneous separated D/N/Robin endpoints.
Research only: exact rational forms, numerical eigenpairs, no certified eigenvalue bounds.
"""
from dataclasses import dataclass
from fractions import Fraction as Q
import json
import numpy as np
from scipy.linalg import eigh
from cognitum.research import kan_function_metrics as o,kan_weak_form as p

PROFILE='cognitum.kan.sturm_liouville_affine.v1'
MAX_CUTS=15
MAX_DENOMINATOR=64
MAX_RECEIPT=131072
need=o.need

def rational(x):
    need(type(x) in (int,Q),'exact coefficient type')
    x=Q(x)
    need(abs(x)<=32 and x.denominator<=1024,'coefficient budget')
    return x

def coefficient(v,lower):
    need(type(v) is tuple and len(v)==2,'affine coefficient')
    a,b=map(rational,v)
    need(lower<=a<=16 and lower<=a+b<=16,'coefficient positivity or range')
    return a,b

def endpoint(v):
    need(type(v) is tuple and len(v)==2 and v[0] in ('D','N','R'),'boundary condition')
    kind,alpha=v;alpha=rational(alpha)
    need((kind=='R' and 0<alpha<=16) or (kind!='R' and alpha==0),'Robin coefficient')
    return kind,alpha

@dataclass(frozen=True,slots=True)
class Problem:
    diffusion:tuple
    potential:tuple
    weight:tuple
    left:tuple
    right:tuple
    def __post_init__(self):
        for key,lower in [('diffusion',Q(1,16)),('potential',Q(0)),('weight',Q(1,16))]:
            object.__setattr__(self,key,coefficient(getattr(self,key),lower))
        for key in ('left','right'):
            object.__setattr__(self,key,endpoint(getattr(self,key)))
    @property
    def null_mode(self):
        return self.left[0]==self.right[0]=='N' and self.potential==(0,0)

def validate(cuts):
    need(type(cuts) is tuple and 1<=len(cuts)<=MAX_CUTS,'knot count')
    need(all(type(x) is Q and 0<x<1 and x.denominator<=MAX_DENOMINATOR
        and x.denominator&(x.denominator-1)==0 for x in cuts),'dyadic knots')
    need(tuple(sorted(set(cuts)))==cuts,'knot order')
    need(all(b-a>=Q(1,MAX_DENOMINATOR) for a,b in zip((Q(0),*cuts),(*cuts,Q(1)))),'knot separation')

def indices(problem,cuts):
    need(type(problem) is Problem,'typed problem')
    return tuple(range(int(problem.left[0]=='D'),len(cuts)+4-int(problem.right[0]=='D')))

def _weighted(a,b,c,h):
    v=o._mul(a,b);z=o._mul(v,c)
    return o._bounded(h*sum((x/Q(i+1) for i,x in enumerate(z)),Q(0)))

def assemble(problem,cuts):
    validate(cuts);ids=indices(problem,cuts);n=len(ids)
    mass=[[Q(0)]*n for _ in ids];stiff=[[Q(0)]*n for _ in ids]
    for a,b,polys in o.f.j._basis(cuts):
        h=b-a;basis=[polys[i] for i in ids]
        deriv=[o._derivative(x,1,h) for x in basis]
        d,v,w=tuple((c[0]+c[1]*a,c[1]*h) for c in (problem.diffusion,problem.potential,problem.weight))
        for i in range(n):
            for j in range(i,n):
                mass[i][j]=mass[j][i]=o._bounded(mass[i][j]+_weighted(basis[i],basis[j],w,h))
                stiff[i][j]=stiff[j][i]=o._bounded(stiff[i][j]+_weighted(deriv[i],deriv[j],d,h)+_weighted(basis[i],basis[j],v,h))
    # Natural flux uses outward normal at each endpoint: n*p*u' + alpha*u = 0.
    if problem.left[0]=='R':stiff[0][0]=o._bounded(stiff[0][0]+problem.left[1])
    if problem.right[0]=='R':stiff[-1][-1]=o._bounded(stiff[-1][-1]+problem.right[1])
    md=p._ldl(mass,True);sd=p._ldl(stiff,not problem.null_mode)
    if problem.null_mode:
        need(sum(x==0 for x in sd)==1 and all(sum(row)==0 for row in stiff),'constant null mode identity')
    raw=o.f.canonical(dict(profile=PROFILE,problem=problem,cuts=cuts,dof=n,active_indices=ids,
        mass=mass,stiffness=stiff,mass_ldl=md,stiffness_ldl=sd,constant_null_mode=problem.null_mode,
        degree=3,domain=['0','1'],execution_authorized=False))
    need(len(raw)<=MAX_RECEIPT,'matrix receipt budget')
    return raw

def replay(problem,cuts,receipt):
    need(type(receipt) is bytes and 0<len(receipt)<=MAX_RECEIPT,'receipt size')
    need(assemble(problem,cuts)==receipt,'matrix replay mismatch')
    return True

def numeric(raw):
    r=json.loads(raw)
    return tuple(np.asarray([[float(Q(x)) for x in row] for row in r[k]]) for k in ('mass','stiffness'))

def solve(problem,cuts,modes=3):
    need(type(modes) is int and 1<=modes<=3,'mode budget')
    raw=assemble(problem,cuts);m,s=numeric(raw)
    need(modes<=len(m),'available modes')
    cond=float(np.linalg.cond(m));need(np.isfinite(cond) and cond<=p.MAX_CONDITION,'mass condition')
    values,vectors=eigh(s,m,subset_by_index=(0,modes-1))
    need(np.isfinite(values).all() and np.isfinite(vectors).all(),'finite spectrum')
    if problem.null_mode:
        need(abs(values[0])<=1e-8 and all(values[1:]>0),'Neumann null mode')
        values[0]=0.
    else:need(all(values>0),'positive spectrum')
    den=np.linalg.norm(s,ord=np.inf)*np.linalg.norm(vectors,ord=np.inf)+np.linalg.norm(m,ord=np.inf)*np.linalg.norm(vectors*values,ord=np.inf)
    residual=float(np.linalg.norm(s@vectors-(m@vectors)*values,ord=np.inf)/den)
    orth=float(np.linalg.norm(vectors.T@m@vectors-np.eye(modes),ord=np.inf))
    need(residual<=1e-9 and orth<=1e-8,'discrete eigenpair verification')
    return raw,dict(cuts=list(map(str,cuts)),dof=len(m),values=values.tolist(),vectors_columns=vectors.tolist(),
        mass_condition=cond,scaled_residual=residual,mass_orthogonality=orth,
        certified_eigenvalue_enclosure=False)

def history(problem,levels=4,modes=3):
    """Nested uniform dyadic refinement; no continuum reference used by solver."""
    need(type(levels) is int and 1<=levels<=4,'level budget')
    rows=[]
    for k in range(1,levels+1):
        n=2**k;cuts=tuple(Q(i,n) for i in range(1,n))
        raw,result=solve(problem,cuts,modes)
        if rows:
            prev=rows[-1][1]
            need(set(prev['cuts'])<set(result['cuts']),'nested trial spaces')
            need(all(v<=u+1e-9*max(1.,abs(u)) for u,v in zip(prev['values'],result['values'])),'Ritz monotonicity')
        rows.append((raw,result))
    return rows
