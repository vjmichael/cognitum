"""Independent full-spectrum residual verification for existing periodic VFA.

Real and imaginary binary64 coefficients become exact rational pairs. Unlike
FFT projection and float64 residual norms, no cancellation or truncation of
residual coefficients is hidden. Proof concerns represented functions only.
"""
from dataclasses import dataclass
from fractions import Fraction as F
from hashlib import sha256
import math
import struct
from cognitum.research.vfa_periodic import Periodic
from . import admission as a, native as n, uncertainty as u, functions_pb2 as pb

METHOD='mel05c.periodic.exact-residual.v1'
MAX_MODE=32
MAX_WIRE=16384
GRID=2**192
ZERO=(F(0),F(0))


def _q(v):
    # Exact binary64 coefficient identity; normalise solely for algebra.
    return F(float(v.real)),F(float(v.imag))


def _coefficients(obj):
    u.require(type(obj) is Periodic and 0<=obj.order<=MAX_MODE,'bounded periodic representation')
    pos=tuple(_q(v) for v in obj.positive)
    u.require(all(abs(x)<=10**6 for pair in pos for x in pair),'coefficient range')
    ident=sha256(b'mel05c.periodic.binary64.v1\0'+struct.pack('<I',len(pos))+b''.join(struct.pack('<dd',float(v.real),float(v.imag)) for v in obj.positive)).digest()
    full={i:q for i,q in enumerate(pos)}
    full.update({-i:(q[0],-q[1]) for i,q in enumerate(pos) if i})
    return full,ident


def _add(a,b):return a[0]+b[0],a[1]+b[1]
def _neg(a):return -a[0],-a[1]
def _mul(a,b):return a[0]*b[0]-a[1]*b[1],a[0]*b[1]+a[1]*b[0]


def _product(a,b,check):
    c={}
    for j,x in a.items():
        check()
        for k,y in b.items():c[j+k]=_add(c.get(j+k,ZERO),_mul(x,y))
    return c


def _subtract(a,b):return {k:_add(a.get(k,ZERO),_neg(b.get(k,ZERO))) for k in sorted(a.keys()|b.keys())}


def _norm(a,d=0):
    # |a+ib|<=|a|+|b|. Sum over BOTH positive and negative modes.
    # derivative of exp(ikx) contributes |k|, not a sampled derivative.
    return sum((abs(k)**d*(abs(v[0])+abs(v[1])) for k,v in a.items()),F(0))


