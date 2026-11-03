"""Independent verifier-side directed Decimal engine for Firth derivatives.

No imports from producer CH40-B/CH40-C interval math. Exact Fraction used
only for model/design/coordinate constants, all interval arithmetic directed
under fresh contexts. Uses separate Jacobian/Hessian loop and adjugate inverse.
"""
from __future__ import annotations
from decimal import Decimal as D, Context, localcontext, ROUND_FLOOR, ROUND_CEILING, ROUND_HALF_EVEN
from fractions import Fraction as F
from itertools import combinations
C=Context(prec=95,Emin=-999999,Emax=999999)

def number(x,direction):
    if isinstance(x, Z):raise TypeError('Already interval')
    f=F(str(x)) if not isinstance(x,F) else x
    with localcontext(C) as cx:
        cx.rounding=direction
        return D(f.numerator)/D(f.denominator)

def rounded(op,a,b,way):
    with localcontext(C) as cx:
        cx.rounding=way
        if op=='+':return a+b
        if op=='*':return a*b
        if op=='/':return a/b
        raise ValueError(op)

class Z:
    __slots__=('lo','hi')
    def __init__(self,a,b=None):
        self.lo=number(a,ROUND_FLOOR);self.hi=number(a if b is None else b,ROUND_CEILING)
        if self.lo>self.hi:raise ValueError('Reversed rational input interval')
    @classmethod
    def raw(cls,a,b):
        p=object.__new__(cls);p.lo,p.hi=a,b
        if a>b or not a.is_finite() or not b.is_finite():raise ArithmeticError('Invalid directed interval')
        return p
    @staticmethod
    def co(x):return x if isinstance(x,Z) else Z(x)
    def __add__(self,x):
        x=self.co(x);return Z.raw(rounded('+',self.lo,x.lo,ROUND_FLOOR),rounded('+',self.hi,x.hi,ROUND_CEILING))
    __radd__=__add__
    def __neg__(self):return Z.raw(-self.hi,-self.lo)
    def __sub__(self,x):return self+-self.co(x)
    def __rsub__(self,x):return self.co(x)-self
    def __mul__(self,x):
        x=self.co(x);v=[(a,b) for a in (self.lo,self.hi) for b in (x.lo,x.hi)]
        return Z.raw(min(rounded('*',a,b,ROUND_FLOOR) for a,b in v),max(rounded('*',a,b,ROUND_CEILING) for a,b in v))
    __rmul__=__mul__
    def __truediv__(self,x):
        x=self.co(x)
        if x.lo<=0<=x.hi:raise ArithmeticError('Division by zero-containing enclosure')
        return self*Z.raw(rounded('/',D(1),x.hi,ROUND_FLOOR),rounded('/',D(1),x.lo,ROUND_CEILING))
    def __rtruediv__(self,x):return self.co(x)/self
    def _trans(self,which):
        if which=='ln' and self.lo<=0:raise ArithmeticError('ln domain')
        with localcontext(C) as cx:
            cx.rounding=ROUND_HALF_EVEN
            aa=self.lo.exp(context=cx) if which=='exp' else self.lo.ln(context=cx)
            bb=self.hi.exp(context=cx) if which=='exp' else self.hi.ln(context=cx)
            return Z.raw(aa.next_minus(context=cx),bb.next_plus(context=cx))
    def exp(self):return self._trans('exp')
    def ln(self):return self._trans('ln')
    def contains(self,other):
        return self.lo<=other.lo and other.hi<=self.hi
    def rationals(self):return (F(self.lo),F(self.hi))

def exactdet(a):
    d=len(a)
    if d==1:return a[0][0]
    if d==2:return a[0][0]*a[1][1]-a[0][1]*a[1][0]
    if d==3:return a[0][0]*(a[1][1]*a[2][2]-a[1][2]*a[2][1])-a[0][1]*(a[1][0]*a[2][2]-a[1][2]*a[2][0])+a[0][2]*(a[1][0]*a[2][1]-a[1][1]*a[2][0])
    raise ValueError('bad dimension')

def proofmodel(cert):
    d=cert['model']['d'];rows=cert['model']['rows'];xx=[[F(str(v)) for v in r['x']] for r in rows]
    if d not in (1,2,3) or any(len(x)!=d for x in xx):raise ValueError('dimension')
    for indices in combinations(range(len(rows)),d):
        a=exactdet([xx[i] for i in indices])
        if a!=0: return d,rows,xx,(indices,a)
    raise ArithmeticError('rank deficient')

