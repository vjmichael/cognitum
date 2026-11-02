"""CH-C14-24 directed MPFR real interval arithmetic (Linux research prototype).

Each endpoint is an MPFR number. All primitive operations round explicitly:
RNDD for lower endpoints, RNDU for upper endpoints. The library's exp/log
implement correct directed rounding as specified by MPFR (not Python float).
MPFR absence or invalid domains raise, never fall back to binary64.
"""
from __future__ import annotations

import ctypes as C
import ctypes.util
from decimal import Decimal


class _M(C.Structure):
    _fields_ = [("_mpfr_prec", C.c_long), ("_mpfr_sign", C.c_int),
                ("_mpfr_exp", C.c_long), ("_mpfr_d", C.POINTER(C.c_ulong))]


_LIBNAME = ctypes.util.find_library("mpfr")
if not _LIBNAME:
    raise RuntimeError("CERTIFICATION_UNAVAILABLE: MPFR library not found")
_L = C.CDLL(_LIBNAME)
_PTR = C.POINTER(_M)


def _fn(name, args, result=C.c_int):
    func = getattr(_L, "mpfr_" + name)
    func.argtypes = args
    func.restype = result
    return func


_init = _fn("init2", [_PTR, C.c_long], None)
_clear = _fn("clear", [_PTR], None)
_set_str = _fn("set_str", [_PTR, C.c_char_p, C.c_int, C.c_int])
_set = _fn("set", [_PTR, _PTR, C.c_int])
_add = _fn("add", [_PTR, _PTR, _PTR, C.c_int])
_sub = _fn("sub", [_PTR, _PTR, _PTR, C.c_int])
_mul = _fn("mul", [_PTR, _PTR, _PTR, C.c_int])
_div = _fn("div", [_PTR, _PTR, _PTR, C.c_int])
_neg = _fn("neg", [_PTR, _PTR, C.c_int])
_exp = _fn("exp", [_PTR, _PTR, C.c_int])
_log = _fn("log", [_PTR, _PTR, C.c_int])
_cmp = _fn("cmp", [_PTR, _PTR])
_number = _fn("number_p", [_PTR])
_get_d = _fn("get_d", [_PTR, C.c_int], C.c_double)

DOWN, UP = 3, 2
PRECISION = 160


class MP:
    __slots__ = ("raw",)

    def __init__(self, value="0", rounding=DOWN):
        self.raw = _M()
        _init(C.byref(self.raw), PRECISION)
        if isinstance(value, MP):
            _set(C.byref(self.raw), C.byref(value.raw), rounding)
        else:
            if isinstance(value, float):
                raise TypeError("Float inputs forbidden: use exact decimal strings")
            if _set_str(C.byref(self.raw), str(value).encode(), 10, rounding) != 0:
                raise ValueError("Invalid MPFR decimal input")
        if not _number(C.byref(self.raw)):
            raise ValueError("Nonfinite MPFR value")

    def __del__(self):
        if getattr(self, "raw", None) is not None:
            _clear(C.byref(self.raw))

    def cmp(self, other):
        return _cmp(C.byref(self.raw), C.byref(other.raw))

    def as_float(self, mode=UP):
        return _get_d(C.byref(self.raw), mode)


def _op(fun, x, y, mode):
    z = MP()
    fun(C.byref(z.raw), C.byref(x.raw), C.byref(y.raw), mode)
    if not _number(C.byref(z.raw)):
        raise ArithmeticError("MPFR operation not finite")
    return z


def _unary(fun, x, mode):
    z = MP()
    fun(C.byref(z.raw), C.byref(x.raw), mode)
    if not _number(C.byref(z.raw)):
        raise ArithmeticError("MPFR transcendental/operation not finite")
    return z


