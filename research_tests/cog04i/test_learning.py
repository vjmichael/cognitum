from dataclasses import replace
from fractions import Fraction as Q
import numpy as np
import pytest
from scipy.integrate import quad
from cognitum.research import kan_differential_learning as s
from cognitum.research.kan_trainable import Layer, Network

IVP=s.Problem('ivp',4,(0,),1)
BVP=s.Problem('bvp',4,(0,),0,1)


def cubic(coeff,cut=(),bias=0,mask=1):
    return Network((Layer('spline_clamped',3,[[0.]*4+list(cut)+[1.]*4],[[coeff]],[[mask]],[bias]),))


@pytest.mark.parametrize('problem,exact,tolerance',[
    (IVP,lambda x:np.exp(-4*x),.031),
    (BVP,lambda x:np.sinh(2*x)/np.sinh(2),.007),
    (s.Problem('ivp',1,(1,),0),lambda x:1-np.exp(-x),.0004),
    (s.Problem('bvp',0,(2,),0,0),lambda x:x*(1-x),1e-12),
    (s.Problem('ivp',0,(0,2),0),lambda x:x*x,1e-12),
    (s.Problem('bvp',0,(0,),2,-1),lambda x:2-3*x,1e-12),
])
def test_analytic_holdout(problem,exact,tolerance):
    result=s.fit(problem,tolerance)
    cert=s.require_accuracy(problem,result.model,result.certificate,tolerance)
    # Disjoint midpoint grid from the Gauss-Legendre training samples.
    x=(np.arange(1001)+.37)/1001
    err=max(abs(result.model.evaluate(x[:,None])[0][:,0]-exact(x)))
    assert result.converged and err<=float(cert.solution_error_upper)+1e-13
    assert err<=tolerance and not any(cert.condition_errors)


@pytest.mark.parametrize('problem', [IVP,BVP])
def test_adaptive_strict_improvement(problem):
    r=s.fit(problem,1e-12)
    assert len(r.history)==5 and not r.converged
    assert all(b.solution_error_upper<a.solution_error_upper for a,b in zip(r.history,r.history[1:]))
    assert len(r.model.layers[0].grid[0])==12
    assert r.certificate==r.history[-1]
    assert r.certificate.solution_error_upper<r.history[0].solution_error_upper/10
    with pytest.raises(ValueError,match='budget'):s.require_accuracy(problem,r.model,r.certificate,1e-12)


@pytest.mark.parametrize('problem',[IVP,BVP])
def test_deterministic_solution_and_history(problem):
    a,b=s.fit(problem,1e-12),s.fit(problem,1e-12)
    assert a.model.research_snapshot()==b.model.research_snapshot() and a.history==b.history


@pytest.mark.parametrize('problem',[IVP,BVP])
def test_full_interval_residual_oracles(problem):
    r=s.fit(problem,1e-12);c=r.certificate
    def residual(x):
        v,d,h=r.model.evaluate([[x]],2)
        return float((d[0,0,0] if problem.kind=='ivp' else -h[0,0,0,0])+problem.reaction*v[0,0]-np.polynomial.polynomial.polyval(x,problem.forcing))
    for span in c.spans:
        a,b=map(float,(span.lower,span.upper));x=np.linspace(a,b,83)[1:-1]
        assert max(abs(residual(v)) for v in x)<=float(span.residual_upper)+1e-11
        integral=quad(lambda y:residual(y)**2,a,b,epsabs=1e-11)[0]
        assert integral==pytest.approx(float(span.residual_squared_l2),abs=1e-11)
    assert c.squared_l2==sum(z.residual_squared_l2 for z in c.spans)
    assert c.residual_upper==max(z.residual_upper for z in c.spans)
    assert c.spans[0].lower==0 and c.spans[-1].upper==1
    assert all(a.upper==b.lower for a,b in zip(c.spans,c.spans[1:]))


def test_exact_zero_residual_and_trace():
    c=s.assess(s.Problem('bvp',0,(0,),0,3),cubic([0,1,2,3]))
    assert c.residual_upper==c.squared_l2==c.solution_error_upper==0


