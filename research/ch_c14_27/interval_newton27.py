"""CH27 fail-closed root-exclusion/interval-Newton contractor.

Only a node strictly interior to the ORIGINAL root domain is eligible for
stationary-root contraction. A global maximizer in that interior is stationary;
original-domain boundary faces must remain covered. No claim of global
concavity or isolated/unique roots is made.
"""
from __future__ import annotations
from decimal import Decimal
from pathlib import Path
from typing import Any
import sys, math
ROOT=Path(__file__).resolve().parent.parent
for base in (ROOT/'CH_C14_24',ROOT/'CH_C14_26',ROOT/'ch_c14_24',ROOT/'ch_c14_26'):
    if base.is_dir() and str(base) not in sys.path:sys.path.insert(0,str(base))
from mpfr_interval import Interval as I, MP, DOWN, UP
from verified_bnb import midpoint_bounds,interval_box

def interior(box,root):
    return all(Decimal(a)>Decimal(x) and Decimal(b)<Decimal(y)
               for (a,b),(x,y) in zip(box,root))

def _float_to_exact_decimal(x):
    if not math.isfinite(x):raise ArithmeticError('Non-finite outward float endpoint')
    s=str(Decimal.from_float(x))
    if len(s)>150:raise ArithmeticError('Cannot serialise extremely small/large contraction bound')
    return s

def _matrix_C(mid_hessian):
    import numpy as np
    d=len(mid_hessian)
    H=np.array([[(h.lo.as_float(DOWN)+h.hi.as_float(UP))/2 for h in row] for row in mid_hessian])
    if not np.isfinite(H).all():return [[('1' if i==j else '0') for j in range(d)] for i in range(d)]
    try:
        C=np.linalg.inv(H)
        if not np.isfinite(C).all() or np.max(np.abs(C))>1e6:raise ValueError('Ill-conditioned')
        return [[format(float(C[i,j]),'.12g') for j in range(d)] for i in range(d)]
    except (np.linalg.LinAlgError,ValueError):
        return [['-0.1' if i==j else '0' for j in range(d)] for i in range(d)]

def contract(model,box,root,*,C=None):
    """Compute validated Krawczyk enclosure of every score root in a box.

    Result is proof-sound only for global-max pruning when original box is
    strictly within root. For all roots x in B, x in m-C*g(m)+(I-C*H(B))(B-m).
    Even if C is singular this inclusion remains true; invertibility is NOT
    required or claimed. C is stored and replayed exactly as decimal strings.
    """
    if not interior(box,root):return {'status':'NOT_INTERIOR'}
    d=len(box); mid,_=midpoint_bounds(box)
    gbox,hbox=model.analytic_derivatives(interval_box(box))
    # A gradient interval omitting zero excludes *all* stationary points.
    for j,g in enumerate(gbox):
        if g.lo.cmp(MP('0'))>0 or g.hi.cmp(MP('0'))<0:
            return {'status':'NO_STATIONARY','reason':'GRADIENT_SIGN','coordinate':j}
    gmid,hmid=model.analytic_derivatives([I(m) for m in mid])
    if C is None:C=_matrix_C(hmid)
    if len(C)!=d or any(len(r)!=d for r in C):raise ValueError('Bad C shape')
    M=[[I(v) for v in row] for row in C]
    center=[I(x) for x in mid]
    offset=[I(a,b)-center[i] for i,(a,b) in enumerate(box)]
    new=[]
    for i in range(d):
        cg=sum((M[i][j]*gmid[j] for j in range(d)),I('0'))
        acc=center[i]-cg
        for j in range(d):
            mat=I(1 if i==j else 0)-sum((M[i][k]*hbox[k][j] for k in range(d)),I('0'))
            acc=acc+mat*offset[j]
        new.append(acc)
    # Strict disjoint Krawczyk enclosure: stationary points impossible.
    for i,(x,y) in enumerate(box):
        if new[i].hi.cmp(MP(x,DOWN))<0 or new[i].lo.cmp(MP(y,UP))>0:
            return {'status':'NO_STATIONARY','reason':'KRAWCZYK_DISJOINT','C':C}
    contracted=[]
    for i,(a,b) in enumerate(box):
        l=I(a).lo if I(a).lo.cmp(new[i].lo)>=0 else new[i].lo
        h=I(b).hi if I(b).hi.cmp(new[i].hi)<=0 else new[i].hi
        lo=Decimal(_float_to_exact_decimal(l.as_float(DOWN)))
        hi=Decimal(_float_to_exact_decimal(h.as_float(UP)))
        # A round-trip outward binary64 conversion cannot shrink a valid K.
        lo=max(Decimal(a),lo);hi=min(Decimal(b),hi)
        if lo>hi:raise ArithmeticError('Unsafe interval contraction conversion')
        contracted.append([str(lo),str(hi)])
    orig_vol=1.; new_vol=1.
    for (a,b),(u,v) in zip(box,contracted):
        orig_vol*=float(Decimal(b)-Decimal(a))
        new_vol*=float(Decimal(v)-Decimal(u))
    ratio=new_vol/orig_vol if orig_vol>0 else 1.
    return {'status':'CONTRACTED' if ratio<.995 else 'NO_GAIN',
            'box':contracted,'C':C,'volume_ratio_display':ratio}

def replay_check(model,original,root,receipt):
    """Higher-precision proof replay; refuses incorrect exclusion or narrowing."""
    if not interior(original,root):raise ValueError('Contractor applied to root boundary')
    status=receipt['status']
    if status=='NO_STATIONARY':
        if receipt.get('reason')=='GRADIENT_SIGN':
            g,_=model.analytic_derivatives(interval_box(original))
            j=receipt['coordinate']
            if not(0<=j<len(g)):raise ValueError('Unknown gradient coordinate')
            if not(g[j].lo.cmp(MP('0'))>0 or g[j].hi.cmp(MP('0'))<0):raise ValueError('Gradient exclusion invalid')
            return True
        if receipt.get('reason')!='KRAWCZYK_DISJOINT':raise ValueError('Unknown exclusion reason')
        r=contract(model,original,root,C=receipt['C'])
        if r['status']!='NO_STATIONARY':raise ValueError('Invalid Krawczyk exclusion')
        return True
    if status!='CONTRACTED':raise ValueError('Invalid contraction status')
    r=contract(model,original,root,C=receipt['C'])
    if r['status']=='NO_STATIONARY':return True  # absence of roots is stronger
    if r['status'] not in ('CONTRACTED','NO_GAIN'):raise ValueError('Unexpected replay status')
    if len(r['box'])!=len(receipt['box']):raise ValueError('Invalid contraction dimension')
    for saved,actual,original_dim in zip(receipt['box'],r['box'],original):
        if not(Decimal(original_dim[0])<=Decimal(saved[0])<=Decimal(actual[0]) and
                Decimal(actual[1])<=Decimal(saved[1])<=Decimal(original_dim[1])):
            raise ValueError('Contraction does not contain all stationary roots')
    return True
