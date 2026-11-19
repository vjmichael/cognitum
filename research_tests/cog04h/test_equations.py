from dataclasses import replace
from fractions import Fraction as Q
import pytest
from cognitum.mel import kan_equations as s, kan_multivariate as m, kan_fields as f


def p(d,coeff):return m.make(d,coeff)
def const(d,v):return m.constant(d,v)
def fn(box,v):return m.Function(box,(v,))
def cond(d,axis,side,order,value,kind='boundary'):
    return s.Condition(axis,side,order,const(d,value),kind)
def ode(order, rhs, degree, conditions, box=((0,1),), time_axis=None):
    return s.Problem(f.derivative(1,(order,)),fn(box,rhs),tuple(conditions),degree,time_axis)


def test_ivp_exact():
    t=m.variable(1,0); p=ode(1,t.scale(2),2,[cond(1,0,'lower',0,3,'initial')],time_axis=0)
    r=s.solve(p); assert r.rank==r.unknowns==3
    assert s.replay(p,r).evaluate((Q(1,2),))==(Q(13,4),)
    assert r.residual.identically_zero and r.residual.squared_l2==0
    assert all(x.identically_zero for x in r.condition_residuals)


def test_second_order_ivp_shifted_time():
    t=m.variable(1,0); p=ode(2,const(1,6),2,[cond(1,0,'lower',0,5,'initial'),cond(1,0,'lower',1,-2,'initial')],box=((2,3),),time_axis=0)
    r=s.solve(p); assert r.candidate.evaluate((3,))==(6,)


def test_dirichlet_bvp():
    p=ode(2,const(1,-2),2,[cond(1,0,'lower',0,0),cond(1,0,'upper',0,0)])
    r=s.solve(p); assert r.candidate.evaluate((Q(1,2),))==(Q(1,4),)


def test_mixed_bvp():
    p=ode(2,const(1,2),2,[cond(1,0,'lower',0,1),cond(1,0,'upper',1,3)])
    assert s.solve(p).candidate.evaluate((1,))==(3,)


def test_rational_coefficients():
    p=ode(1,const(1,Q(2,3)),1,[cond(1,0,'lower',0,Q(1,7))])
    assert s.solve(p).candidate.evaluate((Q(1,2),))==(Q(10,21),)


def test_variable_coefficient_ode():
    t=m.variable(1,0); op=f.derivative(1,(1,)).after(f.multiplier(t.add(const(1,1))))
    p=s.Problem(op,fn(((0,1),),t.scale(2).add(const(1,1))),(cond(1,0,'lower',0,0),),1)
    assert s.solve(p).candidate.outputs==(t,)


def poisson_fixture():
    x,y=(m.variable(2,i) for i in range(2)); one=const(2,1)
    u=x.multiply(one.add(x.scale(-1))).multiply(y.multiply(one.add(y.scale(-1))))
    box=((0,1),(0,1)); rhs=x.multiply(one.add(x.scale(-1))).add(y.multiply(one.add(y.scale(-1)))).scale(-2)
    cs=tuple(cond(2,i,side,0,0) for i in range(2) for side in ('lower','upper'))
    return s.Problem(f.laplace_operator(2),fn(box,rhs),cs,4),u


def test_poisson_boundary_faces():
    p,u=poisson_fixture(); r=s.solve(p)
    assert r.candidate.outputs==(u,) and r.candidate.evaluate((Q(1,2),Q(1,2)))==(Q(1,16),)
    assert len(r.condition_residuals)==4 and all(x.squared_l2==0 for x in r.condition_residuals)


def test_heat_pde_initial_boundary_polynomial():
    # u=x^2+2t, u_t-u_xx=0. Nonconstant Dirichlet traces.
    x,t=(m.variable(2,i) for i in range(2)); xx=x.multiply(x); tt=t.scale(2)
    op=f.derivative(2,(0,1)).add(f.derivative(2,(2,0)).scale(-1))
    cs=(s.Condition(1,'lower',0,xx,'initial'),s.Condition(0,'lower',0,tt),s.Condition(0,'upper',0,tt.add(const(2,1))))
    p=s.Problem(op,fn(((0,1),(0,1)),const(2,0)),cs,2,1)
    assert s.solve(p).candidate.outputs==(xx.add(tt),)


def test_3d_poisson():
    x,y,z=(m.variable(3,i) for i in range(3)); u=x.multiply(x).add(y.multiply(y)).add(z.multiply(z))
    box=((0,1),)*3; cs=[]
    for axis in range(3):
        for side in ('lower','upper'):
            target=u.add((x,y,z)[axis].multiply((x,y,z)[axis]).scale(-1)).add(const(3,int(side=='upper')))
            cs.append(s.Condition(axis,side,0,target))
    p=s.Problem(f.laplace_operator(3),fn(box,const(3,6)),tuple(cs),2)
    assert s.solve(p).candidate.outputs==(u,)


