"""COG-04F: bounded exact sparse multivariate algebra of represented KANs.

Research-only host instrument. A certificate covers a closed rational box on
which each layer component is in a single polynomial span. No extrapolation,
implicit knot crossing, learned-target guarantee, or execution authority.
"""
from dataclasses import dataclass
from fractions import Fraction as Q
from itertools import product
from math import prod
import hashlib
import json
import re
from . import polynomial_kan as pk, polynomial_witness as w, kan_symbolic as scalar
from cognitum.research.kan_trainable import Layer, Network

MAX_DIM=3
MAX_DEGREE=12
MAX_TERMS=256
MAX_EVAL=4096
MAX_STEPS=8
MAX_BYTES=262144
need=scalar.need
q=scalar.rational

@dataclass(frozen=True, slots=True)
class Polynomial:
    dimension:int
    terms:tuple
    def __post_init__(self):
        need(type(self.dimension) is int and 1<=self.dimension<=MAX_DIM,'dimension budget')
        need(type(self.terms) is tuple and len(self.terms)<=MAX_TERMS,'term budget')
        last=None;out=[]
        for e,c in self.terms:
            need(type(e) is tuple and len(e)==self.dimension and all(type(i) is int and 0<=i<=MAX_DEGREE for i in e) and sum(e)<=MAX_DEGREE,'degree budget')
            c=q(c);need(c!=0 and (last is None or last<e),'noncanonical terms');last=e;out.append((e,c))
        object.__setattr__(self,'terms',tuple(out))
    @property
    def degrees(self):return tuple(max((e[i] for e,c in self.terms),default=0) for i in range(self.dimension))
    @property
    def degree(self):return max((sum(e) for e,c in self.terms),default=0)
    def evaluate(self,points):
        need(type(points) in (tuple,list) and len(points)==self.dimension,'point shape')
        points=tuple(map(q,points));return q(sum((q(c*prod(q(x**i) for x,i in zip(points,e))) for e,c in self.terms),Q(0)))
    def scale(self,c):
        c=q(c);return make(self.dimension,((e,q(v*c)) for e,v in self.terms))
    def add(self,other):
        same(self,other);return make(self.dimension,(*self.terms,*other.terms))
    def multiply(self,other):
        same(self,other);need(self.degree+other.degree<=MAX_DEGREE,'product degree budget')
        need(len(self.terms)*len(other.terms)<=MAX_TERMS**2,'product work budget')
        return make(self.dimension,((tuple(i+j for i,j in zip(e,f)),q(c*d)) for e,c in self.terms for f,d in other.terms))
    def divide_exact(self,other):
        same(self,other);need(bool(other.terms),'zero denominator');p=self;result=constant(self.dimension,0);order=lambda item:(sum(item[0]),item[0]);g,d=max(other.terms,key=order)
        for _ in range(MAX_TERMS*2):
            if not p.terms:
                need(result.multiply(other)==self,'division identity');return result
            e,c=max(p.terms,key=order);need(all(i>=j for i,j in zip(e,g)),'quotient not polynomial')
            term=make(self.dimension,[(tuple(i-j for i,j in zip(e,g)),q(c/d))]);result=result.add(term);p=p.add(term.multiply(other).scale(-1))
        raise ValueError('division work budget')
    def partial(self,axis):
        axis_ok(self,axis);return make(self.dimension,((e[:axis]+(e[axis]-1,)+e[axis+1:],q(c*e[axis])) for e,c in self.terms if e[axis]))
    def integral(self,axis,anchor):
        axis_ok(self,axis);anchor=q(anchor);need(self.degree<MAX_DEGREE,'integral degree budget')
        result=[]
        for e,c in self.terms:
            k=e[axis]+1;v=q(c/k);result.append((e[:axis]+(k,)+e[axis+1:],v));result.append((e[:axis]+(0,)+e[axis+1:],q(-v*anchor**k)))
        return make(self.dimension,result)
    def substitute(self,inner):
        need(type(inner) is tuple and len(inner)==self.dimension and all(type(p) is Polynomial for p in inner),'substitution shape')
        d=inner[0].dimension;need(all(p.dimension==d for p in inner),'substitution dimension')
        powers=[]
        for p,n in zip(inner,self.degrees):
            row=[constant(d,1)]
            for _ in range(n):row.append(row[-1].multiply(p))
            powers.append(row)
        result=constant(d,0)
        for e,c in self.terms:
            term=constant(d,c)
            for i,k in enumerate(e):term=term.multiply(powers[i][k])
            result=result.add(term)
        return result


