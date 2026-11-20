from fractions import Fraction as Q
import itertools,json
import numpy as np
import pytest
from scipy.integrate import solve_ivp
from cognitum.research import ssm_linear as s, ssm_verification as v


def model(A,B,C,D,domain='continuous'):
    return s.Model(A,B,C,D,('x',)*len(A),('u',)*len(B[0]),('y',)*len(C),domain)


@pytest.mark.parametrize('domain,A,P,gamma',[('continuous',((-1,),),((1,),),1),('discrete',((0,),),((1,),),1),('discrete',((Q(1,2),),),((2,),),2)])
def test_tight_gain(domain,A,P,gamma):
    m=model(A,((1,),),((1,),),((0,),),domain)
    raw=v.gain_bound(m,P,gamma);assert v.replay(m,P,gamma,raw,'gain')
    q=v.frequency_lower(m,0 if domain=='continuous' else 1,0,(1,),(0,));assert q['lower_squared']==gamma**2
    assert json.loads(raw)['zero_initial_state']
    with pytest.raises(ValueError):v.gain_bound(m,P,Q(gamma)-Q(1,4))
    with pytest.raises(ValueError):v.replay(m,P,gamma,raw+b' ','gain')


@pytest.mark.parametrize('domain,A,B,C,D,P',[('continuous',((-1,),),((1,),),((1,),),((0,),),((1,),)),('discrete',((0,),),((1,),),((0,),),((1,),),((1,),))])
def test_passivity(domain,A,B,C,D,P):
    m=model(A,B,C,D,domain);raw=v.passivity(m,P);r=json.loads(raw);assert v.replay(m,P,((0,1),(1,0)),raw,'dissipation')
    for x,u in itertools.product((-2,0,3),(-1,0,2)):
        dyn=A[0][0]*x+B[0][0]*u; y=C[0][0]*x+D[0][0]*u
        delta=2*x*P[0][0]*dyn if domain=='continuous' else P[0][0]*(dyn*dyn-x*x)
        assert delta<=2*u*y
    assert r['execution_authorized'] is False
    bad=model(A,B,tuple(tuple(-x for x in row) for row in C),tuple(tuple(-x for x in row) for row in D),domain)
    with pytest.raises(ValueError):v.passivity(bad,P)


@pytest.mark.parametrize('domain,real,imag',[('continuous',0,2),('discrete',Q(3,5),Q(4,5)),('discrete',-1,0)])
def test_mimo_frequency(domain,real,imag):
    m=model(((Q(-1,2),Q(1,4)),(0,Q(-1,4))),((1,0),(0,1)),((1,2),(0,1)),((0,1),(1,0)),domain)
    vr=(1,2);vi=(2,-1);r=v.frequency_lower(m,real,imag,vr,vi)
    z=complex(real,imag);A,B,C,D=map(lambda a:np.array(a,float),(m.a,m.b,m.c,m.d));direction=np.array(vr)+1j*np.array(vi)
    y=(C@np.linalg.solve(z*np.eye(2)-A,B)+D)@direction
    assert abs(float(r['lower_squared'])-np.vdot(y,y).real/np.vdot(direction,direction).real)<1e-12


def test_gain_mimo():
    m=model(((-1,0),(0,-2)),((1,0),(0,1)),((1,0),(0,2)),((0,0),(0,0)))
    raw=v.gain_bound(m,((1,0),(0,2)),1);assert v.replay(m,((1,0),(0,2)),1,raw,'gain')
    assert v.frequency_lower(m,0,0,(0,1),(1,0))['lower_squared']==1


def test_gain_refusals():
    m=model(((-1,),),((1,),),((1,),),((0,),));u=model(((1,),),((1,),),((1,),),((0,),));rect=model(((-1,),),((1,0),),((1,),),((0,0),))
    calls=[lambda:v.gain_bound(u,((1,),),2),lambda:v.gain_bound(m,((0,),),1),lambda:v.gain_bound(m,((1,),),0),lambda:v.gain_bound(m,((1,),),True),lambda:v.passivity(rect,((1,),)),lambda:v.dissipativity(m,((1,),),((1,1),(0,1))),lambda:v.frequency_lower(m,1,0,(1,),(0,)),lambda:v.frequency_lower(m,0,0,(0,),(0,)),lambda:v.replay(m,((1,),),1,b'x','other')]
    for call in calls:
        with pytest.raises(ValueError):call()


def cubic(domain='continuous'):
    return v.Polynomial(((((1,),-1 if domain=='continuous' else Q(1,4)),((3,),Q(-1,4) if domain=='continuous' else Q(1,4))),),domain)


@pytest.mark.parametrize('domain',['continuous','discrete'])
def test_equilibrium_and_jacobian(domain):
    m=cubic(domain);z=v.equilibrium(m,(0,));assert z['equilibrium'];assert z['jacobian']==((-1 if domain=='continuous' else Q(1,4),),)
    r=v.equilibrium(m,(Q(1,2),));assert not r['equilibrium'];assert r['jacobian']==((Q(-19,16) if domain=='continuous' else Q(7,16),),)


