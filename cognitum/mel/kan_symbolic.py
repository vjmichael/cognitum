"""COG-04E: bounded exact scalar polynomial-function algebra for reviewed KAN.

Host-side research instruments, not an admission route. Exactness refers to
represented binary64 parameters, not learned targets or floating observations.
No eval, arbitrary expressions, model authority, or unbounded root finding.
"""
from dataclasses import dataclass
from fractions import Fraction as Q
from math import comb
import hashlib
import json
import re
from . import polynomial_kan as pk, polynomial_witness as w
from cognitum.research.kan_trainable import Layer, Network

MAX_DEGREE=64
MAX_PIECES=64
MAX_BITS=4096
MAX_SPLIT=8


def need(ok,msg):
    if not ok: raise ValueError(msg)


def rational(x):
    need(type(x) in (int,float,Q),'rational scalar required')
    try: x=Q(x)
    except (ValueError,OverflowError) as exc: raise ValueError('finite rational required') from exc
    need(max(x.numerator.bit_length(),x.denominator.bit_length())<=MAX_BITS,'rational budget')
    return x


def poly(cs):
    need(type(cs) in (tuple,list) and 1<=len(cs)<=MAX_DEGREE+1,'polynomial degree budget')
    a=tuple(map(rational,cs))
    while len(a)>1 and a[-1]==0:a=a[:-1]
    return a


def val(p,x):
    x=rational(x);v=Q(0)
    for c in reversed(p):v=rational(v*x+c)
    return v


def add(a,b):return poly([rational((a[i] if i<len(a) else 0)+(b[i] if i<len(b) else 0)) for i in range(max(len(a),len(b)))])
def scale(a,c):return poly([rational(c*v) for v in a])
def mul(a,b):
    need(len(a)+len(b)-2<=MAX_DEGREE,'product degree budget');v=[Q(0)]*(len(a)+len(b)-1)
    for i,x in enumerate(a):
        for j,y in enumerate(b):v[i+j]=rational(v[i+j]+x*y)
    return poly(v)
def compose_poly(outer,inner):
    need((len(outer)-1)*(len(inner)-1)<=MAX_DEGREE,'composition degree budget');p=(Q(0),)
    for c in reversed(outer):p=add(mul(p,inner),(c,))
    return p

def deriv(p):return poly([i*c for i,c in enumerate(p) if i] or [0])
def primitive(p):return poly([0]+[c/(i+1) for i,c in enumerate(p)])


def bernstein(p,a,b):
    """Exact convex-hull range via monomial -> Bernstein on [a,b]."""
    n=len(p)-1; local=compose_poly(p,(a,b-a));local=local+(Q(0),)*(n+1-len(local))
    cs=[rational(sum(local[i]*Q(comb(k,i),comb(n,i)) for i in range(k+1))) for k in range(n+1)]
    return min(cs),max(cs)


def enclosure(p,a,b,depth=0):
    need(type(depth) is int and 0<=depth<=MAX_SPLIT,'subdivision budget')
    if depth==0:return bernstein(p,a,b)
    m=(a+b)/2;l=enclosure(p,a,m,depth-1);r=enclosure(p,m,b,depth-1)
    return min(l[0],r[0]),max(l[1],r[1])


@dataclass(frozen=True,slots=True)
class Piece:
    lo:Q
    hi:Q
    coefficients:tuple
    def __post_init__(self):
        object.__setattr__(self,'lo',rational(self.lo));object.__setattr__(self,'hi',rational(self.hi));object.__setattr__(self,'coefficients',poly(self.coefficients));need(self.lo<self.hi,'nonempty span')


