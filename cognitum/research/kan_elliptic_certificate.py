"""COG-04J independent exact verifier for bounded tensor-product cubic KANs.
No numerical fitting library; the represented binary64 inputs are exact rationals.
"""
from dataclasses import dataclass
from fractions import Fraction as Q
from math import comb, isfinite
import hashlib
import json

MAX_SPLITS = 6
MAX_DEGREE = 4
MAX_BYTES = 32768


def need(ok, msg):
    if not ok:
        raise ValueError(msg)


def number(x, bound=100):
    need(type(x) in (int, float) and abs(x) <= bound and isfinite(x), 'bounded finite number')
    return Q(x)


def _identity(data):
    return hashlib.sha256(json.dumps(data, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class Problem:
    """-ax*u_xx-ay*u_yy+c*u=f on [0,1]^2, all four faces zero."""
    ax: float
    ay: float
    reaction: float
    forcing: tuple  # ordered unique (x exponent, y exponent, coefficient)

    def __post_init__(self):
        need(number(self.ax)>=Q(1,16) and number(self.ay)>=Q(1,16), 'positive bounded diffusion')
        need(number(self.reaction)>=0, 'nonnegative reaction required')
        need(type(self.forcing) is tuple and len(self.forcing)<=25, 'forcing term budget')
        prev=(-1,-1)
        for term in self.forcing:
            need(type(term) is tuple and len(term)==3, 'forcing term schema')
            i,j,v=term
            need(type(i) is type(j) is int and 0<=i<=MAX_DEGREE and 0<=j<=MAX_DEGREE and (i,j)>prev, 'ordered unique bounded exponents')
            need(number(v)!=0,'nonzero forcing coefficient');prev=(i,j)

    @property
    def identity(self):
        return _identity([str(number(self.ax)),str(number(self.ay)),str(number(self.reaction)),[(i,j,str(number(v))) for i,j,v in self.forcing]])


@dataclass(frozen=True, slots=True)
class Model:
    """Sum of products of cubic univariate spline edges, coefficients C_ij.
    Tensor-product KAN research architecture, not the existing additive MEL wire.
    """
    xcuts: tuple
    ycuts: tuple
    coefficients: tuple  # row major, x index first

    def __post_init__(self):
        for cuts in (self.xcuts,self.ycuts):
            need(type(cuts) is tuple and len(cuts)<=MAX_SPLITS,'knot budget')
            p=Q(0)
            for v in cuts:
                r=number(v,1);need(r-p>=Q(1,64) and (r*64).denominator==1,'separated dyadic knots');p=r
            need(1-p>=Q(1,64),'right knot separation')
        need(len(self.xcuts)+len(self.ycuts)<=MAX_SPLITS,'total knot budget')
        nx,ny=self.shape
        need(type(self.coefficients) is tuple and len(self.coefficients)==nx*ny,'coefficient shape')
        for v in self.coefficients:number(v,10000)

    @property
    def shape(self):return len(self.xcuts)+4,len(self.ycuts)+4

    def checkpoint(self):
        return json.dumps({'profile':'cog04j-tensor-cubic-v1','x':list(self.xcuts),'y':list(self.ycuts),'c':list(self.coefficients)},separators=(',',':'),allow_nan=False).encode('ascii')

    @property
    def identity(self):return hashlib.sha256(self.checkpoint()).hexdigest()


def restore(raw):
    need(type(raw) is bytes and len(raw)<=MAX_BYTES,'checkpoint size/type')
    v=json.loads(raw)
    need(type(v) is dict and set(v)=={'profile','x','y','c'} and v['profile']=='cog04j-tensor-cubic-v1','checkpoint profile')
    need(all(type(v[k]) is list for k in ('x','y','c')),'checkpoint vectors')
    m=Model(tuple(v['x']),tuple(v['y']),tuple(v['c']));need(m.checkpoint()==raw,'noncanonical checkpoint');return m


def _plus(a,b):
    return tuple((a[i] if i<len(a) else Q(0))+(b[i] if i<len(b) else Q(0)) for i in range(max(len(a),len(b))))


def _linear(p,a,b):
    return _plus(tuple(a*c for c in p),(Q(0),)+tuple(b*c for c in p))


def _basis(cuts):
    """Cox-de Boor in local unit coordinate, no sampled values or SciPy."""
    edges=(Q(0),*map(Q,cuts),Q(1));g=(Q(0),)*3+edges+(Q(1),)*3
    cells=[]
    for k in range(3,len(g)-4):
        lo,hi=g[k:k+2];h=hi-lo
        prev=[(Q(int(i==k)),) for i in range(len(g)-1)]
        for d in range(1,4):
            cur=[]
            for i in range(len(g)-d-1):
                l=g[i+d]-g[i];r=g[i+d+1]-g[i+1];p=(Q(0),)
                if l:p=_plus(p,_linear(prev[i],(lo-g[i])/l,h/l))
                if r:p=_plus(p,_linear(prev[i+1],(g[i+d+1]-lo)/r,-h/r))
                cur.append(p)
            prev=cur
        cells.append((lo,hi,tuple(prev)))
    return cells


def _acc(p,k,c):
    v=p.get(k,Q(0))+c
    if v:p[k]=v
    else:p.pop(k,None)


def _diff(p,axis,order,h):
    out={}
    for (i,j),v in p.items():
        k=(i,j)[axis]
        if k<order:continue
        mult=1
        for t in range(order):mult*=k-t
        e=(i-order,j) if axis==0 else (i,j-order)
        _acc(out,e,v*mult/h**order)
    return out


def _trace(p,axis,end):
    out={}
    for e,v in p.items():
        if end or e[axis]==0:_acc(out,e[1-axis],v)
    return out


def _residual(p,problem,x0,x1,y0,y1):
    r={}
    for e,v in p.items():_acc(r,e,v*Q(problem.reaction))
    for axis,h,a in [(0,x1-x0,problem.ax),(1,y1-y0,problem.ay)]:
        for e,v in _diff(p,axis,2,h).items():_acc(r,e,-Q(a)*v)
    for i,j,v in problem.forcing:
        for k in range(i+1):
            for l in range(j+1):
                _acc(r,(k,l),-Q(v)*comb(i,k)*comb(j,l)*x0**(i-k)*(x1-x0)**k*y0**(j-l)*(y1-y0)**l)
    return r


def _bounds(r,hx,hy):
    nx=max((i for i,j in r),default=0);ny=max((j for i,j in r),default=0)
    b=[sum((v*Q(comb(i,k),comb(nx,k))*Q(comb(j,l),comb(ny,l)) for (k,l),v in r.items() if k<=i and l<=j),Q(0)) for i in range(nx+1) for j in range(ny+1)]
    norm=hx*hy*sum((v*w/Q((i+k+1)*(j+l+1)) for (i,j),v in r.items() for (k,l),w in r.items()),Q(0))
    need(norm>=0,'squared residual identity');return max(map(abs,b)),norm


@dataclass(frozen=True,slots=True)
class Cell:
    box:tuple
    residual_upper:Q
    squared_l2:Q


@dataclass(frozen=True,slots=True)
class Certificate:
    problem_sha256:str
    model_sha256:str
    cells:tuple
    hard_conditions:bool
    c2_interfaces:bool
    residual_upper:Q
    squared_l2:Q
    solution_error_upper:Q|None


def assess(problem,model):
    need(type(problem) is Problem and type(model) is Model,'typed problem/model')
    xs,ys=_basis(model.xcuts),_basis(model.ycuts);nx,ny=model.shape
    patches={};cells=[];boundary=True;continuous=True
    for ix,(x0,x1,bx) in enumerate(xs):
        for iy,(y0,y1,by) in enumerate(ys):
            p={}
            for i,px in enumerate(bx):
                for j,py in enumerate(by):
                    v=Q(model.coefficients[i*ny+j]);
                    if not v:continue
                    for k,a in enumerate(px):
                        for l,b in enumerate(py):
                            if a and b:_acc(p,(k,l),v*a*b)
            patches[ix,iy]=p
            for axis,index,count in [(0,ix,len(xs)),(1,iy,len(ys))]:
                if index==0:boundary=boundary and not _trace(p,axis,0)
                if index==count-1:boundary=boundary and not _trace(p,axis,1)
                if index>0:
                    prev=patches[(ix-1,iy) if axis==0 else (ix,iy-1)]
                    old=xs[ix-1] if axis==0 else ys[iy-1];new=xs[ix] if axis==0 else ys[iy]
                    for order in range(3):
                        continuous=continuous and _trace(_diff(prev,axis,order,old[1]-old[0]),axis,1)==_trace(_diff(p,axis,order,new[1]-new[0]),axis,0)
            r=_residual(p,problem,x0,x1,y0,y1);bound,norm=_bounds(r,x1-x0,y1-y0)
            cells.append(Cell((x0,x1,y0,y1),bound,norm))
    R=max(c.residual_upper for c in cells)
    # Barrier b=R*t*(1-t)/(2*max(ax,ay)); positive on all faces,
    # Lb>=R with c>=0. Maximum principle applies to +/- error.
    error=R/(8*max(Q(problem.ax),Q(problem.ay))) if boundary and continuous else None
    return Certificate(problem.identity,model.identity,tuple(cells),boundary,continuous,R,sum((c.squared_l2 for c in cells),Q(0)),error)


def replay(problem,model,cert):
    need(type(cert) is Certificate and assess(problem,model)==cert,'certificate replay mismatch');return cert


def require_accuracy(problem,model,cert,tolerance):
    t=number(tolerance);need(t>0,'positive tolerance');c=replay(problem,model,cert)
    need(c.solution_error_upper is not None and c.solution_error_upper<=t,'accuracy/condition budget unmet');return c
