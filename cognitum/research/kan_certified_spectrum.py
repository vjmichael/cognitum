"""Rigorous rational continuum eigenvalue enclosures for the bounded R scalar class.

Floating point supplies trial thresholds only. All inequalities and inertia
witnesses are checked with rational arithmetic; no claim for general nonnormal spectra.
"""
from fractions import Fraction as Q
from math import ceil,floor,isqrt
import hashlib,json
import numpy as np
from scipy.linalg import eigh
from cognitum.research import kan_sturm_liouville as r

PROFILE='cognitum.kan.certified_scalar_spectrum.v1'
MAX_RECEIPT=262144
GRID=10**7
need=r.need

def _canonical(x):return r.o.f.canonical(x)
def _sha(x):return hashlib.sha256(x).hexdigest()
def _bound(x):return r.o._bounded(x)

def _atan_interval(q):
    n=16
    a=sum((Q((-1)**i,(2*i+1)*q**(2*i+1)) for i in range(n)),Q(0))
    b=a+Q((-1)**n,(2*n+1)*q**(2*n+1))
    return min(a,b),max(a,b)

def pi_interval():
    """Machin identity and alternating arctangent series remainder."""
    a,b=_atan_interval(5);c,d=_atan_interval(239)
    return 16*a-4*d,16*b-4*c

