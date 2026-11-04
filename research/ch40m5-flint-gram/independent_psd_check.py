"""Independent CH40-M.5 rational/Decimal proof replay. No import of FLINT.

Reconstructs rowwise maxima and independent Fisher Gram PSD ceiling, then
requires the FLINT producer's published interval upper to enclose it. A native
result failing this check is REFUSED, never substituted by float rounding.
"""
from __future__ import annotations
from fractions import Fraction as F
from decimal import Decimal, ROUND_CEILING, localcontext
from pathlib import Path

def _load_checker(reference_dir):
    import sys
    directory=Path(reference_dir).resolve()
    if not directory.is_dir():raise FileNotFoundError('Original independent checker directory required')
    sys.path.insert(0,str(directory))
    from rational_kernel40d import R,model_of,eta,weight_of,det,dec_f
    return R,model_of,eta,weight_of,det,dec_f

def independent_bound(cert,box,reference_dir):
    R,model_of,eta,weight_of,det,dec_f=_load_checker(reference_dir)
    d,rows,xs,_=model_of(cert)
    if d!=3 or len(box)!=3:raise ValueError('Only frozen d3 models')
    ceiling=F(0); wt=[]
    for row,x in zip(rows,xs):
        z=eta(x,box);n,s=row['n'],row['s']
        if s==0:t=-R(n)*(R(1)+R(z.lo).exp()).ln()
        elif s==n:t=-R(n)*(R(1)+(-R(z.hi)).exp()).ln()
        else:
            p=F(s,n)
            t=R(s)*R(p).ln()+R(n-s)*R(1-p).ln()
        ceiling+=t.hi
        # Independent, explicitly outward 85-decimal truncation of each rational
        # upper weight. Keeps exact Gram denominators finite without losing proof.
        with localcontext() as dctx:
            dctx.prec=125
            ceil85=dec_f(weight_of(z).hi,ROUND_CEILING).quantize(Decimal('1e-85'),rounding=ROUND_CEILING)
        wt.append(F(ceil85))
    G=[[F(0) for _ in range(3)] for __ in range(3)]
    for row,x,u in zip(rows,xs,wt):
        for i in range(3):
            for j in range(3):G[i][j]+=row['n']*u*x[i]*x[j]
    D=det(G)
    if D<=0:raise ArithmeticError('Expected SPD upper Gram from full-rank model')
    return ceiling + F(1,2)*R(D).ln().hi, wt

def validate_native(cert,box,candidate,reference_dir):
    ref,ref_w=independent_bound(cert,box,reference_dir)
    if len(candidate['weights_upper'])!=len(ref_w):raise ValueError('weight count mismatch')
    if any(u<v for u,v in zip(candidate['weights_upper'],ref_w)):
        raise ArithmeticError('native weight fails independent upper enclosure')
    if candidate['gram_upper']<ref:raise ArithmeticError('native bound below independently proved ceiling')
    return {'independent_bound':ref,'upper_excess':candidate['gram_upper']-ref,
            'status':'ACCEPTED_CONSERVATIVE_PSD_GRAM_UPPER'}