def test_zero_equation_wrong_boundary():
    p=s.Problem('bvp',0,(0,),0,3);m=cubic([1,2,3,4]);c=s.assess(p,m)
    assert c.residual_upper==0 and c.condition_errors==(1,1) and c.solution_error_upper is None
    with pytest.raises(ValueError):s.require_accuracy(p,m,c,1)


def test_zero_equation_wrong_initial():
    p=s.Problem('ivp',0,(3,),0);m=cubic([1,2,3,4]);c=s.assess(p,m)
    assert c.residual_upper==0 and c.condition_errors==(1,) and c.solution_error_upper is None


def test_exact_nonzero_residual():
    # u=3x; u'+2u-f=3+6x, norm squared=39, max=9
    p=s.Problem('ivp',2,(0,),0);c=s.assess(p,cubic([0,1,2,3]))
    assert c.residual_upper==9 and c.squared_l2==39 and c.solution_error_upper==9


def test_exact_bvp_barrier():
    # u=0, -u''=2, actual error x(1-x) has supremum 1/4.
    p=s.Problem('bvp',0,(2,),0,0);c=s.assess(p,cubic([0,0,0,0]))
    assert c.residual_upper==2 and c.squared_l2==4 and c.solution_error_upper==Q(1,4)


def test_high_degree_forcing():
    p=s.Problem('ivp',0,(0,)*8+(1,),0);r=s.fit(p,1e-12)
    x=np.linspace(0,1,1001);err=max(abs(r.model.evaluate(x[:,None])[0][:,0]-x**9/9))
    assert err<=float(r.certificate.solution_error_upper)+1e-13


@pytest.mark.parametrize('field,value', [('residual_upper',Q(0)),('squared_l2',Q(0)),('solution_error_upper',Q(0)),('problem_sha256','f'*64),('model_sha256','f'*64),('condition_errors',(1,)),('spans',())])
def test_forged_receipt(field,value):
    r=s.fit(IVP,.031)
    with pytest.raises(ValueError,match='replay'):s.replay(IVP,r.model,replace(r.certificate,**{field:value}))


def test_swapped_models_and_problems():
    a,b=s.fit(IVP,.031),s.fit(BVP,.007)
    with pytest.raises(ValueError):s.replay(IVP,b.model,a.certificate)
    with pytest.raises(ValueError):s.replay(BVP,a.model,a.certificate)


@pytest.mark.parametrize('changes',[dict(kind='pde'),dict(reaction=-1),dict(reaction=float('nan')),dict(reaction=float('inf')),dict(reaction=True),dict(forcing=()),dict(forcing=[1]),dict(forcing=(1,)*10),dict(forcing=(float('nan'),)),dict(left=True),dict(left=101),dict(right=0),dict(kind='bvp')])
def test_invalid_problem(changes):
    with pytest.raises(ValueError):replace(IVP,**changes)


@pytest.mark.parametrize('tolerance,refinements',[(0,4),(-1,4),(float('nan'),4),(True,4),(.1,-1),(.1,5),(.1,True),(.1,1.5)])
def test_invalid_budgets(tolerance,refinements):
    with pytest.raises(ValueError):s.fit(IVP,tolerance,refinements)


@pytest.mark.parametrize('m',[cubic([0,0,0,0],bias=1),cubic([0,0,0,0],mask=0),Network((Layer('chebyshev',1,[[0,1]],[[[0,1]]],[[1]],[0]),)),Network((Layer('spline_clamped',3,[[-1]*4+[1]*4],[[[0,0,0,0]]],[[1]],[0]),))])
def test_unsupported_networks(m):
    with pytest.raises(ValueError):s.assess(IVP,m)


def test_no_refinement_budget():
    r=s.fit(IVP,.01,0)
    assert len(r.history)==1 and not r.converged


def test_no_analytic_label_dependencies(monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('checker called numerical basis')
    r=s.fit(IVP,.031);monkeypatch.setattr(Layer,'basis',forbidden)
    assert s.replay(IVP,r.model,r.certificate)==r.certificate
