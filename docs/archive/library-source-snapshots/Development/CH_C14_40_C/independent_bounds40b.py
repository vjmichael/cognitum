"""CH40-B independent coupled likelihood–Fisher and analytic Taylor enclosures.

Built only on CH40-A rational/Decimal interval primitives; deliberately no import of
Cognitum's MPFR, Jet, solver, or coupled/newton implementations. Every Q is
checked for SPD over exact fractions. Scope is finite boxes and positive Fisher.
"""
from __future__ import annotations
from fractions import Fraction as F
from decimal import Decimal as D, localcontext
from exact_decimal40 import IV, CONTEXT, ROUND_CEILING, op
from independent_checker40 import MathematicalModel, det, validate_duals


def interval_abs_upper(x):
    return max(abs(x.lo),abs(x.hi))


def dual_coupled_upper(model:MathematicalModel,box,duals):
    """Upper bound using logdet F <= tr(QF)-logdet Q-d for any SPD Q.

    For each observation, g(p)=s log p+(n-s) log(1-p)+k p(1-p),
    k=n*x^T Q x/2 > 0. g''(p) <= 0 for p in (0,1): tangent
    at ANY rational p0 is a global majorant. No fitted optimizer trusted.
    """
    validate_duals({'model':model.model,'dual_matrices':duals})
    predictors=model.eta(box)
    probabilities=[model.probability(z) for z in predictors]
    best=None; names=[]
    for q in duals:
        exact=[[F(str(z)) for z in row] for row in q]
        detQ=det(exact)
        if detQ<=0:raise ArithmeticError('Q not SPD')
        const=-(IV.rational(detQ).ln()*IV('0.5'))-IV(str(model.d))/IV(2)
        bound=const
        for (n,s),xs,pp in zip(model.counts,model.x,probabilities):
            leverage=sum((xs[j]*exact[j][k]*xs[k] for j in range(model.d) for k in range(model.d)),F(0))
            if leverage<=0 and any(x!=0 for x in xs):raise ArithmeticError('Nonpositive leverage')
            k=IV.rational(F(n,2)*leverage)
            # Float bisection selects tangent location ONLY. Outward arithmetic
            # verifies supporting majorant for ANY strictly interior p0.
            k_guess=float(F(n,2)*leverage)
            lo=max(1e-13,min(1-1e-13,float(pp.lo)))
            hi=max(lo,min(1-1e-13,float(pp.hi)))
            def score(v):return s/v-(n-s)/(1-v)+k_guess*(1-2*v)
            if score(lo)<=0:chosen=lo
            elif score(hi)>=0:chosen=hi
            else:
                a,b=lo,hi
                for _ in range(65):
                    qmid=(a+b)/2
                    if score(qmid)>0:a=qmid
                    else:b=qmid
                chosen=(a+b)/2
            p=IV(format(chosen,'.17g'))
            one=IV(1)
            val=IV(s)*p.ln()+IV(n-s)*(one-p).ln()+k*p*(one-p)
            slope=IV(s)/p-IV(n-s)/(one-p)+k*(one-IV(2)*p)
            tangent=val+slope*(pp-p)
            bound=bound+IV.raw(tangent.lo,tangent.hi)
        if best is None or bound.hi<best:best=bound.hi
        names.append(str(bound.hi))
    return {'upper':best,'by_dual':names}


def _matrix_det_interval(a):
    d=len(a)
    if d==1:return a[0][0]
    if d==2:return a[0][0]*a[1][1]-a[0][1]*a[1][0]
    if d==3:
        return a[0][0]*(a[1][1]*a[2][2]-a[1][2]*a[2][1]) - a[0][1]*(a[1][0]*a[2][2]-a[1][2]*a[2][0]) + a[0][2]*(a[1][0]*a[2][1]-a[1][1]*a[2][0])
    raise ValueError('Dimension')


def _inverse_from_verified_positive_det(a,det_interval):
    """Adjugate formula with a strictly positive *independent* determinant enclosure."""
    d=len(a)
    if det_interval.lo<=0:raise ArithmeticError('Fisher invertibility unproven')
    invdet=IV(1)/det_interval
    if d==1:return [[invdet]]
    out=[]
    for i in range(d):
        row=[]
        for j in range(d):
            # adj(A)_ij is cofactor_ji
            minor=[[a[r][c] for c in range(d) if c!=i] for r in range(d) if r!=j]
            sign=1 if (i+j)%2==0 else -1
            row.append(_matrix_det_interval(minor)*invdet*sign)
        out.append(row)
    return out


