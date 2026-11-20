"""Bounded scientific dynamics, exact structure witnesses and numerical ODEs."""
from dataclasses import dataclass
from fractions import Fraction as Q
from hashlib import sha256
from . import ssm_linear as s, ssm_analysis as a, ssm_foundations as f, ssm_verification as v

mm, tr, add, sub = a.mm, a.tr, a.add, a.sub


def dot(x,y):
    return s.bounded(sum((s.bounded(u*w) for u,w in zip(x,y)),Q(0)))


def vs(x,h):return tuple(s.bounded(h*u) for u in x)


def energy(k,x):return s.bounded(dot(x,s.mv(k,x))/2)


def clock(h,signed=False):
    h=s.rat(h);s.need(0<abs(h)<=1 and (signed or h>0),'step budget');return h


def _coeff(a0,n):return a._symmetric(s.matrix(a0,n,n),n)


@dataclass(frozen=True,slots=True)
class Mechanics:
    """Constant positive mass and rational polynomial potential, 1..4 coordinates."""
    mass:tuple
    potential:tuple
    def __post_init__(self):
        s.need(type(self.mass) is tuple and 1<=len(self.mass)<=4,'mechanics dimension');n=len(self.mass)
        m=_coeff(self.mass,n);s.need(a._ldl(m,True) is not None,'positive mass');object.__setattr__(self,'mass',m)
        s.need(type(self.potential) is tuple and len(self.potential)<=32,'potential budget');rows=[];seen=set()
        for item in self.potential:
            s.need(type(item) is tuple and len(item)==2,'term shape');ex,c=item
            s.need(type(ex) is tuple and len(ex)==n and all(type(e) is int and 0<=e<=4 for e in ex) and sum(ex)<=4,'degree budget')
            s.need(ex not in seen,'duplicate monomial');seen.add(ex);rows.append((ex,s.rat(c)))
        object.__setattr__(self,'potential',tuple(sorted(rows)))
    @property
    def digest(self):return sha256(s.canonical(dict(mass=self.mass,potential=self.potential))).hexdigest()


def _point(m,q):
    s.need(type(m) is Mechanics,'typed mechanics');return s.vector(q,len(m.mass),a._q)


def _val(row,q):return v._interval(row,tuple((z,z) for z in q))[0]


def _grad(m,q):return tuple(_val(v._derivative(m.potential,j),q) for j in range(len(q)))


def _hess(m,q):return tuple(tuple(_val(v._derivative(v._derivative(m.potential,i),j),q) for j in range(len(q))) for i in range(len(q)))


def lagrangian(m,q,velocity):
    q=_point(m,q);velocity=_point(m,velocity);p=s.mv(m.mass,velocity);grad=_grad(m,q);acc=tuple(row[0] for row in s._solve(m.mass,s.outercol(vs(grad,-1))))
    s.need(s.va(s.mv(m.mass,acc),grad)==(Q(0),)*len(q),'Euler-Lagrange residual')
    return dict(momentum=p,acceleration=acc,lagrangian=s.bounded(energy(m.mass,velocity)-_val(m.potential,q)),hamiltonian=s.bounded(energy(m.mass,velocity)+_val(m.potential,q)),execution_authorized=False)


def hamiltonian(m,q,p):
    q=_point(m,q);p=_point(m,p);velocity=tuple(row[0] for row in s._solve(m.mass,s.outercol(p)));return s.bounded(dot(p,velocity)/2+_val(m.potential,q))


def symplectic_form(n):
    z=a._zeros(n,n);return v._join(z,s.eye(n),f.neg(s.eye(n)),z)


def verlet(m,q,p,h):
    """Exact rational kick-drift-kick discrete map; not exact continuous flow."""
    q=_point(m,q);p=_point(m,p);h=clock(h,True);n=len(q);inv=s._solve(m.mass,s.eye(n));half=s.va(p,vs(_grad(m,q),-h/2));qn=s.va(q,vs(s.mv(inv,half),h));pn=s.va(half,vs(_grad(m,qn),-h/2))
    z=a._zeros(n,n);eye=s.eye(n);kick=lambda x:v._join(eye,z,f.scale(_hess(m,x),-h/2),eye);drift=v._join(eye,f.scale(inv,h),z,eye)
    tangent=mm(kick(qn),mm(drift,kick(q)));omega=symplectic_form(n);s.need(mm(tr(tangent),mm(omega,tangent))==omega,'symplectic witness')
    return dict(model_sha256=m.digest,initial=(q,p),final=(qn,pn),step=h,tangent=tangent,energy_before=hamiltonian(m,q,p),energy_after=hamiltonian(m,qn,pn),symplectic=True,continuous_flow_exact=False,execution_authorized=False)