def make(d,terms):
    need(type(d) is int and 1<=d<=MAX_DIM,'dimension budget');r={}
    for n,(e,c) in enumerate(terms):
        need(n<MAX_TERMS**2,'term work budget')
        need(type(e) is tuple and len(e)==d and all(type(i) is int and i>=0 for i in e) and sum(e)<=MAX_DEGREE,'degree budget')
        r[e]=q(r.get(e,Q(0))+q(c))
        if not r[e]:del r[e]
        need(len(r)<=MAX_TERMS,'term budget')
    return Polynomial(d,tuple(sorted(r.items())))
def constant(d,c):return make(d,[((0,)*d,c)])
def variable(d,i):
    need(type(i) is int and 0<=i<d,'axis');return make(d,[(tuple(int(j==i) for j in range(d)),1)])
def same(a,b):need(type(b) is Polynomial and a.dimension==b.dimension,'dimension mismatch')
def axis_ok(p,i):need(type(i) is int and 0<=i<p.dimension,'axis')


def box_checked(box,d):
    need(type(box) is tuple and len(box)==d and all(type(x) is tuple and len(x)==2 for x in box),'box shape')
    b=tuple(tuple(map(q,x)) for x in box);need(all(a<b for a,b in b),'nonempty box');return b


def bounds(p,box):
    # Exact separable interval monomial bound; deliberately conservative.
    box=box_checked(box,p.dimension);out=(Q(0),Q(0))
    for e,c in p.terms:
        v=(c,c)
        for (a,b),k in zip(box,e):
            x,y=q(a**k),q(b**k);lo=min(x,y);hi=max(x,y)
            if k>0 and k%2==0 and a<=0<=b:lo=Q(0)
            v=w.mul(v,(lo,hi))
        out=w.add(out,v)
    return tuple(map(q,out))

@dataclass(frozen=True, slots=True)
class Function:
    box:tuple
    outputs:tuple
    def __post_init__(self):
        need(type(self.outputs) is tuple and 1<=len(self.outputs)<=MAX_DIM and all(type(p) is Polynomial for p in self.outputs),'output profile')
        d=self.outputs[0].dimension;need(all(p.dimension==d for p in self.outputs),'dimension mismatch');object.__setattr__(self,'box',box_checked(self.box,d))
    def evaluate(self,x):
        need(type(x) in (list,tuple) and len(x)==len(self.box),'point shape');x=tuple(map(q,x));need(all(a<=v<=b for v,(a,b) in zip(x,self.box)),'outside certified box');return tuple(p.evaluate(x) for p in self.outputs)
    def snapshot(self):
        raw=json.dumps(dict(schema='cognitum.kan.sparse.v1',box=[[str(a),str(b)] for a,b in self.box],outputs=[[[list(e),str(c)] for e,c in p.terms] for p in self.outputs]),sort_keys=True,separators=(',',':')).encode('ascii');need(len(raw)<=MAX_BYTES,'snapshot budget');return raw
    @property
    def identity(self):return hashlib.sha256(self.snapshot()).hexdigest()

