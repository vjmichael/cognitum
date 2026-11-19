from dataclasses import replace
from fractions import Fraction as Q
from itertools import product
import json
import numpy as np
import pytest
from cognitum.research import kan_spacetime_certificate as v,kan_spacetime_learning as s
from tools.cog04l.benchmark import cases,reference,G

@pytest.fixture(scope='module',params=cases(),ids=lambda p:p[0])
def fitted(request):
    name,p,tol=request.param;return name,p,tol,s.fit(p,tol)

def test_accuracy(fitted):
    _,p,tol,f=fitted;assert f.converged and v.require_accuracy(p,f.model,f.certificate,tol)==f.certificate

def test_conditions(fitted):
    _,p,_,f=fitted;c=f.certificate;assert c.initial_exact and c.boundary_exact and c.interfaces_exact

def test_exact_replay(fitted):
    _,p,_,f=fitted;assert v.replay(p,v.restore(f.model.checkpoint()),f.certificate)==f.certificate

def test_strict_improvement(fitted):
    *_,f=fitted;assert all(a.solution_error_upper>b.solution_error_upper for a,b in zip(f.history,f.history[1:]))

def test_analytic_and_prefix(fitted):
    name,p,_,f=fitted;x=np.linspace(0,1,13);y=np.linspace(0,1,15);t=np.linspace(0,1,17)
    pts=np.array(np.meshgrid(x,y,t,indexing='ij')).reshape(3,-1).T;ref,tail=reference(name,p,x,y,t);err=abs(s.evaluate(p,f.model,pts).reshape(ref.shape)-ref)
    assert err.max()<=float(f.certificate.solution_error_upper)+tail+1e-12
    for slab in f.certificate.slabs:
        mask=(t>=float(slab.interval[0]))&(t<=float(slab.interval[1]));assert err[:,:,mask].max()<=float(slab.solution_error_upper)+tail+1e-12

def test_residual_bound(fitted):
    _,p,_,f=fitted;pts=np.array(list(product(np.linspace(.013,.987,7),repeat=3)));x,y,t=pts.T
    rhs=sum((c*x**i*y**j*t**k for i,j,k,c in p.forcing),np.zeros(len(x)))
    r=s.evaluate(p,f.model,pts,(0,0,1))-p.ax*s.evaluate(p,f.model,pts,(2,0,0))-p.ay*s.evaluate(p,f.model,pts,(0,2,0))+p.reaction*s.evaluate(p,f.model,pts)-rhs
    for cell in f.certificate.cells:
        mask=np.logical_and.reduce([((pts[:,a]>=float(lo))&(pts[:,a]<=float(hi))) for a,(lo,hi) in enumerate(cell.box)])
        if mask.any():assert abs(r[mask]).max()<=float(cell.residual_upper)+1e-12

def test_boundary_samples(fitted):
    _,p,_,f=fitted;uv=np.linspace(0,1,11)
    for axis,end in product(range(2),(0,1)):
        a=np.array(list(product(uv,repeat=3)));a[:,axis]=end;assert abs(s.evaluate(p,f.model,a)).max()<1e-12
    a=np.array(list(product(uv,uv,(0,))));x,y,_=a.T;g=sum((c*x**i*y**j for i,j,c in p.initial),np.zeros(len(a)));assert abs(s.evaluate(p,f.model,a)-g).max()<1e-12

@pytest.mark.parametrize('kwargs',[dict(ax=0),dict(ay=-1),dict(reaction=-1),dict(ax=float('nan')),dict(forcing=((1,1,1,0),)),dict(forcing=((5,0,0,1),)),dict(forcing=((1,0,0,1),(1,0,0,2))),dict(forcing=((1,0,0,True),)),dict(initial=((0,0,1),)),dict(initial=((1,1,1),)),dict(initial=((1,1,1),(0,0,1)))])
def test_bad_problem(kwargs):
    args=dict(ax=1,ay=1,reaction=0,forcing=(),initial=());args.update(kwargs)
    with pytest.raises(ValueError):v.Problem(**args)