def quadratic_port(k,j,r,b,x,u,h):
    """Quadratic port-Hamiltonian implicit midpoint, exact discrete power balance."""
    s.need(type(k) is tuple and 1<=len(k)<=s.DIM,'state dimension');n=len(k);k=_coeff(k,n);r=_coeff(r,n);j=s.matrix(j,n,n);s.need(a._ldl(k,True) is not None and a._ldl(r,False) is not None and j==f.neg(tr(j)),'invalid energy/interconnection/damping')
    s.need(type(b) is tuple and len(b)==n and type(b[0]) is tuple and 1<=len(b[0])<=s.DIM,'port shape');b=s.matrix(b,n,len(b[0]));u=s.vector(u,len(b[0]));x=s.vector(x,n,a._q);h=clock(h)
    A=mm(sub(j,r),k);L=sub(s.eye(n),f.scale(A,h/2));R=add(s.eye(n),f.scale(A,h/2));t=s._solve(L,R);rhs=s.va(s.mv(R,x),vs(s.mv(b,u),h));xn=tuple(row[0] for row in s._solve(L,s.outercol(rhs)))
    mid=vs(s.va(x,xn),Q(1,2));g=s.mv(k,mid);y=s.mv(tr(b),g);work=s.bounded(h*dot(u,y));loss=s.bounded(h*dot(g,s.mv(r,g)));before=energy(k,x);after=energy(k,xn)
    s.need(s.va(x,vs(s.va(s.mv(A,mid),s.mv(b,u)),h))==xn and after-before==work-loss and loss>=0,'discrete power balance')
    return dict(energy_matrix=k,interconnection=j,damping=r,ports=b,initial=x,input=u,step=h,final=xn,transition=t,midpoint_output=y,energy_before=before,energy_after=after,work=work,dissipation=loss,continuous_flow_exact=False,execution_authorized=False)


def invariant_linear(m,l,p=None):
    """Verify homogeneous linear first integrals and optionally quadratic invariant."""
    n=a._model(m);l=s.vector(l,n,a._q);s.need(any(l),'nonzero invariant');row=(l,);zero=(Q(0),)*n;expected=zero if m.domain=='continuous' else l
    s.need(mm(row,m.a)[0]==expected and not any(mm(row,m.b)[0]),'linear invariant failed')
    if p is not None:
        p=a._symmetric(p,n);s.need(any(z for row in p for z in row) and not any(z for row in a._difference(m.a,p,m.domain) for z in row) and not any(z for row in mm(p,m.b) for z in row),'quadratic invariant failed')
    return dict(model_sha256=m.digest,linear=l,quadratic=p,execution_authorized=False)


def integrate(m,x0,h,steps,method='DOP853',event=None):
    """Bounded autonomous polynomial or constant-input-free LTI numerical trajectory.

    Refined same-method and independent other-method check; not a proof of error.
    Event is optional (affine functional, threshold, direction); no completeness claim.
    """
    import numpy as np
    from scipy.integrate import solve_ivp
    s.need(type(m) in (v.Polynomial,s.Model) and m.domain=='continuous','continuous model required');n=len(m.terms) if type(m) is v.Polynomial else len(m.a)
    x0=s.vector(x0,n,s.rat);h=clock(h);steps=a._horizon(steps);s.need(h*steps<=16 and method in ('DOP853','Radau'),'solver budget')
    times=np.linspace(0,float(h*steps),steps+1);initial=np.array(x0,float)
    if type(m) is s.Model:
        A=np.array(m.a,float);rhs=lambda x:A@x
    else:
        terms=tuple(tuple((ex,float(c)) for ex,c in row) for row in m.terms)
        rhs=lambda x:np.array([sum(c*np.prod([z**e for z,e in zip(x,ex)]) for ex,c in row) for row in terms])
    ev=None
    if event is not None:
        s.need(type(event) is tuple and len(event)==3,'event shape');l,value,direction=event;l=s.vector(l,n);value=s.rat(value);s.need(any(l) and type(direction) is int and direction in (-1,0,1),'event functional');lf=np.array(l,float)
        def ev(t,x):return float(lf@x-float(value))
        ev.direction=direction;ev.terminal=False
    def run(solver,rtol,atol,max_step):
        calls=0
        def fun(t,x):
            nonlocal calls
            calls+=1;s.need(calls<=50000 and np.isfinite(x).all() and np.max(np.abs(x))<=1e8,'ODE resource/state budget');y=rhs(x);s.need(np.isfinite(y).all() and np.max(np.abs(y))<=1e10,'ODE derivative budget');return y
        result=solve_ivp(fun,(0,times[-1]),initial,method=solver,t_eval=times,events=ev,rtol=rtol,atol=atol,max_step=max_step)
        s.need(result.success and result.y.shape==(n,steps+1) and np.isfinite(result.y).all(),'ODE failed');events=tuple(float(t) for t in result.t_events[0]) if ev else ();s.need(len(events)<=256,'event budget');return result.y,events,calls
    y,e,c=run(method,1e-9,1e-11,float(h));yr,er,cr=run(method,1e-11,1e-13,float(h)/2);other='Radau' if method=='DOP853' else 'DOP853';yo,eo,co=run(other,1e-10,1e-12,float(h)/2)
    err=float(max(np.max(np.abs(y-yr)),np.max(np.abs(yo-yr)))/max(1.,np.max(np.abs(yr))));s.need(err<=2e-7,'ODE cross-check')
    s.need(len(e)==len(er)==len(eo) and all(abs(t-u)<=2e-7 and abs(t-w)<=2e-7 for t,u,w in zip(er,e,eo)),'event cross-check')
    return dict(model_sha256=m.digest,initial=x0,method=method,times=times,states=yr.T,event_times=er,calls=(c,cr,co),scaled_crosscheck=err,certified=False,event_completeness_certified=False,execution_authorized=False)


