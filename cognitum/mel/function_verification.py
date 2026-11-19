"""MEL-05C continuous represented-function enclosures and verified transformations.

Only bounded Gaussian mixtures and scalar one-layer RBF KAN (zero active
SiLU). Exact rational algebra, reuse MEL-05B outward exp. No fitting claim,
worker rounding guarantee, authorization, or inferred physical uncertainty.
"""
from dataclasses import dataclass
from fractions import Fraction as F
from hashlib import sha256
import math
from . import uncertainty as u, native as n, model_engines as m, admission as a
from . import engines_pb2 as ep, functions_pb2 as pb
from .objects import token

I = u.Interval
P = I.point
MAX_DIM = 4
MAX_TERMS = 32
MAX_CELLS = 128
MAX_CERT = 65536
METHOD = 'mel05c.gaussian-rbf-box-rational.v1'
GRID = 2**192


def _abs(v):
    return max(abs(v.lo), abs(v.hi))


def _round(v):
    return I(F(v.lo*GRID//1, GRID), F(-((-v.hi*GRID)//1), GRID))


def _intersect(x, y):
    return I(max(x.lo, y.lo), min(x.hi, y.hi))


@dataclass(frozen=True, slots=True)
class KanFunction:
    approval: m.Approval
    axis: str
    def __post_init__(self):
        u.require(type(self.approval) is m.Approval and token(self.axis), 'host-reviewed KAN function and axis')
        _kan(self)


def _kan(v):
    ck = v.approval.checkpoint.message()
    u.require(len(ck.layers)==1, 'only one-layer KAN function supported')
    l = ck.layers[0]
    u.require(l.inputs==l.outputs==1 and l.basis==ep.RBF and l.degree==0, 'only scalar RBF KAN supported')
    mask=F(l.mask[0]);u.require(not l.base or F(l.base[0])*mask==0, 'active SiLU unsupported')
    g=tuple(map(F,l.grid))
    # Exact binary32 floor, same represented-function convention as MEL-05B.
    import struct
    scale=max((g[-1]-g[0])/(len(g)-1),F(struct.unpack('<f',struct.pack('<f',1e-4))[0]))
    return ((v.axis,'1'),), '1', ((g[0],g[-1]),), F(l.bias[0]) if l.bias else F(0), tuple(((c,), (1/scale**2,), mask*F(w)) for c,w in zip(g,l.coefficients))


def _function(v):
    if type(v) is KanFunction:
        axes,unit,domain,const,terms=_kan(v)
        return axes,unit,domain,const,terms,pb.FunctionRef(kind='kan.rbf.scalar',content_sha256=bytes.fromhex(v.approval.checkpoint.identity),review_id=v.approval.review_id)
    u.require(type(v) is n.NativeObject, 'typed native function required')
    b=v.message().body
    u.require(b.WhichOneof('representation')=='function','function, not samples')
    t,d=b.shape;u.require(t<=MAX_TERMS and d<=MAX_DIM,'function verification profile size')
    f=b.function;c=tuple(map(F,f.centers));s=tuple(map(F,f.widths))
    terms=tuple((c[k*d:(k+1)*d],tuple(1/(2*w*w) for w in s[k*d:(k+1)*d]),F(f.weights[k])) for k in range(t))
    return tuple((z.name,z.unit) for z in b.axes),b.units[0].numerator,tuple((F(z.lower),F(z.upper)) for z in b.domain),F(f.constant),terms,pb.FunctionRef(kind='vfa.gaussian',content_sha256=bytes.fromhex(v.identity))


def _box(box, domain):
    u.require(type(box) is tuple and len(box)==len(domain),'explicit common box')
    out=[]
    for z,(l,h) in zip(box,domain):
        u.require(type(z) is tuple and len(z)==2 and all(type(v) is float and math.isfinite(v) for v in z),'binary64 box endpoints')
        lo,hi=map(F,z);u.require(l<=lo<hi<=h,'box outside function domain or degenerate')
        out.append(I(lo,hi))
    return tuple(out)


def _terms(terms):
    grouped={}
    for c,q,w in terms:grouped[c,q]=grouped.get((c,q),F(0))+w
    return tuple((c,q,w) for (c,q),w in sorted(grouped.items()) if w)


def _exp(c,q,box):
    dx=tuple(x-P(z) for x,z in zip(box,c))
    exponent=P(0)
    for x,a0 in zip(dx,q): exponent=exponent+x.square().scale(a0)
    return dx,u.gaussian(exponent)


def _range(const,terms,box,hessian=False,check=lambda:None):
    d=len(box);out=[P(const)]+[P(0)]*(d+(d*d if hessian else 0))
    for c,q,w in terms:
        check();dx,g=_exp(c,q,box);v=g.scale(w);grad=[z.scale(-2*a0) for z,a0 in zip(dx,q)]
        out[0]=out[0]+v
        for j in range(d):out[j+1]=out[j+1]+v*grad[j]
        if hessian:
            for j in range(d):
                for k in range(d):
                    mult=grad[j].square()-P(2*q[j]) if j==k else grad[j]*grad[k]
                    out[1+d+j*d+k]=out[1+d+j*d+k]+v*mult
    return tuple(out)


def _pairs(s,t):
    # Cancel identical bases exactly before pairing remaining equal centres.
    residual=_terms(tuple(s)+tuple((c,q,-w) for c,q,w in t))
    # Keep original two signs by grouping same-centre terms in deterministic
    # pairs. Any two signed terms can use the residual identity.
    by={}
    for c,q,w in residual:by.setdefault(c,[]).append((q,w))
    out=[]
    for c,terms in by.items():
        while len(terms)>=2:
            q,w=terms.pop(0);r,v=terms.pop(0);out.append((c,q,w,r,-v))
        if terms:
            q,w=terms.pop();out.append((c,q,w,q,F(0)))
    return tuple(out)


def _delta(const,pairs,box,check):
    """Signed residual intervals, exploiting correlated exponent differences.

    |exp(-q)-exp(-r)| <= |q-r| on nonnegative q,r by mean-value theorem;
    sign is opposite the exponent difference. Intersect with direct bound.
    """
    out=[P(const)]+[P(0)]*len(box)
    for c,q,w,r,v in pairs:
        check();dx,g=_exp(c,q,box);_,h=_exp(c,r,box)
        dq=P(0)
        for z,qa,ra in zip(dx,q,r):dq=dq+z.square().scale(qa-ra)
        # For each point, e^-q-e^-r = -(q-r)*theta, 0<=theta<=1.
        de=_intersect(g-h,(-dq)*I(F(0),F(1)))
        out[0]=out[0]+g.scale(w-v)+de.scale(v)
        for j,z in enumerate(dx):
            out[1+j]=out[1+j]+z.scale(-2)*(g.scale(w*q[j]-v*r[j])+de.scale(v*r[j]))
    return tuple(out)


def _mid(box):return tuple(P((v.lo+v.hi)/2) for v in box)


def _error(bounds):
    return tuple(I(max(F(0),v.lo,-v.hi),_abs(v)) for v in bounds)


def _cell(const,pairs,box,check):
    residual=_delta(const,pairs,box,check)
    middle=_delta(const,pairs,_mid(box),check)
    # Mean-value theorem gives a second uniform value enclosure.
    radius=sum((_abs(z)*(v.hi-v.lo)/2 for z,v in zip(residual[1:],box)),F(0))
    residual=(_intersect(residual[0],middle[0]+I(-radius,radius)),)+residual[1:]
    # Point-wise lower bounds witness an actual counterexample; interval upper
    # bounds cover the whole closed cell. No sampling-only success possible.
    return tuple(_round(I(l.lo,h.hi)) for l,h in zip(_error(middle),_error(residual)))


def _envelope(cells):
    return tuple(I(max(v.lo for v in col),max(v.hi for v in col)) for col in zip(*(v for _,v in cells)))


def _common(scope,src,box):
    u.require(type(scope) is a.Scope,'trusted scope')
    axes,unit,domain,_,_,ref=src
    _box(box,domain)
    msg=pb.Certificate(schema_version=1,method=METHOD,session=scope.session,workspace=scope.workspace,subject=scope.subject,turn=scope.turn,source=ref,output_unit=unit,box=[x for z in box for x in z],represented_inputs_only=True)
    for name,unit in axes:msg.axes.add(name=name,unit=unit)
    return msg


def _put(msg,bounds):
    for b in bounds:
        out=msg.bounds.add();out.lower.numerator=str(b.lo.numerator);out.lower.denominator=str(b.lo.denominator);out.upper.numerator=str(b.hi.numerator);out.upper.denominator=str(b.hi.denominator)
    return Certificate(n.serialize(msg))


def _read_q(x):
    # Strict bounded canonical rationals, no oversized decimal parsing.
    u.require(len(x.numerator)<=128 and len(x.denominator)<=128,'rational wire budget')
    try:q=F(int(x.numerator),int(x.denominator))
    except (ValueError,ZeroDivisionError) as exc:raise ValueError('invalid rational') from exc
    u.require(str(q.numerator)==x.numerator and str(q.denominator)==x.denominator,'noncanonical rational')
    return q


@dataclass(frozen=True,slots=True)
class Certificate:
    wire: bytes
    def __post_init__(self):self.message()
    def message(self):
        c=n.parse(self.wire,pb.Certificate,MAX_CERT)
        a.Scope(c.session,c.workspace,c.subject,c.turn)
        d=len(c.axes)
        u.require(c.schema_version==1 and c.method==METHOD and c.represented_inputs_only and 1<=d<=MAX_DIM and len({v.name for v in c.axes})==d and all(token(v.name) and token(v.unit) for v in c.axes) and token(c.output_unit),'certificate profile')
        u.require(len(c.box)==2*d and all(math.isfinite(v) for v in c.box) and all(c.box[i]<c.box[i+1] for i in range(0,2*d,2)),'certificate box')
        def ref(z):
            u.require(len(z.content_sha256)==32 and ((z.kind=='vfa.gaussian' and not z.review_id) or (z.kind=='kan.rbf.scalar' and n.ID.fullmatch(z.review_id))),'function reference')
        ref(c.source)
        bounds=tuple(I(_read_q(v.lower),_read_q(v.upper)) for v in c.bounds)
        if c.HasField('target'):
            ref(c.target);u.require(1<=c.cells<=c.max_cells<=MAX_CELLS and len(bounds)==len(c.absolute_tolerance)==d+1 and all(0<=v<=1e12 for v in c.absolute_tolerance) and all(v.lo>=0 for v in bounds),'comparison certificate shape')
            u.require(c.verdict==_verdict(bounds,tuple(map(F,c.absolute_tolerance))),'certificate verdict')
        else:u.require(c.verdict=='enclosed' and not c.absolute_tolerance and c.max_cells==c.cells==1 and len(bounds)==1+d+d*d and c.source.kind=='vfa.gaussian','range certificate shape')
        return c
    @property
    def bounds(self):return tuple(I(_read_q(v.lower),_read_q(v.upper)) for v in self.message().bounds)
    @property
    def identity(self):return sha256(b'mel05c.Certificate\0'+self.wire).hexdigest()


def enclose(scope,function,box,*,check=lambda:None):
    """Value, gradient and Hessian ranges on a closed box for represented VFA."""
    src=_function(function);u.require(type(function) is n.NativeObject,'VFA range profile')
    msg=_common(scope,src,box);check();msg.cells=msg.max_cells=1;msg.verdict='enclosed'
    bounds=_range(src[3],_terms(src[4]),_box(box,src[2]),True,check)
    return _put(msg,tuple(map(_round,bounds)))


def _verdict(bounds,tol):
    if any(v.lo>t for v,t in zip(bounds,tol)):return 'outside'
    if all(v.hi<=t for v,t in zip(bounds,tol)):return 'within'
    return 'inconclusive'


def certify(scope,source,target,box,absolute_tolerance,*,max_cells=32,check=lambda:None):
    """Uniform value AND gradient approximation certificate on a closed box.

    Deterministic subdivision of unresolved cells. Exhaustion is inconclusive;
    a positive verdict requires covering the entire domain within tolerance.
    """
    s,t=_function(source),_function(target);u.require(s[:2]==t[:2],'axis or unit mismatch')
    b=_box(box,s[2]);_box(box,t[2]);d=len(b)
    u.require(type(max_cells) is int and 1<=max_cells<=MAX_CELLS,'cell budget')
    u.require(type(absolute_tolerance) is tuple and len(absolute_tolerance)==d+1 and all(type(v) is float and 0<=v<=1e12 for v in absolute_tolerance),'explicit value and gradient tolerances')
    tol=tuple(map(F,absolute_tolerance));p=_pairs(s[4],t[4]);const=s[3]-t[3]
    check();cells=[(b,_cell(const,p,b,check))]
    while len(cells)<max_cells:
        check();bounds=_envelope(cells)
        if _verdict(bounds,tol)!='inconclusive':break
        idx=next(j for j,(_,v) in enumerate(cells) if any(z.hi>k for z,k in zip(v,tol)))
        old,_=cells.pop(idx);axis=max(range(d),key=lambda j:(old[j].hi-old[j].lo)/(b[j].hi-b[j].lo));lo,hi=old[axis].lo,old[axis].hi;mid=(lo+hi)/2
        for s0 in (I(lo,mid),I(mid,hi)):
            child=old[:axis]+(s0,)+old[axis+1:];cells.append((child,_cell(const,p,child,check)))
    bounds=_envelope(cells);msg=_common(scope,s,box);msg.target.CopyFrom(t[5]);msg.absolute_tolerance.extend(absolute_tolerance);msg.cells=len(cells);msg.max_cells=max_cells;msg.verdict=_verdict(bounds,tol)
    check();return _put(msg,bounds)


def replay(scope,source,certificate,box,*,target=None,absolute_tolerance=None,max_cells=32,check=lambda:None):
    u.require(type(certificate) is Certificate,'typed certificate')
    expected=enclose(scope,source,box,check=check) if target is None else certify(scope,source,target,box,absolute_tolerance,max_cells=max_cells,check=check)
    u.require(expected.wire==certificate.wire,'function certificate replay mismatch')
    return expected.message().verdict


def propose_vfa(source):
    """Construct inert binary64 Gaussian candidate from approved RBF KAN.

    Rounded sqrt/width is NOT exact equivalence: certify and replay separately.
    """
    u.require(type(source) is KanFunction,'approved KAN source')
    axes,unit,domain,const,terms,_=_function(source)
    return n.gaussian([[float(c[0])] for c,_,_ in terms],[[math.sqrt(float(1/(2*q[0]))) ] for _,q,_ in terms],[float(w) for _,_,w in terms],constant=float(const),axes=list(axes),domain=[tuple(map(float,v)) for v in domain],output_unit=unit)


def propose_kan(source):
    """Inert checkpoint proposal; never an Approval or grant. Host reviews it.

    Only scalar dimensionless, 3–12 distinct centers. Precision narrowing and
    common RBF scale can change the function; uniform certificate is required.
    """
    u.require(type(source) is n.NativeObject,'native VFA source')
    axes,unit,domain,const,terms,_=_function(source);terms=sorted(terms)
    u.require(len(axes)==1 and axes[0][1]==unit=='1' and 3<=len(terms)<=12 and len({c for c,_,_ in terms})==len(terms),'unsupported KAN proposal shape or units')
    layer=ep.KanLayer(inputs=1,outputs=1,knots=len(terms),basis=ep.RBF,grid=[float(c[0]) for c,_,_ in terms],coefficients=[float(w) for _,_,w in terms],bias=[float(const)],mask=[1.])
    return m.Checkpoint(m.checkpoint_wire([layer]))


def verified_target(scope,source,target,certificate,box,absolute_tolerance,*,max_cells=32,check=lambda:None):
    """Replay host-retained inputs before returning the inert bound transfer.

    The contained function/checkpoint still requires the existing authorization
    path for any worker invocation; no authority is transferred by a proof.
    """
    u.require(replay(scope,source,certificate,box,target=target,absolute_tolerance=absolute_tolerance,max_cells=max_cells,check=check)=='within','function approximation not verified')
    return VerifiedTransfer(scope,target,certificate,box)


@dataclass(frozen=True,slots=True)
class VerifiedTransfer:
    # A convenience receipt; externally constructed instances are untrusted.
    # At a consuming boundary, call verified_target again to replay retained
    # scope/source/candidate/policy. The math claim is limited to this box.
    scope:a.Scope
    candidate:n.NativeObject|KanFunction
    certificate:Certificate
    box:tuple

    def covers(self,scope,requested_box):
        u.require(scope==self.scope,'transfer scope mismatch')
        _box(requested_box,tuple(tuple(map(F,z)) for z in self.box))
        return True