def load_snapshot(raw,pin):
    need(type(raw) is bytes and 0<len(raw)<=MAX_BYTES and hashlib.sha256(raw).hexdigest()==pin,'snapshot pin')
    try:m=json.loads(raw.decode('ascii'))
    except (UnicodeError,ValueError,RecursionError) as exc:raise ValueError('snapshot JSON') from exc
    need(type(m) is dict and set(m)=={'schema','box','outputs'} and m['schema']=='cognitum.kan.sparse.v1','snapshot schema')
    def rational(s):
        need(type(s) is str and len(s)<=2500 and re.fullmatch(r'-?(?:0|[1-9][0-9]*)(?:/[1-9][0-9]*)?',s) is not None,'rational text');v=q(Q(s));need(str(v)==s,'noncanonical rational');return v
    need(type(m['box']) is list and 1<=len(m['box'])<=MAX_DIM and all(type(v) is list and len(v)==2 for v in m['box']),'box shape');b=tuple(tuple(map(rational,v)) for v in m['box']);d=len(b)
    need(type(m['outputs']) is list and 1<=len(m['outputs'])<=MAX_DIM,'output profile');o=[]
    for row in m['outputs']:
        need(type(row) is list and len(row)<=MAX_TERMS and all(type(t) is list and len(t)==2 and type(t[0]) is list for t in row),'term schema');o.append(Polynomial(d,tuple((tuple(e),rational(c)) for e,c in row)))
    f=Function(b,tuple(o));need(f.snapshot()==raw,'noncanonical snapshot');return f


def _grid_points(box,degrees):
    need(prod(k+1 for k in degrees)<=MAX_EVAL,'identity grid budget')
    return product(*[tuple(a+(b-a)*Q(j+1,k+2) for j in range(k+1)) for (a,b),k in zip(box,degrees)])


def _edge_poly(layer,i,o,span):
    g=tuple(map(w.q,layer.grid[i]));a,b=span;need(g[0]<=a<=b<=g[-1],'intermediate domain not certified')
    if layer.kind=='chebyshev':basis=w.cheb_polys(*g,layer.degree)
    else:
        choices=[j for j in range(len(g)-1) if g[j]<g[j+1] and g[j]<=a<=b<=g[j+1]]
        need(bool(choices),'knot crossing not certified');basis=w.spline_polys(g,layer.degree,choices[0])
    p=(Q(0),)
    for c,v in zip(layer.coefficients[o,i],basis):p=scalar.add(p,scalar.scale(v,w.q(c)*w.q(layer.mask[o,i])))
    return p


def _exact_layer(layer,x):
    # Independent direct basis evaluation from the checkpoint, no monomial expansion.
    rows=[]
    for i,z in enumerate(x):
        g=tuple(map(w.q,layer.grid[i]));need(g[0]<=z<=g[-1],'oracle domain');p=layer.degree
        if layer.kind=='chebyshev':
            t=(2*z-g[0]-g[-1])/(g[-1]-g[0]);r=[Q(1)]
            if p:r.append(t)
            for k in range(2,p+1):r.append(q(2*t*r[-1]-r[-2]))
        else:
            j=max(j for j in range(len(g)-1) if g[j]<g[j+1] and (g[j]<=z<g[j+1] or z==g[-1]==g[j+1]));r=[Q(int(k==j)) for k in range(len(g)-1)]
            for k in range(1,p+1):r=[q(((z-g[j])*r[j]/(g[j+k]-g[j]) if g[j+k]!=g[j] else 0)+((g[j+k+1]-z)*r[j+1]/(g[j+k+1]-g[j+1]) if g[j+k+1]!=g[j+1] else 0)) for j in range(len(r)-1)]
        rows.append(r)
    return tuple(q(w.q(layer.bias[o])+sum(w.q(layer.mask[o,i])*sum(w.q(c)*v for c,v in zip(layer.coefficients[o,i],rows[i])) for i in range(layer.inputs))) for o in range(layer.outputs))

@dataclass(frozen=True, slots=True)
class Extraction:
    checkpoint_sha256:str
    function:Function


