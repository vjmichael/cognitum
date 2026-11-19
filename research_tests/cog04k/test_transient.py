from dataclasses import replace
from fractions import Fraction as Q
import numpy as np
import pytest
from cognitum.research import kan_transient_certificate as v,kan_transient_learning as s,kan_elliptic_certificate as e,kan_elliptic_learning as l
from tools.cog04k.benchmark import cases,analytic

ZERO=v.Problem(1,0,(),(0,))
Z=v.Model(e.Model((),(),(0,)*16))
M=v.Model(e.Model((),(),tuple(j if i in (1,2) else 0 for i in range(4) for j in range(4))))
EXACT=v.Problem(1,0,((0,1,18),(1,0,9),(2,0,-9)),(0,))

@pytest.fixture(scope='module',params=cases(),ids=lambda x:x[0])
def learned(request):
    name,p,tol=request.param;return name,p,tol,s.fit(p,tol)


def test_exact_nontrivial():
    c=v.assess(EXACT,M);assert c.initial_exact and c.boundary_exact and c.interfaces_exact and c.residual_upper==c.squared_l2==c.solution_error_upper==0
    v.require_accuracy(EXACT,M,c,1e-12)


def test_zero_residual_wrong_initial():
    p=v.Problem(1,0,((0,0,6),),(0,));m=v.Model(e.Model((),(),tuple(int(i in (1,2)) for i in range(4) for _ in range(4))))
    c=v.assess(p,m);assert c.residual_upper==0 and not c.initial_exact and c.boundary_exact and c.solution_error_upper is None
    with pytest.raises(ValueError):v.require_accuracy(p,m,c,1.)


def test_zero_residual_wrong_boundary():
    p=v.Problem(1,0,((0,0,3),),(0,));m=v.Model(e.Model((),(),tuple(j for _ in range(4) for j in range(4))))
    c=v.assess(p,m);assert c.residual_upper==0 and c.initial_exact and not c.boundary_exact and c.solution_error_upper is None
    with pytest.raises(ValueError):v.require_accuracy(p,m,c,1.)


def test_zero_residual_lift_nonzero_initial():
    p=v.Problem(1,0,((0,0,2),),(0,1,-1));c=v.assess(p,Z)
    assert c.residual_upper==c.solution_error_upper==0 and c.initial_exact and c.boundary_exact


def test_time_integral_and_spatial_barrier():
    p=v.Problem(1,0,((0,0,1),),(0,));m=v.Model(e.Model((),(.0625,.125,.5),(0,)*28));c=v.assess(p,m)
    assert c.squared_l2==c.residual_upper==1 and c.solution_error_upper==Q(1,8)
    assert [a.accumulated_upper for a in c.slabs]==[Q(1,16),Q(1,8),Q(1,2),Q(1)]
    assert [a.solution_error_upper for a in c.slabs]==[Q(1,16),Q(1,8),Q(1,8),Q(1,8)]


def test_reaction_barrier():
    p=v.Problem(1,32,((0,0,1),),(0,));assert v.assess(p,Z).solution_error_upper==Q(1,32)


def test_analytic_reference_and_conditions(learned):
    name,p,tol,f=learned;c=v.require_accuracy(p,f.model,f.certificate,tol)
    pts=np.random.default_rng(71).uniform(0,1,(2500,2));expected,tail=analytic(name,p,pts);actual=s.evaluate(p,f.model,pts)
    assert max(abs(actual-expected))<=float(c.solution_error_upper)+tail+1e-12
    assert c.initial_exact and c.boundary_exact and c.interfaces_exact and f.converged
    x=np.linspace(0,1,41);assert np.max(abs(s.evaluate(p,f.model,np.c_[x,0*x])-np.polynomial.polynomial.polyval(x,p.initial)))<1e-15
    assert not np.any(s.evaluate(p,f.model,np.c_[0*x,x]));assert not np.any(s.evaluate(p,f.model,np.c_[0*x+1,x]))
    assert sum((b-a)*(d-c) for a,b,c,d in (z.box for z in c.cells))==1
    assert all(a.solution_error_upper>b.solution_error_upper for a,b in zip(f.history,f.history[1:]))
    assert c==v.assess(p,v.restore(f.model.checkpoint()))


