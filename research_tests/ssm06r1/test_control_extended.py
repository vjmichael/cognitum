import itertools
from fractions import Fraction
import numpy as np
import pytest
from cognitum.research import ssm_control as c, ssm_control_extended as e


@pytest.mark.parametrize('seed',[1,17,81])
def test_uio(seed):
    A=np.array([[.9,.2,.1],[0,.8,.3],[0,0,.7]]);B=np.ones((3,1));C=np.eye(3)[:2];E=np.array([[1],[0],[0]]);rng=np.random.default_rng(seed);U=rng.normal(size=(20,1));W=100*rng.normal(size=(20,1));z=e.unknown_input(A,B,C,E,[.1,.2,.3],[1,2,3],[0,0,0],U,W);q=e.unknown_input(A,B,C,E,[.1,.2,.3],[1,2,3],[0,0,0],U,np.zeros_like(W));np.testing.assert_allclose(z['errors'],q['errors'],atol=1e-10);assert np.linalg.norm(z['errors'][-1])<1e-8


def test_uio_rank():
    with pytest.raises(ValueError,match='rank'):e.unknown_input(np.eye(2),[[1],[0]],[[1,0]],[[0],[1]],[.1,.2],[0,0],[0,0],[[0]],[[1]])


def test_robust_corners():
    A=np.array([[.8,.2],[-.1,.7]]);B=np.eye(2);w=np.array([.1,.15]);z=e.uncertain_plan(A,B,np.eye(2),np.eye(2),np.eye(2),[.7,.8],3,[1,1],[1,1],disturbance=w)
    for signs in itertools.product([-1,1],repeat=6):
        x=np.array([.7,.8])
        for j,u in enumerate(z['inputs']):
            x=A@x+B@u+w*np.array(signs[2*j:2*j+2]);assert np.all(abs(x)<=1+1e-8);assert np.all(abs(x-z['states'][j+1])<=z['tightening'][j]+1e-8)


def test_robust_active():
    z=e.uncertain_plan([[2]],[[1]],[[0]],[[1]],[[0]],[.8],1,[1],[2],disturbance=[.2]);assert z['inputs'][0,0]==pytest.approx(-.8);assert z['states'][-1,0]==pytest.approx(.8)


def test_robust_infeasible():
    with pytest.raises(ValueError):e.uncertain_plan([[2]],[[1]],[[1]],[[1]],[[1]],[1],2,[1],[.1],disturbance=[.2])


@pytest.mark.parametrize('seed',[2,31,82])
def test_chance(seed):
    A=np.array([[1.1]]);B=np.array([[1.]]);z=e.uncertain_plan(A,B,[[0]],[[1]],[[0]],[.7],3,[1],[2],noise_cov=[[.01]],risk=.05);rng=np.random.default_rng(seed);X=np.full(20000,.7);bad=np.zeros(len(X),bool)
    for u in z['inputs']:
        X=1.1*X+u[0]+rng.normal(0,.1,len(X));bad|=abs(X)>1
    assert bad.mean()<.055 and z['joint_risk_bound']==.05


def test_chance_refuse():
    with pytest.raises(ValueError):e.uncertain_plan([[1]],[[1]],[[1]],[[1]],[[1]],[0],3,[1],[1],noise_cov=[[1]],risk=.05)


def test_receding():
    z=e.receding([[1]],[[1]],[[1]],[[.1]],[[1]],[.8],4,[1],[.5],[[.1],[-.1]]*8,[.1]);assert np.max(abs(z['states']))<=1 and np.max(abs(z['inputs']))<=.5+1e-8 and not z['recursive_feasibility_established']


def test_receding_refuse():
    with pytest.raises(ValueError):e.receding([[1]],[[1]],[[1]],[[1]],[[1]],[0],2,[1],[1],[[.2]],[.1])


def test_adaptive():
    rng=np.random.default_rng(12);X=rng.normal(size=(50,1));U=rng.normal(size=(50,1));Y=.8*X+.7*U;z=e.adaptive([[.8]],[[.7]],[[1]],[[1]],[[1]],[.7],3,[2],[1],X,U,Y,[[0]]*5);np.testing.assert_allclose(z['models'],np.tile([[[.8,.7]]],(5,1,1)),atol=1e-12);assert abs(z['states'][-1,0])<.1 and not z['robustness_established']


def test_adaptive_rank():
    with pytest.raises(ValueError,match='rank'):e.adaptive([[1]],[[1]],[[1]],[[1]],[[1]],[0],2,[1],[1],[[1],[2]],[[1],[2]],[[2],[4]],[[0]])


def trajectory(seed):
    rng=np.random.default_rng(seed);A=np.array([[.8,.1],[0,.6]]);B=np.array([[1],[.4]]);X=[np.array([.1,.2])];U=rng.normal(size=(100,1))
    for u in U:X.append(A@X[-1]+B@u)
    return A,B,np.array(X),U


@pytest.mark.parametrize('h',[1,4,8])
def test_data_plan(h):
    A,B,X,U=trajectory(10);args=(np.eye(2),[[1]],np.eye(2),[1,.5],h,[2,2],[.7]);a=e.data_plan(X,U,*args);b=c.mpc(A,B,*args);np.testing.assert_allclose(a['inputs'],b['inputs'],atol=1e-7);np.testing.assert_allclose(a['states'],b['states'],atol=1e-7)


def test_data_rank():
    with pytest.raises(ValueError,match='rank'):e.data_plan(np.zeros((30,1)),np.zeros((29,1)),[[1]],[[1]],[[1]],[0],3,[1],[1])


def test_data_noise():
    A,B,X,U=trajectory(10);X[20]+=1
    with pytest.raises(ValueError,match='inconsistent'):e.data_plan(X,U,np.eye(2),[[1]],np.eye(2),[0,0],4,[2,2],[1])


def test_experiment():
    z=e.experiment_design([[1,0],[0,2],[1,1]],2,np.zeros((2,2)),[1,1,1]);assert z['indices']==(0,1) and z['logdet']==pytest.approx(np.log(4))


def test_experiment_rank():
    with pytest.raises(ValueError):e.experiment_design([[1,0],[2,0]],2,np.zeros((2,2)),[1,1])


def test_sensor():
    A=np.diag([.8,.4]);z=e.sensor_design(A,[[1,0],[0,1],[1,1]],1,3,[1,1,1]);assert z['indices']==(2,) and np.linalg.det(z['gramian'])>0


def test_sensor_rank():
    with pytest.raises(ValueError):e.sensor_design(np.eye(2),[[1,0],[0,1]],1,4,[1,1])


@pytest.mark.parametrize('b,expected',[(1,'-3/4'),(-1,'3/4')])
def test_safety(b,expected):
    z=e.scalar_safety(2,b,'3/4',2 if b==1 else -2,1,2,'1/4');assert z['input']==expected and z['state_margin']=='0' and not z['execution_authorized']


def test_safety_no_action():
    assert e.scalar_safety('1/2',0,1,0,1,1,'1/4')['input']=='0'


@pytest.mark.parametrize('args',[(2,1,2,0,1,1,0),(3,0,1,0,1,1,0),(3,1,1,0,1,1,0),(1,1,.5,0,1,1,0)])
def test_safety_refuse(args):
    with pytest.raises(ValueError):e.scalar_safety(*args)
