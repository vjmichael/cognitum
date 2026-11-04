"""Numerical cross-check of the 3x3 determinant formula emitted for IBEX and SCIP.
Independent *algebraic shape* check, not a proof of either native parser or rigorous arithmetic.
"""
from __future__ import annotations
import math


def explicit_firth_float(cert,beta):
    I=[[0.0]*3 for _ in range(3)]
    terms=[]
    for r in cert['model']['rows']:
        x=[float(v) for v in r['x']];z=math.fsum(x[i]*float(beta[i]) for i in range(3))
        n,s=int(r['n']),int(r['s'])
        p=1/(1+math.exp(-z))
        w=n*p*(1-p)
        for i in range(3):
            for j in range(i,3):I[i][j]+=w*x[i]*x[j]
        terms.append(s*z-n*(max(z,0)+math.log1p(math.exp(-abs(z)))))
    a,b,c=I[0][0],I[0][1],I[0][2]
    d,e,f=I[1][1],I[1][2],I[2][2]
    det=a*d*f+2*b*c*e-a*e*e-d*c*c-f*b*b
    if not math.isfinite(det) or det<=0:raise ArithmeticError('explicit Fisher determinant not established')
    return math.fsum(terms)+0.5*math.log(det)

