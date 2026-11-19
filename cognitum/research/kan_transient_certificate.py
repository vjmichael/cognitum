"""COG-04K: exact continuous certificate for 1+1D parabolic tensor KAN.
Independently reconstructs piecewise polynomials from binary64 checkpoint values.
For u_t-a*u_xx+c*u=f, a>0,c>=0 on the unit space-time rectangle.
"""
from dataclasses import dataclass
from fractions import Fraction as Q
from math import comb
import hashlib,json
from . import kan_elliptic_certificate as v

need,number=v.need,v.number
PROFILE='cog04k-parabolic-tensor-cubic-v1'

@dataclass(frozen=True,slots=True)
class Problem:
    diffusion:float
    reaction:float
    forcing:tuple
    initial:tuple # power coefficients, ascending; exact endpoint zero
    def __post_init__(self):
        v.Problem(self.diffusion,1,self.reaction,self.forcing)
        need(type(self.initial) is tuple and 1<=len(self.initial)<=5,'initial degree budget')
        p=tuple(number(x) for x in self.initial)
        need(p[0]==0 and sum(p)==0 and (len(p)==1 or p[-1]!=0),'canonical zero-endpoint initial polynomial')
    @property
    def identity(self):return v._identity([PROFILE,v.Problem(self.diffusion,1,self.reaction,self.forcing).identity,[str(Q(x)) for x in self.initial]])

@dataclass(frozen=True,slots=True)
class Model:
    # The represented solution is g(x)+s(x,t), not just s.
    spline:v.Model
    def __post_init__(self):need(type(self.spline) is v.Model,'typed tensor spline')
    def checkpoint(self):
        m=self.spline
        return json.dumps(dict(profile=PROFILE,x=list(m.xcuts),t=list(m.ycuts),c=list(m.coefficients)),separators=(',',':'),allow_nan=False).encode('ascii')
    @property
    def identity(self):return hashlib.sha256(self.checkpoint()).hexdigest()

def restore(raw):
    need(type(raw) is bytes and len(raw)<=v.MAX_BYTES,'checkpoint size/type')
    a=json.loads(raw);need(type(a) is dict and set(a)=={'profile','x','t','c'} and a['profile']==PROFILE,'checkpoint profile')
    need(all(type(a[k]) is list for k in ('x','t','c')),'checkpoint vectors')
    m=Model(v.Model(tuple(a['x']),tuple(a['t']),tuple(a['c'])));need(m.checkpoint()==raw,'noncanonical checkpoint');return m

def shift(terms,x0,x1,t0,t1):
    p={}
    for i,j,c in terms:
        for k in range(i+1):
            for l in range(j+1):
                v._acc(p,(k,l),Q(c)*comb(i,k)*comb(j,l)*x0**(i-k)*(x1-x0)**k*t0**(j-l)*(t1-t0)**l)
    return p

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
    squared_l2:Q
    solution_error_upper:Q|None

def assess(problem,model):
    need(type(problem) is Problem and type(model) is Model,'typed problem/model')
    m=model.spline;xs,ts=v._basis(m.xcuts),v._basis(m.ycuts);nx,nt=m.shape
    patches={};cells=[];initial=boundary=interfaces=True
    for ix,(x0,x1,bx) in enumerate(xs):
        for it,(t0,t1,bt) in enumerate(ts):
            p={}
            for i,px in enumerate(bx):
                for j,pt in enumerate(bt):
                    c=Q(m.coefficients[i*nt+j])
                    if c:
                        for k,a in enumerate(px):
                            for l,b in enumerate(pt):v._acc(p,(k,l),c*a*b)
            g=shift(tuple((i,0,c) for i,c in enumerate(problem.initial)),x0,x1,t0,t1)
            # Check the zero correction on initial face; include the lifting on spatial faces.
            if it==0:initial=initial and not v._trace(p,1,0)
            for e,c in g.items():v._acc(p,e,c)
            patches[ix,it]=p
            if ix==0:boundary=boundary and not v._trace(p,0,0)
            if ix==len(xs)-1:boundary=boundary and not v._trace(p,0,1)
            for axis,index,segments in [(0,ix,xs),(1,it,ts)]:
                if index:
                    old=patches[(ix-1,it) if axis==0 else (ix,it-1)]
                    hlo=segments[index-1][1]-segments[index-1][0];hhi=segments[index][1]-segments[index][0]
                    for order in range(3):
                        interfaces=interfaces and v._trace(v._diff(old,axis,order,hlo),axis,1)==v._trace(v._diff(p,axis,order,hhi),axis,0)
            r={}
            for e,c in p.items():v._acc(r,e,Q(problem.reaction)*c)
            for e,c in v._diff(p,1,1,t1-t0).items():v._acc(r,e,c)
            for e,c in v._diff(p,0,2,x1-x0).items():v._acc(r,e,-Q(problem.diffusion)*c)
            for e,c in shift(problem.forcing,x0,x1,t0,t1).items():v._acc(r,e,-c)
            R,L2=v._bounds(r,x1-x0,t1-t0);cells.append(v.Cell((x0,x1,t0,t1),R,L2))
    valid=initial and boundary and interfaces;slabs=[];acc=peak=Q(0);bounds=[]
    # Comparison principle: on each time slab, integrate the spatial sup residual.
    # Alternative stationary spatial and reaction barriers apply over the prefix.
    for t0,t1,_ in ts:
        R=max(c.residual_upper for c in cells if c.box[2:]==(t0,t1));acc+=(t1-t0)*R;peak=max(peak,R)
        candidates=[acc,peak/(8*Q(problem.diffusion))]
        if problem.reaction:candidates.append(peak/Q(problem.reaction))
        bound=min(candidates) if valid else None
        slabs.append(Slab((t0,t1),R,acc,bound));bounds.append(bound)
    return Certificate(problem.identity,model.identity,tuple(cells),tuple(slabs),initial,boundary,interfaces,peak,sum((c.squared_l2 for c in cells),Q(0)),max(bounds) if valid else None)

def replay(problem,model,certificate):
    need(type(certificate) is Certificate and assess(problem,model)==certificate,'certificate replay mismatch');return certificate

def require_accuracy(problem,model,certificate,tolerance):
    t=number(tolerance);need(t>0,'positive tolerance');c=replay(problem,model,certificate)
    need(c.solution_error_upper is not None and c.solution_error_upper<=t,'accuracy/condition budget unmet');return c
