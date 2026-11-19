"""COG-04L: exact certificate for 2+1D scalar parabolic tensor splines.
Independent of NumPy/SciPy fitting. Binary64 checkpoint values are exact rationals.
Unit square, unit time, constant positive anisotropic diffusion and c>=0.
"""
from dataclasses import dataclass
from fractions import Fraction as Q
from itertools import product
from math import comb, prod
import json, hashlib
from . import kan_elliptic_certificate as v

PROFILE='cog04l-parabolic-tensor-cubic-v1'
MAX_SPLITS=5
MAX_BYTES=65536
need,number=v.need,v.number


def _terms(terms,dim):
    need(type(terms) is tuple and len(terms)<=5**dim,'term budget')
    prev=(-1,)*dim
    for term in terms:
        need(type(term) is tuple and len(term)==dim+1,'term schema')
        e,c=term[:-1],term[-1]
        need(all(type(i) is int and 0<=i<=4 for i in e) and e>prev and number(c)!=0,'canonical terms')
        prev=e


def _trace(p,axis,end):
    out={}
    for e,c in p.items():
        if end or e[axis]==0:v._acc(out,e[:axis]+e[axis+1:],c)
    return out


@dataclass(frozen=True,slots=True)
class Problem:
    ax:float
    ay:float
    reaction:float
    forcing:tuple
    initial:tuple # (i,j,coefficient), polynomial on the square
    def __post_init__(self):
        need(number(self.ax)>=Q(1,16) and number(self.ay)>=Q(1,16) and number(self.reaction)>=0,'coercive diffusion/reaction')
        _terms(self.forcing,3);_terms(self.initial,2)
        g={e[:2]:Q(e[2]) for e in self.initial}
        need(all(not _trace(g,a,z) for a,z in product(range(2),range(2))),'incompatible initial boundary')
    @property
    def identity(self):
        return v._identity([PROFILE,*map(lambda x:str(Q(x)),(self.ax,self.ay,self.reaction)),[(*e[:-1],str(Q(e[-1]))) for e in self.forcing],[(*e[:-1],str(Q(e[-1]))) for e in self.initial]])


@dataclass(frozen=True,slots=True)
class Model:
    cuts:tuple
    coefficients:tuple
    def __post_init__(self):
        need(type(self.cuts) is tuple and len(self.cuts)==3,'three axes required')
        need(all(type(k) is tuple for k in self.cuts) and sum(map(len,self.cuts))<=MAX_SPLITS,'total knot budget')
        for k in self.cuts:
            prev=Q(0)
            for x in k:
                r=number(x,1);need(r-prev>=Q(1,64) and (r*64).denominator==1,'separated dyadic knots');prev=r
            need(1-prev>=Q(1,64),'right knot separation')
        need(type(self.coefficients) is tuple and len(self.coefficients)==prod(self.shape),'tensor shape')
        for x in self.coefficients:number(x,10000)
    @property
    def shape(self):return tuple(len(k)+4 for k in self.cuts)
    def checkpoint(self):return json.dumps(dict(profile=PROFILE,cuts=self.cuts,c=self.coefficients),separators=(',',':'),allow_nan=False).encode('ascii')
    @property
    def identity(self):return hashlib.sha256(self.checkpoint()).hexdigest()


def restore(raw):
    need(type(raw) is bytes and len(raw)<=MAX_BYTES,'checkpoint size/type')
    p=json.loads(raw);need(type(p) is dict and set(p)=={'profile','cuts','c'} and p['profile']==PROFILE,'checkpoint profile')
    need(type(p['cuts']) is list and all(type(k) is list for k in p['cuts']) and type(p['c']) is list,'checkpoint schema')
    m=Model(tuple(map(tuple,p['cuts'])),tuple(p['c']));need(m.checkpoint()==raw,'noncanonical checkpoint');return m


def _diff(p,axis,order,h):
    out={}
    for e,c in p.items():
        k=e[axis]
        if k>=order:v._acc(out,e[:axis]+(k-order,)+e[axis+1:],c*prod(range(k-order+1,k+1))/h**order)
    return out


def _shift(terms,box):
    out={}
    for term in terms:
        ex=term[:-1];c=Q(term[-1])
        for k in product(*(range(i+1) for i in ex)):
            v._acc(out,k,c*prod(comb(i,j)*a**(i-j)*(b-a)**j for i,j,(a,b) in zip(ex,k,box)))
    return out


