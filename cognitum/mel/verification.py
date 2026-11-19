"""Independent, bounded mathematical witnesses; never authority or model proof.

VFA: exact rational exponent/coefficient construction from submitted IEEE754
values, then outward-rounded Decimal enclosures. Decimal.exp is correctly
rounded ROUND_HALF_EVEN; bracket by adjacent representable values. Large
negative exponent tail uses e > 2. No NumPy/libm oracle, no inferred input
uncertainty, no end-to-end guarantee and no KAN numerical certification.
"""
from dataclasses import dataclass
from decimal import (Context, Decimal, ROUND_FLOOR, ROUND_CEILING, ROUND_HALF_EVEN,
                     InvalidOperation, DivisionByZero, Overflow)
from fractions import Fraction
import hashlib
import re
from . import admission as a, native as n, engines as e, exchange as x
from . import verification_pb2 as pb
from .objects import need, token, number

DIGITS = 80
MAX_TERMS = 32
MAX_POINTS = 16
MAX_COMPONENTS = MAX_POINTS * 8
MAX_CERTIFICATE = 65536
TAIL = 256
METHOD = 'vfa.rational-decimal-enclosure.v1'
HDC_METHOD = 'hdc.packed-independent-witness.v1'
DOMAIN = b'cognitum.mel.verification.v1.Certificate\x00'
_DECIMAL = re.compile(r'-?\d(?:\d{0,79})(?:\.\d{1,80})?(?:E[+-]?\d{1,5})?\Z', re.ASCII)
ZERO = Decimal(0)
ONE = Decimal(1)


class _Arithmetic:
    def __init__(self):
        # Explicit policy: caller DefaultContext and current context do not
        # control precision, traps, rounding or exponent range.
        def context(rounding):
            return Context(prec=DIGITS, rounding=rounding, Emin=-999999, Emax=999999,
                           capitals=1, clamp=0, flags=[], traps=[InvalidOperation, DivisionByZero, Overflow])
        self.down = context(ROUND_FLOOR)
        self.up = context(ROUND_CEILING)
        self.near = context(ROUND_HALF_EVEN)

    def rational(self, q):
        u,v=Decimal(q.numerator),Decimal(q.denominator)
        return self.down.divide(u,v), self.up.divide(u,v)

    def exp_negative(self, q):
        # q is an exact nonnegative rational, not the worker's rounded exponent.
        if q == 0:return ONE,ONE
        if q >= TAIL:return ZERO,self.rational(Fraction(1,2**TAIL))[1]
        lo,hi=self.rational(-q)
        return max(ZERO,self.down.next_minus(self.near.exp(lo))), min(ONE,self.up.next_plus(self.near.exp(hi)))

    def multiply(self, a, b):
        pairs=[(u,v) for u in a for v in b]
        return min(self.down.multiply(u,v) for u,v in pairs),max(self.up.multiply(u,v) for u,v in pairs)

    def add(self, a, b):
        return self.down.add(a[0],b[0]),self.up.add(a[1],b[1])

    def error(self, bounds, observed):
        lo,hi=bounds;y=Decimal.from_float(observed)
        return max(ZERO,self.down.subtract(lo,y),self.down.subtract(y,hi)),max(ZERO,self.up.subtract(y,lo),self.up.subtract(hi,y))


def _bounds(call):
    fm,pm=n.pair(call.function,call.points);f,p=fm.body,pm.body
    t,d=f.shape;rows=p.shape[0]
    need(t<=MAX_TERMS and rows<=MAX_POINTS,'verification budget exceeded')
    ar=_Arithmetic();g=call.operation=='vfa.gradient';mix=f.function
    centers=tuple(map(Fraction,mix.centers));widths=tuple(map(Fraction,mix.widths));weights=tuple(map(Fraction,mix.weights));coords=tuple(map(Fraction,p.points.coordinates))
    result=[]
    for row in range(rows):
        base=[(ZERO,ZERO)]*d if g else [ar.rational(Fraction(mix.constant))]
        for k,w in enumerate(weights):
            if not w:continue
            diffs=[coords[row*d+j]-centers[k*d+j] for j in range(d)]
            sigma=widths[k*d:(k+1)*d]
            q=sum(((v/z)**2 for v,z in zip(diffs,sigma)),Fraction())/2
            exponential=ar.exp_negative(q)
            multipliers=[-w*v/(z*z) for v,z in zip(diffs,sigma)] if g else [w]
            for j,m in enumerate(multipliers):
                if m:base[j]=ar.add(base[j],ar.multiply(ar.rational(m),exponential))
        result.extend(base)
    return tuple(result)


def _decimal(s):
    need(type(s) is str and len(s)<=96 and _DECIMAL.fullmatch(s) is not None,'certificate decimal encoding')
    value=Decimal(s);need(value.is_finite() and -10000<=value.adjusted()<=10000,'certificate decimal range')
    return value


def _status(comps,tols):
    # Decimal bounds describe exact absolute discrepancy, not observed MAE.
    outside=False;within=True
    for i,v in enumerate(comps):
        t=Decimal.from_float(tols[i%len(tols)])
        outside |= _decimal(v.absolute_error_lower)>t
        within &= _decimal(v.absolute_error_upper)<=t
    return pb.OUTSIDE_TOLERANCE if outside else pb.WITHIN_TOLERANCE if within else pb.INCONCLUSIVE