@dataclass(frozen=True,slots=True)
class Function:
    """Closed contiguous domain, continuous exact pieces, no extrapolation."""
    pieces:tuple
    def __post_init__(self):
        need(type(self.pieces) is tuple and 1<=len(self.pieces)<=MAX_PIECES and all(type(p) is Piece for p in self.pieces),'piece budget/type')
        for l,r in zip(self.pieces,self.pieces[1:]):
            need(l.hi==r.lo,'gap or overlap');need(val(l.coefficients,l.hi)==val(r.coefficients,r.lo),'discontinuous function unsupported')
    @property
    def domain(self):return self.pieces[0].lo,self.pieces[-1].hi
    def evaluate(self,x):
        x=rational(x);return val(self.at(x).coefficients,x)
    def at(self,x):
        x=rational(x);need(self.domain[0]<=x<=self.domain[1],'outside domain')
        return next(p for p in self.pieces if p.lo<=x<=p.hi)
    def range(self,depth=0):
        need(type(depth) is int and 0<=depth<=MAX_SPLIT and len(self.pieces)*(1<<depth)<=1024,'range cell budget')
        vals=[enclosure(p.coefficients,p.lo,p.hi,depth) for p in self.pieces];return min(v[0] for v in vals),max(v[1] for v in vals)
    def snapshot(self):
        raw=json.dumps({'schema':'cognitum.mel.kan.symbolic.v1','pieces':[[str(p.lo),str(p.hi),[str(v) for v in p.coefficients]] for p in self.pieces]},sort_keys=True,separators=(',',':')).encode('ascii');need(len(raw)<=262144,'snapshot budget');return raw
    @property
    def identity(self):return hashlib.sha256(self.snapshot()).hexdigest()


def canonical(pieces):
    out=[]
    for p in pieces:
        if out and out[-1].hi==p.lo and out[-1].coefficients==p.coefficients:out[-1]=Piece(out[-1].lo,p.hi,p.coefficients)
        else:out.append(p)
        need(len(out)<=MAX_PIECES,'piece budget')
    return Function(tuple(out))


def function(lo,hi,coefficients):return Function((Piece(lo,hi,coefficients),))


def combine(a,b,op):
    need(type(a) is Function and type(b) is Function and a.domain==b.domain,'same function domain required')
    cuts=sorted({v for f in (a,b) for p in f.pieces for v in (p.lo,p.hi)})
    need(len(cuts)<=MAX_PIECES+1,'partition budget');out=[]
    for lo,hi in zip(cuts,cuts[1:]):
        p=a.at((lo+hi)/2).coefficients;q=b.at((lo+hi)/2).coefficients
        if op=='add':r=add(p,q)
        elif op=='subtract':r=add(p,scale(q,-1))
        elif op=='multiply':r=mul(p,q)
        elif op=='divide':
            need(separated(q,lo,hi),'denominator not certified nonzero')
            r=divide_exact(p,q);need(mul(r,q)==p,'division identity')
        else:raise ValueError('unknown functional operation')
        out.append(Piece(lo,hi,r))
    return canonical(out)


def separated(p,a,b,depth=0):
    low,high=bernstein(p,a,b)
    if low>0 or high<0:return True
    if depth>=MAX_SPLIT or val(p,a)==0 or val(p,b)==0:return False
    mid=(a+b)/2
    return separated(p,a,mid,depth+1) and separated(p,mid,b,depth+1)


def divide_exact(p,q):
    need(q!=(Q(0),),'zero denominator');r=[Q(0)]*max(1,len(p)-len(q)+1)
    while len(p)>=len(q) and p!=(Q(0),):
        n=len(p)-len(q);v=rational(p[-1]/q[-1]);r[n]=v;p=add(p,scale((Q(0),)*n+q,-v))
    need(p==(Q(0),),'quotient is not polynomial');return poly(r)


def differentiate(f):
    need(type(f) is Function,'function required')
    return canonical([Piece(p.lo,p.hi,deriv(p.coefficients)) for p in f.pieces])


def integrate(f):
    """Primitive anchored at zero at left endpoint; exact piece constants."""
    need(type(f) is Function,'function required');out=[];last=Q(0)
    for p in f.pieces:
        r=primitive(p.coefficients);r=add(r,(last-val(r,p.lo),));out.append(Piece(p.lo,p.hi,r));last=val(r,p.hi)
    return canonical(out)