def _bernstein_bound(p):
    # Separable exact power-to-Bernstein conversion on [0,1]^3.
    degrees=tuple(max((e[a] for e in p),default=0) for a in range(3))
    b=p
    for a,n in enumerate(degrees):
        out={}
        for e,c in b.items():
            for j in range(e[a],n+1):v._acc(out,e[:a]+(j,)+e[a+1:],c*Q(comb(j,e[a]),comb(n,e[a])))
        b=out
    return max(map(abs,b.values()),default=Q(0))


def _patch(model,bases):
    _,ny,nt=model.shape;p={}
    # Only nonzero local basis polynomials participate.
    active=[[(i,[(j,c) for j,c in enumerate(poly) if c]) for i,poly in enumerate(b) if any(poly)] for b in bases]
    for (i,bx),(j,by),(k,bt) in product(*active):
        c=Q(model.coefficients[(i*ny+j)*nt+k])
        if c:
            for (a,x),(b,y),(d,t) in product(bx,by,bt):v._acc(p,(a,b,d),c*x*y*t)
    return p


@dataclass(frozen=True,slots=True)
class Cell:
    box:tuple
    residual_upper:Q

@dataclass(frozen=True,slots=True)
class Slab:
    interval:tuple
    residual_upper:Q
    accumulated_upper:Q
    solution_error_upper:Q|None

@dataclass(frozen=True,slots=True)
class Certificate:
    problem_sha256:str
    model_sha256:str
    cells:tuple
    slabs:tuple
    initial_exact:bool
    boundary_exact:bool
    interfaces_exact:bool
    residual_upper:Q
    solution_error_upper:Q|None


def assess(problem,model):
    need(type(problem) is Problem and type(model) is Model,'typed problem/model')
    axes=tuple(v._basis(k) for k in model.cuts);shape=tuple(map(len,axes));patches={};cells=[];initial=boundary=interfaces=True
    for idx in product(*(range(n) for n in shape)):
        seg=tuple(axes[a][i] for a,i in enumerate(idx));box=tuple((s[0],s[1]) for s in seg);h=tuple(b-a for a,b in box)
        p=_patch(model,[s[2] for s in seg]);g=_shift(tuple((i,j,0,c) for i,j,c in problem.initial),box)
        if idx[2]==0:initial=initial and not _trace(p,2,0)
        for e,c in g.items():v._acc(p,e,c)
        patches[idx]=p
        for a,i in enumerate(idx):
            if a<2:
                if i==0:boundary=boundary and not _trace(p,a,0)
                if i==shape[a]-1:boundary=boundary and not _trace(p,a,1)
            if i:
                prev=patches[idx[:a]+(i-1,)+idx[a+1:]];sa=axes[a][i-1];oldh=sa[1]-sa[0]
                for order in range(3):interfaces=interfaces and _trace(_diff(prev,a,order,oldh),a,1)==_trace(_diff(p,a,order,h[a]),a,0)
        r={}
        for e,c in p.items():v._acc(r,e,Q(problem.reaction)*c)
        for a,order,mult in [(0,2,-Q(problem.ax)),(1,2,-Q(problem.ay)),(2,1,Q(1))]:
            for e,c in _diff(p,a,order,h[a]).items():v._acc(r,e,mult*c)
        for e,c in _shift(problem.forcing,box).items():v._acc(r,e,-c)
        cells.append(Cell(box,_bernstein_bound(r)))
    valid=initial and boundary and interfaces;acc=peak=Q(0);slabs=[]
    for a,b,_ in axes[2]:
        R=max(c.residual_upper for c in cells if c.box[2]==(a,b));acc+=(b-a)*R;peak=max(peak,R)
        # Parabolic comparison: accumulated sup residual, or static quadratic
        # barrier in the higher diffusion spatial axis, or reaction barrier.
        candidates=[acc,peak/(8*max(Q(problem.ax),Q(problem.ay)))]
        if problem.reaction:candidates.append(peak/Q(problem.reaction))
        slabs.append(Slab((a,b),R,acc,min(candidates) if valid else None))
    return Certificate(problem.identity,model.identity,tuple(cells),tuple(slabs),initial,boundary,interfaces,peak,max(s.solution_error_upper for s in slabs) if valid else None)


def replay(problem,model,certificate):
    need(type(certificate) is Certificate and assess(problem,model)==certificate,'certificate replay mismatch');return certificate


def require_accuracy(problem,model,certificate,tolerance):
    t=number(tolerance);need(t>0,'positive tolerance');c=replay(problem,model,certificate)
    need(c.solution_error_upper is not None and c.solution_error_upper<=t,'accuracy/condition budget unmet');return c
