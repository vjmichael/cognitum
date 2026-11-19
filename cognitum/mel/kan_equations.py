"""COG-04H: exact finite polynomial trial-space differential equation solving.

Scalar linear ODE/PDE on rational Cartesian boxes. A successful witness proves
identities for the represented polynomial, not general well-posedness or learned
accuracy. No routing, model authorization, or approximation fallback.
"""
from dataclasses import dataclass
from fractions import Fraction as Q
from itertools import product
from math import factorial, prod
import hashlib
import json
from . import kan_multivariate as m, kan_fields as f

MAX_UNKNOWNS = 64
MAX_ROWS = 512
MAX_CONDITIONS = 16
MAX_ELIMINATION = 4_000_000
need, q = m.need, m.q

@dataclass(frozen=True, slots=True)
class Condition:
    """Coordinate derivative trace on a face; target is a full-dimensional
    polynomial independent of the fixed axis. Neumann outward signs are
    encoded by the caller in the target. Initial traces use the lower face.
    """
    axis: int
    side: str
    order: int
    target: m.Polynomial
    kind: str = 'boundary'

    def __post_init__(self):
        need(type(self.target) is m.Polynomial, 'condition target')
        m.axis_ok(self.target, self.axis)
        need(type(self.side) is str and type(self.kind) is str and self.side in ('lower','upper') and self.kind in ('boundary','initial'), 'condition kind/side')
        need(type(self.order) is int and 0 <= self.order <= f.MAX_ORDER, 'condition derivative order')
        need(self.kind != 'initial' or self.side == 'lower', 'initial must be lower face')
        need(self.target.degrees[self.axis] == 0, 'target depends on fixed axis')

@dataclass(frozen=True, slots=True)
class Problem:
    operator: f.DifferentialOperator
    source: m.Function
    conditions: tuple
    degree: int
    time_axis: int | None = None

    def __post_init__(self):
        need(type(self.operator) is f.DifferentialOperator and type(self.source) is m.Function, 'problem types')
        d=self.operator.dimension
        need(len(self.source.box)==d and len(self.source.outputs)==1 and self.operator.terms, 'scalar nonzero operator')
        need(type(self.degree) is int and 0<=self.degree<=m.MAX_DEGREE, 'trial degree')
        need(type(self.conditions) is tuple and 1<=len(self.conditions)<=MAX_CONDITIONS, 'condition count')
        need(self.time_axis is None or type(self.time_axis) is int and 0<=self.time_axis<d, 'time axis')
        for c in self.conditions:
            need(type(c) is Condition and c.target.dimension==d, 'condition dimension')
            need(c.kind!='initial' or c.axis==self.time_axis, 'initial time axis')
        if self.time_axis is not None:
            required=max(a[self.time_axis] for a,_ in self.operator.terms)
            orders={c.order for c in self.conditions if c.kind=='initial'}
            need(required>0 and set(range(required))<=orders, 'initial derivative conditions required')
        _basis(d,self.degree)

    @property
    def identity(self):
        raw=json.dumps(["cognitum.kan.equation.v1",self.operator.identity,self.source.identity,self.degree,self.time_axis,
            [[c.axis,c.side,c.order,c.kind,[[list(e),str(v)] for e,v in c.target.terms]] for c in self.conditions]],
            separators=(',',':')).encode('ascii')
        need(len(raw)<=m.MAX_BYTES,'problem identity budget')
        return hashlib.sha256(raw).hexdigest()


def _basis(d,n):
    # Enumerate only total-degree admissible exponents, bounded before allocation.
    from math import comb
    need(comb(d+n,d)<=MAX_UNKNOWNS,'trial basis budget')
    return tuple(e for e in product(range(n+1),repeat=d) if sum(e)<=n)


def _trace(p,c,box):
    alpha=tuple(c.order if i==c.axis else 0 for i in range(p.dimension))
    derivative=f.multi_partial(p,alpha)
    x=box[c.axis][c.side=='upper']
    return m.make(p.dimension, ((e[:c.axis]+(0,)+e[c.axis+1:],q(v*x**e[c.axis])) for e,v in derivative.terms))


