"""Independent interval Krawczyk validation for an interior score root.

Uses CH40-B Decimal analytic Firth score/Hessian; no legacy MPFR/Jet/Newton.
The proof rule is only applicable strictly inside the original root box. A
boundary global maximum need not have vanishing score and is NEVER excluded.
"""
from __future__ import annotations
from fractions import Fraction as F
from decimal import Decimal as D,localcontext
from exact_decimal40 import IV, CONTEXT
from independent_bounds40b import objective_derivatives


def _decimal(x):
    f=F(x)
    with localcontext(CONTEXT) as ctx:
        z=D(f.numerator)/D(f.denominator)
        if F(z)!=f:raise ValueError('Exact midpoint not representable')
        return str(z)


def interior(box,root):
    if len(box)!=len(root):raise ValueError('Mismatched root dimensions')
    return all(F(str(a))>F(str(x)) and F(str(b))<F(str(y))
               and F(str(a))<F(str(b)) for (a,b),(x,y) in zip(box,root))


def krawczyk(model,box,root,C):
    """Recompute K=m-Cg(m)+(Id-C H(B))(B-m) in a second implementation.
    Only sufficient root inclusion/disjointness is claimed, not uniqueness.
    """
    if not interior(box,root):raise ValueError('Not interior to frozen root')
    d=model.d
    if len(C)!=d or any(len(row)!=d for row in C):raise ValueError('Invalid preconditioner')
    pre=[[IV(str(v)) for v in row] for row in C]
    mids=[_decimal((F(str(a))+F(str(b)))/2) for a,b in box]
    gmid,_=objective_derivatives(model,[(x,x) for x in mids])
    gbox,hbox=objective_derivatives(model,box)
    for j,v in enumerate(gbox):
        if v.lo>0 or v.hi<0:
            return {'status':'NO_STATIONARY','reason':'GRADIENT_SIGN','coordinate':j,'proof_scope':'strict_root_interior'}
    centers=[IV(x) for x in mids]
    deltas=[IV(a,b)-centers[j] for j,(a,b) in enumerate(box)]
    enclosure=[]
    for i in range(d):
        z=centers[i]-sum((pre[i][k]*gmid[k] for k in range(d)),IV(0))
        for j in range(d):
            h=sum((pre[i][k]*hbox[k][j] for k in range(d)),IV(0))
            z=z+(IV(int(i==j))-h)*deltas[j]
        enclosure.append(z)
    isects=[]
    for z,(a,b) in zip(enclosure,box):
        lo=max(z.lo,D(str(a)));hi=min(z.hi,D(str(b)))
        if lo>hi:
            return {'status':'NO_STATIONARY','reason':'KRAWCZYK_DISJOINT','proof_scope':'strict_root_interior',
                    'krawczyk_enclosure':[[str(q.lo),str(q.hi)] for q in enclosure]}
        isects.append([str(lo),str(hi)])
    shrink=any(D(a)<D(x) or D(b)>D(y) for (a,b),(x,y) in zip(box,isects))
    return {'status':'CONTRACTED' if shrink else 'NO_GAIN','box':isects,
            'krawczyk_enclosure':[[str(q.lo),str(q.hi)] for q in enclosure],
            'proof_scope':'strict_root_interior'}


def check_claim(model,box,root,C,claim):
    """A claimed contraction MUST contain independent K(B) intersection."""
    got=krawczyk(model,box,root,C)
    if claim['status']=='NO_STATIONARY':
        if got['status']!='NO_STATIONARY':raise ValueError('Forged exclusion')
        if claim.get('reason')!=got.get('reason'):raise ValueError('Wrong exclusion reason')
        return got
    if claim['status']!='CONTRACTED':raise ValueError('Unknown positive contraction claim')
    if got['status']=='NO_STATIONARY':return got
    saved=claim['box']
    if len(saved)!=model.d or any(len(r)!=2 for r in saved):raise ValueError('Forged contraction dimension')
    for (a,b),(u,v),(x,y) in zip(box,saved,got['box']):
        a,b,u,v,x,y=map(lambda s:F(str(s)),(a,b,u,v,x,y))
        if not(a<=u<=x<=y<=v<=b):raise ValueError('Claim excludes possible stationary root')
    return got
