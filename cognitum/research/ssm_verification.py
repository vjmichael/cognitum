"""Bounded exact dissipativity and polynomial verification; no live execution."""
from dataclasses import dataclass
from fractions import Fraction as Q
from hashlib import sha256
from . import ssm_linear as s, ssm_analysis as a, ssm_foundations as f

mm, tr, add, sub = a.mm, a.tr, a.add, a.sub


def _join(x,y,z,w):
    return tuple(r+t for r,t in zip(x,y))+tuple(r+t for r,t in zip(z,w))


def _receipt(profile,m,**kwargs):
    return s.canonical(dict(profile=profile,model_sha256=m.digest,execution_authorized=False,**kwargs))


def dissipativity(m,p,supply):
    """Storage V=x^T P x, supply [u;y]^T S [u;y], all states/inputs."""
    n=a._model(m);k=len(m.input_units);l=len(m.output_units)
    p=a._symmetric(p,n);supply=a._symmetric(supply,k+l)
    pp=a._ldl(p,True);s.need(pp is not None,'positive storage required')
    z=a._zeros(k,n);j=tuple(r+t for r,t in zip(z,s.eye(k)))+tuple(r+t for r,t in zip(m.c,m.d))
    supplied=mm(tr(j),mm(supply,j))
    if m.domain=='continuous':
        w=mm(p,m.b);delta=_join(add(mm(tr(m.a),p),mm(p,m.a)),w,tr(w),a._zeros(k,k))
    else:
        w=tuple(r+t for r,t in zip(m.a,m.b));delta=sub(mm(tr(w),mm(p,w)),_join(p,a._zeros(n,k),a._zeros(k,n),a._zeros(k,k)))
    slack=sub(supplied,delta);piv=a._ldl(slack,False);s.need(piv is not None,'dissipation inequality failed')
    return _receipt('cognitum.ssm.dissipation.v1',m,p=p,supply=supply,slack=slack,p_pivots=pp,slack_pivots=piv)


def passivity(m,p):
    a._model(m);k=len(m.input_units);s.need(k==len(m.output_units),'passivity requires matched ports')
    z=a._zeros(k,k);return dissipativity(m,p,_join(z,s.eye(k),s.eye(k),z))


def gain_bound(m,p,gamma):
    a._model(m);gamma=s.rat(gamma);s.need(gamma>0,'positive gain required')
    s.need(a.stability(m)['strictly_stable'],'strict stability required')
    k=len(m.input_units);l=len(m.output_units)
    supply=_join(f.scale(s.eye(k),gamma*gamma),a._zeros(k,l),a._zeros(l,k),f.neg(s.eye(l)))
    witness=dissipativity(m,p,supply)
    return _receipt('cognitum.ssm.gain_bound.v1',m,gamma=gamma,p=a._symmetric(p,len(m.a)),dissipation_sha256=sha256(witness).hexdigest(),zero_initial_state=True)


def frequency_lower(m,real,imag,vr,vi):
    """Exact squared gain lower bound in one complex direction at one frequency."""
    n=a._model(m);real=s.rat(real);imag=s.rat(imag);k=len(m.input_units)
    s.need(real==0 if m.domain=='continuous' else real*real+imag*imag==1,'frequency domain')
    s.need(a.stability(m)['strictly_stable'],'strict stability required')
    vr=s.vector(vr,k);vi=s.vector(vi,k);den=sum(v*v for v in vr+vi);s.need(den>0,'zero direction')
    d=sub(f.scale(s.eye(n),real),m.a);j=f.scale(s.eye(n),imag)
    system=_join(d,f.neg(j),j,d);rhs=tuple((x,) for x in s.mv(m.b,vr)+s.mv(m.b,vi));x=s._solve(system,rhs)
    xr=tuple(v[0] for v in x[:n]);xi=tuple(v[0] for v in x[n:]);yr=s.va(s.mv(m.c,xr),s.mv(m.d,vr));yi=s.va(s.mv(m.c,xi),s.mv(m.d,vi))
    lower=s.bounded(sum(v*v for v in yr+yi)/den)
    return dict(model_sha256=m.digest,real=real,imag=imag,direction_real=vr,direction_imag=vi,lower_squared=lower,execution_authorized=False)