def compose(outer,inner):
    """Certified range containment per span, exact affine knot preimages.

    Subdivision is bounded; nonlinear crossings that cannot be resolved are
    refused (not approximated or silently assigned to a piece).
    """
    need(type(outer) is Function and type(inner) is Function,'function required');out=[]
    def emit(p,a,b,depth):
        low,high=bernstein(p,a,b)
        for v in outer.pieces:
            if v.lo<=low<=high<=v.hi:
                r=compose_poly(v.coefficients,p);degree=max(len(r)-1,(len(p)-1)*(len(v.coefficients)-1))
                for j in range(1,degree+2):
                    x=a+(b-a)*Q(j,degree+2);need(val(r,x)==outer.evaluate(val(p,x)),'composition identity mismatch')
                out.append(Piece(a,b,r));need(len(out)<=MAX_PIECES,'composition piece budget');return
        need(depth<MAX_SPLIT,'composition range not certified in a single outer span')
        mid=(a+b)/2;emit(p,a,mid,depth+1);emit(p,mid,b,depth+1)
    for v in inner.pieces:
        p=v.coefficients;cuts={v.lo,v.hi}
        if len(p)==2:
            for o in outer.pieces:
                x=(o.hi-p[0])/p[1]
                if v.lo<x<v.hi:cuts.add(x)
        cuts=sorted(cuts)
        for a,b in zip(cuts,cuts[1:]):emit(p,a,b,0)
    return canonical(out)


def layer_function(layer):
    need(layer.inputs==layer.outputs==1 and layer.kind in ('chebyshev','spline_clamped'),'scalar polynomial layer required')
    g=tuple(map(w.q,layer.grid[0]));weights=tuple(map(w.q,layer.coefficients[0,0]));mask=w.q(layer.mask[0,0]);bias=w.q(layer.bias[0])
    if layer.kind=='chebyshev':spans=[(g[0],g[1],w.cheb_polys(*g,layer.degree))]
    else:spans=[(g[i],g[i+1],w.spline_polys(g,layer.degree,i)) for i in range(len(g)-1) if g[i]<g[i+1]]
    pieces=[]
    for lo,hi,basis in spans:
        p=(bias,)
        for c,b in zip(weights,basis):p=add(p,scale(b,c*mask))
        pieces.append(Piece(lo,hi,p))
    return canonical(pieces)


def exact_layer_value(layer,x):
    """Independent scalar recurrence, not the polynomial coefficient builder."""
    g=tuple(map(w.q,layer.grid[0]));need(g[0]<=x<=g[-1],'oracle domain');p=layer.degree
    if layer.kind=='chebyshev':
        z=(2*x-g[0]-g[-1])/(g[-1]-g[0]);b=[Q(1)]
        if p:b.append(z)
        for i in range(2,p+1):b.append(rational(2*z*b[-1]-b[-2]))
    else:
        span=max(i for i in range(len(g)-1) if g[i]<g[i+1] and (g[i]<=x<g[i+1] or x==g[-1]==g[i+1]));b=[Q(int(i==span)) for i in range(len(g)-1)]
        for k in range(1,p+1):
            b=[rational(((x-g[i])*b[i]/(g[i+k]-g[i]) if g[i+k]!=g[i] else 0)+((g[i+k+1]-x)*b[i+1]/(g[i+k+1]-g[i+1]) if g[i+k+1]!=g[i+1] else 0)) for i in range(len(b)-1)]
    return rational(w.q(layer.bias[0])+w.q(layer.mask[0,0])*sum(c*w.q(v) for c,v in zip(b,layer.coefficients[0,0])))