def objective_derivatives(model:MathematicalModel,box):
    """Outward score and Hessian for Firth logistic likelihood, including 1/2 logdet I.

    I = sum n*w*x*x^T; I_a = sum n*w'*x_a*x*x^T;
    I_ab=sum n*w''*x_a*x_b*x*x^T.
    d logdet I / da=tr(I^-1 I_a).
    d^2 logdet I /dadb=tr(I^-1 I_ab-I^-1 I_b I^-1 I_a).
    """
    d=model.d;eta=model.eta(box);nrows=len(model.x)
    pp=[model.probability(z) for z in eta]
    one=IV(1);two=IV(2);half=IV('0.5')
    w=[p*(one-p) for p in pp]
    w1=[wi*(one-two*pi) for wi,pi in zip(w,pp)]
    w2=[wi*((one-two*pi)*(one-two*pi)-two*wi) for wi,pi in zip(w,pp)]
    def mzero():return [[IV(0) for _ in range(d)] for _ in range(d)]
    Fm=mzero();Fm1=[mzero() for _ in range(d)];Fm2=[[mzero() for _ in range(d)] for _ in range(d)]
    llg=[IV(0) for _ in range(d)];llh=mzero()
    for i,((n,s),xs) in enumerate(zip(model.counts,model.X)):
        for a in range(d):
            llg[a]=llg[a]+(IV(s)-IV(n)*pp[i])*xs[a]
            for b in range(d):llh[a][b]=llh[a][b]-IV(n)*w[i]*xs[a]*xs[b]
        for j in range(d):
            for k in range(d):
                v=IV(n)*xs[j]*xs[k]
                Fm[j][k]=Fm[j][k]+v*w[i]
                for a in range(d):
                    Fm1[a][j][k]=Fm1[a][j][k]+v*w1[i]*xs[a]
                    for b in range(d):
                        Fm2[a][b][j][k]=Fm2[a][b][j][k]+v*w2[i]*xs[a]*xs[b]
    # Determinant strictly positive on every finite box: independent Cauchy–Binet
    # nonzero design minor and positive logistic weights supply lower endpoint.
    minor_det=model.info_det(w)
    direct_det=_matrix_det_interval(Fm)
    detF=IV.raw(max(minor_det.lo,direct_det.lo),min(minor_det.hi,direct_det.hi))
    Inv=_inverse_from_verified_positive_det(Fm,detF)
    def mmul(A,B):
        return [[sum((A[i][k]*B[k][j] for k in range(d)),IV(0)) for j in range(d)] for i in range(d)]
    def trace(A):return sum((A[i][i] for i in range(d)),IV(0))
    score=[];hess=[]
    C=[mmul(Inv,Fm1[a]) for a in range(d)]
    for a in range(d):
        score.append(llg[a]+half*trace(C[a]))
    for a in range(d):
        row=[]
        for b in range(d):
            term=mmul(Inv,Fm2[a][b])
            row.append(llh[a][b]+half*(trace(term)-trace(mmul(C[b],C[a]))))
        hess.append(row)
    return score,hess


def taylor_upper(model:MathematicalModel,box):
    """Sound order-two Taylor upper over B using point gradient and box Hessian."""
    width=[];mid=[]
    for a,b in box:
        aa=F(str(a));bb=F(str(b));m=(aa+bb)/2
        mid.append(m);width.append(IV.rational((bb-aa)/2).hi)
    # Fraction midpoints may be dyadic (finite decimal); stringify exactly.
    def finite_decimal(x):
        with localcontext(CONTEXT) as ctx:
            z=D(x.numerator)/D(x.denominator)
            if F(z)!=x:raise ValueError('Midpoint not exactly decimal representable at working precision')
            return str(z)
    mstr=[finite_decimal(x) for x in mid]
    pointbox=[(x,x) for x in mstr]
    fmid=model.objective_bound(pointbox)
    grad,_=objective_derivatives(model,pointbox)
    _,hess=objective_derivatives(model,box)
    total=IV(fmid)
    for i in range(model.d):total=total+IV(interval_abs_upper(grad[i]))*IV(width[i])
    for i in range(model.d):
        for j in range(model.d):
            total=total+IV('0.5')*IV(interval_abs_upper(hess[i][j]))*IV(width[i])*IV(width[j])
    return total.hi