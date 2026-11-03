"""CH40-A: independent interval arithmetic built on CPython libmpdec Decimal.

No imported Cognitum/MPFR arithmetic, BnB, or certificate verifier modules.
All primitive arithmetic uses directed Decimal contexts. Decimal exp and ln
are correctly rounded to ROUND_HALF_EVEN (Python decimal contract); we widen
one representable context step each way. Result is a finite real enclosure.
This is a second arithmetic implementation, NOT a formally verified kernel.
"""
from __future__ import annotations
from decimal import Decimal as D, Context, localcontext, ROUND_FLOOR, ROUND_CEILING, ROUND_HALF_EVEN, InvalidOperation
from fractions import Fraction

PRECISION = 85  # decimal significant digits, > 224 binary bits
CONTEXT = Context(prec=PRECISION, Emax=999999, Emin=-999999)


def value(x):
    if isinstance(x, D):
        result = x
    elif isinstance(x, (str, int)) and not isinstance(x, bool) and len(str(x)) <= 300:
        result = D(str(x))
    else:
        raise TypeError('Only exact finite decimal literals/integers accepted')
    if not result.is_finite(): raise ValueError('Nonfinite decimal')
    return result


def op(which, a, b=None, rnd=ROUND_FLOOR):
    with localcontext(CONTEXT) as ctx:
        ctx.rounding = rnd
        if which=='add': z=a+b
        elif which=='sub': z=a-b
        elif which=='mul': z=a*b
        elif which=='div':
            if b == 0: raise ArithmeticError('Zero division')
            z=a/b
        else: raise ValueError('Unknown operation')
    if not z.is_finite(): raise ArithmeticError('Nonfinite arithmetic')
    return z


def trans(which, x):
    # IEEE correctly-rounded half-even Decimal transcendental plus one ulp
    # in both directions. ROUND_FLOOR/Ceiling on exp/ln are NOT relied on.
    with localcontext(CONTEXT) as ctx:
        ctx.rounding=ROUND_HALF_EVEN
        if which=='exp': y=x.exp(context=ctx)
        elif which=='ln':
            if x<=0:raise ArithmeticError('ln domain')
            y=x.ln(context=ctx)
        else:raise ValueError('Unknown transcendental')
        if not y.is_finite(): raise ArithmeticError('Nonfinite transcendental')
        return (y.next_minus(context=ctx), y.next_plus(context=ctx))


class IV:
    __slots__=('lo','hi')
    def __init__(self,lo,hi=None):
        a,b=value(lo),value(lo if hi is None else hi)
        if a>b: raise ValueError('Invalid interval')
        # Inputs may have more significant digits than context's precision.
        # Construct outward endpoints, rather than silently truncating.
        self.lo=op('add',a,D(0),ROUND_FLOOR)
        self.hi=op('add',b,D(0),ROUND_CEILING)
    @classmethod
    def raw(cls,a,b):
        r=object.__new__(cls);r.lo,r.hi=a,b
        if a>b or not a.is_finite() or not b.is_finite():raise ArithmeticError('Invalid interval result')
        return r
    @classmethod
    def rational(cls,frac:Fraction):
        f=Fraction(frac)
        return cls.raw(op('div',D(f.numerator),D(f.denominator),ROUND_FLOOR),
                       op('div',D(f.numerator),D(f.denominator),ROUND_CEILING))
    @staticmethod
    def cv(z):return z if isinstance(z,IV) else IV(z)
    def __add__(self,o):
        o=self.cv(o)
        return IV.raw(op('add',self.lo,o.lo),op('add',self.hi,o.hi,ROUND_CEILING))
    __radd__=__add__
    def __neg__(self):return IV.raw(-self.hi,-self.lo)
    def __sub__(self,o):return self+-self.cv(o)
    def __rsub__(self,o):return self.cv(o)-self
    def __mul__(self,o):
        o=self.cv(o)
        pairs=((a,b) for a in (self.lo,self.hi) for b in (o.lo,o.hi))
        vals=list(pairs)
        return IV.raw(min(op('mul',a,b) for a,b in vals),
                      max(op('mul',a,b,ROUND_CEILING) for a,b in vals))
    __rmul__=__mul__
    def __truediv__(self,o):
        o=self.cv(o)
        if o.lo<=0<=o.hi:raise ArithmeticError('Interval division by zero-containing interval')
        inv=IV.raw(op('div',D(1),o.hi),op('div',D(1),o.lo,ROUND_CEILING))
        return self*inv
    def __rtruediv__(self,o):return self.cv(o)/self
    def exp(self):return IV.raw(trans('exp',self.lo)[0],trans('exp',self.hi)[1])
    def ln(self):
        if self.lo<=0:raise ArithmeticError('Nonpositive interval ln')
        return IV.raw(trans('ln',self.lo)[0],trans('ln',self.hi)[1])
    def square_nonnegative(self):
        if self.lo<0:raise ArithmeticError('Expected nonnegative interval')
        return self*self
    def contains(self,x):return self.lo<=value(x)<=self.hi
    def __repr__(self):return f'[{self.lo},{self.hi}]'