@dataclass(frozen=True,slots=True)
class Certificate:
    """Immutable untrusted wire. Call replay before relying on its verdict."""
    wire: bytes
    def __post_init__(self):self.message()
    @property
    def identity(self):return hashlib.sha256(DOMAIN+self.wire).hexdigest()
    def message(self):
        c=n.parse(self.wire,pb.Certificate,MAX_CERTIFICATE)
        a.Scope(c.scope.session,c.scope.workspace,c.scope.subject,c.scope.turn)
        need(c.schema_version==1 and c.represented_inputs_only and all(len(v)==32 for v in (c.descriptor_sha256,c.request_sha256,c.result_sha256)) and len(c.kernel_git_blob)==20,'certificate identity')
        if c.operation in n.OP:
            need(c.method==METHOD and c.decimal_digits==DIGITS and c.kernel_git_blob==bytes.fromhex(n.KERNEL),'verification method')
            shape=list(c.shape);grad=c.operation=='vfa.gradient';cols=shape[1] if len(shape)==2 else 1
            need(len(shape)==(2 if grad else 1) and 1<=shape[0]<=MAX_POINTS and 1<=cols<=8 and len(c.components)==shape[0]*cols<=MAX_COMPONENTS,'certificate shape')
            need(len(c.units)==len(c.absolute_tolerance)==cols and all(token(u.numerator) and token(u.denominator) for u in c.units),'certificate units or tolerances')
            need(all(0<=number(v,1e12) for v in c.absolute_tolerance),'certificate tolerance')
            for v in c.components:
                need(v.HasField('observed'),'missing observation');number(v.observed,1e12)
                lo,hi,el,eu=map(_decimal,(v.lower,v.upper,v.absolute_error_lower,v.absolute_error_upper))
                need(lo<=hi and ZERO<=el<=eu,'certificate bound order')
                need(_Arithmetic().error((lo,hi),v.observed)==(el,eu),'inconsistent error enclosure')
            need(c.verdict==_status(c.components,c.absolute_tolerance),'certificate verdict mismatch')
        else:
            need(c.operation in ('hdc.bind','hdc.query') and c.method==HDC_METHOD and c.verdict==pb.EXACT_SUBMITTED_BITS and c.decimal_digits==0 and c.kernel_git_blob==bytes.fromhex(e.HDC_BLOB),'unsupported witness')
            need(len(c.shape)==1 and 1<=c.shape[0]<=(e.MAX_DIM if c.operation=='hdc.bind' else e.MAX_CANDIDATES) and not c.components and not c.units and not c.absolute_tolerance,'HDC witness shape')
        return c


def _common(scope,call,receipt,method,kernel):
    return pb.Certificate(schema_version=1,scope=pb.Scope(session=scope.session,workspace=scope.workspace,subject=scope.subject,turn=scope.turn),operation=call.operation,descriptor_sha256=bytes.fromhex(receipt.descriptor_sha256),request_sha256=bytes.fromhex(receipt.request_sha256),result_sha256=bytes.fromhex(receipt.result_sha256),kernel_git_blob=bytes.fromhex(kernel),method=method,represented_inputs_only=True)


def certify_vfa(scope,call,receipt,absolute_tolerance):
    """Recompute mathematical enclosures and bound error of the submitted result.

    One trusted binary64 absolute tolerance per output unit (one for scalar
    values or one per gradient axis). No certificate for unrepresented inputs.
    """
    need(type(scope) is a.Scope and type(call) is n.NativeCall,'typed VFA request and scope')
    f,q=n.pair(call.function,call.points);rows,d=q.body.shape
    need(f.body.shape[0]<=MAX_TERMS and rows<=MAX_POINTS,'verification budget exceeded')
    cols=d if call.operation=='vfa.gradient' else 1
    need(type(absolute_tolerance) is tuple and len(absolute_tolerance)==cols,'per-component tolerance required')
    tol=tuple(number(v,1e12) for v in absolute_tolerance);need(all(v>=0 for v in tol),'negative tolerance')
    result,_,_=x._checked_receipt(scope,call,receipt);b=result.message().body
    c=_common(scope,call,receipt,METHOD,n.KERNEL);c.decimal_digits=DIGITS;c.shape.extend(b.shape);c.absolute_tolerance.extend(tol)
    for u in b.units:c.units.add(numerator=u.numerator,denominator=u.denominator)
    values=b.gradient.values if call.operation=='vfa.gradient' else b.values.values
    bounds=_bounds(call);ar=_Arithmetic()
    for (lo,hi),v in zip(bounds,values):
        el,eu=ar.error((lo,hi),v);c.components.add(observed=v,lower=format(lo,"E"),upper=format(hi,"E"),absolute_error_lower=format(el,"E"),absolute_error_upper=format(eu,"E"))
    c.verdict=_status(c.components,c.absolute_tolerance)
    return Certificate(n.serialize(c))


def certify_hdc(scope,call,receipt):
    """Reuse independent exact XOR/Hamming witness; no semantic similarity claim."""
    need(type(scope) is a.Scope and type(call) is e.Call and call.operation in ('hdc.bind','hdc.query'),'HDC-only witness')
    x._checked_receipt(scope,call,receipt)
    c=_common(scope,call,receipt,HDC_METHOD,e.HDC_BLOB);c.verdict=pb.EXACT_SUBMITTED_BITS
    c.shape.append(call.message.bind.left.dimension if call.operation=='hdc.bind' else len(call.message.query.candidates))
    return Certificate(n.serialize(c))


def replay(scope,call,receipt,certificate,*,absolute_tolerance=None):
    """Rebuild using retained trusted inputs and caller's independent tolerance."""
    need(type(certificate) is Certificate,'typed verification certificate')
    if type(call) is n.NativeCall:
        expected=certify_vfa(scope,call,receipt,absolute_tolerance)
    else:
        need(absolute_tolerance is None,'HDC has no numerical tolerance');expected=certify_hdc(scope,call,receipt)
    need(expected.wire==certificate.wire,'verification replay mismatch')
    return expected.message().verdict