class Interval:
    __slots__ = ("lo", "hi")

    def __init__(self, low="0", high=None):
        self.lo = MP(low, DOWN)
        self.hi = MP(low if high is None else high, UP)
        if self.lo.cmp(self.hi) > 0:
            raise ValueError("Interval inverted")

    @classmethod
    def from_ends(cls, a, b):
        obj = object.__new__(cls)
        obj.lo, obj.hi = a, b
        if a.cmp(b) > 0:
            raise ValueError("Interval inverted")
        return obj

    @staticmethod
    def coerce(other):
        return other if isinstance(other, Interval) else Interval(other)

    def __add__(self, other):
        b = self.coerce(other)
        return self.from_ends(_op(_add, self.lo, b.lo, DOWN), _op(_add, self.hi, b.hi, UP))
    __radd__ = __add__

    def __neg__(self):
        return self.from_ends(_unary(_neg, self.hi, DOWN), _unary(_neg, self.lo, UP))

    def __sub__(self, other):
        return self + (-self.coerce(other))

    def __rsub__(self, other):
        return self.coerce(other) - self

    def __mul__(self, other):
        b = self.coerce(other)
        aa = (self.lo, self.hi)
        bb = (b.lo, b.hi)
        lower = [_op(_mul, a, c, DOWN) for a in aa for c in bb]
        upper = [_op(_mul, a, c, UP) for a in aa for c in bb]
        lo = min(lower, key=lambda x: x.as_float(DOWN))
        hi = max(upper, key=lambda x: x.as_float(UP))
        # Float-derived sort keys are NOT used for proof: explicitly compare MPFR.
        for x in lower:
            if x.cmp(lo) < 0:
                lo = x
        for x in upper:
            if x.cmp(hi) > 0:
                hi = x
        return self.from_ends(lo, hi)
    __rmul__ = __mul__

    def __truediv__(self, other):
        b = self.coerce(other)
        zero = MP("0")
        if b.lo.cmp(zero) <= 0 and b.hi.cmp(zero) >= 0:
            raise ArithmeticError("Division interval contains zero")
        one = MP("1")
        reciprocal = self.from_ends(_op(_div, one, b.hi, DOWN), _op(_div, one, b.lo, UP))
        return self * reciprocal

    def __rtruediv__(self, other):
        return self.coerce(other) / self

    def exp(self):
        return self.from_ends(_unary(_exp, self.lo, DOWN), _unary(_exp, self.hi, UP))

    def log(self):
        if self.lo.cmp(MP("0")) <= 0:
            raise ArithmeticError("Log interval is not strictly positive")
        return self.from_ends(_unary(_log, self.lo, DOWN), _unary(_log, self.hi, UP))

    def contains(self, number: str):
        return self.lo.cmp(MP(number, DOWN)) <= 0 and self.hi.cmp(MP(number, UP)) >= 0

    def mid_approx(self):
        return (self.lo.as_float(DOWN) + self.hi.as_float(UP)) / 2

    def upper_float(self):
        return self.hi.as_float(UP)

    def lower_float(self):
        return self.lo.as_float(DOWN)

    def __repr__(self):
        return f"I({self.lower_float():.15g}, {self.upper_float():.15g})"


def up_abs(a: Interval) -> Interval:
    """Certified upper bound for |a|, as interval [0,U]."""
    z = Interval("0")
    lo_abs = (-Interval.from_ends(a.lo, a.lo)) if a.lo.cmp(MP("0")) < 0 else Interval.from_ends(a.lo, a.lo)
    hi_abs = (-Interval.from_ends(a.hi, a.hi)) if a.hi.cmp(MP("0")) < 0 else Interval.from_ends(a.hi, a.hi)
    upper = lo_abs.hi if lo_abs.hi.cmp(hi_abs.hi) >= 0 else hi_abs.hi
    return Interval.from_ends(z.lo, upper)


def upper_min(a: Interval, b: Interval) -> Interval:
    """Return an upper bound on min of two sound upper bounds."""
    return Interval.from_ends(MP("0"), a.hi if a.hi.cmp(b.hi) <= 0 else b.hi)


def nonpositive(a: MP) -> bool:
    return a.cmp(MP("0")) <= 0


def checked_threshold(upper: MP, lower: MP, eps: str) -> bool:
    # Compare U <= L + eps conservatively. L+eps is rounded DOWN.
    limit = _op(_add, lower, MP(eps, DOWN), DOWN)
    return upper.cmp(limit) <= 0
