import numpy as np
import pytest
from cognitum.research import ssm_control as c


@pytest.mark.parametrize('poles',[[.2,.4],[-.3,.5],[0,.8]])
def test_placement(poles):
    A=np.array([[1,.2],[0,1]]);B=np.array([[0],[1]]);z=c.placement(A,B,poles);np.testing.assert_allclose(np.sort(z['poles']),poles,atol=1e-9);assert not z['execution_authorized']


@pytest.mark.parametrize('poles',[[.2,.2],[1,.2],[.1]])
def test_pole_refuse(poles):
    with pytest.raises(ValueError):c.placement([[1,.2],[0,1]],[[0],[1]],poles)


def test_uncontrollable():
    with pytest.raises(ValueError,match='rank'):c.placement(np.eye(2),[[1],[0]],[.2,.3])


def test_observer():
    A=np.array([[1,.2],[0,.9]]);C=np.array([[1,0]]);z=c.observer(A,C,[.2,.4],[1,2],[0,0],[[.1]]*20,[[0],[1]]);F=A-z['gain']@C
    for k,e in enumerate(z['errors']):np.testing.assert_allclose(e,np.linalg.matrix_power(F,k)@[1,2],atol=1e-12)
    assert np.linalg.norm(z['errors'][-1])<1e-5


def test_unobservable():
    with pytest.raises(ValueError,match='rank'):c.observer(np.eye(2),[[1,0]],[.2,.3],[1,2],[0,0],[[0]],[[0],[1]])


@pytest.mark.parametrize('a',[.5,1.,1.2])
def test_lqr_scalar(a):
    z=c.lqr([[a]],[[1]],[[1]],[[1]]);P=(a*a+np.sqrt(a**4+4))/2;assert z['value'][0,0]==pytest.approx(P);assert z['gain'][0,0]==pytest.approx(a*P/(1+P));assert z['residual']<1e-10


def test_lqr_unstabilizable():
    with pytest.raises(ValueError):c.lqr([[1.2]],[[0]],[[1]],[[1]])


@pytest.mark.parametrize('N',[1,4,16])
def test_finite(N):
    z=c.finite_lqr([[1]],[[1]],[[1]],[[1]],[[2]],[1],N);P=2.
    for _ in range(N):P=1+P/(1+P)
    assert z['cost']==pytest.approx(P);assert z['value']==pytest.approx(P)


@pytest.mark.parametrize('N',[1,4,8])
def test_mpc_unconstrained(N):
    A=[[1,.2],[0,1]];B=[[0],[1]];Q=[[1,0],[0,.3]];R=[[.5]];P=[[2,0],[0,1]];x=[1,.3];a=c.finite_lqr(A,B,Q,R,P,x,N);b=c.mpc(A,B,Q,R,P,x,N,[100,100],[100]);np.testing.assert_allclose(a['inputs'],b['inputs'],atol=1e-10);assert a['cost']==pytest.approx(b['cost'])


def test_mpc_active():
    z=c.mpc([[1]],[[1]],[[1]],[[.1]],[[1]],[1],3,[2],[.2]);np.testing.assert_allclose(z['inputs'][:,0],[-.2]*3,atol=1e-7);np.testing.assert_allclose(z['states'][:,0],[1,.8,.6,.4],atol=1e-7);assert z['stationarity_residual']<1e-6


def test_mpc_state_constraint():
    z=c.mpc([[2]],[[1]],[[0]],[[1]],[[0]],[.9],1,[1],[2]);assert z['inputs'][0,0]==pytest.approx(-.8);assert z['states'][-1,0]==pytest.approx(1)


@pytest.mark.parametrize('x,u',[(1,.1),(2,10)])
def test_mpc_infeasible(x,u):
    with pytest.raises(ValueError):c.mpc([[2]],[[1]],[[1]],[[1]],[[1]],[x],3,[1],[u])


def test_lqg_separation():
    A=np.array([[1,.2],[0,.9]]);B=np.array([[0],[1]]);C=np.array([[1,0]]);args=(A,B,C,np.eye(2),[[1]],np.eye(2)*.01,[[.1]],[1,2],[0,0],32,9);z=c.lqg(*args);p=np.r_[np.linalg.eigvals(A-B@z['control_gain']),np.linalg.eigvals(A-z['observer_gain']@C)];np.testing.assert_allclose(np.sort_complex(z['poles']),np.sort_complex(p),atol=1e-9);np.testing.assert_array_equal(z['states'],c.lqg(*args)['states']);assert np.max(abs(p))<1


def test_lqg_reference_gain():
    z=c.lqg([[1]],[[1]],[[1]],[[1]],[[1]],[[.25]],[[1]],[0],[0],5,1);P=(.25+np.sqrt(.25**2+1))/2;assert z['observer_gain'][0,0]==pytest.approx(P/(P+1))


def test_exact_box():
    z=c.box_witness([[1]],[[1]],[['1/2']],[2],[1],['1/4']);assert z['state_margin']==('3/4',) and z['input_margin']==('0',) and z['exact_rational_box_verified'] and not z['execution_authorized']


@pytest.mark.parametrize('K,w',[[[['1/2']],[2]],[[[2]],[0]],[[[.5]],[0]]])
def test_exact_box_refuse(K,w):
    with pytest.raises(ValueError):c.box_witness([[1]],[[1]],K,[2],[1],w)


def test_exact_box_coupled():
    z=c.box_witness([['1/2','1/4'],[0,'1/4']],[[0],[0]],[[0,0]],[1,2],[1],[0,'1/2']);assert z['state_margin']==('0','1')