def test_inconsistent_conditions():
    p=ode(1,const(1,0),1,[cond(1,0,'lower',0,0),cond(1,0,'upper',0,1)])
    with pytest.raises(ValueError,match='inconsistent'):s.solve(p)


def test_underdetermined_neumann():
    p=ode(2,const(1,0),2,[cond(1,0,'lower',1,0),cond(1,0,'upper',1,0)])
    with pytest.raises(ValueError,match='underdetermined'):s.solve(p)


def test_insufficient_polynomial_degree():
    p=ode(1,m.variable(1,0),1,[cond(1,0,'lower',0,0)])
    with pytest.raises(ValueError,match='inconsistent'):s.solve(p)


def test_zero_equation_residual_wrong_boundary():
    p=ode(1,const(1,0),1,[cond(1,0,'lower',0,0)])
    with pytest.raises(ValueError,match='condition residual'):s.certify_candidate(p,fn(p.source.box,const(1,1)))


def test_good_boundary_wrong_equation():
    p=ode(1,const(1,1),1,[cond(1,0,'lower',0,0)])
    with pytest.raises(ValueError,match='equation residual'):s.certify_candidate(p,fn(p.source.box,const(1,0)))


def test_hidden_face_error():
    p,u=poisson_fixture(); x,y=(m.variable(2,i) for i in range(2))
    # harmonic perturbation vanishes on corner (0,0), not on all faces.
    with pytest.raises(ValueError,match='condition residual'):s.certify_candidate(p,fn(p.source.box,u.add(x.multiply(y))))


def test_tampered_rank():
    p,u=poisson_fixture(); r=s.solve(p)
    with pytest.raises(ValueError,match='rank/candidate'):s.replay(p,replace(r,rank=0))


def test_tampered_residual():
    p,u=poisson_fixture(); r=s.solve(p)
    with pytest.raises(ValueError,match='residual witness'):s.replay(p,replace(r,residual=replace(r.residual,squared_l2=Q(1))))


def test_wrong_problem_pin():
    p,u=poisson_fixture(); r=s.solve(p)
    with pytest.raises(ValueError,match='problem pin'):s.replay(replace(p,degree=5),r)


def test_wrong_domain():
    p,u=poisson_fixture()
    with pytest.raises(ValueError,match='candidate domain'):s.certify_candidate(p,fn(((0,2),(0,1)),u))


def test_missing_initial_derivative():
    with pytest.raises(ValueError,match='initial derivative'):ode(2,const(1,1),2,[cond(1,0,'lower',0,0,'initial')],time_axis=0)


def test_wrong_initial_face():
    with pytest.raises(ValueError,match='lower face'):cond(1,0,'upper',0,0,'initial')


def test_time_axis_required():
    with pytest.raises(ValueError,match='initial time axis'):ode(1,const(1,0),1,[cond(1,0,'lower',0,0,'initial')])


def test_target_independent_of_fixed_axis():
    with pytest.raises(ValueError,match='fixed axis'):s.Condition(0,'lower',0,m.variable(2,0))


def test_degree_budget():
    with pytest.raises(ValueError,match='trial basis budget'):s.Problem(f.laplace_operator(3),fn(((0,1),)*3,const(3,0)),(cond(3,0,'lower',0,0),),12)


def test_empty_conditions():
    with pytest.raises(ValueError,match='condition count'):ode(1,const(1,0),1,[])


def test_bad_conditions_order():
    with pytest.raises(ValueError,match='derivative order'):cond(1,0,'lower',5,0)


def test_zero_operator():
    with pytest.raises(ValueError,match='nonzero operator'):s.Problem(f.operator(1,()),fn(((0,1),),const(1,0)),(cond(1,0,'lower',0,0),),1)


def test_false_solver_rank_rejected(monkeypatch):
    p=ode(2,const(1,0),2,[cond(1,0,'lower',1,0),cond(1,0,'upper',1,0)])
    monkeypatch.setattr(s,'_eliminate',lambda rows,n:('unique_trial',n,(Q(0),)*n))
    with pytest.raises(ValueError,match='independent rank'):s.solve(p)


def test_corrupted_trace_rejected(monkeypatch):
    p=ode(1,const(1,1),1,[cond(1,0,'lower',0,0)])
    monkeypatch.setattr(s,'_trace',lambda poly,c,box:const(1,0))
    with pytest.raises(ValueError,match='trace identity'):s.solve(p)