@pytest.mark.parametrize('cuts,coef',[(((),()),(0,)*64),(((.1,),(),()),(0,)*80),(((.5,.5),(),()),(0,)*96),(((0.,),(),()),(0,)*80),(((1.,),(),()),(0,)*80),(((.125,.25,.375,.5,.625,.75),(),()),(0,)*160),(((),(),()),(0,)*63),(((),(),()),(float('inf'),)*64),(((),(),()),(True,)*64)])
def test_bad_model(cuts,coef):
    with pytest.raises(ValueError):v.Model(cuts,coef)

@pytest.mark.parametrize('axis,end',list(product(range(2),(0,3))))
def test_tampered_boundary(axis,end):
    p=v.Problem(1,1,0,(),());c=np.zeros((4,4,4));idx=[1,1,1];idx[axis]=end;c[tuple(idx)]=1;m=v.Model(((),(),()),tuple(map(float,c.ravel())));r=v.assess(p,m)
    assert not r.boundary_exact and r.solution_error_upper is None

def test_wrong_initial():
    p=v.Problem(1,1,0,(),());c=np.zeros((4,4,4));c[1,1,0]=1;m=v.Model(((),(),()),tuple(map(float,c.ravel())));r=v.assess(p,m);assert not r.initial_exact and r.solution_error_upper is None

def test_zero_resid_wrong_boundary():
    p=v.Problem(1,1,0,(),());m=v.Model(((),(),()),(1,)*64);c=v.assess(p,m);assert c.residual_upper==0 and c.solution_error_upper is None

def test_forged_certificate():
    _,p,_,=cases()[1];f=s.fit(p,.1)
    with pytest.raises(ValueError):v.replay(p,f.model,replace(f.certificate,solution_error_upper=Q(0)))

def test_wrong_problem():
    _,p,_=cases()[1];f=s.fit(p,.1)
    with pytest.raises(ValueError):v.replay(replace(p,reaction=1),f.model,f.certificate)

def test_wrong_model():
    _,p,_=cases()[1];f=s.fit(p,.1);coef=list(f.model.coefficients);coef[0]=1
    with pytest.raises(ValueError):v.replay(p,replace(f.model,coefficients=tuple(coef)),f.certificate)

def test_budget_abstain():
    _,p,_=cases()[1];f=s.fit(p,1e-9,0);assert not f.converged
    with pytest.raises(ValueError):v.require_accuracy(p,f.model,f.certificate,1e-9)

@pytest.mark.parametrize('raw',[b'{}',b'[]',b' '*65537,b'{"profile":"wrong","cuts":[],"c":[]}',b'{"profile":"cog04l-parabolic-tensor-cubic-v1","cuts":[],"c":[]}'],ids=['empty-object', 'empty-array', 'oversized-checkpoint', 'wrong-profile', 'invalid-shape'])
def test_bad_checkpoint(raw):
    with pytest.raises(ValueError):v.restore(raw)

def test_noncanonical_checkpoint():
    r=v.Model(((),(),()),(0,)*64).checkpoint()
    with pytest.raises(ValueError):v.restore(r+b' ')

@pytest.mark.parametrize('pts',[[[0,0]],[[0,0,2]],[[0,0,float('nan')]],[],[['0','0','0']]])
def test_bad_points(pts):
    p=v.Problem(1,1,0,(),());m=v.Model(((),(),()),(0,)*64)
    with pytest.raises(ValueError):s.evaluate(p,m,pts)

@pytest.mark.parametrize('der',[(1,1,1),(3,0,0),(True,0,0),(0,0),[0,0,0]])
def test_bad_derivative(der):
    p=v.Problem(1,1,0,(),());m=v.Model(((),(),()),(0,)*64)
    with pytest.raises(ValueError):s.evaluate(p,m,[[0,0,0]],der)

@pytest.mark.parametrize('kwargs',[dict(tolerance=0),dict(tolerance=-1),dict(max_refinements=6),dict(max_refinements=True)])
def test_bad_fit(kwargs):
    with pytest.raises(ValueError):s.fit(v.Problem(1,1,0,(),()),**kwargs)

def test_bernstein_exact_constant_and_zero():
    assert v._bernstein_bound({})==0 and v._bernstein_bound({(0,0,0):Q(-3)})==3
    assert v._bernstein_bound({(1,1,1):Q(2)})==2
