"""CH40-D checker-side interval kernel. No CH23-40 producer mathematical imports.

Basic arithmetic is exact rational (Fraction). Exponential and logarithm use
independent CPython libmpdec correctly-rounded calculations widened by >=1 ulp
at each 95-digit Decimal endpoint; all other algebra is exact rational.
"""
from __future__ import annotations
from decimal import Decimal,Context,localcontext,ROUND_FLOOR,ROUND_CEILING,ROUND_HALF_EVEN
from fractions import Fraction as F
from itertools import combinations

CTX=Context(prec=95,Emin=-999999,Emax=999999)

def dec_f(x, direction):
    x=F(x)
    with localcontext(CTX) as ctx:
        ctx.rounding=direction
        v=Decimal(x.numerator)/Decimal(x.denominator)
    return v

def trans(kind,x,direction):
    x=F(x)
    arg=dec_f(x,ROUND_FLOOR if direction=='lo' else ROUND_CEILING)
    with localcontext(CTX) as ctx:
        ctx.rounding=ROUND_HALF_EVEN
        if kind=='exp': val=arg.exp(context=ctx)
        elif kind=='ln':
            if x<=0:raise ArithmeticError('ln on non-positive interval')
            val=arg.ln(context=ctx)
        else:raise ValueError(kind)
        val=val.next_minus(context=ctx) if direction=='lo' else val.next_plus(context=ctx)
    return F(val)

class R:
    __slots__=('lo','hi')
    def __init__(self,a,b=None):
        self.lo=F(str(a));self.hi=F(str(a if b is None else b))
        if self.lo>self.hi:raise ValueError('Invalid rational interval')
    @classmethod
    def raw(cls,a,b):
        o=object.__new__(cls);o.lo=F(a);o.hi=F(b)
        if o.lo>o.hi:raise ArithmeticError('Invalid rational result')
        return o
    @staticmethod
    def co(x):return x if isinstance(x,R) else R(x)
    def __add__(self,y):
        y=self.co(y);return R.raw(self.lo+y.lo,self.hi+y.hi)
    __radd__=__add__
    def __neg__(self):return R.raw(-self.hi,-self.lo)
    def __sub__(self,y):return self+-self.co(y)
    def __rsub__(self,y):return self.co(y)-self
    def __mul__(self,y):
        y=self.co(y);v=[a*b for a in (self.lo,self.hi) for b in (y.lo,y.hi)]
        return R.raw(min(v),max(v))
    __rmul__=__mul__
    def __truediv__(self,y):
        y=self.co(y)
        if y.lo<=0<=y.hi:raise ArithmeticError('Division by interval containing zero')
        return self*R.raw(F(1,y.hi),F(1,y.lo))
    def __rtruediv__(self,y):return self.co(y)/self
    def exp(self):return R.raw(trans('exp',self.lo,'lo'),trans('exp',self.hi,'hi'))
    def ln(self):
        if self.lo<=0:raise ArithmeticError('ln non-positive')
        return R.raw(trans('ln',self.lo,'lo'),trans('ln',self.hi,'hi'))
    def contains(self,x):
        y=self.co(x);return self.lo<=y.lo and y.hi<=self.hi
    def intersects(self,y):
        y=self.co(y);return max(self.lo,y.lo)<=min(self.hi,y.hi)
    def intersection(self,y):
        y=self.co(y);return R.raw(max(self.lo,y.lo),min(self.hi,y.hi))
    def upper_abs(self):return max(abs(self.lo),abs(self.hi))
    def out(self,places=48):
        # Round endpoints outward to bounded-size finite decimal values.
        q=Decimal(10)**(-places)
        with localcontext(CTX) as ctx:
            ctx.prec=max(CTX.prec,places+35)
            lo=dec_f(self.lo,ROUND_FLOOR).quantize(q,rounding=ROUND_FLOOR)
            hi=dec_f(self.hi,ROUND_CEILING).quantize(q,rounding=ROUND_CEILING)
        return [str(lo),str(hi)]