@pytest.mark.parametrize('domain,rate',[('continuous',1),('discrete',Q(1,2))])
def test_local_contraction(domain,rate):
    m=cubic(domain);lo=(-Q(1,2),);hi=(Q(1,2),);raw=v.local_contraction(m,lo,hi,(0,),rate);r=json.loads(raw);assert r['execution_authorized'] is False
    assert v.invariant_box(m,lo,hi)
    with pytest.raises(ValueError):v.local_contraction(m,lo,hi,(0,),Q(2) if domain=='continuous' else Q(1,4))


def test_coupled_jacobian():
    m=v.Polynomial(((((1,0),-2),((0,1),Q(1,2)),((3,0),-1)),(((0,1),-2),((1,0),Q(1,2)))))
    r=v.equilibrium(m,(Q(1,2),Q(-1,2)));assert r['jacobian']==((Q(-11,4),Q(1,2)),(Q(1,2),-2))
    assert v.local_contraction(m,(-1,-1),(1,1),(0,0),Q(3,2))


@pytest.mark.parametrize('h',[Q(1,8),Q(1,4),Q(1,2)])
def test_validated_tube(h):
    m=v.Polynomial(((((1,),-1),),));r=v.validated_step(m,(Q(1,2),),(1,),(0,),(2,),h) if h<Q(1,4) else v.validated_step(m,(Q(1,2),),(1,),(-2,),(3,),h)
    # Compare actual analytic endpoint; enclosure is exact despite approximate comparator.
    l,u=r['endpoint'][0];assert float(l)<=.5*np.exp(-float(h))<=np.exp(-float(h))<=float(u)
    with pytest.raises(ValueError):v.validated_step(m,(1,),(1,),(1,),(1,),h)


def test_nonlinear_tube():
    m=cubic();r=v.validated_step(m,(Q(1,2),),(Q(1,2),),(0,),(1,),Q(1,8));l,u=r['endpoint'][0]
    y=solve_ivp(lambda t,x:-x-x**3/4,(0,.125),[.5],rtol=1e-12,atol=1e-14).y[0,-1];assert float(l)<=y<=float(u)


@pytest.mark.parametrize('mu,count',[(-1,0),(0,1),(1,2)])
def test_saddle_node(mu,count):
    r=v.normal_form('saddle_node',mu);assert r['real_equilibria']==count and r['fold']==(mu==0)
    m=v.Polynomial(((((0,),mu),((2,),-1)),));assert v.equilibrium(m,(1,))['equilibrium']==(mu==1)


@pytest.mark.parametrize('mu,cubic,radius,attracting',[(1,-1,1,True),(-1,-1,None,False),(-1,1,1,False),(1,1,None,False),(0,-1,None,False),(0,1,None,False)])
def test_hopf(mu,cubic,radius,attracting):
    r=v.normal_form('hopf',mu,cubic);assert r['cycle_radius_squared']==radius and r['cycle_attracting']==attracting and r['hopf']==(mu==0)
    m=v.Polynomial(((((1,0),mu),((0,1),-1),((3,0),cubic),((1,2),cubic)),(((1,0),1),((0,1),mu),((2,1),cubic),((0,3),cubic))));z=v.equilibrium(m,(0,0));assert z['equilibrium'] and z['jacobian']==((mu,-1),(1,mu))


def test_polynomial_refusals():
    m=v.Polynomial(((((1,),1),),));calls=[lambda:v.Polynomial(((((4,),1),),)),lambda:v.Polynomial(((((True,),1),),)),lambda:v.Polynomial(((((1,),1),((1,),2)),)),lambda:v.Polynomial(((((1,),1.),),)),lambda:v.equilibrium(m,(True,)),lambda:v.equilibrium(m,(Q(1<<4096),)),lambda:v.invariant_box(m,(-1,),(1,)),lambda:v.invariant_box(m,(1,),(-1,)),lambda:v.local_contraction(m,(-1,),(1,),(1,),1),lambda:v.normal_form('hopf',0,0),lambda:v.normal_form('unknown',0),lambda:v.validated_step(cubic('discrete'),(0,),(0,),(-1,),(1,),1)]
    for call in calls:
        with pytest.raises(ValueError):call()


@pytest.mark.parametrize('mu,stable',[(-1,True),(0,False),(1,False)])
def test_linearization(mu,stable):
    m=v.Polynomial(((((1,0),mu),((0,1),4),((3,0),-1)),(((1,0),-4),((0,1),mu),((0,3),-1))))
    r=v.linearization(m,(0,0));assert r['local_exponential_stability_proved']==stable
    assert bool(r['lyapunov_sha256'])==stable
    with pytest.raises(ValueError):v.linearization(m,(1,0))


def test_general_supply():
    # V=x^2, x'= -2x+u, y=2x+u. Supply 2u*y-y^2+4x^2 is
    # not a supply in ports only; use the strictly passive actual port supply.
    m=model(((-2,),),((1,),),((2,),),((1,),));S=((1,1),(1,0));raw=v.dissipativity(m,((1,),),S)
    assert v.replay(m,((1,),),S,raw,'dissipation')
    for x,u in itertools.product((-2,0,3),(-1,0,2)):
        assert 2*x*(-2*x+u)<=u*u+2*u*(2*x+u)
