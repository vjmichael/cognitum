"""CH27 research: rigorous likelihood--Fisher-information coupled convex-dual bound.

For ANY exactly-specified SPD Q, logdet(F) <= tr(Q F)-logdet(Q)-d.
With F=sum_i n_i*p_i*(1-p_i)*x_i*x_i^T this yields a separable
univariate *coupled* log-likelihood plus Fisher-weight envelope.
Each scalar surrogate is strictly concave in p and bounded by its exact
supporting line at a heuristic (untrusted) p0; all bound arithmetic uses
outward-rounded MPFR. The selected Q and supporting points need NOT be
numerically optimal for validity; they only affect tightness.
"""
from __future__ import annotations
from fractions import Fraction
from pathlib import Path
import sys, math
ROOT=Path(__file__).resolve().parent.parent
for base in (ROOT/'CH_C14_24',ROOT/'CH_C14_26',ROOT/'ch_c14_24',ROOT/'ch_c14_26'):
    if base.is_dir() and str(base) not in sys.path: sys.path.insert(0,str(base))
from mpfr_interval import Interval as I, MP, UP
from verified_bnb import determinant, interval_box, midpoint_bounds
from improved_bounds import ImprovedObjective

ZERO=I('0'); ONE=I('1'); HALF=I('0.5')

def is_spd_exact(Q):
    """Exact Sylvester check: input decimal matrix has no float dependencies."""
    d=len(Q)
    if d<1 or d>3 or any(len(r)!=d for r in Q):return False
    a=[[Fraction(str(v)) for v in row] for row in Q]
    if any(a[i][j]!=a[j][i] for i in range(d) for j in range(d)):return False
    if a[0][0]<=0:return False
    if d>=2 and a[0][0]*a[1][1]-a[0][1]*a[1][0]<=0:return False
    if d==3:
        det=(a[0][0]*(a[1][1]*a[2][2]-a[1][2]*a[2][1])
            -a[0][1]*(a[1][0]*a[2][2]-a[1][2]*a[2][0])
            +a[0][2]*(a[1][0]*a[2][1]-a[1][1]*a[2][0]))
        if det<=0:return False
    return True

def heuristic_Q(model, points, precision_decimals=12):
    """Heuristic-only Q generation; *every* Q must pass exact SPD check."""
    import numpy as np
    X=np.array([[float(v) for v in row['x']] for row in model.data['rows']],dtype=float)
    n=np.array([row['n'] for row in model.data['rows']],dtype=float)
    out=[]
    for point in points:
        try:
            eta=X@np.array([float(q) for q in point],dtype=float)
            p=np.exp(-np.logaddexp(0,-eta))
            w=n*p*(1-p)
            fisher=X.T@(w[:,None]*X)
            inv=np.linalg.inv(fisher)
            inv=(inv+inv.T)/2
            q=[[format(float(inv[i,j]),f'.{precision_decimals}g') for j in range(model.d)] for i in range(model.d)]
            if is_spd_exact(q) and q not in out:out.append(q)
        except (OverflowError,ZeroDivisionError,ValueError,np.linalg.LinAlgError):continue
    return out

def _max_upper(a,b):return a if a.cmp(b)>=0 else b

def _min_upper(a,b):return a if a.cmp(b)<=0 else b

def _heuristic_tangent_p(p_interval, k_float, n, s):
    """Float used ONLY to select a supporting-point location, NEVER proof bounds."""
    # Solve monotonic scalar score on heuristic floating-point bracket.
    low=max(1.e-12,min(1.-1.e-12,p_interval.lo.as_float(UP)))
    high=max(low,min(1.-1.e-12,p_interval.hi.as_float(UP)))
    def score(z):return s/z-(n-s)/(1-z)+k_float*(1-2*z)
    if score(low)<=0:return format(low,'.17g')
    if score(high)>=0:return format(high,'.17g')
    a,b=low,high
    for _ in range(38):
        m=(a+b)/2
        if score(m)>0:a=m
        else:b=m
    return format((a+b)/2,'.17g')

class CoupledObjective(ImprovedObjective):
    def __init__(self,data, Qs):
        self.data=data
        super().__init__(data)
        if not Qs:raise ValueError('At least one SPD dual witness required')
        self.duals=[]
        for qstr in Qs:
            if not is_spd_exact(qstr):raise ValueError('Dual matrix is not exactly SPD')
            q=[[I(v) for v in row] for row in qstr]
            detq=determinant(q)
            if detq.lo.cmp(MP('0'))<=0:raise ArithmeticError('Unable to certify positive Q determinant')
            const=-(HALF*detq.log())-I(self.d)*HALF
            kappa=[]
            for xx,n,s in self.groups_const:
                v=sum((xx[j]*q[j][k]*xx[k] for j in range(self.d) for k in range(self.d)),I('0'))
                if v.hi.cmp(MP('0'))<0:raise ArithmeticError('Positive definite Q gave negative leverage upper')
                ka=(I(n)*HALF*v).hi
                kappa.append(I.from_ends(ka,ka))
            self.duals.append((const,kappa))
        self.last_method='coupled_logdet_dual'

    def coupled_upper(self,box):
        # Choose the minimum of independent certified upper bounds from SPD Qs.
        best=None
        X=[I(a,b) for a,b in box]
        predictors=[sum((xx[j]*X[j] for j in range(self.d)),I('0')) for xx,n,s in self.groups_const]
        probs=[ONE/(ONE+(-eta).exp()) for eta in predictors]
        for const,kappas in self.duals:
            total=const
            for (xx,n,s),pbox,k in zip(self.groups_const,probs,kappas):
                p0=I(_heuristic_tangent_p(pbox,k.hi.as_float(UP),n,s))
                if p0.lo.cmp(MP('0'))<=0 or p0.hi.cmp(MP('1'))>=0:raise ArithmeticError('Unsafe tangent location')
                # g(p) = s*log p + (n-s)*log(1-p) + k*p(1-p), concave
                # on (0,1) because g''=-s/p²-(n-s)/(1-p)²-2k <= 0.
                val=I(s)*p0.log()+I(n-s)*(ONE-p0).log()+k*p0*(ONE-p0)
                slope=I(s)/p0-I(n-s)/(ONE-p0)+k*(ONE-I(2)*p0)
                cap=val+slope*(pbox-p0)  # supporting-line majorant at p0
                total=total+I.from_ends(cap.hi,cap.hi)
            if best is None or total.hi.cmp(best)<0:best=total.hi
        return best

    def bound(self,box,mode='hybrid'):
        if mode=='coupled_only':
            point=self.objective([I(z) for z in midpoint_bounds(box)[0]])[0]
            cap=self.coupled_upper(box)
            if cap.cmp(point.lo)<0:raise ArithmeticError('Dual bound smaller than feasible objective')
            return I.from_ends(point.lo,cap),'coupled_logdet_dual'
        direct,method=self.objective(interval_box(box))
        cap=self.coupled_upper(box)
        if cap.cmp(direct.hi)<0:
            if cap.cmp(direct.lo)<0:raise ArithmeticError('Inconsistent dual and direct bounds')
            return I.from_ends(direct.lo,cap),'coupled_logdet_dual'
        return direct,method