def _trace_oracle(p,c,box):
    # Independent direct coefficient formula, no differentiation/substitution API.
    out={}; x=box[c.axis][c.side=='upper']
    for e,v in p.terms:
        k=e[c.axis]
        if k>=c.order:
            z=e[:c.axis]+(0,)+e[c.axis+1:]
            value=q(v*(factorial(k)//factorial(k-c.order))*x**(k-c.order))
            out[z]=q(out.get(z,Q(0))+value)
    return tuple(sorted((e,v) for e,v in out.items() if v))


def _system(p):
    d=p.operator.dimension; basis=_basis(d,p.degree); box=p.source.box
    columns=[]
    for e in basis:
        x=m.make(d,[(e,1)])
        # Existing G operator independently checks each basis response.
        response=p.operator.apply(m.Function(box,(x,))).outputs[0]
        traces=[]
        for c in p.conditions:
            t=_trace(x,c,box)
            need(t.terms==_trace_oracle(x,c,box),'trace identity')
            traces.append(t)
        columns.append(tuple(dict(v.terms) for v in (response,*traces)))
    targets=tuple(dict(v.terms) for v in (p.source.outputs[0],*(c.target for c in p.conditions)))
    rows=[]
    for j,target in enumerate(targets):
        keys=set(target)
        for col in columns: keys.update(col[j])
        need(len(rows)+len(keys)<=MAX_ROWS,'coefficient row budget')
        for e in sorted(keys):
            rows.append([col[j].get(e,Q(0)) for col in columns]+[target.get(e,Q(0))])
    return basis, rows


def _eliminate(rows,n):
    a=[r[:] for r in rows]; pivot=[]; work=0
    for j in range(n):
        k=next((k for k in range(len(pivot),len(a)) if a[k][j]),None)
        if k is None: continue
        i=len(pivot); a[i],a[k]=a[k],a[i]
        divisor=a[i][j]; a[i]=[q(x/divisor) for x in a[i]]
        for k,r in enumerate(a):
            if k==i or not r[j]: continue
            work+=n+1;need(work<=MAX_ELIMINATION,'elimination work budget')
            v=r[j];a[k]=[q(x-v*y) for x,y in zip(r,a[i])]
        pivot.append(j)
    if any(not any(r[:n]) and r[n] for r in a): return 'inconsistent',len(pivot),None
    if len(pivot)<n: return 'underdetermined',len(pivot),None
    return 'unique_trial',n,tuple(a[i][n] for i in range(n))


@dataclass(frozen=True, slots=True)
class Solution:
    problem_sha256: str
    rank: int
    unknowns: int
    candidate: m.Function
    residual: f.ResidualCertificate
    condition_residuals: tuple


@dataclass(frozen=True, slots=True)
class ConditionResidual:
    axis: int
    side: str
    order: int
    kind: str
    field_sha256: str
    absolute_upper: Q
    squared_l2: Q
    identically_zero: bool


@dataclass(frozen=True, slots=True)
class ResidualReport:
    problem_sha256: str
    candidate_sha256: str
    equation: f.ResidualCertificate
    conditions: tuple


def assess_candidate(p,candidate):
    """Exact continuous residual bounds; nonzero reports do not imply validity.

    Face norms integrate over the unfixed dimensions (point squared residual
    in 1-D). The interval sup bound is conservative, not a solution error bound.
    """
    need(type(p) is Problem and type(candidate) is m.Function,'candidate type')
    need(candidate.box==p.source.box and len(candidate.outputs)==1,'candidate domain')
    u=candidate.outputs[0];need(u.degree<=p.degree,'candidate outside trial degree')
    value=p.operator.apply(candidate).outputs[0]
    need(f._oracle_apply(p.operator,u)==value.terms,'independent equation identity')
    residual=m.Function(candidate.box,(value.add(p.source.outputs[0].scale(-1)),))
    rc=f.residual_certificate(residual)
    checks=[]
    for c in p.conditions:
        t=_trace(u,c,candidate.box)
        need(t.terms==_trace_oracle(u,c,candidate.box),'trace identity')
        r=f.residual_certificate(m.Function(candidate.box,(t.add(c.target.scale(-1)),)))
        lo,hi=candidate.box[c.axis]
        checks.append(ConditionResidual(c.axis,c.side,c.order,c.kind,r.field_sha256,
             r.absolute_upper[0],q(r.squared_l2/(hi-lo)),r.identically_zero))
    return ResidualReport(p.identity,candidate.identity,rc,tuple(checks))


def replay_assessment(p,candidate,report):
    need(type(report) is ResidualReport and assess_candidate(p,candidate)==report,'residual report witness mismatch')
    return report


def certify_candidate(p,candidate):
    """Qualify only an exactly satisfied equation and every declared trace."""
    report=assess_candidate(p,candidate)
    need(report.equation.identically_zero,'equation residual nonzero')
    need(all(c.identically_zero for c in report.conditions),'condition residual nonzero')
    return report.equation,report.conditions


def _independent_full_rank(rows,n):
    # Forward elimination only on the original coefficient columns, independent
    # of the augmented RREF solver and its reported pivot choices.
    a=[r[:n] for r in rows]; rank=0; work=0
    for j in range(n):
        k=next((k for k in range(rank,len(a)) if a[k][j]),None)
        if k is None: continue
        a[rank],a[k]=a[k],a[rank]; pivot=a[rank][j]
        for i in range(rank+1,len(a)):
            if not a[i][j]: continue
            ratio=q(a[i][j]/pivot); a[i][j]=Q(0)
            for l in range(j+1,n):
                work+=1;need(work<=MAX_ELIMINATION,'rank verification work budget')
                a[i][l]=q(a[i][l]-ratio*a[rank][l])
        rank+=1
    return rank==n


@dataclass(frozen=True, slots=True)
class CheckpointCertificate:
    extraction: m.Extraction
    residuals: ResidualReport


def certify_checkpoint(p,checkpoint):
    """Bind condition and residual certificates to exact KAN extraction."""
    need(type(p) is Problem,'problem type')
    extraction=m.extract(checkpoint,p.source.box)
    candidate=m.replay(checkpoint,extraction)
    report=assess_candidate(p,candidate)
    need(report.equation.identically_zero and all(c.identically_zero for c in report.conditions), 'checkpoint solution residual nonzero')
    return CheckpointCertificate(extraction,report)


def replay_checkpoint(p,checkpoint,witness):
    need(type(witness) is CheckpointCertificate and certify_checkpoint(p,checkpoint)==witness,'checkpoint solution witness mismatch')
    return witness.extraction.function


def solve(p):
    need(type(p) is Problem,'problem type')
    basis,rows=_system(p);status,rank,coefficients=_eliminate(rows,len(basis))
    need(status=='unique_trial',status+' polynomial trial system')
    need(rank==len(basis) and _independent_full_rank(rows,len(basis)),'independent rank mismatch')
    need(all(sum((x*v for x,v in zip(r,coefficients)),Q(0))==r[-1] for r in rows),'coefficient witness mismatch')
    candidate=m.Function(p.source.box,(m.make(p.operator.dimension,zip(basis,coefficients)),))
    residual,conditions=certify_candidate(p,candidate)
    return Solution(p.identity,rank,len(basis),candidate,residual,conditions)


def replay(p,s):
    need(type(p) is Problem and type(s) is Solution and s.problem_sha256==p.identity,'solution problem pin')
    need(type(s.rank) is int and type(s.unknowns) is int,'solution rank type')
    rc,conditions=certify_candidate(p,s.candidate)
    need((rc,conditions)==(s.residual,s.condition_residuals),'solution residual witness mismatch')
    need(solve(p)==s,'solution rank/candidate mismatch')
    return s.candidate