def det(A):
    d=len(A)
    if d==1:return A[0][0]
    if d==2:return A[0][0]*A[1][1]-A[0][1]*A[1][0]
    if d==3:return A[0][0]*(A[1][1]*A[2][2]-A[1][2]*A[2][1])-A[0][1]*(A[1][0]*A[2][2]-A[1][2]*A[2][0])+A[0][2]*(A[1][0]*A[2][1]-A[1][1]*A[2][0])
    raise ValueError('Only dimensions 1-3')

def model_of(cert):
    model=cert['model'];d=model['d'];rows=model['rows']
    if type(d) is not int or d not in (1,2,3) or not rows or len(rows)>1000:raise ValueError('Model limit')
    xs=[]
    for row in rows:
        if len(row['x'])!=d or type(row['n']) is not int or type(row['s']) is not int or not 0<=row['s']<=row['n'] or row['n']<=0:raise ValueError('Model row')
        xs.append([F(str(x)) for x in row['x']])
    if sum(row['n'] for row in rows)!=model['n_raw']:raise ValueError('Original observation mismatch')
    basis=next(((ids,det([xs[i] for i in ids])) for ids in combinations(range(len(xs)),d) if det([xs[i] for i in ids])!=0),None)
    if basis is None:raise ArithmeticError('Rank deficiency')
    return d,rows,xs,basis

def eta(x,box):
    return sum((R(a,b)*R(xi) for xi,(a,b) in zip(x,box)),R(0))

def p_of(z):return R(1)/(R(1)+(-z).exp())

def weight_of(z):
    def point(t):return R(1)/(R(2)+R(t).exp()+(-R(t)).exp())
    left,right=point(z.lo),point(z.hi)
    return R.raw(min(left.lo,right.lo),F(1,4) if z.lo<=0<=z.hi else max(left.hi,right.hi))

def fisher_det_interval(rows,xs,weights,basis,*,point=False):
    ids,minor=basis;d=len(xs[0]);lower=R(minor*minor)
    for i in ids:lower=lower*R(rows[i]['n'])*weights[i]
    diag=[]
    for j in range(d):diag.append(sum((R(rows[i]['n']*xs[i][j]*xs[i][j])*weights[i] for i in range(len(xs))),R(0)))
    upper=R(1)
    for q in diag:upper=upper*q
    lo,hi=lower.lo,upper.hi
    if point:
        mat=[[sum((R(rows[i]['n']*xs[i][j]*xs[i][k])*weights[i] for i in range(len(xs))),R(0)) for k in range(d)] for j in range(d)]
        exact=det(mat);lo=max(lo,exact.lo);hi=min(hi,exact.hi)
    if lo<=0 or hi<lo:raise ArithmeticError('Cannot establish Fisher SPD')
    return R.raw(lo,hi)

def direct_components(cert,box):
    d,rows,xs,basis=model_of(cert);terms=[];weights=[]
    for row,x in zip(rows,xs):
        z=eta(x,box);weights.append(weight_of(z));n,s=row['n'],row['s']
        if s==0: term=-R(n)*(R(1)+R(z.lo).exp()).ln()
        elif s==n:term=-R(n)*(R(1)+(-R(z.hi)).exp()).ln()
        else:term=z*R(s)-(R(1)+z.exp()).ln()*R(n)
        terms.append(term)
    determinant=fisher_det_interval(rows,xs,weights,basis)
    objective=sum(terms,R(0))+R(F(1,2))*determinant.ln()
    return terms,determinant,objective

def direct_upper(cert,box):
    return direct_components(cert,box)[2]