def inv_positive_fisher(M,w,rows,x,basis):
    d=len(M);ids,bdet=basis;minor=Z(bdet*bdet)
    for i in ids:minor=minor*Z(rows[i]['n'])*w[i]
    diag=Z(1)
    for j in range(d):diag=diag*M[j][j]
    detm=exactdet(M)
    low=max(minor.lo,detm.lo);hi=min(diag.hi,detm.hi)
    if low<=0 or low>hi:raise ArithmeticError('No verified Fisher determinant')
    invdet=Z(1)/Z.raw(low,hi)
    if d==1:return [[invdet]]
    inv=[]
    for i in range(d):
        row=[]
        for j in range(d):
            minorM=[[M[u][v] for v in range(d) if v!=i] for u in range(d) if u!=j]
            row.append(exactdet(minorM)*invdet*(1 if (i+j)%2==0 else -1))
        inv.append(row)
    return inv

def f_derivatives(cert,box):
    d,rows,x,basis=proofmodel(cert)
    BB=[Z(a,b) for a,b in box]
    eta=[sum((BB[j]*Z(xi[j]) for j in range(d)),Z(0)) for xi in x]
    prob=[Z(1)/(Z(1)+(-z).exp()) for z in eta]
    weights=[p*(Z(1)-p) for p in prob]
    dw=[w*(Z(1)-Z(2)*p) for w,p in zip(weights,prob)]
    d2w=[w*((Z(1)-Z(2)*p)*(Z(1)-Z(2)*p)-Z(2)*w) for w,p in zip(weights,prob)]
    mat=lambda:[[Z(0) for j in range(d)] for i in range(d)]
    fisher=mat();fisher_deriv=[mat() for _ in range(d)];fisher_second=[[mat() for _ in range(d)] for _ in range(d)]
    score=[Z(0) for _ in range(d)];hess=mat()
    for i,(row,xi) in enumerate(zip(rows,x)):
        n,s=row['n'],row['s']
        for a in range(d):
            score[a]=score[a]+(Z(s)-Z(n)*prob[i])*Z(xi[a])
            for b in range(d):hess[a][b]=hess[a][b]-Z(n*xi[a]*xi[b])*weights[i]
        for j in range(d):
            for k in range(d):
                factor=Z(n*xi[j]*xi[k]);fisher[j][k]=fisher[j][k]+factor*weights[i]
                for a in range(d):
                    fisher_deriv[a][j][k]=fisher_deriv[a][j][k]+factor*Z(xi[a])*dw[i]
                    for b in range(d):
                        fisher_second[a][b][j][k]=fisher_second[a][b][j][k]+factor*Z(xi[a]*xi[b])*d2w[i]
    inverse=inv_positive_fisher(fisher,weights,rows,x,basis)
    def mm(A,B):return [[sum((A[i][k]*B[k][j] for k in range(d)),Z(0)) for j in range(d)] for i in range(d)]
    def trace(A):return sum((A[i][i] for i in range(d)),Z(0))
    left=[mm(inverse,fisher_deriv[a]) for a in range(d)]
    for a in range(d):score[a]=score[a]+Z('0.5')*trace(left[a])
    for a in range(d):
        for b in range(d):hess[a][b]=hess[a][b]+Z('0.5')*(trace(mm(inverse,fisher_second[a][b]))-trace(mm(left[b],left[a])))
    return score,hess

def point_firth(cert,mid):
    d,rows,x,basis=proofmodel(cert);box=[Z(v) for v in mid]
    ll=Z(0);P=[];W=[]
    for row,xi in zip(rows,x):
        z=sum((box[j]*Z(xi[j]) for j in range(d)),Z(0))
        ll=ll+z*Z(row['s'])-Z(row['n'])*(Z(1)+z.exp()).ln()
        p=Z(1)/(Z(1)+(-z).exp());P.append(p)
        # Enclose symmetric logistic weight with the same stable formula as producer
        w=Z(1)/(Z(2)+z.exp()+(-z).exp());W.append(w)
    fisher=[[sum((Z(row['n']*xi[j]*xi[k])*w for row,xi,w in zip(rows,x,W)),Z(0)) for k in range(d)] for j in range(d)]
    ids,bdet=basis;lower=Z(bdet*bdet)
    for i in ids:lower=lower*Z(rows[i]['n'])*W[i]
    upper=Z(1)
    for j in range(d):upper=upper*fisher[j][j]
    dt=exactdet(fisher)
    lo=max(lower.lo,dt.lo);hi=min(upper.hi,dt.hi)
    if lo<=0 or lo>hi:raise ArithmeticError('No Fisher point positivity')
    return ll+Z('0.5')*Z.raw(lo,hi).ln()
