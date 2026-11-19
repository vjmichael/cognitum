"""Independent MEL-05B interval reference for the bounded mathematical profile.

No worker kernel, NumPy, statistics, learned calibration or authorization here.
Exact rational algebra and outward-rounded Decimal exponential enclosures.
The enclosure describes an ideal real composition of represented parameters,
not unknown physical inputs, training uncertainty, or float32 execution itself.
"""
from dataclasses import dataclass
from decimal import Context, Decimal, ROUND_FLOOR, ROUND_CEILING, ROUND_HALF_EVEN, InvalidOperation, DivisionByZero, Overflow
from fractions import Fraction as F
import math
import struct

MAX_BITS = 8192
MAX_ROWS = 16
MAX_TERMS = 32


def require(ok, why):
    if not ok:
        raise ValueError(why)


def rational(x):
    require(type(x) in (int, float, F) and (type(x) != float or math.isfinite(x)), 'finite represented number')
    q = F(x)
    require(max(q.numerator.bit_length(), q.denominator.bit_length()) <= MAX_BITS, 'rational budget')
    return q


@dataclass(frozen=True, slots=True)
class Interval:
    lo: F
    hi: F

    def __post_init__(self):
        require(type(self.lo) is F and type(self.hi) is F and self.lo <= self.hi, 'ordered rational enclosure')
        rational(self.lo); rational(self.hi)

    @classmethod
    def point(cls, x):
        q = rational(x)
        return cls(q, q)

    def __add__(self, other):
        return Interval(self.lo + other.lo, self.hi + other.hi)

    def __neg__(self):
        return Interval(-self.hi, -self.lo)

    def __sub__(self, other):
        return self + (-other)

    def __mul__(self, other):
        p = [a*b for a in (self.lo, self.hi) for b in (other.lo, other.hi)]
        return Interval(min(p), max(p))

    def reciprocal(self):
        require(not self.lo <= 0 <= self.hi, 'interval division by zero')
        return Interval(1/self.hi, 1/self.lo)

    def square(self):
        lo, hi = self.lo**2, self.hi**2
        return Interval(F(0) if self.lo <= 0 <= self.hi else min(lo, hi), max(lo, hi))

    def scale(self, q):
        return self * Interval.point(q)

    def contains(self, x):
        q = rational(x)
        return self.lo <= q <= self.hi

    def error(self, observation):
        y = rational(observation)
        return Interval(max(F(0), self.lo-y, y-self.hi), max(abs(y-self.lo), abs(y-self.hi)))


def hull(xs):
    return Interval(min(x.lo for x in xs), max(x.hi for x in xs))