def polynomial_invariant(m,terms):
    """Exact first-integral identity grad I dot f=0 for a continuous polynomial."""
    s.need(type(m) is v.Polynomial and m.domain=='continuous','continuous polynomial required');n=len(m.terms)
    # Reuse the potential validator for degree <=4, bounded canonical terms.
    integral=Mechanics(s.eye(n),terms).potential;s.need(any(c and any(ex) for ex,c in integral),'nonconstant integral required')
    accum={}
    for j,row in enumerate(m.terms):
        for ex,c in v._derivative(integral,j):
            for exp,d in row:
                key=tuple(i+k for i,k in zip(ex,exp));accum[key]=s.bounded(accum.get(key,Q(0))+s.bounded(c*d))
    s.need(not any(accum.values()),'first-integral polynomial identity failed')
    return dict(model_sha256=m.digest,integral=integral,coefficient_count=len(accum),execution_authorized=False)


def verlet_trajectory(m,q,p,h,steps):
    """Numerical fixed-step symplectic splitting with energy/refinement diagnostics."""
    import numpy as np
    q=_point(m,q);p=_point(m,p);q=tuple(s.rat(x) for x in q);p=tuple(s.rat(x) for x in p);h=clock(h);s.need(type(steps) is int and 1<=steps<=4096 and h*steps<=128,'trajectory budget')
    # Validate exact one-step map including tangent witness before floating execution.
    witness=verlet(m,q,p,h);n=len(q);mass=np.array(m.mass,float)
    s.need(np.linalg.cond(mass)<=1e8,'mass conditioning budget');inv=np.linalg.inv(mass)
    terms=tuple((ex,float(c)) for ex,c in m.potential);der=tuple(tuple((ex,float(c)) for ex,c in v._derivative(m.potential,j)) for j in range(n))
    def val(row,x):return sum(c*np.prod([z**e for z,e in zip(x,ex)]) for ex,c in row)
    def grad(x):return np.array([val(row,x) for row in der])
    def run(dt,count):
        x=np.array(q,float);y=np.array(p,float);states=[np.concatenate((x,y))];ener=[float(y@inv@y/2+val(terms,x))]
        for _ in range(count):
            half=y-dt/2*grad(x);x=x+dt*(inv@half);y=half-dt/2*grad(x);z=np.concatenate((x,y));e=float(y@inv@y/2+val(terms,x))
            s.need(np.isfinite(z).all() and np.max(np.abs(z))<=1e8 and np.isfinite(e),'mechanical trajectory budget');states.append(z);ener.append(e)
        return np.array(states),np.array(ener)
    states,ener=run(float(h),steps);fine,_=run(float(h)/2,steps*2);first=np.array(witness['final'][0]+witness['final'][1],float)
    s.need(np.allclose(states[1],first,rtol=1e-12,atol=1e-12),'exact step disagreement')
    return dict(model_sha256=m.digest,step=str(h),states=states,energy=ener,max_energy_deviation=float(np.max(np.abs(ener-ener[0]))),max_refinement_difference=float(np.max(np.abs(states-fine[::2]))),exact_step_sha256=sha256(s.canonical(witness)).hexdigest(),certified=False,execution_authorized=False)