def verify_layer(layer,f):
    """Check degree+1 rational evaluations independently on every original knot span.

    Also split at proposed boundaries; equal polynomials at d+1 distinct
    points imply identity on each span. Continuity covers endpoints.
    """
    g=tuple(map(w.q,layer.grid[0]));need(f.domain==(g[0],g[-1]),'extracted domain mismatch');cuts=sorted(set(g)|{v for p in f.pieces for v in (p.lo,p.hi)})
    for a,b in zip(cuts,cuts[1:]):
        p=f.at((a+b)/2).coefficients;d=max(layer.degree,len(p)-1)
        for i in range(1,d+2):
            x=a+(b-a)*Q(i,d+2);need(val(p,x)==exact_layer_value(layer,x),'symbolic coefficient mismatch')
    return True


@dataclass(frozen=True,slots=True)
class Extraction:
    checkpoint_sha256:str
    function:Function
    layer_sha256:tuple


def extract(checkpoint):
    need(type(checkpoint) is pk.Checkpoint,'pinned checkpoint required');model=checkpoint.model();layers=[]
    for l in model.layers:
        f=layer_function(l);verify_layer(l,f);layers.append(f)
    f=layers[0]
    for outer in layers[1:]:f=compose(outer,f)
    return Extraction(checkpoint.identity,f,tuple(x.identity for x in layers))


def replay(checkpoint,certificate):
    need(type(certificate) is Extraction and extract(checkpoint)==certificate,'extraction witness mismatch');return certificate.function


@dataclass(frozen=True,slots=True)
class Operator:
    """Ordered mathematical operator chain, explicit primitive anchor."""
    steps:tuple
    def __post_init__(self):
        need(type(self.steps) is tuple and 1<=len(self.steps)<=8 and all(type(s) is str and s in ('D','I') for s in self.steps),'operator profile')
    def after(self,before):
        need(type(before) is Operator,'operator required');return Operator(before.steps+self.steps)
    def apply(self,f):
        need(type(f) is Function,'function required')
        for step in self.steps:
            result=differentiate(f) if step=='D' else integrate(f)
            verify_operator_step(step,f,result);f=result
        return f


def verify_operator_step(step,before,after):
    """Independent point identities for D or I, using direct power sums.

    On every common span equality follows from the residual polynomial degree;
    continuity is a Function invariant. For I, anchor fixes its unique constant.
    """
    need(step in ('D','I') and type(before) is Function and type(after) is Function and before.domain==after.domain,'operator identity domain')
    if step=='I':need(after.evaluate(after.domain[0])==0,'primitive anchor mismatch')
    cuts=sorted({v for fn in (before,after) for p in fn.pieces for v in (p.lo,p.hi)})
    need(len(cuts)<=MAX_PIECES+1,'operator verification partition budget')
    for lo,hi in zip(cuts,cuts[1:]):
        left=before.at((lo+hi)/2).coefficients;right=after.at((lo+hi)/2).coefficients
        target,source=(right,left) if step=='D' else (left,right)
        degree=max(len(target)-1,len(source)-2,0)
        for j in range(1,degree+2):
            x=lo+(hi-lo)*Q(j,degree+2)
            expected=rational(sum(i*c*x**(i-1) for i,c in enumerate(source) if i));need(val(target,x)==expected,'operator derivative identity mismatch')
    return True


@dataclass(frozen=True,slots=True)
class OperatorWitness:
    operator:Operator
    input_sha256:str
    result:Function


def apply_verified(operator,f):
    need(type(operator) is Operator and type(f) is Function,'operator witness profile');return OperatorWitness(operator,f.identity,operator.apply(f))


def replay_operator(witness,f):
    need(type(witness) is OperatorWitness and apply_verified(witness.operator,f)==witness,'operator witness mismatch');return witness.result


