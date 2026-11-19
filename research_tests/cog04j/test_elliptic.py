from dataclasses import replace, fields
from fractions import Fraction as Q
import numpy as np
import pytest
from cognitum.research import kan_elliptic_certificate as v, kan_elliptic_learning as s
from tools.cog04j.benchmark import cases, analytic_series, F

ZERO=v.Problem(1,1,0,())
EXACT=v.Problem(1,1,0,((0,1,18),(0,2,-18),(1,0,18),(2,0,-18)))
M=v.Model((),(),tuple(int(i in (1,2) and j in (1,2)) for i in range(4) for j in range(4)))
Z=v.Model((),(),(0,)*16)


def test_exact_nontrivial_solution():
    c=v.assess(EXACT,M);assert c.residual_upper==c.squared_l2==c.solution_error_upper==0 and c.hard_conditions and c.c2_interfaces


def test_exact_squared_l2_and_barrier():
    c=v.assess(v.Problem(2,1,0,((0,0,1),)),Z);assert c.squared_l2==c.residual_upper==1 and c.solution_error_upper==Q(1,16)


def test_zero_residual_wrong_boundary():
    c=v.assess(ZERO,v.Model((),(),(1,)*16));assert c.residual_upper==0 and not c.hard_conditions and c.solution_error_upper is None
    with pytest.raises(ValueError):v.require_accuracy(ZERO,v.Model((),(),(1,)*16),c,.1)

@pytest.mark.parametrize('axis,deriv',[(0,0),(0,1),(0,2),(1,0),(1,1),(1,2)])
def test_independent_cog04a_basis(axis,deriv):
    from cognitum.research.kan_trainable import Layer
    cuts=(.25,.5,.875) if axis==0 else (.125,.75)
    n=len(cuts)+4;grid=s._grid(cuts);layer=Layer('spline_clamped',3,[grid],np.zeros((1,1,n)),[[1.]],[0.])
    x=np.linspace(.005,.995,101);assert np.max(abs(layer.basis(x[:,None],deriv)[deriv][:,0,:]-s._basis(cuts,x,deriv)))<1e-10

@pytest.mark.parametrize('name,p,t',cases())
def test_analytic(name,p,t):
    f=s.fit(p,t);c=v.require_accuracy(p,f.model,f.certificate,t)
    pts=np.random.default_rng(44).uniform(0,1,(2000,2));x,y=pts.T
    expected,tail=(x*(1-x)*y*(1-y),0.) if name=='poisson' else (x**3*(1-x)*y*(1-y),0.) if name=='asymmetric' else analytic_series(p,pts)
    assert max(abs(s.evaluate(f.model,pts)-expected))<=float(c.solution_error_upper)+tail+1e-12
    assert all(a.solution_error_upper>b.solution_error_upper for a,b in zip(f.history,f.history[1:]))
    assert f.converged and c.c2_interfaces and c.hard_conditions


def test_boundary_all_faces_and_cell_cover():
    f=s.fit(v.Problem(1,1,4,F),.00031);m,c=f.model,f.certificate
    x=np.linspace(0,1,33);pts=np.vstack((np.c_[x,0*x],np.c_[x,0*x+1],np.c_[0*x,x],np.c_[0*x+1,x]));assert not np.any(s.evaluate(m,pts))
    assert sum((b-a)*(d-c) for a,b,c,d in (cell.box for cell in f.certificate.cells))==1
    assert len(f.certificate.cells)==(len(m.xcuts)+1)*(len(m.ycuts)+1)
    for cell in f.certificate.cells:
        a,b,c,d=map(float,cell.box);pts=np.array([(x,y) for x in np.linspace(a,b,5) for y in np.linspace(c,d,5)])
        x,y=pts.T;r=-s.evaluate(m,pts,(2,0))-s.evaluate(m,pts,(0,2))+4*s.evaluate(m,pts)-x*(1-x)*y*(1-y)
        assert max(abs(r))<=float(cell.residual_upper)+1e-12