def sqrt_upper(x):
    need(type(x) is Q and x>=0,'sqrt domain')
    scale=10**12
    k=isqrt((x.numerator*scale*scale)//x.denominator)
    return Q(k if Q(k*k,scale*scale)==x else k+1,scale)

def assemble_supported(problem,cuts):
    """Equivalent R assembly: enumerate only locally nonzero cubic basis functions."""
    r.validate(cuts);ids=r.indices(problem,cuts);n=len(ids)
    mass=[[Q(0)]*n for _ in ids];stiff=[[Q(0)]*n for _ in ids]
    for a,b,polys in r.o.f.j._basis(cuts):
        h=b-a;active=[(i,polys[j]) for i,j in enumerate(ids) if any(polys[j])]
        deriv=[(i,v,r.o._derivative(v,1,h)) for i,v in active]
        d,v,w=tuple((c[0]+c[1]*a,c[1]*h) for c in (problem.diffusion,problem.potential,problem.weight))
        for i,bi,di in deriv:
            for j,bj,dj in deriv:
                if j<i:continue
                mass[i][j]=mass[j][i]=_bound(mass[i][j]+r._weighted(bi,bj,w,h))
                stiff[i][j]=stiff[j][i]=_bound(stiff[i][j]+r._weighted(di,dj,d,h)+r._weighted(bi,bj,v,h))
    if problem.left[0]=='R':stiff[0][0]=_bound(stiff[0][0]+problem.left[1])
    if problem.right[0]=='R':stiff[-1][-1]=_bound(stiff[-1][-1]+problem.right[1])
    md=r.p._ldl(mass,True);sd=r.p._ldl(stiff,not problem.null_mode)
    if problem.null_mode:need(sum(x==0 for x in sd)==1 and all(sum(row)==0 for row in stiff),'constant null mode identity')
    raw=_canonical(dict(profile=r.PROFILE,problem=problem,cuts=cuts,dof=n,active_indices=ids,
        mass=mass,stiffness=stiff,mass_ldl=md,stiffness_ldl=sd,constant_null_mode=problem.null_mode,
        degree=3,domain=['0','1'],execution_authorized=False))
    need(len(raw)<=r.MAX_RECEIPT,'matrix receipt budget')
    return raw

def _dense_inertia(M,S,t):
    B=[[_bound(s-t*m) for m,s in zip(mr,sr)] for mr,sr in zip(M,S)];p=[]
    for k in range(len(B)):
        d=B[k][k]
        if not d:raise ZeroDivisionError('zero inertia pivot')
        p.append(d)
        for i in range(k+1,len(B)):
            for j in range(i,len(B)):
                B[j][i]=B[i][j]=_bound(B[i][j]-B[i][k]*B[j][k]/d)
    return _witness(p)

def _tri_inertia(md,mo,kd,ko,t):
    p=[]
    for i,(m,s) in enumerate(zip(md,kd)):
        d=s-t*m
        if i:d-=(ko[i-1]-t*mo[i-1])**2/p[-1]
        if not d:raise ZeroDivisionError('zero inertia pivot')
        p.append(_bound(d))
    return _witness(p)

def _witness(p):
    return dict(negative_pivots=sum(x<0 for x in p),pivot_count=len(p),pivots_sha256=_sha(_canonical(p)))

def _comparison(problem,cells,pi_lo,include_potential):
    """Piecewise constant lower diffusion/reaction and upper weight comparator."""
    h=Q(1,cells);md=[Q(0)]*(cells+1);kd=md.copy();mo=[Q(0)]*cells;ko=mo.copy()
    d,v,w=problem.diffusion,problem.potential,problem.weight
    beta=min(v[0]/w[0],sum(v)/sum(w));c2=Q(0);vmax=Q(0)
    def at(c,x):return c[0]+c[1]*x
    for i in range(cells):
        x,y=i*h,(i+1)*h
        p=min(at(d,x),at(d,y));weight=max(at(w,x),at(w,y))
        reaction=min(at(v,x)-beta*at(w,x),at(v,y)-beta*at(w,y)) if include_potential else Q(0)
        need(p>0 and weight>0 and reaction>=0,'comparison coefficients')
        m=weight*h/3;s=p/h;v0=reaction*h/3
        md[i]+=m;md[i+1]+=m;kd[i]+=s+v0;kd[i+1]+=s+v0
        mo[i]=m/2;ko[i]=-s+v0/2
        c2=max(c2,h*h*weight/(pi_lo**2*p));vmax=max(vmax,reaction/weight)
    for i,bc in ((0,problem.left),(cells,problem.right)):
        if bc[0]=='R':kd[i]+=bc[1]
    lo=int(problem.left[0]=='D');hi=cells+1-int(problem.right[0]=='D')
    return (md[lo:hi],mo[lo:hi-1],kd[lo:hi],ko[lo:hi-1]),beta,c2,vmax

def _mat(d,o):
    return np.diag(list(map(float,d)))+np.diag(list(map(float,o)),1)+np.diag(list(map(float,o)),-1)

def _trial(values,inertia,upper):
    result=[]
    for i,value in enumerate(values):
        for offset in range(2,12):
            t=Q(ceil(float(value)*GRID)+offset,GRID) if upper else max(Q(0),Q(floor(float(value)*GRID)-offset,GRID))
            if not upper and t==0:result.append(t);break
            try:w=inertia(t)
            except ZeroDivisionError:continue
            if (w['negative_pivots']>=i+1 if upper else w['negative_pivots']<=i):
                result.append(t);break
        else:raise ValueError('unable to certify numerical trial threshold')
    return result

def _validate_trials(ts):
    need(type(ts) is list and len(ts)==3 and all(type(t) is Q and 0<=t<=100000 and t.denominator<=GRID for t in ts),'trial threshold budget')

def _lower(comp,beta,c2,vmax,t,i,include_potential):
    if t==0:return beta,None
    w=_tri_inertia(*comp,t);need(w['negative_pivots']<=i,'comparison lower inertia')
    if include_potential:
        # Energy stability of the nodal interpolation in the diffusion+Robin seminorm,
        # with reaction perturbation bounded in weighted L2.
        c=sqrt_upper(c2)
        lower=beta+t/(1+c*sqrt_upper(vmax)+c*sqrt_upper(t))**2
    else:lower=beta+t/(1+c2*t)
    return _bound(lower),w

def _proof(problem,cuts,raw,approx,uppers,lower0,lower1):
    need(type(problem) is r.Problem,'scalar profile only')
    r.validate(cuts)
    for ts in (uppers,lower0,lower1):_validate_trials(ts)
    need(type(approx) is list and len(approx)==3 and all(type(x) is Q and abs(x)<=100000 and x.denominator.bit_length()<=128 for x in approx),'approximation budget')
    a=json.loads(raw);M,S=([[Q(x) for x in row] for row in a[k]] for k in ('mass','stiffness'))
    pi_lo,pi_hi=pi_interval();cells=min(64,4*(len(cuts)+1))
    c0,beta,c2,v0=_comparison(problem,cells,pi_lo,False)
    c1,beta1,c21,v1=_comparison(problem,cells,pi_lo,True)
    need(beta==beta1 and c2==c21,'comparison consistency')
    d,v,w=problem.diffusion,problem.potential,problem.weight
    de=int(problem.left[0]=='D')+int(problem.right[0]=='D')
    analytic=not any(c[1] for c in (d,v,w)) and all(bc[0]!='R' for bc in (problem.left,problem.right))
    rows=[]
    for i,(x,u,t0,t1) in enumerate(zip(approx,uppers,lower0,lower1)):
        # Congruence LDL inertia proves at least i+1 finite Ritz eigenvalues < u;
        # conforming min-max then bounds the continuum eigenvalue by u.
        uw=_dense_inertia(M,S,u);need(uw['negative_pivots']>=i+1,'Ritz upper inertia')
        l0,lw0=_lower(c0,beta,c2,v0,t0,i,False);l1,lw1=_lower(c1,beta,c2,v1,t1,i,True)
        mode=Q(i)+Q(de,2)
        global_lower=beta+min(d[0],sum(d))*mode**2*pi_lo**2/max(w[0],sum(w))
        lo=max(global_lower,l0,l1);hi=u
        if analytic:
            lo=max(lo,(d[0]*mode**2*pi_lo**2+v[0])/w[0])
            hi=min(hi,(d[0]*mode**2*pi_hi**2+v[0])/w[0])
        if problem.null_mode and not i:lo=hi=Q(0)
        need(0<=lo<=hi,'inconsistent continuum enclosure')
        rows.append(dict(index=i+1,approximation=x,ritz_upper_trial=u,ritz_upper_witness=uw,
            diffusion_lower_trial=t0,diffusion_witness=lw0,reaction_lower_trial=t1,reaction_witness=lw1,
            comparison_diffusion_lower=l0,comparison_reaction_lower=l1,global_comparison_lower=global_lower,
            lower=lo,upper=hi,absolute_error_upper=max(abs(x-lo),abs(x-hi))))
    result=_canonical(dict(profile=PROFILE,problem=problem,cuts=cuts,exact_matrix_sha256=_sha(raw),
        comparison_cells=cells,pi_interval=(pi_lo,pi_hi),beta=beta,interpolation_constant_squared=c2,
        reaction_ratio_bound=v1,analytic_tightening=analytic,rows=rows,
        theorem='conforming_minmax_and_piecewise_constant_comparison_interpolation',
        certified_continuum_eigenvalue_bounds=True,execution_authorized=False))
    need(len(result)<=MAX_RECEIPT,'certificate budget')
    return result

def certify(problem,cuts):
    raw=assemble_supported(problem,cuts);a=json.loads(raw)
    M,S=([[Q(x) for x in row] for row in a[k]] for k in ('mass','stiffness'))
    m,s=r.numeric(raw);z=eigh(s,m,eigvals_only=True,subset_by_index=(0,2))
    need(np.isfinite(z).all(),'finite trial spectrum')
    if problem.null_mode:z[0]=0.
    approx=[Q(float(v)) for v in z]
    up=_trial(z,lambda t:_dense_inertia(M,S,t),True)
    trials=[]
    for full in (False,True):
        comp,_,_,_=_comparison(problem,min(64,4*(len(cuts)+1)),pi_interval()[0],full)
        md,mo,kd,ko=comp
        v=eigh(_mat(kd,ko),_mat(md,mo),eigvals_only=True,subset_by_index=(0,2))
        trials.append(_trial(v,lambda t:_tri_inertia(*comp,t),False))
    return raw,_proof(problem,cuts,raw,approx,up,*trials)

def replay(problem,cuts,certificate):
    """Verification uses no floating-point eigensolver or trusted numerical hints."""
    need(type(certificate) is bytes and 0<len(certificate)<=MAX_RECEIPT,'certificate size')
    d=json.loads(certificate);rows=d['rows']
    need(type(rows) is list and len(rows)==3,'certificate rows')
    fields=('approximation','ritz_upper_trial','diffusion_lower_trial','reaction_lower_trial')
    args=[[Q(row[key]) for row in rows] for key in fields]
    raw=assemble_supported(problem,cuts)
    need(_proof(problem,cuts,raw,*args)==certificate,'certificate replay mismatch')
    return True