def _upper(q):
    u.rational(q);return F(-((-q*GRID)//1),GRID)


def _lower(q):
    u.rational(q);return F(q*GRID//1,GRID)


def _write(q,out):out.numerator=str(q.numerator);out.denominator=str(q.denominator)


def _read(v):
    u.require(len(v.numerator)<=128 and len(v.denominator)<=128,'rational length')
    try:q=F(int(v.numerator),int(v.denominator))
    except (ValueError,ZeroDivisionError) as exc:raise ValueError('invalid rational') from exc
    u.require(str(q.numerator)==v.numerator and str(q.denominator)==v.denominator and q>=0,'canonical nonnegative rational')
    return q


@dataclass(frozen=True,slots=True)
class Certificate:
    wire:bytes
    def __post_init__(self):self.message()
    def message(self):
        z=n.parse(self.wire,pb.SpectralCertificate,MAX_WIRE)
        a.Scope(z.session,z.workspace,z.subject,z.turn)
        u.require(z.schema_version==1 and z.method==METHOD and z.represented_inputs_only and z.operation in ('truncation','product','quotient') and len(z.left_sha256)==len(z.candidate_sha256)==32 and len(z.right_sha256)==(0 if z.operation=='truncation' else 32),'spectral profile')
        u.require(len(z.absolute_tolerance)==len(z.residual_upper)==len(z.error_upper)==2 and all(0<=x<=1e12 for x in z.absolute_tolerance),'spectral tolerance')
        res=tuple(map(_read,z.residual_upper));err=tuple(map(_read,z.error_upper))
        if z.operation=='quotient':
            u.require(0<z.minimum_separation<=1e6 and _read(z.denominator_lower)>=F(z.minimum_separation),'denominator bound')
        else:u.require(not z.HasField('denominator_lower') and z.minimum_separation==0 and res==err,'unnecessary denominator metadata')
        u.require(z.verdict==('within' if all(v<=F(t) for v,t in zip(err,z.absolute_tolerance)) else 'inconclusive'),'spectral verdict')
        return z
    @property
    def error_upper(self):return tuple(map(_read,self.message().error_upper))
    @property
    def identity(self):return sha256(b'mel05c.SpectralCertificate\0'+self.wire).hexdigest()


def certify(scope,operation,left,candidate,absolute_tolerance,*,right=None,minimum_separation=0.,check=lambda:None):
    """Proof of a uniform value AND first derivative residual over all x.

    For quotient, r=f-gq, |f/g-q|<=||r||/delta and derivative bound
    ||r'||/delta + ||r|| ||g'||/delta². Nonseparation or high relative
    condition is refusal, not a numerical solution or an automatic fallback.
    """
    u.require(type(scope) is a.Scope and type(operation) is str and operation in ('truncation','product','quotient'),'scope/operation')
    u.require(type(absolute_tolerance) is tuple and len(absolute_tolerance)==2 and all(type(t) is float and 0<=t<=1e12 for t in absolute_tolerance),'value and derivative tolerances')
    u.require(type(minimum_separation) is float and math.isfinite(minimum_separation) and (0<minimum_separation<=1e6 if operation=='quotient' else minimum_separation==0.),'explicit denominator policy')
    f,fh=_coefficients(left);q,qh=_coefficients(candidate);check()
    z=pb.SpectralCertificate(schema_version=1,method=METHOD,session=scope.session,workspace=scope.workspace,subject=scope.subject,turn=scope.turn,operation=operation,left_sha256=fh,candidate_sha256=qh,absolute_tolerance=absolute_tolerance,minimum_separation=minimum_separation,represented_inputs_only=True)
    if operation=='truncation':
        u.require(right is None and candidate.order<=left.order,'truncation profile')
        # Exact coefficient-prefix requirement (not an arbitrary fitted function).
        u.require(all(q[k]==f[k] for k in q),'not an exact coefficient truncation')
        r=_subtract(f,q)
    else:
        g,gh=_coefficients(right);z.right_sha256=gh
        r=_subtract(_product(f,g,check),q) if operation=='product' else _subtract(f,_product(g,q,check))
    upper=(_norm(r),_norm(r,1));error=upper
    if operation=='quotient':
        delta=abs(g[0][0])-sum((abs(v[0])+abs(v[1]) for k,v in g.items() if k),F(0))
        delta=_lower(delta)
        u.require(delta>=F(minimum_separation) and delta>0 and delta>=_norm(g)/2**40,'denominator not safely separated')
        _write(delta,z.denominator_lower)
        error=(upper[0]/delta,upper[1]/delta+upper[0]*_norm(g,1)/delta**2)
    for x in upper:_write(_upper(x),z.residual_upper.add())
    for x in error:_write(_upper(x),z.error_upper.add())
    z.verdict='within' if all(_upper(v)<=F(t) for v,t in zip(error,absolute_tolerance)) else 'inconclusive'
    check();return Certificate(n.serialize(z))


def replay(scope,operation,left,candidate,certificate,absolute_tolerance,*,right=None,minimum_separation=0.,check=lambda:None):
    u.require(type(certificate) is Certificate,'typed spectral certificate')
    expected=certify(scope,operation,left,candidate,absolute_tolerance,right=right,minimum_separation=minimum_separation,check=check)
    u.require(expected.wire==certificate.wire,'spectral certificate replay mismatch')
    return expected.message().verdict