def test_public_exact_kan_checkpoint():
    # Requires the recovered full worker/checkpoint dependency closure.
    p=ode(2,const(1,-2),2,[cond(1,0,'lower',0,0),cond(1,0,'upper',0,0)])
    u=s.solve(p).candidate; cp=m.export_additive(u)
    w=s.certify_checkpoint(p,cp); e,r=w.extraction,w.residuals
    assert e.function==u and e.checkpoint_sha256==cp.identity and r.equation.identically_zero and all(c.identically_zero for c in r.conditions)
    assert s.replay_checkpoint(p,cp,w)==u
    with pytest.raises(ValueError,match='solution witness'):s.replay_checkpoint(p,cp,replace(w,residuals=replace(r,problem_sha256='0'*64)))
    wrong=m.export_additive(fn(p.source.box,m.constant(1,0)))
    with pytest.raises(ValueError,match='residual nonzero'):s.certify_checkpoint(p,wrong)


def test_nonzero_continuous_residual():
    # u=t^2, requested u'=1; exact residual 2t-1. Integral is 1/3.
    t=m.variable(1,0); p=ode(1,const(1,1),2,[cond(1,0,'lower',0,0)])
    candidate=fn(p.source.box,t.multiply(t)); r=s.assess_candidate(p,candidate)
    assert r.equation.squared_l2==Q(1,3) and not r.equation.identically_zero
    assert r.equation.absolute_upper==(1,)
    assert s.replay_assessment(p,candidate,r)==r


def test_nonzero_face_norm_true_surface_not_volume():
    # u=y has zero Laplacian, but at x=0 it has nonzero residual y.
    # Face integral over y in [0,3] is 9, independent of x-width 2.
    x,y=(m.variable(2,i) for i in range(2)); box=((0,2),(0,3))
    p=s.Problem(f.laplace_operator(2),fn(box,const(2,0)),(cond(2,0,'lower',0,0),),1)
    r=s.assess_candidate(p,fn(box,y)); c=r.conditions[0]
    assert r.equation.identically_zero and c.squared_l2==9 and c.absolute_upper==3 and not c.identically_zero


def test_one_dimensional_boundary_point_norm():
    p=ode(1,const(1,0),1,[cond(1,0,'upper',0,0)],box=((2,5),))
    r=s.assess_candidate(p,fn(p.source.box,const(1,2)))
    assert r.conditions[0].squared_l2==4 and r.conditions[0].absolute_upper==2


def test_nonzero_report_tampering():
    p=ode(1,const(1,0),1,[cond(1,0,'lower',0,0)]);u=fn(p.source.box,const(1,1)); r=s.assess_candidate(p,u)
    with pytest.raises(ValueError,match='report witness'):s.replay_assessment(p,u,replace(r,candidate_sha256='0'*64))


def test_wave_equation_two_initial_derivatives():
    # u = x^2+t^2+x*t. Both initial displacement and velocity enforced.
    x,t=(m.variable(2,i) for i in range(2)); xx=x.multiply(x); tt=t.multiply(t)
    u=xx.add(tt).add(x.multiply(t)); op=f.derivative(2,(0,2)).add(f.derivative(2,(2,0)).scale(-1))
    cs=(s.Condition(1,'lower',0,xx,'initial'),s.Condition(1,'lower',1,x,'initial'),s.Condition(0,'lower',0,tt),s.Condition(0,'upper',0,tt.add(t).add(const(2,1))))
    p=s.Problem(op,fn(((0,1),(0,1)),const(2,0)),cs,2,1)
    assert s.replay(p,s.solve(p)).outputs==(u,)


def test_fourth_order_clamped_beam():
    # u=x^2(1-x)^2, u''''=24, clamped both ends.
    x=m.variable(1,0); y=const(1,1).add(x.scale(-1)); u=x.multiply(x).multiply(y.multiply(y))
    cs=tuple(cond(1,0,side,order,0) for side in ('lower','upper') for order in (0,1))
    p=ode(4,const(1,24),4,cs)
    assert s.solve(p).candidate.outputs==(u,)


def test_nonpolynomial_solution_abstention():
    # u'-u=0, u(0)=1 gives e^x, not an exact polynomial on [0,1].
    op=f.derivative(1,(1,)).add(f.multiplier(const(1,-1)))
    p=s.Problem(op,fn(((0,1),),const(1,0)),(cond(1,0,'lower',0,1,'initial'),),5,0)
    with pytest.raises(ValueError,match='inconsistent'):s.solve(p)
