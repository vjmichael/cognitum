"""Bounded conforming cubic spline Ritz approximation of the 1D Dirichlet Laplacian.

Research only. Exact rational forms, approximate numerical spectrum.
No general PDE, certified floating-point eigenvalue enclosure or production route.
"""
from fractions import Fraction as Q
import json
import numpy as np
from scipy.interpolate import BSpline
from scipy.linalg import eigh
from cognitum.research import kan_function_metrics as o,kan_weak_form as p

PROFILE='cognitum.kan.continuum_dirichlet_ritz.v1'
MAX_CUTS=11
MAX_STEPS=11
MAX_DENOMINATOR=128
MAX_RECEIPT=65536
need=o.need

def validate(cuts):
    need(type(cuts) is tuple and 1<=len(cuts)<=MAX_CUTS,'knot count')
    need(all(type(c) is Q and 0<c<1 and c.denominator<=MAX_DENOMINATOR
        and c.denominator&(c.denominator-1)==0 for c in cuts),'dyadic interior knots')
    need(tuple(sorted(set(cuts)))==cuts,'strict knot ordering')
    need(all(b-a>=Q(1,MAX_DENOMINATOR) for a,b in zip((Q(0),*cuts),(*cuts,Q(1)))),'knot separation')

def assemble(cuts):
    validate(cuts)
    n=len(cuts)+2
    m=[[Q(0)]*n for _ in range(n)];s=[[Q(0)]*n for _ in range(n)]
    # Exclude the first and last clamped basis functions: exact homogeneous Dirichlet trace.
    for a,b,polys in o.f.j._basis(cuts):
        h=b-a;basis=polys[1:-1]
        need(len(basis)==n,'basis dimension')
        deriv=[o._derivative(poly,1,h) for poly in basis]
        for i in range(n):
            for j in range(i,n):
                m[i][j]=m[j][i]=o._bounded(m[i][j]+o._poly_inner(basis[i],basis[j],h))
                s[i][j]=s[j][i]=o._bounded(s[i][j]+o._poly_inner(deriv[i],deriv[j],h))
    raw=o.f.canonical(dict(profile=PROFILE,cuts=cuts,dof=n,degree=3,domain=['0','1'],
        boundary='homogeneous-dirichlet',mass=m,stiffness=s,mass_ldl=p._ldl(m,True),
        stiffness_ldl=p._ldl(s,True),execution_authorized=False))
    need(len(raw)<=MAX_RECEIPT,'continuum matrix receipt budget')
    return raw

def replay(cuts,receipt):
    need(type(receipt) is bytes and 0<len(receipt)<=MAX_RECEIPT,'receipt size')
    need(assemble(cuts)==receipt,'matrix replay mismatch')
    return True

def numeric(raw):
    r=json.loads(raw)
    return tuple(np.asarray([[float(Q(x)) for x in row] for row in r[key]]) for key in ('mass','stiffness'))

def solve(cuts,modes):
    validate(cuts)
    need(type(modes) is int and 1<=modes<=3 and modes<=len(cuts)+2,'mode budget')
    raw=assemble(cuts);m,s=numeric(raw)
    cond=float(np.linalg.cond(m))
    need(np.isfinite(cond) and cond<=p.MAX_CONDITION,'mass condition')
    values,vectors=eigh(s,m,subset_by_index=(0,modes-1))
    need(np.isfinite(values).all() and np.isfinite(vectors).all() and np.all(values>0),'positive spectrum')
    residual=float(np.linalg.norm(s@vectors-(m@vectors)*values,ord=np.inf)/
        (np.linalg.norm(s,ord=np.inf)*np.linalg.norm(vectors,ord=np.inf)
        +np.linalg.norm(m,ord=np.inf)*np.linalg.norm(vectors*values,ord=np.inf)))
    orth=float(np.linalg.norm(vectors.T@m@vectors-np.eye(modes),ord=np.inf))
    need(residual<=1e-9 and orth<=1e-8,'discrete spectral verification')
    # Cellwise relative strong residual indicator, not a certified eigenvalue error estimate.
    edges=(Q(0),*cuts,Q(1));knots=np.array([0.]*3+list(map(float,edges))+[1.]*3)
    spline=BSpline(knots,np.eye(len(cuts)+4),3)
    x,w=np.polynomial.legendre.leggauss(6);scores=[]
    for a,b in zip(edges,edges[1:]):
        lo,hi=float(a),float(b);pts=(lo+hi)/2+(hi-lo)*x/2;wt=(hi-lo)*w/2
        z=(spline(pts,nu=2)[:,1:-1]@vectors+(spline(pts)[:,1:-1]@vectors)*values)/values
        scores.append(float(np.sum(wt[:,None]*z*z)))
    need(all(np.isfinite(v) and v>=0 for v in scores),'residual indicators')
    return raw,dict(cuts=[str(c) for c in cuts],dof=len(cuts)+2,values=values.tolist(),
        vectors_columns=vectors.tolist(),mass_condition=cond,scaled_residual=residual,
        mass_orthogonality=orth,cell_indicators=scores,certified_eigenvalue_enclosure=False)

def refine(cuts,scores):
    validate(cuts)
    need(len(cuts)<MAX_CUTS and type(scores) is list and len(scores)==len(cuts)+1
        and all(type(x) is float and np.isfinite(x) and x>=0 for x in scores),'refinement budget or indicators')
    edges=(Q(0),*cuts,Q(1));eligible=[i for i,(a,b) in enumerate(zip(edges,edges[1:])) if b-a>=Q(2,MAX_DENOMINATOR)]
    need(bool(eligible),'refinement exhausted')
    largest=max(scores[i] for i in eligible)
    # Stable tie rule, independent of floating round-off on symmetric cells.
    i=next(i for i in eligible if largest-scores[i]<=1e-12*max(largest,1e-300))
    nxt=tuple(sorted((*cuts,(edges[i]+edges[i+1])/2)));validate(nxt)
    return nxt,i

def adaptive(*,steps=9,modes=3):
    need(type(steps) is int and 1<=steps<=MAX_STEPS,'step budget')
    cuts=(Q(1,2),);rows=[]
    for k in range(steps):
        raw,result=solve(cuts,modes)
        if rows:
            prev=rows[-1][1]
            need(set(prev['cuts']).issubset(result['cuts']) and result['dof']==prev['dof']+1,'nonnested spaces')
            need(all(v<=u+1e-9*max(1.,abs(u)) for u,v in zip(prev['values'],result['values'])),'Ritz monotonicity')
        rows.append((raw,result))
        if k+1<steps:
            cuts,i=refine(cuts,result['cell_indicators']);result['marked_cell']=i
    return rows
