"""C14 G25I research ONLY: binary-outcome causal partial-identification analysis.

Gamma is a user-supplied, *unverified* uniform risk-difference bound on
E[Y(t)|T=t,W=w] - E[Y(t)|T!=t,W=w] for t in {0,1} and observed W.

Finite-sample bands use 7 Bonferroni-adjusted Clopper-Pearson binomial
intervals (P(W=0), P(T=1|W=w), P(Y=1|T=t,W=w)).
These intervals cover the sensitivity IDENTIFIED SET given Gamma; they do NOT
validate Gamma, consistency, sample representativeness, or exchangeability.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import math
import numpy as np
from scipy.special import expit
from scipy.stats import beta

FAMILIES=("measured", "randomized_hidden_prognostic", "latent_confounder", "misclassified_confounder", "weak_positive_overlap", "structural_zero_overlap")
SIZES=(900,1800)
GAMMAS=(0.0, 0.10, 0.25, 0.50, 1.0)
ALPHA=0.05

@dataclass(frozen=True)
class Population:
    family:str
    table:np.ndarray # observed joint P(W,T,Y) shape (2,2,2)
    truth:float
    min_propensity:float
    # research-only; true selection contrast in each observed stratum and arm
    gamma_needed:float|None
    true_contrasts:tuple

@dataclass(frozen=True)
class Dataset:
    family:str
    n:int
    seed:int
    w:np.ndarray
    t:np.ndarray
    y:np.ndarray
    sha:str


def _terms(family):
    if family not in FAMILIES:raise ValueError("unknown family")
    p_x=np.array([.52,.48]); p_u=np.array([[.73,.27],[.42,.58]])
    if family=="misclassified_confounder": p_u[:]=(.5,.5)
    trans=[]
    for x in range(2):
        for u in range(2):
            if family=="structural_zero_overlap":e=float(x)
            elif family=="weak_positive_overlap": e=.018 if x==0 else .982
            else:
                be=(-.42+.78*x)
                if family=="latent_confounder": be+=1.60*(u-.5)
                if family=="misclassified_confounder":be=-1.5+3.0*x
                e=float(expit(be))
            b0=-1.42+1.05*x
            b1=-.90+1.17*x
            if family in ("randomized_hidden_prognostic","latent_confounder"):
                b0+=1.35*(u-.5);b1+=1.55*(u-.5)
            if family=="misclassified_confounder":
                b0=-2.2+2.4*x;b1=-1.40+2.5*x
            q0=float(expit(b0));q1=float(expit(b1))
            pw=(.75 if x==0 else .25) if family=="misclassified_confounder" else (1. if x==0 else 0.)
            trans.append((x,u,p_x[x]*p_u[x,u],e,q0,q1,pw))
    return trans


def population(family):
    table=np.zeros((2,2,2),dtype=float)
    cf=np.zeros((2,2,2),dtype=float) # E[Y(t) I(W=w,T=assigned)] numerator
    truth=0.;minimum=1.
    for x,u,p,e,q0,q1,pw0 in _terms(family):
        truth+=p*(q1-q0)
        minimum=min(minimum,e,1-e)
        for w,pw in ((0,pw0),(1,1-pw0)):
            for t,pt in ((0,1-e),(1,e)):
                mass=p*pw*pt
                table[w,t,1]+=mass*(q1 if t else q0)
                table[w,t,0]+=mass*(1-(q1 if t else q0))
                cf[w,t,0]+=mass*q0;cf[w,t,1]+=mass*q1
    contrast=[]
    for w in range(2):
        for t in range(2):
            denom=np.sum(table[w,t,:]);denom_opp=np.sum(table[w,1-t,:])
            if denom==0 or denom_opp==0:
                contrast.append(None);continue
            own=cf[w,t,t]/denom
            opp=cf[w,1-t,t]/denom_opp
            contrast.append(float(own-opp))
    needed=max(map(abs,(c for c in contrast if c is not None)),default=0.) if all(c is not None for c in contrast) else None
    if abs(table.sum()-1)>1e-12: raise AssertionError('not a probability table')
    return Population(family,table,float(truth),float(minimum),needed,tuple(contrast))


def generate(family,n,seed):
    if family not in FAMILIES or n not in SIZES:raise ValueError('unknown settings')
    rng=np.random.default_rng(seed)
    terms=_terms(family)
    probs=np.array([q[2] for q in terms]);index=rng.choice(len(terms),n,p=probs)
    r=np.asarray(terms,dtype=float)
    w=(rng.random(n)>=r[index,6]).astype(np.uint8)
    t=(rng.random(n)<r[index,3]).astype(np.uint8)
    q=np.where(t==1,r[index,5],r[index,4])
    y=(rng.random(n)<q).astype(np.uint8)
    h=hashlib.sha256()
    for arr in (w,t,y):h.update(arr.tobytes())
    h.update(f'G25I:{family}:{n}:{seed}'.encode())
    return Dataset(family,n,seed,w,t,y,h.hexdigest())


def counts(case):
    z=np.zeros((2,2,2),dtype=int)
    np.add.at(z,(case.w,case.t,case.y),1)
    return z


def exact_binomial(k,n,alpha=ALPHA/7):
    if n<=0:return (0.,1.)
    if not (0<=k<=n):raise ValueError('invalid binomial counts')
    lo=0. if k==0 else float(beta.ppf(alpha/2,k,n-k+1))
    hi=1. if k==n else float(beta.ppf(1-alpha/2,k+1,n-k))
    return lo,hi


def _cell(e,m0,m1,gamma):
    def lim(e):
        lo=e*m1[0]+(1-e)*max(0.,m1[0]-gamma)-(1-e)*m0[1]-e*min(1.,m0[1]+gamma)
        hi=e*m1[1]+(1-e)*min(1.,m1[1]+gamma)-(1-e)*m0[0]-e*max(0.,m0[0]-gamma)
        return lo,hi
    lo0,hi0=lim(e[0]);lo1,hi1=lim(e[1]);return min(lo0,lo1),max(hi0,hi1)


def _assumption_bounds(e,m0,m1,gamma):
    e=float(e);m0=float(m0);m1=float(m1)
    return _cell((e,e),(m0,m0),(m1,m1),gamma)


def from_counts(z,gamma,alpha=ALPHA):
    """Two distinct outputs: plug-in identified-set estimate and honest outer band.

    'honest' means simultaneous binomial uncertainty conditional on Gamma and
    i.i.d. sampling, NOT that Gamma or the causal model have been verified.
    """
    z=np.asarray(z,dtype=int)
    if z.shape!=(2,2,2) or np.any(z<0):raise ValueError('invalid table')
    n=int(z.sum())
    if n==0:raise ValueError('no observations')
    if not (0<=gamma<=1):raise ValueError('gamma out of range')
    nr=z.sum(axis=(1,2)); p0=float(nr[0]/n)
    arm=z.sum(axis=2)
    if np.any(arm==0):
        return {'status':'observed_arm_missing','identified':None,'outer95':[-1.,1.],
                'reason':'cannot support a conditional sensitivity calculation in an empty W/T arm'}
    lp=exact_binomial(int(nr[0]),n,alpha/7)
    lo_cell=[];hi_cell=[];pl=[];ph=[]
    for w in range(2):
        e=arm[w,1]/nr[w]
        m0=z[w,0,1]/arm[w,0];m1=z[w,1,1]/arm[w,1]
        yl0=exact_binomial(int(z[w,0,1]),int(arm[w,0]),alpha/7)
        yl1=exact_binomial(int(z[w,1,1]),int(arm[w,1]),alpha/7)
        el=exact_binomial(int(arm[w,1]),int(nr[w]),alpha/7)
        a,b=_assumption_bounds(e,m0,m1,gamma)
        c,d=_cell(el,yl0,yl1,gamma)
        lo_cell.append(c);hi_cell.append(d);pl.append(a);ph.append(b)
    identified=[p0*pl[0]+(1-p0)*pl[1],p0*ph[0]+(1-p0)*ph[1]]
    bound_lo=[p*lo_cell[0]+(1-p)*lo_cell[1] for p in lp]
    bound_hi=[p*hi_cell[0]+(1-p)*hi_cell[1] for p in lp]
    outer=[max(-1.,min(bound_lo)),min(1.,max(bound_hi))]
    if identified[0]>identified[1]+1e-12 or outer[0]>identified[0]+1e-9 or outer[1]<identified[1]-1e-9:
        raise AssertionError('outer interval must contain plug-in identified set')
    return {'status':'computed_conditional_on_gamma','identified':[float(v) for v in identified],
            'outer95':[float(v) for v in outer],
            'reason':'gamma is not validated from observational data; conditional interval only'}


def manski_from_counts(z):
    z=np.asarray(z,dtype=int);n=z.sum()
    if n<=0:raise ValueError('empty data')
    y1_t1=z[:,1,1].sum()/n; y1_t0=z[:,0,1].sum()/n
    pt1=z[:,1,:].sum()/n;pt0=1-pt1
    return [float(y1_t1-y1_t0-pt1),float(y1_t1-y1_t0+pt0)]


def policy(observed,z=None,assumptions=None):
    """Fitted numerical intervals NEVER constitute an automatic causal grant."""
    if observed is None:raise ValueError('missing observed evidence')
    if z is not None and np.any(np.asarray(z).sum(axis=2)==0):
        return {'causal_admitted':False,'status':'observed_support_failure'}
    if z is not None and np.min(np.asarray(z).sum(axis=2))<25:
        return {'causal_admitted':False,'status':'limited_empirical_overlap_warning'}
    a=assumptions or {}
    if not (a.get('consistency_supported') and a.get('exchangeability_justification') and a.get('measurement_validity_supported')):
        return {'causal_admitted':False,'status':'causal_assumptions_not_established'}
    return {'causal_admitted':False,'status':'conditional_analyst_assumptions_only_not_automatically_verified'}