def export_candidate(f):
    """Exact conversion to existing scalar Chebyshev checkpoint when possible.

    No authority granted; refuse rounding, multiple distinct pieces or degree>8.
    Independently re-extract exported checkpoint and require equality.
    """
    need(type(f) is Function and len(f.pieces)==1,'single polynomial export only');p=f.pieces[0];n=len(p.coefficients)-1;need(n<=8,'checkpoint degree budget')
    lo,hi=p.lo,p.hi;rem=p.coefficients;basis=w.cheb_polys(lo,hi,n);cs=[Q(0)]*(n+1)
    for k in range(n,-1,-1):
        cs[k]=rational((rem[k] if k<len(rem) else 0)/basis[k][-1]);rem=add(rem,scale(basis[k],-cs[k]))
    need(rem==(Q(0),),'basis transport residual')
    def binary64(x):
        try:y=float(x)
        except OverflowError as e:raise ValueError('binary64 transport') from e
        need(Q(y)==x,'lossy binary64 transport refused');return y
    cp=pk.export_checkpoint(Network((Layer('chebyshev',n,[[binary64(lo),binary64(hi)]],[[[binary64(c) for c in cs]]],[[1.]],[0.]),)))
    need(extract(cp).function==f,'export symbolic identity mismatch');return cp


@dataclass(frozen=True,slots=True)
class ArithmeticWitness:
    operation:str
    operands:tuple
    result:Function


def arithmetic(operation,a,b):
    """Exact functional arithmetic with a replayable operand/result witness."""
    need(type(a) is Function and type(b) is Function,'function required')
    f=combine(a,b,operation)
    # Independent evaluation of the defining identity, on a common refinement.
    # The residual degree is bounded by the maximum degree of its terms.
    cuts=sorted({v for fn in (a,b,f) for p in fn.pieces for v in (p.lo,p.hi)})
    need(len(cuts)<=MAX_PIECES+1,'verification partition budget')
    for lo,hi in zip(cuts,cuts[1:]):
        p,q,r=(fn.at((lo+hi)/2).coefficients for fn in (a,b,f))
        ds=[len(z)-1 for z in (p,q,r)];d=max(ds)
        if operation=='multiply':d=max(d,ds[0]+ds[1])
        if operation=='divide':d=max(d,ds[1]+ds[2])
        for j in range(1,d+2):
            x=lo+(hi-lo)*Q(j,d+2);u,v,z=(val(k,x) for k in (p,q,r))
            ok={'add':lambda:z==u+v,'subtract':lambda:z==u-v,'multiply':lambda:z==u*v,'divide':lambda:z*v==u}[operation]()
            need(ok,'arithmetic identity mismatch')
    return ArithmeticWitness(operation,(a.identity,b.identity),f)


def replay_arithmetic(witness,a,b):
    need(type(witness) is ArithmeticWitness and arithmetic(witness.operation,a,b)==witness,'arithmetic witness mismatch');return witness.result


def load_snapshot(raw,expected_sha256):
    """Immutable canonical exact rational snapshot; content identity is not authority."""
    need(type(raw) is bytes and 0<len(raw)<=262144 and hashlib.sha256(raw).hexdigest()==expected_sha256,'symbolic snapshot pin')
    try:data=json.loads(raw.decode('ascii'))
    except (ValueError,UnicodeDecodeError,RecursionError) as exc:raise ValueError('symbolic snapshot JSON') from exc
    need(type(data) is dict and set(data)=={'schema','pieces'} and data['schema']=='cognitum.mel.kan.symbolic.v1' and type(data['pieces']) is list and 1<=len(data['pieces'])<=MAX_PIECES,'symbolic snapshot schema')
    def scalar(x):
        need(type(x) is str and 1<=len(x)<=2500 and re.fullmatch(r'-?(?:0|[1-9][0-9]*)(?:/[1-9][0-9]*)?',x,re.ASCII) is not None,'symbolic rational text budget')
        try:r=rational(Q(x))
        except (ValueError,ZeroDivisionError,OverflowError) as exc:raise ValueError('invalid rational text') from exc
        need(str(r)==x,'noncanonical rational text');return r
    pieces=[]
    for row in data['pieces']:
        need(type(row) is list and len(row)==3 and type(row[2]) is list and 1<=len(row[2])<=MAX_DEGREE+1,'symbolic piece schema')
        pieces.append(Piece(scalar(row[0]),scalar(row[1]),tuple(map(scalar,row[2]))))
    f=Function(tuple(pieces));need(f.snapshot()==raw,'noncanonical symbolic snapshot');return f