def replay(m,p,parameter,raw,kind):
    s.need(type(raw) is bytes and 0<len(raw)<=s.FRAME,'receipt budget')
    if kind=='gain':expected=gain_bound(m,p,parameter)
    elif kind=='dissipation':expected=dissipativity(m,p,parameter)
    else:raise ValueError('unsupported receipt')
    s.need(raw==expected,'receipt mismatch');return True


@dataclass(frozen=True,slots=True)
class Polynomial:
    """Autonomous rational polynomial vector field/map, dimension 1..4, degree <=3."""
    terms:tuple
    domain:str='continuous'
    def __post_init__(self):
        s.need(type(self.terms) is tuple and 1<=len(self.terms)<=4,'polynomial dimension');n=len(self.terms)
        s.need(type(self.domain) is str and self.domain in ('continuous','discrete'),'domain')
        rows=[]
        for row in self.terms:
            s.need(type(row) is tuple and len(row)<=32,'term budget');seen=set();out=[]
            for term in row:
                s.need(type(term) is tuple and len(term)==2,'term shape');ex,c=term
                s.need(type(ex) is tuple and len(ex)==n and all(type(v) is int and 0<=v<=3 for v in ex) and sum(ex)<=3,'degree budget')
                s.need(ex not in seen,'duplicate monomial');seen.add(ex);out.append((ex,s.rat(c)))
            rows.append(tuple(sorted(out)))
        object.__setattr__(self,'terms',tuple(rows))
    @property
    def digest(self):return sha256(s.canonical(dict(terms=self.terms,domain=self.domain))).hexdigest()


def _mul(x,y):
    v=tuple(s.bounded(u*w) for u in x for w in y);return min(v),max(v)


def _power(x,e):
    if not e:return Q(1),Q(1)
    lo,hi=x;u,v=s.bounded(lo**e),s.bounded(hi**e)
    return (Q(0) if e%2==0 and lo<=0<=hi else min(u,v),max(u,v))


def _interval(row,box):
    lo=hi=Q(0)
    for ex,c in row:
        v=(c,c)
        for x,e in zip(box,ex):v=_mul(v,_power(x,e))
        lo=s.bounded(lo+v[0]);hi=s.bounded(hi+v[1])
    return lo,hi


def _box(m,lo,hi):
    s.need(type(m) is Polynomial,'typed polynomial');n=len(m.terms);lo=s.vector(lo,n,a._q);hi=s.vector(hi,n,a._q)
    s.need(all(x<=y for x,y in zip(lo,hi)),'invalid box');return tuple(zip(lo,hi))


def _derivative(row,j):
    return tuple((ex[:j]+(ex[j]-1,)+ex[j+1:],s.bounded(c*ex[j])) for ex,c in row if ex[j])


def equilibrium(m,x):
    box=_box(m,x,x);point=tuple(v[0] for v in box);value=tuple(_interval(row,box)[0] for row in m.terms)
    jac=tuple(tuple(_interval(_derivative(row,j),box)[0] for j in range(len(box))) for row in m.terms)
    residual=value if m.domain=='continuous' else tuple(s.bounded(v-w) for v,w in zip(value,point))
    return dict(model_sha256=m.digest,point=point,residual=residual,equilibrium=not any(residual),jacobian=jac,execution_authorized=False)


def linearization(m,x):
    """Strict stability of a verified equilibrium Jacobian implies local exponential stability."""
    eq=equilibrium(m,x);s.need(eq['equilibrium'],'equilibrium required');n=len(m.terms)
    linear=s.Model(eq['jacobian'],a._zeros(n,1),a._zeros(1,n),((Q(0),),),('state',)*n,('none',),('none',),m.domain)
    witness=a.stability(linear);p=witness['p'];stable=p is not None
    return dict(model_sha256=m.digest,point=eq['point'],jacobian=eq['jacobian'],local_exponential_stability_proved=stable,linear_model_sha256=linear.digest,lyapunov_sha256=sha256(a.lyapunov_certificate(linear,p)).hexdigest() if stable else None,execution_authorized=False)


