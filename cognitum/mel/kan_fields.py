"""COG-04G: exact bounded Cartesian scientific operators on symbolic KAN fields.

Represented polynomials on a common closed rational box, not learned-target
accuracy. No distributional/atlas derivatives, physical unit inference, solver,
new route or authority. Derived checkpoint exports use existing MEL review.
"""
from dataclasses import dataclass
from fractions import Fraction as Q
from itertools import product
from math import comb, factorial, prod
import hashlib
import json
from . import kan_multivariate as m

MAX_ORDER = 4
MAX_OPERATOR_TERMS = 35
MAX_WORK = 100000
need, q = m.need, m.q


def _index(a, d):
    need(type(a) is tuple and len(a) == d and all(type(v) is int and v >= 0 for v in a)
         and sum(a) <= MAX_ORDER, 'differential order budget')
    return a


def multi_partial(p, alpha):
    _index(alpha, p.dimension)
    for i, n in enumerate(alpha):
        for _ in range(n):
            p = p.partial(i)
    return p


def _raw_derivative(terms, alpha):
    # Independent falling-factorial monomial oracle; no Polynomial.partial.
    out = {}
    for e, c in terms:
        if all(i >= j for i, j in zip(e, alpha)):
            k = tuple(i-j for i,j in zip(e,alpha))
            out[k] = q(c*prod(factorial(i)//factorial(i-j) for i,j in zip(e,alpha)))
    return out


def _accumulate(dest, e, c):
    v = q(dest.get(e, Q(0)) + c)
    if v:
        dest[e] = v
    else:
        dest.pop(e, None)
    need(len(dest) <= m.MAX_TERMS, 'oracle term budget')


def _oracle_apply(op, p):
    out = {}; work = 0
    for a, coeff in op.terms:
        derivative = _raw_derivative(p.terms, a)
        for e,c in coeff.terms:
            for f,v in derivative.items():
                work += 1; need(work <= MAX_WORK, 'oracle work budget')
                _accumulate(out, tuple(i+j for i,j in zip(e,f)), q(c*v))
    return tuple(sorted(out.items()))


@dataclass(frozen=True, slots=True)
class DifferentialOperator:
    """Normal form sum a_alpha(x) D^alpha, applied componentwise."""
    dimension: int
    terms: tuple

    def __post_init__(self):
        need(type(self.dimension) is int and 1 <= self.dimension <= m.MAX_DIM, 'dimension budget')
        need(type(self.terms) is tuple and len(self.terms) <= MAX_OPERATOR_TERMS, 'operator term budget')
        previous = None
        for item in self.terms:
            need(type(item) is tuple and len(item) == 2, 'operator term')
            a,p = item; _index(a,self.dimension)
            need(type(p) is m.Polynomial and p.dimension == self.dimension and bool(p.terms), 'operator coefficient')
            need(previous is None or previous < a, 'noncanonical operator'); previous = a

    @property
    def order(self):
        return max((sum(a) for a,_ in self.terms), default=0)

    @property
    def identity(self):
        raw = json.dumps({'schema':'cognitum.kan.differential.v1','dimension':self.dimension,
             'terms':[[list(a),[[list(e),str(c)] for e,c in p.terms]] for a,p in self.terms]},
             sort_keys=True,separators=(',',':')).encode('ascii')
        need(len(raw) <= m.MAX_BYTES,'operator identity budget')
        return hashlib.sha256(raw).hexdigest()

    def add(self, other):
        _same_op(self,other)
        return operator(self.dimension,(*self.terms,*other.terms))

    def scale(self, value):
        value=q(value)
        return operator(self.dimension,tuple((a,p.scale(value)) for a,p in self.terms))

    def apply(self, field):
        _field(field)
        need(len(field.box)==self.dimension,'operator dimension')
        out=[]; work=0
        for p in field.outputs:
            v=m.constant(self.dimension,0)
            for a,c in self.terms:
                d=multi_partial(p,a)
                work+=max(1,len(c.terms)*len(d.terms));need(work<=MAX_WORK,'operator application work budget')
                v=v.add(c.multiply(d))
            need(v.terms==_oracle_apply(self,p),'independent differential identity')
            out.append(v)
        return m.Function(field.box,tuple(out))

    def after(self, inner):
        """self ∘ inner, with full variable-coefficient Leibniz expansion."""
        _same_op(self,inner)
        need(self.order+inner.order <= MAX_ORDER, 'composition order budget')
        rows=[]; work=0
        for a,p in self.terms:
            for b,r in inner.terms:
                for c in product(*(range(i+1) for i in a)):
                    work+=1;need(work<=MAX_WORK,'composition work budget')
                    derivative=multi_partial(r,c)
                    power=tuple(i-j+k for i,j,k in zip(a,c,b))
                    work+=len(p.terms)*len(derivative.terms);need(work<=MAX_WORK,'composition work budget')
                    v=p.multiply(derivative).scale(prod(comb(i,j) for i,j in zip(a,c)))
                    rows.append((power,v))
        result=operator(self.dimension,tuple(rows))
        # A second normal-form construction: sequentially apply each one-axis
        # D to the inner operator dict via the product rule, independently of
        # binomial expansion. Compare exact coefficient identities.
        expected=_compose_oracle(self,inner)
        need(tuple((a,p.terms) for a,p in result.terms)==expected,'independent operator composition identity')
        return result


def _compose_oracle(outer,inner):
    out={}; work=0
    for a,p in outer.terms:
        state={b:dict(r.terms) for b,r in inner.terms}
        for axis,n in enumerate(a):
            for _ in range(n):
                next_state={}
                for b,row in state.items():
                    shifted=list(b); shifted[axis]+=1; shifted=tuple(shifted)
                    for e,c in row.items():
                        work+=1;need(work<=MAX_WORK,'composition oracle budget')
                        _accumulate(next_state.setdefault(shifted,{}),e,c)
                        if e[axis]:
                            f=list(e);f[axis]-=1
                            _accumulate(next_state.setdefault(b,{}),tuple(f),q(c*e[axis]))
                state={b:r for b,r in next_state.items() if r}
        for b,row in state.items():
            for e,c in p.terms:
                for f,v in row.items():
                    work+=1;need(work<=MAX_WORK,'composition oracle budget')
                    _accumulate(out.setdefault(b,{}),tuple(i+j for i,j in zip(e,f)),q(c*v))
    return tuple((b,tuple(sorted(row.items()))) for b,row in sorted(out.items()) if row)


def _same_op(a,b):
    need(type(b) is DifferentialOperator and a.dimension==b.dimension,'operator dimension')


def operator(d, rows):
    need(type(d) is int and 1<=d<=m.MAX_DIM,'dimension budget')
    need(type(rows) is tuple and len(rows)<=MAX_WORK,'operator work budget')
    acc={}
    for row in rows:
        need(type(row) is tuple and len(row)==2,'operator term')
        a,p=row;_index(a,d);need(type(p) is m.Polynomial and p.dimension==d,'operator coefficient')
        v=acc.get(a,m.constant(d,0)).add(p)
        if v.terms:acc[a]=v
        else:acc.pop(a,None)
    return DifferentialOperator(d,tuple(sorted(acc.items())))


def derivative(d, alpha):
    return operator(d,((alpha,m.constant(d,1)),))


def multiplier(p):
    need(type(p) is m.Polynomial,'polynomial coefficient')
    return operator(p.dimension,(((0,)*p.dimension,p),))


def laplace_operator(d):
    need(type(d) is int and 1<=d<=m.MAX_DIM,'dimension budget')
    return operator(d,tuple((tuple(2*int(i==j) for j in range(d)),m.constant(d,1)) for i in range(d)))


def _field(f):
    need(type(f) is m.Function,'single polynomial field required')
    return f


def _scalar(f):
    _field(f);need(len(f.outputs)==1,'scalar field required');return f.outputs[0]


def _vector(f):
    _field(f);need(len(f.outputs)==len(f.box),'Cartesian vector field required');return f.outputs


def _common(*fs):
    for f in fs:_field(f)
    need(all(f.box==fs[0].box for f in fs),'field domain mismatch')


def _d(p,i):
    return p.partial(i)


def _sum(ps,d):
    v=m.constant(d,0)
    for p in ps:v=v.add(p)
    return v


def _component(f, i):return m.Function(f.box,(f.outputs[i],))


def jacobian(f):
    _field(f)
    return tuple(certify('gradient',_component(f,i)).result for i in range(len(f.outputs)))


def hessian(f):
    _scalar(f)
    return jacobian(certify('gradient',f).result)


def _raw_field(op, fs):
    f=fs[0]; d=len(f.box)
    if op=='gradient':
        p=_scalar(f);out=tuple(_d(p,i) for i in range(d))
    elif op=='divergence':
        v=_vector(f);out=(_sum((_d(p,i) for i,p in enumerate(v)),d),)
    elif op=='curl':
        v=_vector(f);need(d in (2,3),'curl dimension')
        pairs=((1,0,0,1),) if d==2 else ((2,1,1,2),(0,2,2,0),(1,0,0,1))
        out=tuple(_d(v[a],i).add(_d(v[b],j).scale(-1)) for a,i,b,j in pairs)
    elif op=='laplacian':
        out=laplace_operator(d).apply(f).outputs
    elif op=='advection':
        v=_vector(fs[1]);out=tuple(_sum((a.multiply(_d(p,i)) for i,a in enumerate(v)),d) for p in f.outputs)
    elif op=='diffusion':
        k=_scalar(fs[1]);out=tuple(_sum((_d(k.multiply(_d(p,i)),i) for i in range(d)),d) for p in f.outputs)
    elif op=='poisson_residual':
        p=_scalar(f);b=_scalar(fs[1]);out=(_sum((_d(_d(p,i),i) for i in range(d)),d).add(b.scale(-1)),)
    else:raise ValueError('field operation')
    return m.Function(f.box,out)


def _oracle_field(op, fs):
    # Express field identities independently in terms of direct coefficient
    # oracle applications, including expanded divergence-form diffusion.
    f=fs[0];d=len(f.box)
    a=[tuple(int(i==j) for j in range(d)) for i in range(d)]
    def dd(p,axis,order=1):return _raw_derivative(p.terms,tuple(order*v for v in a[axis]))
    def merge(parts):
        out={}
        for row,sign in parts:
            for e,c in row.items():_accumulate(out,e,q(sign*c))
        return tuple(sorted(out.items()))
    if op=='gradient':return tuple(tuple(sorted(dd(f.outputs[0],i).items())) for i in range(d))
    if op=='divergence':return (merge((dd(p,i),1) for i,p in enumerate(f.outputs)),)
    if op=='curl':
        v=f.outputs;pairs=((1,0,0,1),) if d==2 else ((2,1,1,2),(0,2,2,0),(1,0,0,1))
        return tuple(merge(((dd(v[u],i),1),(dd(v[vv],j),-1))) for u,i,vv,j in pairs)
    if op=='laplacian':return tuple(merge((dd(p,i,2),1) for i in range(d)) for p in f.outputs)
    if op=='poisson_residual':return (merge([*( (dd(f.outputs[0],i,2),1) for i in range(d)),(dict(fs[1].outputs[0].terms),-1)]),)
    if op=='advection':
        L=operator(d,tuple((a[i],v) for i,v in enumerate(fs[1].outputs)))
    elif op=='diffusion':
        k=fs[1].outputs[0];rows=[]
        for i in range(d):
            rows.append((tuple(2*v for v in a[i]),k))
            rows.append((a[i],m.Polynomial(d,tuple(sorted(dd(k,i).items())))))
        L=operator(d,tuple(rows))
    else:raise ValueError('field operation')
    return tuple(_oracle_apply(L,p) for p in f.outputs)


_ARITY={'gradient':1,'divergence':1,'curl':1,'laplacian':1,'advection':2,'diffusion':2,'poisson_residual':2}

@dataclass(frozen=True, slots=True)
class FieldWitness:
    operation:str
    inputs:tuple
    result:m.Function


def certify(op,*fields):
    need(type(op) is str and op in _ARITY and len(fields)==_ARITY[op],'field operation arity')
    _common(*fields);r=_raw_field(op,fields)
    need(tuple(p.terms for p in r.outputs)==_oracle_field(op,fields),'independent field identity')
    return FieldWitness(op,tuple(f.identity for f in fields),r)


def replay(witness,*fields):
    need(type(witness) is FieldWitness and certify(witness.operation,*fields)==witness,'field witness mismatch')
    return witness.result


@dataclass(frozen=True, slots=True)
class ResidualCertificate:
    field_sha256:str
    absolute_upper:tuple
    squared_l2:Q
    identically_zero:bool


def residual_certificate(f):
    """Continuous per-component conservative sup bounds and exact squared L2.

    A zero residual is an identity of represented parameters, not a PDE
    solution certificate (no boundary/initial conditions or target accuracy).
    """
    _field(f);bounds=[];norm=Q(0);work=0
    for p in f.outputs:
        lo,hi=m.bounds(p,f.box);bounds.append(max(abs(lo),abs(hi)))
        for e,c in p.terms:
            for g,v in p.terms:
                work+=1;need(work<=MAX_WORK,'residual integration budget')
                k=tuple(i+j+1 for i,j in zip(e,g))
                integral=q(prod(q((b**j-a**j)/j) for j,(a,b) in zip(k,f.box)))
                norm=q(norm+q(c*v*integral))
    zero=all(not p.terms for p in f.outputs)
    need(norm>=0 and (norm==0)==zero,'residual norm identity')
    return ResidualCertificate(f.identity,tuple(bounds),norm,zero)


def replay_residual(c,f):
    need(type(c) is ResidualCertificate and residual_certificate(f)==c,'residual witness mismatch')
    return c
