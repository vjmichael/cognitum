from fractions import Fraction as Q
import itertools
import numpy as np
import pytest
from scipy.linalg import expm
from cognitum.research import ssm_linear as s, ssm_dynamics as d, ssm_verification as v


def model(A,B=None):
    n=len(A);return s.Model(A,B if B is not None else ((0,),)*n,((1,)+(0,)*(n-1),),((0,),),('x',)*n,('u',),('y',),'continuous')


@pytest.mark.parametrize('method',['DOP853','Radau'])
@pytest.mark.parametrize('A,x',[(((-2,),),(1,)),(((-1,2),(0,-1)),(1,2)),(((-32,0),(0,-1)),(1,1)),(((0,1),(-1,0)),(1,0))])
def test_integrate(method,A,x):
    m=model(A);r=d.integrate(m,x,Q(1,8),16,method);ref=np.array([expm(np.array(A,float)*t)@np.array(x) for t in r['times']]);np.testing.assert_allclose(r['states'],ref,rtol=1e-8,atol=2e-10);assert not r['certified'] and r['scaled_crosscheck']<2e-7


@pytest.mark.parametrize('method',['DOP853','Radau'])
def test_event(method):
    m=model(((-1,),));r=d.integrate(m,(1,),Q(1,8),16,method,((1,),Q(1,2),-1));assert len(r['event_times'])==1 and abs(r['event_times'][0]-np.log(2))<1e-8;assert not r['event_completeness_certified']
    assert d.integrate(m,(1,),Q(1,8),16,method,((1,),Q(1,2),1))['event_times']==()


def test_nonlinear_ode():
    m=v.Polynomial(((((2,),-1),),));r=d.integrate(m,(1,),Q(1,8),16);np.testing.assert_allclose(r['states'][:,0],1/(1+r['times']),atol=1e-9)


@pytest.mark.parametrize('mass',[((2,),),((2,1),(1,2))])
def test_lagrangian(mass):
    n=len(mass);potential=tuple((tuple(2 if i==j else 0 for i in range(n)),Q(1,2)) for j in range(n));m=d.Mechanics(mass,potential);q=(Q(1,2),)*n;vel=(Q(1),)*n;r=d.lagrangian(m,q,vel)
    assert r['momentum']==tuple(sum(row) for row in mass);assert s.mv(m.mass,r['acceleration'])==tuple(-x for x in q);assert r['hamiltonian']==d.hamiltonian(m,q,r['momentum']);assert r['hamiltonian']-r['lagrangian']==n*Q(1,4)


@pytest.mark.parametrize('quartic',[False,True])
def test_verlet_reversible(quartic):
    m=d.Mechanics(((1,),),(((2,),Q(1,2)),)+((((4,),Q(1,4)),) if quartic else ()));q=(Q(1,2),);p=(Q(1,4),);h=Q(1,8);r=d.verlet(m,q,p,h);qn,pn=r['final'];rr=d.verlet(m,qn,pn,-h);assert rr['final']==(q,p)
    ph=p[0]-h/2*(q[0]+(q[0]**3 if quartic else 0));x=q[0]+h*ph;y=ph-h/2*(x+(x**3 if quartic else 0));assert (qn,pn)==((x,),(y,));t=r['tangent'];assert t[0][0]*t[1][1]-t[0][1]*t[1][0]==1;assert not r['continuous_flow_exact']
    assert r['energy_after']!=r['energy_before']


def test_coupled_verlet():
    m=d.Mechanics(((2,1),(1,2)),(((2,0),1),((0,2),1),((1,1),Q(1,2)),((2,2),Q(1,4))));q=(Q(1,2),Q(1,3));p=(Q(1,4),Q(-1,2));r=d.verlet(m,q,p,Q(1,8));assert d.verlet(m,*r['final'],-Q(1,8))['final']==(q,p);assert r['symplectic']


def test_mechanical_trajectory():
    m=d.Mechanics(((1,),),(((2,),Q(1,2)),));r=d.verlet_trajectory(m,(1,),(0,),Q(1,16),1024);t=np.arange(1025)/16;assert np.max(np.abs(r['states'][:,0]-np.cos(t)))<.012;assert r['max_energy_deviation']<.001 and r['max_refinement_difference']<.02;assert not r['certified'];q=d.verlet_trajectory(m,(1,),(0,),Q(1,32),2048);assert q['max_energy_deviation']<r['max_energy_deviation']/3