def extract(cp,box=None):
    need(type(cp) is pk.Checkpoint,'typed checkpoint');net=cp.model();first=net.layers[0];d=first.inputs
    need(1<=d<=MAX_DIM and 1<=net.layers[-1].outputs<=MAX_DIM,'symbolic dimensions')
    if box is None:box=tuple((w.q(row[0]),w.q(row[-1])) for row in first.grid)
    box=box_checked(box,d);z=tuple(variable(d,i) for i in range(d));degree=1
    for layer in net.layers:
        ranges=[bounds(v,box) for v in z];new=[];degree*=max(1,layer.degree);need(degree<=MAX_DEGREE,'extraction degree budget')
        for o in range(layer.outputs):
            result=constant(d,w.q(layer.bias[o]))
            for i,v in enumerate(z):
                p=_edge_poly(layer,i,o,ranges[i]);term=constant(d,0)
                for c in reversed(p):term=term.multiply(v).add(constant(d,c))
                result=result.add(term)
            new.append(result)
        # Identity theorem on a tensor grid; independent recurrence checks each layer.
        for point in _grid_points(box,(degree,)*d):
            expected=_exact_layer(layer,tuple(v.evaluate(point) for v in z));need(tuple(v.evaluate(point) for v in new)==expected,'extraction identity mismatch')
        z=tuple(new)
    return Extraction(cp.identity,Function(box,z))

def replay(cp,e):
    need(type(e) is Extraction and extract(cp,e.function.box)==e,'extraction witness mismatch');return e.function


def compose(outer,inner):
    need(type(outer) is Function and type(inner) is Function and len(outer.box)==len(inner.outputs),'composition profile')
    for v,(a,b) in zip(inner.outputs,outer.box):
        lo,hi=bounds(v,inner.box);need(a<=lo<=hi<=b,'composition domain not certified')
    result=Function(inner.box,tuple(p.substitute(inner.outputs) for p in outer.outputs));degree=max(p.degree for p in outer.outputs)*max(p.degree for p in inner.outputs)
    for x in _grid_points(inner.box,(degree,)*len(inner.box)):need(result.evaluate(x)==outer.evaluate(inner.evaluate(x)),'composition identity mismatch')
    return result

@dataclass(frozen=True, slots=True)
class Operator:
    steps:tuple
    def __post_init__(self):
        need(type(self.steps) is tuple and 1<=len(self.steps)<=MAX_STEPS,'operator budget');need(all(type(v) is tuple and len(v)==2 and v[0] in ('D','I') and type(v[1]) is int and 0<=v[1]<MAX_DIM for v in self.steps),'operator step')
    def after(self,other):need(type(other) is Operator,'operator required');return Operator(other.steps+self.steps)
    def apply(self,f):
        need(type(f) is Function,'function required')
        for kind,i in self.steps:
            need(i<len(f.box),'operator axis');before=f
            out=tuple(p.partial(i) if kind=='D' else p.integral(i,f.box[i][0]) for p in f.outputs);f=Function(f.box,out)
            # Integral verification via independent derivative identity + zero anchor.
            for a,b in zip(before.outputs,f.outputs):
                source,target=(a,b) if kind=='D' else (b,a);degree=max(source.degree,target.degree)
                for x in _grid_points(f.box,(degree,)*len(f.box)):
                    v=q(sum((c*e[i]*prod(q(t**(k-int(j==i))) for j,(t,k) in enumerate(zip(x,e))) for e,c in source.terms if e[i]),Q(0)));need(target.evaluate(x)==v,'operator derivative identity')
                    if kind=='I':y=list(x);y[i]=f.box[i][0];need(source.evaluate(y)==0,'operator anchor identity')
        return f

@dataclass(frozen=True, slots=True)
class Witness:
    operation:str
    operands:tuple
    steps:tuple
    result:Function

