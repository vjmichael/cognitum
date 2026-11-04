"""Optional FLINT/Arb point enclosure: new engine, old independent Fraction checker.
Never claims production pass unless the actual flint module executes and intervals overlap.
"""
from __future__ import annotations
from fractions import Fraction as F
from time import process_time

class BackendUnavailable(RuntimeError):pass


def dyadic(arb_endpoint):
    """Convert an *exact* Arb binary endpoint to a Fraction, without decimal string roundoff."""
    mantissa, exponent=arb_endpoint.man_exp()
    m,e=int(mantissa),int(exponent)
    return F(m*2**e,1) if e>=0 else F(m,2**(-e))


def fraction_arb(f, arb):
    f=F(f)
    return arb(f'{f.numerator}/{f.denominator}')


def arb_point(case, point, *,precision=256):
    try:from flint import arb,arb_mat,ctx,__version__ as flint_ver
    except ImportError as e:raise BackendUnavailable('python-flint not installed') from e
    if precision<128 or precision>2048:raise ValueError('unsafe Arb precision limit')
    start=process_time()
    oldprec=ctx.prec
    try:
        ctx.prec=precision
        b=[fraction_arb(F(str(float(q))),arb) for q in point]
        likelihood=arb(0)
        d=3
        fisher=[[arb(0) for _ in range(d)] for __ in range(d)]
        for row in case.certificate['model']['rows']:
            x=[fraction_arb(F(v),arb) for v in row['x']]
            n,s=row['n'],row['s']
            z=sum((xi*bi for xi,bi in zip(x,b)),arb(0))
            # Avoid unstable plain probability logs in Firth/logistic.
            likelihood+=arb(s)*z-arb(n)*(arb(1)+z.exp()).log()
            p=arb(1)/(arb(1)+(-z).exp());w=arb(n)*p*(arb(1)-p)
            for i in range(d):
                for j in range(d):fisher[i][j]+=w*x[i]*x[j]
        D=arb_mat(fisher).det()
        if dyadic(D.lower())<=0:raise ArithmeticError('Arb Fisher determinant enclosure does not establish SPD')
        objective=likelihood+D.log()/2
        lo,hi=dyadic(objective.lower()),dyadic(objective.upper())
        if lo>hi:raise AssertionError('invalid Arb interval')
        return {'backend':'python-flint/Arb','version':str(flint_ver),'precision_bits':precision,
                'lower':str(lo),'upper':str(hi),'cpu_seconds':round(process_time()-start,6)}
    finally:ctx.prec=oldprec


def compare_point(case, point, reference_dir):
    # Fail fast if backend absent. Do not perform expensive reference arithmetic for a missing library.
    import importlib.util
    if importlib.util.find_spec('flint') is None:raise BackendUnavailable('python-flint not installed')
    # A float point must be viewed as an EXACT dyadic rational in *both* oracles.
    from frozen40m2 import point_lower
    ref=point_lower(case,point,reference_dir)
    got=arb_point(case,point)
    lo,hi=F(got['lower']),F(got['upper'])
    if max(lo,ref.lo)>min(hi,ref.hi):raise ArithmeticError('Independent Arb and rational intervals are disjoint')
    got['overlap_independent_rational']=True
    got['reference_lower']=str(ref.lo)
    got['reference_upper']=str(ref.hi)
    got['certified_point_only']=True
    return got