@pytest.mark.parametrize('rval',[0,Q(1,2),2])
@pytest.mark.parametrize('uval',[0,1])
def test_port_balance(rval,uval):
    K=((2,0),(0,1));J=((0,1),(-1,0));R=((0,0),(0,rval));B=((0,),(1,));x=(Q(1),Q(1,2));h=Q(1,4);r=d.quadratic_port(K,J,R,B,x,(uval,),h);z=r['final'];mid=tuple((i+j)/2 for i,j in zip(x,z));assert z[0]-x[0]==h*mid[1];assert z[1]-x[1]==h*(-2*mid[0]-rval*mid[1]+uval);assert r['work']==h*uval*mid[1] and r['dissipation']==h*rval*mid[1]**2;assert r['energy_after']-r['energy_before']==r['work']-r['dissipation'];assert r['dissipation']>=0
    if not rval and not uval:assert r['energy_before']==r['energy_after'];T=r['transition'];assert d.mm(d.tr(T),d.mm(d.symplectic_form(1),T))==d.symplectic_form(1)
    if rval and not uval:assert r['energy_after']<=r['energy_before']


def test_mass_network():
    A=((-1,1,0),(1,-2,1),(0,1,-1));m=model(A);r=d.invariant_linear(m,(1,1,1));assert r['linear']==(1,1,1);z=d.integrate(m,(3,0,0),Q(1,4),16);np.testing.assert_allclose(z['states'].sum(axis=1),3,atol=1e-10);assert z['states'].min()>=-1e-10;assert (z['states'][-1]**2).sum()<9
    with pytest.raises(ValueError):d.invariant_linear(m,(1,0,0))


def test_quadratic_linear_invariant():
    m=model(((0,1,0),(-1,0,0),(0,0,0)));r=d.invariant_linear(m,(0,0,1),s.eye(3));assert r['quadratic']==s.eye(3)
    with pytest.raises(ValueError):d.invariant_linear(m,(0,0,1),((1,0,0),(0,2,0),(0,0,1)))


def test_polynomial_first_integral():
    m=v.Polynomial(((((0,1),1),),(((1,0),-1),((3,0),-1))));H=(((2,0),Q(1,2)),((4,0),Q(1,4)),((0,2),Q(1,2)));assert d.polynomial_invariant(m,H)['coefficient_count']>0
    with pytest.raises(ValueError):d.polynomial_invariant(m,H[:-1])


def test_refusals():
    m=d.Mechanics(((1,),),(((2,),Q(1,2)),));M=model(((-1,),));calls=[lambda:d.Mechanics(((0,),),()),lambda:d.Mechanics(((1,2),(0,1)),()),lambda:d.Mechanics(((1,),),(((5,),1),)),lambda:d.Mechanics(((1,),),(((2,),1),((2,),1))),lambda:d.verlet(m,(1,),(0,),0),lambda:d.verlet(m,(True,),(0,),Q(1,2)),lambda:d.verlet_trajectory(m,(1,),(0,),Q(1,2),4097),lambda:d.integrate(M,(1,),1,17),lambda:d.integrate(M,(1,),Q(1,2),1,'unknown'),lambda:d.integrate(M,(1,),Q(1,2),1,event=((0,),0,1)),lambda:d.integrate(M,(1,),Q(1,2),True),lambda:d.quadratic_port(((1,),),((1,),),((0,),),((1,),),(1,),(0,),Q(1,2)),lambda:d.quadratic_port(((1,),),((0,),),((-1,),),((1,),),(1,),(0,),Q(1,2)),lambda:d.polynomial_invariant(v.Polynomial(((),)),(((0,),1),))]
    for f in calls:
        with pytest.raises(ValueError):f()


def test_multiport_balance():
    K=((2,1,0),(1,2,0),(0,0,1));J=((0,1,0),(-1,0,1),(0,-1,0));R=((1,0,0),(0,0,0),(0,0,2));B=((1,0),(0,1),(1,1));x=(Q(1),Q(-1),Q(2));u=(Q(1,2),Q(-1,4));h=Q(1,8);z=d.quadratic_port(K,J,R,B,x,u,h)
    mid=tuple((i+j)/2 for i,j in zip(x,z['final']));g=(2*mid[0]+mid[1],mid[0]+2*mid[1],mid[2]);y=(g[0]+g[2],g[1]+g[2]);assert z['midpoint_output']==y;assert z['dissipation']==h*(g[0]**2+2*g[2]**2);assert z['work']==h*(u[0]*y[0]+u[1]*y[1])


def test_discrete_invariant():
    m=s.Model(((0,1,0),(1,0,0),(0,0,1)),((0,),(0,),(0,)),((1,0,0),),((0,),),('x',)*3,('u',),('y',));r=d.invariant_linear(m,(1,1,0),s.eye(3));assert r['linear']==(1,1,0)
    b=s.Model(m.a,((1,),(0,),(0,)),m.c,m.d,m.state_units,m.input_units,m.output_units)
    with pytest.raises(ValueError):d.invariant_linear(b,(1,1,0),s.eye(3))