def manipulate(op,a,b=None):
    need(type(a) is Function,'function required')
    if isinstance(op,Operator):need(b is None,'operator operands');return Witness('operator',(a.identity,),op.steps,op.apply(a))
    need(type(b) is Function,'function required')
    if op=='compose':f=compose(a,b)
    else:
        need(a.box==b.box and len(a.outputs)==len(b.outputs),'arithmetic domain/output mismatch');need(op in ('add','subtract','multiply','divide'),'operation')
        if op=='divide':
            for p in b.outputs:
                lo,hi=bounds(p,b.box);need(lo>0 or hi<0,'denominator not certified nonzero')
        f=Function(a.box,tuple(x.add(y) if op=='add' else x.add(y.scale(-1)) if op=='subtract' else x.multiply(y) if op=='multiply' else x.divide_exact(y) for x,y in zip(a.outputs,b.outputs)))
        d=max(p.degree for p in a.outputs)+max(p.degree for p in b.outputs) if op=='multiply' else max(max(p.degree for p in a.outputs),max(p.degree for p in b.outputs)+max(p.degree for p in f.outputs)) if op=='divide' else max(p.degree for p in (*a.outputs,*b.outputs))
        for x in _grid_points(a.box,(d,)*len(a.box)):
            av,bv=a.evaluate(x),b.evaluate(x);rv=f.evaluate(x)
            if op=='divide':need(tuple(u*v for u,v in zip(rv,bv))==av,'division identity')
            else:
                expected=tuple(u+v if op=='add' else u-v if op=='subtract' else u*v for u,v in zip(av,bv));need(rv==expected,'arithmetic identity')
    return Witness(op,(a.identity,b.identity),(),f)

def replay_operation(e,a,b=None):
    need(type(e) is Witness and manipulate(Operator(e.steps) if e.operation=='operator' else e.operation,a,b)==e,'operation witness mismatch');return e.result


def export_additive(f):
    """Lossless separable polynomial checkpoint. Cross terms never silently dropped."""
    need(type(f) is Function,'function required');d=len(f.box);n=max(p.degree for p in f.outputs);need(n<=8,'checkpoint degree budget')
    def binary(x):
        try:v=float(x)
        except OverflowError as exc:raise ValueError('binary64 transport') from exc
        need(Q(v)==x,'lossy binary64 transport');return v
    coeff=[];bias=[]
    for p in f.outputs:
        need(all(sum(k!=0 for k in e)<=1 for e,c in p.terms),'nonseparable checkpoint export')
        terms=dict(p.terms);bias.append(binary(terms.get((0,)*d,0)));row=[]
        for i,(lo,hi) in enumerate(f.box):
            rem=scalar.poly([0]+[terms.get(tuple(k if j==i else 0 for j in range(d)),0) for k in range(1,n+1)]);basis=w.cheb_polys(lo,hi,n);cs=[Q(0)]*(n+1)
            for k in range(n,-1,-1):cs[k]=q((rem[k] if k<len(rem) else 0)/basis[k][-1]);rem=scalar.add(rem,scalar.scale(basis[k],-cs[k]))
            need(rem==(Q(0),),'basis residual');row.append(list(map(binary,cs)))
        coeff.append(row)
    cp=pk.export_checkpoint(Network((Layer('chebyshev',n,[[binary(a),binary(b)] for a,b in f.box],coeff,[[1.]*d for _ in f.outputs],bias),)))
    need(extract(cp).function==f,'checkpoint roundtrip mismatch');return cp


def export_quadratic(f):
    """Exact bivariate quadratic export using the polarization identity.

    Closed unit box only, at most three outputs; four hidden coordinates
    x, y, (x+y)/2, (x-y)/2. No approximate fitting or silent coefficient loss.
    """
    need(type(f) is Function and f.box==((Q(-1),Q(1)),)*2 and all(p.degree<=2 for p in f.outputs),'quadratic export profile')
    def binary(x):
        try:v=float(x)
        except OverflowError as exc:raise ValueError('binary64 transport') from exc
        need(Q(v)==x,'lossy binary64 transport');return v
    hidden=Layer('chebyshev',1,[[-1,1]]*2,[[[0,1],[0,0]],[[0,0],[0,1]],[[0,.5],[0,.5]],[[0,.5],[0,-.5]]],[[1,0],[0,1],[1,1],[1,1]],[0]*4)
    coeff=[];bias=[]
    for p in f.outputs:
        t=dict(p.terms);a=t.get((2,0),Q(0));b=t.get((0,2),Q(0));c=t.get((1,1),Q(0));u=t.get((1,0),Q(0));v=t.get((0,1),Q(0))
        coeff.append([list(map(binary,row)) for row in ((a/2,u,a/2),(b/2,v,b/2),(c/2,0,c/2),(-c/2,0,-c/2))]);bias.append(binary(t.get((0,0),Q(0))))
    outer=Layer('chebyshev',2,[[-1,1]]*4,coeff,[[1]*4 for _ in f.outputs],bias)
    cp=pk.export_checkpoint(Network((hidden,outer)));need(extract(cp).function==f,'quadratic checkpoint roundtrip mismatch');return cp


