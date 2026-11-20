"""Bounded exact Galerkin forms on certified represented KAN fields; research only."""
from fractions import Fraction as Q
from itertools import combinations_with_replacement
import json
import numpy as np
from scipy.linalg import eigh
from cognitum.research import kan_function_metrics as o

PROFILE='cognitum.kan.weak_form.v1'
MAX_BASIS=4
MAX_WORK=600000
MAX_RECEIPT=65536
MAX_CONDITION=1e8
need=o.need

def _ldl(matrix,strict):
    """Exact symmetric positive (semi)definite witness, no pivot approximation."""
    n=len(matrix)
    l=[[Q(int(i==j)) for j in range(n)] for i in range(n)]
    d=[]
    for j in range(n):
        p=o._bounded(matrix[j][j]-sum((l[j][k]**2*d[k] for k in range(j)),Q(0)))
        need(p>0 if strict else p>=0,'mass singular or indefinite' if strict else 'stiffness indefinite')
        d.append(p)
        for i in range(j+1,n):
            r=o._bounded(matrix[i][j]-sum((l[i][k]*l[j][k]*d[k] for k in range(j)),Q(0)))
            need(p!=0 or r==0,'zero pivot with nonzero coupling')
            l[i][j]=o._bounded(r/p) if p else Q(0)
    return tuple(d)

def assemble(checkpoints):
    """Unit-box L2 mass and spatial-gradient stiffness, time never a derivative axis."""
    need(type(checkpoints) is tuple and 1<=len(checkpoints)<=MAX_BASIS,'basis count')
    need(all(type(x) is bytes and 0<len(x)<=o.f.MAX_FRAME for x in checkpoints),'checkpoint budget')
    fields=[o._field(x) for x in checkpoints]
    mod=fields[0][0]
    need(all(f[0] is mod for f in fields),'incompatible profiles')
    axes=next(names for m,names in o.f.PROFILES.values() if m is mod)
    spatial=tuple(i for i,a in enumerate(axes) if a!='t')
    components=(-1,*spatial)
    n=len(fields)
    pairs=tuple(combinations_with_replacement(range(n),2))
    work=len(components)*sum(len(fields[i][2])*len(fields[j][2]) for i,j in pairs)
    need(work<=MAX_WORK,'aggregate weak form work budget')
    mass=[[Q(0)]*n for _ in range(n)]
    stiffness=[[Q(0)]*n for _ in range(n)]
    cache={}
    for i,j in pairs:
        _,ac,at=fields[i];_,bc,bt=fields[j]
        for component in components:
            grams=[]
            for axis,(a,b) in enumerate(zip(ac,bc)):
                order=int(axis==component)
                key=(a,b,order)
                if key not in cache:cache[key]=o._axis_gram(a,b,order)
                grams.append(cache[key])
            x=o._contract(at,bt,grams)
            target=mass if component==-1 else stiffness
            target[i][j]=target[j][i]=o._bounded(target[i][j]+x)
    md=_ldl(mass,True);sd=_ldl(stiffness,False)
    raw=o.f.canonical(dict(profile=PROFILE,axes=axes,stiffness_axes=tuple(axes[i] for i in spatial),
        checkpoint_sha256=[o.f.digest(x).hex() for x in checkpoints],mass=mass,stiffness=stiffness,
        exact_mass_ldl_pivots=md,exact_stiffness_ldl_pivots=sd,work_units=work,
        assurance='exact-represented-subspace-unit-box',physical_pde_spectrum=False,execution_authorized=False))
    need(len(raw)<=MAX_RECEIPT,'weak form receipt budget')
    return raw

def replay(checkpoints,receipt):
    need(type(receipt) is bytes and 0<len(receipt)<=MAX_RECEIPT,'weak form receipt size')
    need(assemble(checkpoints)==receipt,'weak form replay mismatch')
    return True

def matrices(checkpoints):
    raw=assemble(checkpoints);r=json.loads(raw)
    return raw,*(np.asarray([[float(Q(x)) for x in row] for row in r[key]]) for key in ('mass','stiffness'))

def spectrum(checkpoints):
    """Float64 Ritz spectrum of the supplied finite subspace, not a continuum eigensolver."""
    raw,m,s=matrices(checkpoints)
    need(np.isfinite(m).all() and np.isfinite(s).all(),'nonfinite matrix')
    cond=float(np.linalg.cond(m))
    need(np.isfinite(cond) and cond<=MAX_CONDITION,'ill-conditioned mass matrix')
    try:values,vectors=eigh(s,m,check_finite=True)
    except (ValueError,np.linalg.LinAlgError) as e:raise ValueError('numerical generalized eigenproblem') from e
    scale=max(1.,float(np.max(np.abs(values))))
    need(np.isfinite(values).all() and np.isfinite(vectors).all() and values[0]>=-1e-10*scale,'invalid Ritz spectrum')
    residuals=[]
    for value,v in zip(values,vectors.T):
        a=s@v;b=value*(m@v)
        residuals.append(float(np.linalg.norm(a-b)/max(1e-300,np.linalg.norm(a)+np.linalg.norm(b),
            np.linalg.norm(s)*np.linalg.norm(v)*np.finfo(float).eps)))
    orth=float(np.linalg.norm(vectors.T@m@vectors-np.eye(len(values)),ord=np.inf))
    # Near-null modes can have small absolute residual but unstable relative residual.
    absolute=float(np.linalg.norm(s@vectors-(m@vectors)*values,ord=np.inf)/
        max(1e-300,np.linalg.norm(s,ord=np.inf)*np.linalg.norm(vectors,ord=np.inf)
        +np.linalg.norm(m,ord=np.inf)*np.linalg.norm(vectors*values,ord=np.inf)))
    need(absolute<=1e-9 and orth<=1e-8,'Ritz residual or mass orthogonality')
    return raw,dict(values=values.tolist(),vectors_columns=vectors.tolist(),mass_condition=cond,
        scaled_matrix_residual=absolute,mass_orthogonality=orth,
        per_mode_relative_residual=residuals,solver='scipy.linalg.eigh',physical_pde_spectrum=False)