def test_numerical_quadrature_matches_exact_l2():
    p=v.Problem(1,1,4,F);m=s.fit(p,.002).model;c=v.assess(p,m);x,wx=s._nodes(m.xcuts);y,wy=s._nodes(m.ycuts);pts=np.array(np.meshgrid(x,y,indexing='ij')).reshape(2,-1).T
    a,b=pts.T;r=-s.evaluate(m,pts,(2,0))-s.evaluate(m,pts,(0,2))+4*s.evaluate(m,pts)-a*(1-a)*b*(1-b)
    assert abs(np.dot(r*r,(wx[:,None]*wy[None,:]).ravel())-float(c.squared_l2))<1e-13

@pytest.mark.parametrize('field,value',[('problem_sha256','bad'),('model_sha256','bad'),('cells',()),('hard_conditions',False),('c2_interfaces',False),('residual_upper',Q(99)),('squared_l2',Q(99)),('solution_error_upper',Q(99))])
def test_certificate_tamper(field,value):
    c=v.assess(EXACT,M)
    with pytest.raises(ValueError):v.replay(EXACT,M,replace(c,**{field:value}))

@pytest.mark.parametrize('kwargs',[{'ax':0},{'ay':-1},{'reaction':-1},{'ax':True},{'reaction':float('nan')},{'forcing':((0,0,0),)},{'forcing':((0,0,1),(0,0,2))},{'forcing':((5,0,1),)},{'forcing':((True,0,1),)},{'forcing':[]}])
def test_problem_rejection(kwargs):
    with pytest.raises(ValueError):replace(ZERO,**kwargs)

@pytest.mark.parametrize('kwargs',[{'xcuts':(.1,)},{'xcuts':(.5,.5)},{'xcuts':(0.,)},{'ycuts':(1.,)},{'xcuts':(.25,.5,.75,.875),'ycuts':(.25,.5,.75)},{'coefficients':(0,)*15},{'coefficients':(float('inf'),)*16},{'coefficients':(True,)*16}])
def test_model_rejection(kwargs):
    with pytest.raises(ValueError):replace(Z,**kwargs)

@pytest.mark.parametrize('bad',[b'{}',b' '+M.checkpoint(),M.checkpoint()+b'\n',b' '*32769,b'{"profile":"cog04j-tensor-cubic-v1","x":[],"y":[],"c":[NaN]}'],ids=['empty-object', 'leading-whitespace', 'trailing-newline', 'oversized-checkpoint', 'nonfinite-coefficient'])
def test_checkpoint_rejection(bad):
    with pytest.raises(ValueError):v.restore(bad)


def test_checkpoint_exact_replay():
    f=s.fit(v.Problem(1,1,4,F),.002);m=v.restore(f.model.checkpoint());assert m==f.model;v.replay(v.Problem(1,1,4,F),m,f.certificate)
    c=list(m.coefficients);c[0]=1.;tampered=replace(m,coefficients=tuple(c));assert not v.assess(v.Problem(1,1,4,F),tampered).hard_conditions
    with pytest.raises(ValueError):v.replay(v.Problem(1,1,4,F),tampered,f.certificate)


def test_no_false_convergence():
    f=s.fit(v.Problem(1,1,0,((0,0,1),)),.001);assert not f.converged and f.certificate.residual_upper>=1
    with pytest.raises(ValueError):v.require_accuracy(v.Problem(1,1,0,((0,0,1),)),f.model,f.certificate,.001)

@pytest.mark.parametrize('kwargs',[{'tolerance':0},{'tolerance':float('nan')},{'max_refinements':7},{'max_refinements':True}])
def test_fit_budget(kwargs):
    with pytest.raises(ValueError):s.fit(ZERO,**kwargs)

@pytest.mark.parametrize('points',[[],[[1.1,.4]],[[float('nan'),.2]],[[.2,.3,.4]]])
def test_evaluation_rejection(points):
    with pytest.raises(ValueError):s.evaluate(M,points)