def coupled_terms(cert,box,q_index,points):
    d,rows,xs,basis=model_of(cert); Q=[[F(str(s)) for s in row] for row in cert['dual_matrices'][q_index]]
    if any(Q[i][j]!=Q[j][i] for i in range(d) for j in range(d)):raise ArithmeticError('Non symmetric dual')
    if Q[0][0]<=0 or (d>=2 and det([row[:2] for row in Q[:2]])<=0) or (d==3 and det(Q)<=0):raise ArithmeticError('Dual not SPD')
    if len(points)!=len(rows):raise ValueError('Row support count')
    kdim=R(d);constant=-R(F(1,2))*R(det(Q)).ln()-kdim/R(2);terms=[];term_details=[]
    for (row,x,point) in zip(rows,xs,points):
        p0=F(str(point))
        if p0<=0 or p0>=1:raise ArithmeticError('Invalid tangent support point')
        z=eta(x,box);pp=p_of(z);s,n=row['s'],row['n']
        leverage=sum((x[i]*Q[i][j]*x[j] for i in range(d) for j in range(d)),F(0))
        if leverage<=0:raise ArithmeticError('Invalid leverage')
        k=F(n,2)*leverage
        # For g(p)=s ln p+(n-s)ln(1-p)+k p(1-p), g''(p)<0.
        val=R(s)*R(p0).ln()+R(n-s)*R(1-p0).ln()+R(k*p0*(1-p0))
        slope=R(F(s,1)/p0-F(n-s,1)/(1-p0)+k*(1-2*p0))
        terms.append(val+slope*(pp-R(p0)))
        term_details.append({'value':val,'slope':slope,'probability':pp})
    upper=constant+sum(terms,R(0))
    return constant,terms,upper,term_details

def derivatives(cert,box):
    """Independent Firth score and Hessian, not a call to CH40-B producer."""
    d,rows,xs,basis=model_of(cert)
    z=[eta(x,box) for x in xs];p=[p_of(t) for t in z];w=[t*(R(1)-t) for t in p]
    w1=[a*(R(1)-R(2)*b) for a,b in zip(w,p)]
    w2=[a*((R(1)-R(2)*b)*(R(1)-R(2)*b)-R(2)*a) for a,b in zip(w,p)]
    def mat():return [[R(0) for _ in range(d)] for _ in range(d)]
    I=mat();I1=[mat() for _ in range(d)];I2=[[mat() for _ in range(d)] for _ in range(d)]
    ll1=[R(0) for _ in range(d)];ll2=mat()
    for i,(row,x) in enumerate(zip(rows,xs)):
        n,s=row['n'],row['s']
        for a in range(d):
            ll1[a]=ll1[a]+(R(s)-R(n)*p[i])*R(x[a])
            for b in range(d):ll2[a][b]=ll2[a][b]-R(n*x[a]*x[b])*w[i]
        for j in range(d):
            for k in range(d):
                z0=R(n*x[j]*x[k]);I[j][k]=I[j][k]+z0*w[i]
                for a in range(d):
                    I1[a][j][k]=I1[a][j][k]+z0*R(x[a])*w1[i]
                    for b in range(d):I2[a][b][j][k]=I2[a][b][j][k]+z0*R(x[a]*x[b])*w2[i]
    detD=fisher_det_interval(rows,xs,w,basis)
    dense=det(I)
    detD=detD.intersection(dense)
    if detD.lo<=0:raise ArithmeticError('No positive Fisher determinant proof')
    invdet=R(1)/detD
    if d==1:Inv=[[invdet]]
    else:
        Inv=[]
        for i in range(d):
            line=[]
            for j in range(d):
                minor=[[I[a][b] for b in range(d) if b!=i] for a in range(d) if a!=j]
                line.append(det(minor)*invdet*(1 if (i+j)%2==0 else -1))
            Inv.append(line)
    def mm(A,B):return [[sum((A[i][k]*B[k][j] for k in range(d)),R(0)) for j in range(d)] for i in range(d)]
    def trace(A):return sum((A[i][i] for i in range(d)),R(0))
    C=[mm(Inv,I1[a]) for a in range(d)]
    grad=[ll1[a]+R(F(1,2))*trace(C[a]) for a in range(d)]
    hess=[]
    for a in range(d):
        line=[]
        for b in range(d):line.append(ll2[a][b]+R(F(1,2))*(trace(mm(Inv,I2[a][b]))-trace(mm(C[b],C[a]))))
        hess.append(line)
    return grad,hess

def point_objective(cert,center):
    d,rows,xs,basis=model_of(cert);box=[[t,t] for t in center]
    ps=[];val=R(0)
    for row,x in zip(rows,xs):
        z=eta(x,box);n,s=row['n'],row['s']
        val=val+R(s)*z-R(n)*(R(1)+z.exp()).ln()
        ps.append(weight_of(z))
    detI=fisher_det_interval(rows,xs,ps,basis,point=True)
    return val+R(F(1,2))*detI.ln()