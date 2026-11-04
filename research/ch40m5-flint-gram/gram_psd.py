"""CH40-M.5: certified Fisher logdet *upper* via PSD Gram dominance.

For w_i(beta)<=u_i, I(beta)=sum n_i*w_i(beta)*x_i*x_i^T <=
G=sum n_i*u_i*x_i*x_i^T in Loewner order. Hence det(I(beta))<=det(G)
for nonnegative definite G, and det(G)>0 for full-rank rows with u_i>0.

One box, 3-D frozen Firth logistic objective, exact rational Gram matrix.
No global proof or signed scientific certificate is produced by this module.
"""
from __future__ import annotations
from fractions import Fraction as F
from flint import arb,ctx

def dyadic(endpoint):
    """Convert exact Arb endpoint to exact rational, never decimal-string rounding."""
    mant,exponent=endpoint.man_exp()
    m,e=int(mant),int(exponent)
    return F(m*2**e,1) if e>=0 else F(m,2**-e)

def fraction_arb(value,arb_type=arb):
    q=F(value)
    return arb_type(f'{q.numerator}/{q.denominator}')

def frac(x):return F(str(x))
def det3(m):
    a,b,c=m[0];d,e,f=m[1];g,h,i=m[2]
    return a*(e*i-f*h)-b*(d*i-f*g)+c*(d*h-e*g)

def eta_extrema(row,box):
    """Exact linear-form extrema; avoid wide Arb ball radius rounding."""
    if len(row['x'])!=3 or len(box)!=3:raise ValueError('3-dimensional model required')
    terms=[]
    for v,(lo,hi) in zip(row['x'],box):
        x,a,b=frac(v),frac(lo),frac(hi)
        if a>b:raise ValueError('Reversed box')
        terms.append((min(x*a,x*b),max(x*a,x*b)))
    return sum((v[0] for v in terms),F(0)),sum((v[1] for v in terms),F(0))

def weight_upper_endpoints(lo,hi):
    if lo>hi:raise ValueError('Reversed predictor interval')
    if lo<=0<=hi:return F(1,4)
    t=lo if abs(lo)<=abs(hi) else hi
    a=fraction_arb(t,arb)
    weight=arb(1)/(arb(2)+a.exp()+(-a).exp())
    return min(F(1,4),dyadic(weight.upper()))

def gram3(rows,weight_ceils):
    G=[[F(0) for _ in range(3)] for _ in range(3)]
    if len(rows)!=len(weight_ceils):raise ValueError('weight count mismatch')
    for row,u in zip(rows,weight_ceils):
        if type(row.get('n')) is not int or row['n']<=0:raise ValueError('Invalid row observation count')
        if u<=0:raise ArithmeticError('weight upper must be positive')
        x=[frac(v) for v in row['x']]; k=int(row['n'])*u
        for j in range(3):
            for t in range(j,3):G[j][t]+=k*x[j]*x[t]
    for j in range(3):
        for t in range(j):G[j][t]=G[t][j]
    return G

def native_cap(cert,box,prec=192):
    if not 128<=prec<=2048:raise ValueError('Arb precision must be between 128 and 2048 bits')
    if cert['model']['d']!=3:raise ValueError('Only 3D original cases')
    if not (0<len(cert['model']['rows'])<=1000):raise ValueError('Invalid row count')
    rows=cert['model']['rows']
    if len(box)!=3:raise ValueError('expected three parameter intervals')
    previous=ctx.prec
    try:
        ctx.prec=prec
        upper_ll=F(0);weights=[]
        for row in rows:
            lo,hi=eta_extrema(row,box)
            if type(row.get('n')) is not int or type(row.get('s')) is not int:raise ValueError('Invalid integer counts')
            n,s=row['n'],row['s']
            if not (n>=1 and 0<=s<=n):raise ValueError('Invalid row')
            if s==0:term=-arb(n)*(arb(1)+fraction_arb(lo,arb).exp()).log()
            elif s==n:term=-arb(n)*(arb(1)+(-fraction_arb(hi,arb)).exp()).log()
            else:
                p=F(s,n)
                term=arb(s)*fraction_arb(p,arb).log()+arb(n-s)*fraction_arb(1-p,arb).log()
            upper_ll+=dyadic(term.upper())
            weights.append(weight_upper_endpoints(lo,hi))
        G=gram3(rows,weights); D=det3(G)
        if D<=0:raise ArithmeticError('positive Fisher determinant upper not established')
        logdet=dyadic(fraction_arb(D,arb).log().upper())
        gram=upper_ll+F(1,2)*logdet
        hadamard=upper_ll+F(1,2)*dyadic(fraction_arb(G[0][0]*G[1][1]*G[2][2],arb).log().upper())
        return {'gram_upper':gram,'hadamard_upper':hadamard,
                'likelihood_upper':upper_ll,'det_gram':D,'weights_upper':weights,
                'gram_matrix':G,'hadamard_margin':hadamard-gram,'precision_bits':prec}
    finally:ctx.prec=previous
