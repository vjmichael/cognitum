"""Research-only 256-bit native MPFR producer of CH40's existing PSD-Gram bound.

Mathematical formula is the same as CH40-M5F's Arb producer. Exact parameter
linear-form extrema and Gram determinants use Fraction; MPFR handles only
transcendental endpoints and uses directed rounding. Never claims global proof.
"""
from __future__ import annotations
from decimal import Decimal,localcontext,ROUND_FLOOR,ROUND_CEILING
from fractions import Fraction as F
import ctypes as C
import ctypes.util
from pathlib import Path

L=C.CDLL(C.util.find_library('mpfr') or 'libmpfr.so.6')
class _M(C.Structure):
    _fields_=[('_mpfr_prec',C.c_long),('_mpfr_sign',C.c_int),('_mpfr_exp',C.c_long),('_mpfr_d',C.c_void_p)]
P=C.POINTER(_M)
def bind(name,arg,ret=C.c_int):
    f=getattr(L,'mpfr_'+name);f.argtypes=arg;f.restype=ret;return f
_init=bind('init2',[P,C.c_long],None); _clear=bind('clear',[P],None)
_set=bind('set_str',[P,C.c_char_p,C.c_int,C.c_int])
_add=bind('add',[P,P,P,C.c_int]);_mul=bind('mul',[P,P,P,C.c_int])
_exp=bind('exp',[P,P,C.c_int]);_log=bind('log',[P,P,C.c_int]); _div=bind('div',[P,P,P,C.c_int]);_neg=bind('neg',[P,P,C.c_int])
_get=bind('get_str',[C.c_void_p,C.POINTER(C.c_long),C.c_int,C.c_size_t,P,C.c_int],C.c_void_p)
_free=bind('free_str',[C.c_void_p],None)
DOWN=3;UP=2;PREC=256
class MP:
    def __init__(self):
        self.raw=_M();_init(C.byref(self.raw),PREC)
    def __del__(self):
        if hasattr(self,'raw'): _clear(C.byref(self.raw))
    @staticmethod
    def decimal(s,rnd):
        obj=MP(); rc=_set(C.byref(obj.raw),str(s).encode('ascii'),10,rnd)
        if rc:raise ValueError('mpfr_set_str failed')
        return obj
    def string(self,rnd=UP):
        exp=C.c_long()
        ptr=_get(None,C.byref(exp),10,0,C.byref(self.raw),rnd)
        if not ptr:raise ArithmeticError('mpfr_get_str failed')
        try:s=C.string_at(ptr).decode()
        finally:_free(ptr)
        sign='-' if s.startswith('-') else ''
        s=s.lstrip('-')
        return sign+s[0]+('.'+s[1:] if len(s)>1 else '')+'e'+str(exp.value-1)
def calc(op,a,b=None,rnd=UP):
    c=MP();args=[C.byref(c.raw),C.byref(a.raw)]
    if b is not None:args.append(C.byref(b.raw))
    op(*args,rnd)
    return c

def decimal_bracket(q):
    q=F(q)
    with localcontext() as ctx:
        ctx.prec=110;ctx.rounding=ROUND_FLOOR
        lo=Decimal(q.numerator)/Decimal(q.denominator)
        ctx.rounding=ROUND_CEILING
        hi=Decimal(q.numerator)/Decimal(q.denominator)
    return str(lo),str(hi)

def at(q):
    lo,hi=decimal_bracket(q)
    return MP.decimal(lo,DOWN),MP.decimal(hi,UP)

def lower_log_one_plus_exp(q):
    """Downward bound on log(1+exp(q)), for a *negative* likelihood term."""
    qlo,_=at(q)
    z=calc(_exp,qlo,rnd=DOWN)
    one,_=at(F(1))
    w=calc(_add,one,z,rnd=DOWN)
    return calc(_log,w,rnd=DOWN)

def neg_scaled_upper(x,n):
    """Upper of -n*x where x is a *lower* bound; n is positive integer."""
    tmp=calc(_neg,x,rnd=UP)
    nn,_=at(F(n))
    return F(calc(_mul,tmp,nn,rnd=UP).string(UP))

def log_frac_upper(q):
    if q<=0:raise ValueError('log requires positive rational')
    _,hi=at(q)
    return F(calc(_log,hi,rnd=UP).string(UP))

def weight_ceiling(q):
    """One exact t endpoint. w(t)=1/(2+exp(t)+exp(-t))."""
    lo,hi=at(q)
    z=calc(_exp,lo,rnd=DOWN)
    minus=calc(_neg,hi,rnd=DOWN)
    zn=calc(_exp,minus,rnd=DOWN)
    two,_=at(F(2));one,_=at(F(1))
    den=calc(_add,calc(_add,two,z,rnd=DOWN),zn,rnd=DOWN)
    return min(F(1,4),F(calc(_div,one,den,rnd=UP).string(UP)))

def upper(cert,box):
    from gram_psd import eta_extrema,gram3,det3
    rows=cert['model']['rows']
    if cert['model']['d']!=3 or not (0<len(rows)<=1000) or len(box)!=3:
        raise ValueError('Frozen 3D model required')
    ll=F(0);wt=[]
    for row in rows:
        n,s=row['n'],row['s']
        if type(n) is not int or type(s) is not int or n<1 or not 0<=s<=n:
            raise ValueError('Invalid row counts')
        zlo,zhi=eta_extrema(row,box)
        if s==0:
            ll+=neg_scaled_upper(lower_log_one_plus_exp(zlo),n)
        elif s==n:
            ll+=neg_scaled_upper(lower_log_one_plus_exp(-zhi),n)
        else:
            p=F(s,n)
            ll+=s*log_frac_upper(p)+(n-s)*log_frac_upper(1-p)
        t=None if zlo<=0<=zhi else (zlo if abs(zlo)<=abs(zhi) else zhi)
        wt.append(F(1,4) if t is None else weight_ceiling(t))
    G=gram3(rows,wt);D=det3(G)
    if D<=0:raise ArithmeticError('SPD Gram determinant not established')
    cap=ll+F(1,2)*log_frac_upper(D)
    return {'gram_upper':cap,'likelihood_upper':ll,'weights_upper':wt,'det_gram':D,
            'precision_bits':PREC,'engine':'libmpfr_256','bound_rule':'PSD_GRAM_DOMINANCE'}
