"""CH40-E producer-side observer, used only in a SHA256-verified research copy.

The historical MPFR solver and coupled bound arithmetic are left unchanged;
observers read completed results and preserve exact binary MPFR endpoints.  An
independent checker must still justify each numerical upper-bound assertion.
"""
from __future__ import annotations
import ctypes as C
import ctypes.util
import hashlib
import json
from fractions import Fraction
from mpfr_interval import MP, Interval

_LIB=C.CDLL(ctypes.util.find_library('mpfr'))
_LIB.mpfr_get_str.argtypes=[C.c_void_p,C.POINTER(C.c_long),C.c_int,C.c_size_t,C.c_void_p,C.c_int]
_LIB.mpfr_get_str.restype=C.c_void_p
_LIB.mpfr_free_str.argtypes=[C.c_void_p]
_LIB.mpfr_free_str.restype=None

NODES=[]

def mp_exact(m:MP):
    """Save exact base-2 MPFR significand/exponent; NEVER binary64 display."""
    exponent=C.c_long()
    p=_LIB.mpfr_get_str(None,C.byref(exponent),2,0,C.byref(m.raw),0)
    if not p:raise RuntimeError('Cannot export exact MPFR endpoint')
    try:s=C.string_at(p).decode('ascii')
    finally:_LIB.mpfr_free_str(p)
    sign='-' if s.startswith('-') else ''
    digits=s.lstrip('-')
    if not digits or not set(digits)<=set('01'):raise ValueError('Invalid MPFR bits')
    return {'significand':sign+digits,'exponent':exponent.value}

def iv_exact(iv:Interval):return [mp_exact(iv.lo),mp_exact(iv.hi)]

def f_of(d):
    s=d['significand'];sgn=-1 if s.startswith('-') else 1;bits=s.lstrip('-')
    num=sgn*int(bits,2);shift=d['exponent']-len(bits)
    if abs(shift)>10000:raise ValueError('MPFR exponent exceeds allowed research range')
    return Fraction(num*(2**max(shift,0)),2**max(-shift,0))

def record_node(rec,direct,bound,cap,parentcap,model):
    # Called from the original solver AFTER all directed-rounding comparisons.
    trace={
        'id':rec['id'],'parent':rec.get('parent_id'),'box':rec['effective_box'],
        'mode':rec['bound_mode'],'method':rec['upper_method'],
        'direct':iv_exact(direct),'direct_trace':getattr(model,'_ch40e_direct',None),'local':iv_exact(bound),
        'effective_cap':mp_exact(cap),'parent_cap':mp_exact(parentcap) if parentcap is not None else None,
        'display_local':rec['local_upper_bound_display'],
        'display_effective':rec['upper_bound_ceil_display'],
        'dual_candidates':getattr(model,'_ch40e_observed',[]) if rec['bound_mode']=='coupled' else []
    }
    NODES.append(trace)


def record_dual(qindex,const,kappas,rows,total):
    return {'q_index':qindex,'constant':iv_exact(const),
            'kappa':[mp_exact(q.hi) for q in kappas],
            'rows':rows,'computed_total_hi':mp_exact(total.hi)}