def test_cell_residual_and_time_slabs(learned):
    name,p,tol,f=learned;c=f.certificate;m=f.model
    assert len(c.cells)==(len(m.spline.xcuts)+1)*(len(m.spline.ycuts)+1)
    for cell in c.cells:
        a,b,d,z=map(float,cell.box);pts=np.array([(x,t) for x in np.linspace(a,b,7) for t in np.linspace(d,z,7)])
        x,t=pts.T;rhs=sum((q*x**i*t**j for i,j,q in p.forcing),np.zeros(len(x)))
        r=s.evaluate(p,m,pts,(0,1))-p.diffusion*s.evaluate(p,m,pts,(2,0))+p.reaction*s.evaluate(p,m,pts)-rhs
        assert max(abs(r))<=float(cell.residual_upper)+2e-12
    for slab in c.slabs:
        a,b=map(float,slab.interval);pts=np.array([(x,t) for x in np.linspace(0,1,19) for t in np.linspace(a,b,21)])
        expected,tail=analytic(name,p,pts);assert max(abs(s.evaluate(p,m,pts)-expected))<=float(slab.solution_error_upper)+tail+1e-12


def test_exact_l2_matches_quadrature(learned):
    _,p,_,f=learned;m=f.model;x,wx=l._nodes(m.spline.xcuts);t,wt=l._nodes(m.spline.ycuts);pts=np.array(np.meshgrid(x,t,indexing='ij')).reshape(2,-1).T;x,t=pts.T
    rhs=sum((q*x**i*t**j for i,j,q in p.forcing),np.zeros(len(x)))
    r=s.evaluate(p,m,pts,(0,1))-p.diffusion*s.evaluate(p,m,pts,(2,0))+p.reaction*s.evaluate(p,m,pts)-rhs
    assert abs(np.dot(r*r,(wx[:,None]*wt[None,:]).ravel())-float(f.certificate.squared_l2))<1e-12

@pytest.mark.parametrize('field,value',[('problem_sha256','bad'),('model_sha256','bad'),('cells',()),('slabs',()),('initial_exact',False),('boundary_exact',False),('interfaces_exact',False),('residual_upper',Q(99)),('squared_l2',Q(99)),('solution_error_upper',Q(99))])
def test_certificate_tamper(field,value):
    c=v.assess(EXACT,M)
    with pytest.raises(ValueError):v.replay(EXACT,M,replace(c,**{field:value}))

@pytest.mark.parametrize('kwargs',[{'diffusion':0},{'diffusion':-1},{'diffusion':True},{'reaction':-1},{'reaction':float('nan')},{'forcing':((0,0,0),)},{'forcing':((0,0,1),(0,0,2))},{'forcing':((5,0,1),)},{'forcing':[]},{'initial':(1,)},{'initial':(0,1)},{'initial':(0,0)},{'initial':[]},{'initial':(0,1,-1,0,0,0)},{'initial':(0,float('nan'))},{'initial':(False,)}])
def test_invalid_problem(kwargs):
    with pytest.raises(ValueError):replace(ZERO,**kwargs)

@pytest.mark.parametrize('bad',[b'{}',b' '+M.checkpoint(),M.checkpoint()+b'\n',b' '*32769,Z.spline.checkpoint(),b'{"profile":"cog04k-parabolic-tensor-cubic-v1","x":[],"t":[],"c":[NaN]}'],ids=['empty-object', 'leading-whitespace', 'trailing-newline', 'oversized-checkpoint', 'wrong-profile', 'nonfinite-coefficient'])
def test_checkpoint_rejection(bad):
    with pytest.raises(ValueError):v.restore(bad)


def test_problem_binding():
    c=v.assess(EXACT,M)
    with pytest.raises(ValueError):v.replay(replace(EXACT,reaction=1),M,c)
    with pytest.raises(ValueError):v.replay(EXACT,Z,c)


def test_unmet_accuracy_fails_closed():
    p=v.Problem(1,0,((0,0,1),),(0,));f=s.fit(p,1e-12,0);assert not f.converged
    with pytest.raises(ValueError):v.require_accuracy(p,f.model,f.certificate,1e-12)

@pytest.mark.parametrize('kwargs',[{'tolerance':0},{'tolerance':float('nan')},{'max_refinements':7},{'max_refinements':True},{'max_refinements':-1}])
def test_fit_budget(kwargs):
    with pytest.raises(ValueError):s.fit(ZERO,**kwargs)

@pytest.mark.parametrize('points',[[],[[1.1,.4]],[[float('nan'),.2]],[[.2,.3,.4]]])
def test_evaluation_rejection(points):
    with pytest.raises(ValueError):s.evaluate(EXACT,M,points)
