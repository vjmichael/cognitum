"""COG-04I: residual-trained scalar cubic KAN, continuous rational verification.

Bounded research profile on [0,1]: stable linear IVP u'+a*u=f and
coercive Dirichlet BVP -u''+a*u=f, a>=0; polynomial forcing. No routing,
training authorization, generic nonlinear/PDE or floating evaluation guarantee.
"""
from dataclasses import dataclass
from fractions import Fraction as Q
from math import comb, isfinite
import hashlib
import json
import numpy as np
from .kan_trainable import Layer, Network
from cognitum.mel import polynomial_witness as w

MAX_REFINEMENTS = 4  # existing cubic checkpoint: at most 12 knots
MAX_FORCING_DEGREE = 8


def need(ok, message):
    if not ok:
        raise ValueError(message)


def _number(x):
    need(type(x) in (int, float) and abs(x) <= 100 and isfinite(x), 'bounded finite scalar')
    return Q(x)


@dataclass(frozen=True, slots=True)
class Problem:
    kind: str
    reaction: float
    forcing: tuple
    left: float
    right: float | None = None

    def __post_init__(self):
        need(self.kind in ('ivp', 'bvp') and type(self.kind) is str, 'unsupported equation')
        need(_number(self.reaction) >= 0, 'stability requires nonnegative reaction')
        need(type(self.forcing) is tuple and 1 <= len(self.forcing) <= MAX_FORCING_DEGREE + 1, 'forcing polynomial profile')
        for c in self.forcing:
            _number(c)
        _number(self.left)
        if self.kind == 'bvp':
            _number(self.right)
        else:
            need(self.right is None, 'IVP must have only initial data')

    @property
    def identity(self):
        fields = [self.kind, str(_number(self.reaction)), [str(_number(c)) for c in self.forcing], str(_number(self.left)), None if self.right is None else str(_number(self.right))]
        return hashlib.sha256(json.dumps(fields, separators=(',', ':')).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class Span:
    lower: Q
    upper: Q
    residual_upper: Q
    residual_squared_l2: Q


@dataclass(frozen=True, slots=True)
class Certificate:
    problem_sha256: str
    model_sha256: str
    spans: tuple
    condition_errors: tuple
    residual_upper: Q
    squared_l2: Q
    solution_error_upper: Q | None


def _eval(poly, x):
    return w.evaluate(poly, (x, x))[0]


def _bernstein_abs(p, a, b):
    # Exact enclosure on the WHOLE span, including endpoints, not sampling.
    n = len(p) - 1
    power = [w.cap(sum((p[k] * comb(k, j) * a ** (k-j) * (b-a) ** j for k in range(j, n+1)), Q(0))) for j in range(n+1)]
    coeff = [w.cap(sum((power[j] * Q(comb(i,j), comb(n,j)) for j in range(i+1)), Q(0))) for i in range(n+1)]
    return max(map(abs, coeff))


def _square_integral(p, a, b):
    v = w.times(p, p)
    value = w.cap(sum((c * (b ** (i+1) - a ** (i+1)) / (i+1) for i,c in enumerate(v)), Q(0)))
    need(value >= 0, 'invalid squared residual')
    return value


def assess(problem, model):
    """Replay actual binary64 model parameters as exact rationals. No NumPy
    derivative, solver samples, optimiser state or analytic target in checker.
    Prove C2 continuity and enforce exact endpoint traces. For valid traces,
    error <= R on stable IVP (integrating factor), <= R/8 on Dirichlet BVP
    (comparison with x(1-x)/2), where R is supremum residual enclosure.
    """
    need(type(problem) is Problem and type(model) is Network and len(model.layers)==1, 'typed scalar network')
    l = model.layers[0]
    need(l.kind=='spline_clamped' and l.degree==3 and l.inputs==l.outputs==1 and l.mask[0,0]==1 and l.bias[0]==0, 'cubic scalar edge profile')
    g = tuple(map(w.q, l.grid[0])); coeff = tuple(map(w.q, l.coefficients[0,0]))
    need(g[0]==0 and g[-1]==1, 'unit domain required')
    a = _number(problem.reaction); f = tuple(map(_number, problem.forcing))
    spans=[]; previous=None; left=None; right=None
    for k,(lo,hi) in enumerate(zip(g,g[1:])):
        if lo==hi:
            continue
        p=(Q(0),)
        for c,b in zip(coeff,w.spline_polys(g,3,k)):
            p=w.plus(p,w.scale(b,c))
        d=w.diff(p); h=w.diff(d)
        start=tuple(_eval(v,lo) for v in (p,d,h)); end=tuple(_eval(v,hi) for v in (p,d,h))
        if previous is not None:
            need(start==previous, 'C2 knot continuity failed')
        else:
            left=start[0]
        right=end[0]; previous=end
        differential=d if problem.kind=='ivp' else w.scale(h,Q(-1))
        residual=w.plus(w.plus(differential,w.scale(p,a)),w.scale(f,Q(-1)))
        spans.append(Span(lo,hi,_bernstein_abs(residual,lo,hi),_square_integral(residual,lo,hi)))
    traces=(left-_number(problem.left),)
    if problem.kind=='bvp':
        traces+=(right-_number(problem.right),)
    upper=max(s.residual_upper for s in spans)
    error=(upper if problem.kind=='ivp' else upper/8) if not any(traces) else None
    return Certificate(problem.identity,model.research_snapshot()[1],tuple(spans),traces,upper,w.cap(sum((s.residual_squared_l2 for s in spans),Q(0))),error)


def replay(problem, model, certificate):
    need(type(certificate) is Certificate and assess(problem,model)==certificate, 'certificate replay mismatch')
    return certificate


def require_accuracy(problem, model, certificate, tolerance):
    t=_number(tolerance); need(t>0,'positive tolerance required')
    c=replay(problem,model,certificate)
    need(c.solution_error_upper is not None and c.solution_error_upper<=t, 'accuracy/condition budget unmet')
    return c


def _fit(problem, cuts):
    grid=[0.]*4+list(cuts)+[1.]*4;n=len(grid)-4
    empty=Layer('spline_clamped',3,[grid],np.zeros((1,1,n)),[[1.]],[0.])
    # Fixed interior quadrature, enough nodes for squared polynomial residual.
    z,weights=np.polynomial.legendre.leggauss(10)
    xs=[]; ws=[]
    for l,r in zip((0.,*cuts),(*cuts,1.)):
        xs.extend(l+(z+1)*(r-l)/2); ws.extend(weights*(r-l)/2)
    x=np.array(xs); weights=np.sqrt(ws)
    basis=empty.basis(x[:,None],2)
    a=float(problem.reaction)
    operator=(basis[1] if problem.kind=='ivp' else -basis[2])+a*basis[0]
    A=operator[:,0,:]; b=np.polynomial.polynomial.polyval(x,problem.forcing)
    # Clamped endpoint coefficients set exactly, not a soft loss penalty.
    fixed={0:float(problem.left)}
    if problem.kind=='bvp':fixed[n-1]=float(problem.right)
    free=[i for i in range(n) if i not in fixed]; c=np.zeros(n)
    for i,v in fixed.items(): c[i]=v; b=b-A[:,i]*v
    sol,_,rank,_=np.linalg.lstsq(A[:,free]*weights[:,None],b*weights,rcond=None)
    need(rank==len(free) and np.isfinite(sol).all(),'rank deficient/nonfinite fit')
    c[free]=sol
    return Network((empty.updated(c.reshape(1,1,n),[0.]),))


@dataclass(frozen=True, slots=True)
class Fit:
    model: Network
    certificate: Certificate
    history: tuple  # verified accepted stages only, no target labels
    converged: bool


def fit(problem,tolerance=0.01,max_refinements=MAX_REFINEMENTS):
    need(type(problem) is Problem and type(max_refinements) is int and 0<=max_refinements<=MAX_REFINEMENTS,'refinement budget')
    t=_number(tolerance);need(t>0,'positive tolerance required')
    cuts=(); model=_fit(problem,cuts); cert=assess(problem,model)
    need(cert.solution_error_upper is not None,'hard condition failure')
    history=[cert]
    for _ in range(max_refinements):
        if cert.solution_error_upper<=t:break
        # Rank spans by independently verified residual; try in descending order.
        # Keep only strict certified full-domain error improvement.
        for span in sorted(cert.spans,key=lambda s:(-s.residual_upper,s.lower)):
            mid=float((span.lower+span.upper)/2)
            candidate_cuts=tuple(sorted((*cuts,mid)))
            candidate=_fit(problem,candidate_cuts); c=assess(problem,candidate)
            if c.solution_error_upper is not None and c.solution_error_upper<cert.solution_error_upper:
                model,cert,cuts=candidate,c,candidate_cuts;history.append(c);break
        else:break
    return Fit(model,cert,tuple(history),cert.solution_error_upper<=t)
