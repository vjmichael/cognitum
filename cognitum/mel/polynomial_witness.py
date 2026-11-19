"""Independent exact rational polynomial witness and continuous box enclosure.

The function is the ideal function of the represented binary64 parameters;
no training-target error, uncertain inputs, or extrapolation is certified.
Polynomial pieces are constructed in monomial form, not by the worker's
vectorized basis/derivative recurrence. All interval operations are rational.
"""
from fractions import Fraction as Q
import math


def need(ok, msg):
    if not ok: raise ValueError(msg)


def q(x):
    return Q(float(x))


def cap(x):
    need(max(x.numerator.bit_length(), x.denominator.bit_length()) <= 16384, 'rational witness budget')
    return x


def plus(a,b):
    return tuple(cap((a[i] if i<len(a) else Q(0))+(b[i] if i<len(b) else Q(0))) for i in range(max(len(a),len(b))))


def times(a,b):
    out=[Q(0)]*(len(a)+len(b)-1)
    for i,u in enumerate(a):
        for j,v in enumerate(b):out[i+j]=cap(out[i+j]+u*v)
    return tuple(out)


def scale(a,x):return tuple(cap(v*x) for v in a)


def diff(a):return tuple(cap(i*v) for i,v in enumerate(a) if i) or (Q(0),)


def interval(x):return (x,x)


def add(a,b):return (cap(a[0]+b[0]),cap(a[1]+b[1]))


def mul(a,b):
    v=[cap(x*y) for x in a for y in b];return min(v),max(v)


def evaluate(poly,x):
    out=interval(Q(0))
    for c in reversed(poly):out=add(mul(out,x),interval(c))
    return out


def cheb_polys(lo,hi,degree):
    z=(-(lo+hi)/(hi-lo),Q(2)/(hi-lo));p=[(Q(1),)]
    if degree:p.append(z)
    for _ in range(2,degree+1):p.append(plus(scale(times(z,p[-1]),Q(2)),scale(p[-2],Q(-1))))
    return p


def spline_polys(g,p,span):
    # Degree zero for a particular nonempty knot span, polynomial on its closure.
    b=[(Q(int(i==span)),) for i in range(len(g)-1)]
    for k in range(1,p+1):
        out=[]
        for i in range(len(b)-1):
            l,r=g[i+k]-g[i],g[i+k+1]-g[i+1]
            u=times(b[i],(-g[i]/l,Q(1)/l)) if l else (Q(0),)
            v=times(b[i+1],(g[i+k+1]/r,-Q(1)/r)) if r else (Q(0),)
            out.append(plus(u,v))
        b=out
    return b


def edge(layer,o,i,x,order):
    g=tuple(map(q,layer.grid[i]));lo,hi=x
    need(g[0]<=lo<=hi<=g[-1],'exact intermediate outside certified domain')
    if layer.kind=='chebyshev':pieces=[(x,cheb_polys(*g,layer.degree))]
    else:
        if order:
            need(g[0]<lo and hi<g[-1],'spline endpoint derivative not certified')
            if order>=layer.degree:
                need(not any(lo<=v<=hi for v in g if g[0]<v<g[-1]),'nonsmooth knot derivative not certified')
        spans=[j for j in range(len(g)-1) if g[j]<g[j+1] and max(lo,g[j])<=min(hi,g[j+1])]
        # Interior continuity for clamped profile (simple interior knots), or
        # right-hand point convention if needed. Derivatives at nonsmooth knots refused above.
        pieces=[((max(lo,g[j]),min(hi,g[j+1])),spline_polys(g,layer.degree,j)) for j in spans]
    w=tuple(map(q,layer.coefficients[o,i]));active=q(layer.mask[o,i]);acc=[[] for _ in range(order+1)]
    for bounds,polys in pieces:
        p=(Q(0),)
        for c,b in zip(w,polys):p=plus(p,scale(b,c*active))
        for d in range(order+1):
            acc[d].append(evaluate(p,bounds));p=diff(p)
    return tuple((min(v[0] for v in values),max(v[1] for v in values)) for values in acc)


def sum_intervals(values):
    out=interval(Q(0))
    for v in values:out=add(out,v)
    return out


def enclose(model,box,order):
    """Value/Jacobian/Hessian enclosure on a closed box. Refuse domain ambiguity.

    Natural interval extension can overestimate, notably across compositions.
    Not an optimal range algorithm. Derivatives only on certified smooth domain.
    Output shape follows Network.evaluate (one row, no batch dimension here).
    """
    n=model.layers[0].inputs;need(len(box)==n and order in (0,1,2),'box profile')
    z=[(q(lo),q(hi)) for lo,hi in box];need(all(lo<=hi for lo,hi in z),'box ordering')
    jac=[[interval(Q(i==j)) for j in range(n)] for i in range(n)]
    hess=[[[interval(Q(0)) for _ in range(n)] for _ in range(n)] for _ in range(n)]
    for layer in model.layers:
        edges=[[edge(layer,o,i,z[i],order) for i in range(layer.inputs)] for o in range(layer.outputs)]
        newz=[add(interval(q(layer.bias[o])),sum_intervals(e[0] for e in row)) for o,row in enumerate(edges)]
        if order:
            newj=[[sum_intervals(mul(row[i][1],jac[i][j]) for i in range(layer.inputs)) for j in range(n)] for row in edges]
            if order==2:
                hess=[[[sum_intervals(add(mul(row[i][1],hess[i][j][k]),mul(row[i][2],mul(jac[i][j],jac[i][k]))) for i in range(layer.inputs)) for k in range(n)] for j in range(n)] for row in edges]
            jac=newj
        z=newz
    return (z,jac,hess)[:order+1]


def flatten(tree):
    if isinstance(tree,tuple) and len(tree)==2 and all(isinstance(v,Q) for v in tree):yield tree
    else:
        for v in tree:yield from flatten(v)


def outward(qv,upper):
    f=float(qv);need(math.isfinite(f) and abs(f)<=1e12,'certified range')
    if (Q(f)<qv if upper else Q(f)>qv):f=math.nextafter(f,math.inf if upper else -math.inf)
    return f