def invariant_box(m,lo,hi):
    """Universal polynomial face test (flow) or image inclusion (map)."""
    box=_box(m,lo,hi);s.need(all(l<h for l,h in box),'nondegenerate box')
    checks=[]
    for i,row in enumerate(m.terms):
        l,h=box[i]
        if m.domain=='continuous':
            lower=_interval(row,box[:i]+((l,l),)+box[i+1:]);upper=_interval(row,box[:i]+((h,h),)+box[i+1:]);s.need(lower[0]>=0 and upper[1]<=0,'inward face failed');checks.append((lower,upper))
        else:
            image=_interval(row,box);s.need(l<=image[0]<=image[1]<=h,'map inclusion failed');checks.append(image)
    return _receipt('cognitum.ssm.invariant_box.v1',m,box=box,checks=checks)


def local_contraction(m,lo,hi,x,rate):
    """Invariant convex box and infinity-norm contraction about known equilibrium."""
    box=_box(m,lo,hi);eq=equilibrium(m,x);rate=s.rat(rate)
    s.need(eq['equilibrium'] and all(l<=z<=h for (l,h),z in zip(box,eq['point'])),'equilibrium in box required')
    s.need(rate>0 and (m.domain=='continuous' or rate<1),'contraction rate');inv=invariant_box(m,lo,hi)
    jac=tuple(tuple(_interval(_derivative(row,j),box) for j in range(len(box))) for row in m.terms)
    bounds=[]
    for i,row in enumerate(jac):
        bound=sum((max(abs(l),abs(h)) for j,(l,h) in enumerate(row) if j!=i),Q(0))
        bound=s.bounded(bound+(row[i][1] if m.domain=='continuous' else max(map(abs,row[i]))));bounds.append(bound)
    s.need(all(v<=(-rate if m.domain=='continuous' else rate) for v in bounds),'contraction bound failed')
    return _receipt('cognitum.ssm.local_contraction.v1',m,box=box,point=eq['point'],rate=rate,row_bounds=tuple(bounds),invariance_sha256=sha256(inv).hexdigest())


def validated_step(m,lo,hi,tube_lo,tube_hi,h):
    """Exact Picard tube inclusion and terminal enclosure for autonomous flow."""
    box=_box(m,lo,hi);tube=_box(m,tube_lo,tube_hi);h=s.rat(h);s.need(m.domain=='continuous' and h>0,'positive flow step')
    field=tuple(_interval(row,tube) for row in m.terms)
    end=[]
    for (l,u),(tl,tu),(fl,fu) in zip(box,tube,field):
        s.need(tl<s.bounded(l+min(Q(0),s.bounded(h*fl))) and s.bounded(u+max(Q(0),s.bounded(h*fu)))<tu,'strict Picard tube inclusion failed')
        end.append((s.bounded(l+h*fl),s.bounded(u+h*fu)))
    return dict(model_sha256=m.digest,tube=tube,initial=box,endpoint=tuple(end),step=h,execution_authorized=False)


def normal_form(kind,mu,cubic=-1):
    """Analytic canonical saddle-node / Hopf families, not generic detection."""
    mu=s.rat(mu);cubic=s.rat(cubic)
    if kind=='saddle_node':
        # x'=mu-x^2; roots +/- sqrt(mu), with nonzero f_mu and f_xx.
        return dict(kind=kind,mu=mu,real_equilibria=2 if mu>0 else 1 if mu==0 else 0,fold=mu==0,root_squared=mu if mu>=0 else None,positive_root_stable=mu>0,execution_authorized=False)
    s.need(kind=='hopf' and cubic!=0,'supported nondegenerate normal form required')
    # z'=(mu+i)z+cubic*z*|z|^2. Radial equation r'=mu*r+cubic*r^3.
    radius=s.bounded(-mu/cubic);return dict(kind=kind,mu=mu,cubic=cubic,hopf=mu==0,supercritical=cubic<0,origin_strictly_linearly_stable=mu<0,cycle_radius_squared=radius if radius>0 else None,cycle_attracting=radius>0 and mu>0,execution_authorized=False)