MAX_CELLS=32

@dataclass(frozen=True, slots=True)
class Atlas:
    """Disjoint interiors of a tensor partition; exact common-face agreement.

    Each cell certifies a closed restricted polynomial. Derivatives of cells
    describe polynomial extensions, not a global derivative across seams.
    """
    box:tuple
    cuts:tuple
    cells:tuple
    def __post_init__(self):
        need(type(self.cells) is tuple and 1<=len(self.cells)<=MAX_CELLS and all(type(f) is Function for f in self.cells),'cell budget');d=len(self.cells[0].box);b=box_checked(self.box,d);object.__setattr__(self,'box',b)
        need(type(self.cuts) is tuple and len(self.cuts)==d and all(type(v) is tuple and 2<=len(v)<=MAX_CELLS+1 for v in self.cuts),'partition budget');cuts=tuple(tuple(map(q,v)) for v in self.cuts);object.__setattr__(self,'cuts',cuts)
        need(all(v[0]==a and v[-1]==z and all(l<r for l,r in zip(v,v[1:])) for v,(a,z) in zip(cuts,b)),'partition domain')
        shape=tuple(len(v)-1 for v in cuts);need(prod(shape)==len(self.cells),'partition count');mapping={}
        for idx,f in zip(product(*[range(k) for k in shape]),self.cells):
            expected=tuple((v[i],v[i+1]) for v,i in zip(cuts,idx));need(f.box==expected and len(f.outputs)==len(self.cells[0].outputs),'partition cell identity');mapping[idx]=f
        # Verify exact common-face polynomials by substituting the fixed axis,
        # not by merely comparing a handful of arbitrary samples.
        for idx,f in mapping.items():
            for axis,k in enumerate(idx):
                if k+1>=shape[axis]:continue
                adj=idx[:axis]+(k+1,)+idx[axis+1:];g=mapping[adj];fixed=cuts[axis][k+1]
                inner=tuple(constant(d,fixed) if i==axis else variable(d,i) for i in range(d))
                need(all(p.substitute(inner)==r.substitute(inner) for p,r in zip(f.outputs,g.outputs)),'discontinuous partition face')
    def evaluate(self,point):
        need(type(point) in (tuple,list) and len(point)==len(self.box),'point shape');point=tuple(map(q,point));need(all(a<=v<=b for v,(a,b) in zip(point,self.box)),'outside certified box')
        return next(f.evaluate(point) for f in self.cells if all(a<=v<=b for v,(a,b) in zip(point,f.box)))

@dataclass(frozen=True, slots=True)
class AtlasExtraction:
    checkpoint_sha256:str
    atlas:Atlas


def extract_atlas(cp,box=None):
    need(type(cp) is pk.Checkpoint,'typed checkpoint');l=cp.model().layers[0];d=l.inputs;need(1<=d<=MAX_DIM,'symbolic dimensions')
    if box is None:box=tuple((w.q(v[0]),w.q(v[-1])) for v in l.grid)
    box=box_checked(box,d);cuts=tuple(tuple(sorted({a,b}|({w.q(t) for t in l.grid[i] if a<w.q(t)<b} if l.kind=='spline_clamped' else set()))) for i,(a,b) in enumerate(box));need(prod(len(v)-1 for v in cuts)<=MAX_CELLS,'partition cell budget')
    cells=tuple(extract(cp,tuple(b)).function for b in product(*[tuple(zip(v,v[1:])) for v in cuts]))
    return AtlasExtraction(cp.identity,Atlas(box,cuts,cells))

def replay_atlas(cp,e):
    need(type(e) is AtlasExtraction and extract_atlas(cp,e.atlas.box)==e,'atlas witness mismatch');return e.atlas