def exp_minus(q):
    """q >= 0; independent directed arguments, adjacent Decimal exp bounds.

    Truncate to a fixed dyadic grid *outward*, keeping rational growth bounded.
    For large q use e > 2, not a rounded zero.
    """
    require(type(q) is F and q >= 0, 'nonnegative exponent')
    if q == 0:
        return Interval.point(1)
    if q >= 256:
        return Interval(F(0), F(1, 2**256))
    down = Context(prec=80, rounding=ROUND_FLOOR, Emin=-999999, Emax=999999, capitals=1, clamp=0, flags=[], traps=[InvalidOperation, DivisionByZero, Overflow])
    up = Context(prec=80, rounding=ROUND_CEILING, Emin=-999999, Emax=999999, capitals=1, clamp=0, flags=[], traps=[InvalidOperation, DivisionByZero, Overflow])
    near = Context(prec=80, rounding=ROUND_HALF_EVEN, Emin=-999999, Emax=999999, capitals=1, clamp=0, flags=[], traps=[InvalidOperation, DivisionByZero, Overflow])
    a, b = Decimal(-q.numerator), Decimal(q.denominator)
    low = F(down.next_minus(near.exp(down.divide(a,b))))
    high = F(up.next_plus(near.exp(up.divide(a,b))))
    grid = 2**192
    return Interval(max(F(0), F(low*grid//1, grid)), min(F(1), F(-((-high*grid)//1), grid)))


def gaussian(q):
    require(q.lo >= 0, 'squared distance enclosure')
    return Interval(exp_minus(q.hi).lo, exp_minus(q.lo).hi)


def f32(x):
    q = struct.unpack('<f', struct.pack('<f', x))[0]
    require(math.isfinite(q) and q == x, 'exact binary32 parameter required')
    return F(q)


def previous_f32(x):
    f = float(x)
    f32(f)
    bits = struct.unpack('<I', struct.pack('<f', f))[0]
    bits = 0x80000001 if f == 0 else bits-1 if f > 0 else bits+1
    return F(struct.unpack('<f', struct.pack('<I', bits))[0])


def _spline_span(z, grid, degree, span):
    # Closed span enclosure, with a fixed half-open indicator for its interior.
    # At a discontinuous knot both one-sided values may be included conservatively.
    basis = [Interval.point(int(i == span)) for i in range(len(grid)-1)]
    for k in range(1, degree+1):
        basis = [(z-Interval.point(grid[i])).scale(1/(grid[i+k]-grid[i])) * basis[i]
                 + (Interval.point(grid[i+k+1])-z).scale(1/(grid[i+k+1]-grid[i+1])) * basis[i+1]
                 for i in range(len(basis)-1)]
    # B-splines on strictly separated knots are nonnegative, at most one.
    return [Interval(max(F(0), b.lo), min(F(1), b.hi)) for b in basis]


def spline(z, grid, degree):
    require(grid[0] <= z.lo <= z.hi <= grid[-1], 'uncertain input outside KAN knot domain')
    if z.lo == z.hi == grid[-1]:
        z = Interval.point(previous_f32(grid[-1]))
    if z.lo == z.hi:
        i = next(i for i in range(len(grid)-1) if grid[i] <= z.lo < grid[i+1])
        return _spline_span(z, grid, degree, i)
    pieces = []
    for i in range(len(grid)-1):
        lo, hi = max(z.lo, grid[i]), min(z.hi, grid[i+1])
        if lo <= hi:
            pieces.append(_spline_span(Interval(lo,hi), grid, degree,i))
    if z.hi == grid[-1]:
        pieces.append(spline(Interval.point(grid[-1]),grid,degree))
    return [hull(col) for col in zip(*pieces)]


def rbf(z, grid):
    require(grid[0] <= z.lo <= z.hi <= grid[-1], 'uncertain input outside KAN knot domain')
    floor = F(struct.unpack('<f',struct.pack('<f',1e-4))[0])
    scale = max((grid[-1]-grid[0])/(len(grid)-1),floor)
    return [gaussian((z-Interval.point(g)).scale(1/scale).square()) for g in grid]


def _sigmoid_point(x):
    x = max(F(-70), min(F(70), x))
    e = exp_minus(abs(x)); one = Interval.point(1)
    return (one+e).reciprocal() if x >= 0 else e*(one+e).reciprocal()


def silu(z):
    # Monotone clipped sigmoid, multiplied by the original signed input.
    return z * Interval(_sigmoid_point(z.lo).lo, _sigmoid_point(z.hi).hi)


def kan_bounds(layers, rows, *, check=lambda:None):
    """Pure independent interpretation of the existing EngineRequest KanLayer fields.

    Parameters are represented binary32; intermediate mathematical values are
    real intervals (no approximation of actual float32 rounding). Observation
    discrepancy is checked separately, including all worker arithmetic error.
    """
    require(1 <= len(layers) <= 2 and 1 <= len(rows) <= MAX_ROWS, 'KAN verification size')
    z = tuple(tuple(row) for row in rows)
    for layer in layers:
        check()
        i,o,k,d = layer.inputs,layer.outputs,layer.knots,layer.degree
        require(1<=i<=8 and 1<=o<=8 and 3<=k<=12 and all(len(row)==i and all(type(v) is Interval for v in row) for row in z), 'KAN shape')
        require((layer.basis==1 and 0<=d<=3 and k-d-1>0) or (layer.basis==2 and d==0), 'KAN basis')
        count = k-d-1 if layer.basis==1 else k
        def params(values, size):
            require(len(values)==size,'KAN parameter shape')
            out=tuple(f32(v) for v in values)
            require(all(abs(v)<=1000 for v in out),'KAN parameter range')
            return out
        grid=params(layer.grid,i*k); w=params(layer.coefficients,o*i*count); mask=params(layer.mask,o*i)
        require(all(v in (0,1) for v in mask),'KAN binary mask')
        base=params(layer.base,o*i) if layer.base else (F(0),)*(o*i)
        bias=params(layer.bias,o) if layer.bias else (F(0),)*o
        grids=[grid[j*k:(j+1)*k] for j in range(i)]
        require(all(all(b>a for a,b in zip(g,g[1:])) for g in grids),'KAN knot separation')
        out=[]
        for row in z:
            check()
            bases=[spline(v,g,d) if layer.basis==1 else rbf(v,g) for v,g in zip(row,grids)]
            bs=[silu(v) if any(base[a*i+j]*mask[a*i+j] for a in range(o)) else Interval.point(0) for j,v in enumerate(row)]
            rr=[]
            for a in range(o):
                check()
                t=Interval.point(bias[a])
                for j in range(i):
                    edge=a*i+j
                    if not mask[edge]: continue
                    for l,b in enumerate(bases[j]):
                        t=t+b.scale(w[edge*count+l])
                    t=t+bs[j].scale(base[edge])
                rr.append(t)
            out.append(tuple(rr))
        z=tuple(out)
    return z


def vfa_bounds(function, rows, *, check=lambda:None):
    """Bounded Gaussian VFA value propagation, not arbitrary functions."""
    t,d = function.shape
    require(0<=t<=MAX_TERMS and 1<=d<=8 and 1<=len(rows)<=MAX_ROWS, 'VFA propagation budget')
    mix=function.function
    centers=tuple(map(rational,mix.centers)); widths=tuple(map(rational,mix.widths)); weights=tuple(map(rational,mix.weights))
    require(len(centers)==len(widths)==t*d and len(weights)==t and all(w>0 for w in widths), 'VFA parameters')
    out=[]
    for row in rows:
        check()
        require(len(row)==d and all(type(v) is Interval for v in row),'VFA shape')
        require(all(rational(dom.lower)<=v.lo<=v.hi<=rational(dom.upper) for dom,v in zip(function.domain,row)) and len(function.domain)==d,'uncertain input outside VFA domain')
        y=Interval.point(mix.constant)
        for k,w in enumerate(weights):
            check()
            if not w:continue
            q=Interval.point(0)
            for j,v in enumerate(row):
                q=q+(v-Interval.point(centers[k*d+j])).scale(1/widths[k*d+j]).square()
            y=y+gaussian(q.scale(F(1,2))).scale(w)
        out.append((y,))
    return tuple(out)


def threshold_bit(bounds, at_least, observed):
    """Inclusive >= threshold: crossing or contradicted observation is refused."""
    t=rational(at_least); y=rational(observed)
    bit=1 if bounds.lo>=t else 0 if bounds.hi<t else None
    if bit is None:return 'ambiguous',None
    if bit != int(y>=t):return 'contradicted',None
    return 'verified',bit


def error_verdict(bounds, observed, tolerance):
    t=rational(tolerance); require(t>=0,'negative tolerance')
    err=bounds.error(observed)
    return 'within' if err.hi<=t else 'outside' if err.lo>t else 'inconclusive'
