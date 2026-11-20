import numpy as np
import pytest
from scipy.integrate import solve_ivp
from cognitum.research import ssm_scientific_learning as s


@pytest.mark.parametrize('steps',[1,4,8])
def test_ode(steps):
    t=np.linspace(0,1,21);z=s.neural_ode([[1]],[0],[[.7]],[.4],t,steps);ref=np.arcsinh(np.sinh(.4)*np.exp(.7*t));np.testing.assert_allclose(z['states'][:,0],ref,atol=1e-7);assert not z['execution_authorized']


def test_ode_tangent():
    W=[[1,.2],[-.3,.8]];b=[.1,-.2];V=np.array([[.3,.1],[-.2,.4]]);x=np.array([.2,.5]);t=[0,.1,.3,.7];z=s.neural_ode(W,b,V,x,t);q=np.r_[V.ravel(),x];h=1e-6
    def evaluate(q):return s.neural_ode(W,b,q[:4].reshape(2,2),q[4:],t)['states']
    fd=np.stack([(evaluate(q+h*d)-evaluate(q-h*d))/(2*h) for d in np.eye(len(q))],-1);np.testing.assert_allclose(z['jacobian'],fd,atol=1e-8)
    ref=solve_ivp(lambda t,x:V@np.tanh(np.array(W)@x+b),(0,.7),x,t_eval=t,rtol=1e-12,atol=1e-13).y.T;np.testing.assert_allclose(z['states'],ref,atol=1e-7)


@pytest.mark.parametrize('x0',[.3,.8,-.4])
def test_latent_fit(x0):
    t=np.linspace(0,1,21);y=2*np.arcsinh(np.sinh(x0)*np.exp(.7*t));z=s.latent_fit([[1]],[0],[[2]],t,y[:,None],[[.4]],[x0*.8]);assert z['readout'][0,0]==pytest.approx(.7,abs=1e-7);assert z['initial_state'][0]==pytest.approx(x0,abs=1e-7);h=s.neural_ode([[1]],[0],z['readout'],[.65],t);np.testing.assert_allclose(h['states'][:,0],np.arcsinh(np.sinh(.65)*np.exp(.7*t)),atol=1e-7)


def test_latent_unidentifiable():
    with pytest.raises(ValueError,match='rank'):s.latent_fit([[1]],[0],[[0]],[0,.5,1],[[0],[0],[0]],[[.4]],[.2])


@pytest.mark.parametrize('substeps',[4,16])
def test_cde(substeps):
    t=[0,.1,.4,.8,1.3];u=np.array([[0,0],[.1,.3],[.2,-.1],[.3,.2],[.5,.1]]);z=s.cde([[1]],[0],[[[.4],[.2]]],[.5],t,u,substeps);ref=np.arcsinh(np.sinh(.5)*np.exp(u@[.4,.2]));np.testing.assert_allclose(z['states'][:,0],ref,atol=1e-7);u[3:]+=1;w=s.cde([[1]],[0],[[[.4],[.2]]],[.5],t,u,substeps);np.testing.assert_array_equal(w['states'][:3],z['states'][:3]);assert w['interior_requires_next_knot']


def test_signature():
    u=[[0,0],[1,0],[1,2],[0,2],[0,0]];z=s.signature(u);np.testing.assert_allclose(z['level1'][-1],[0,0]);np.testing.assert_allclose(z['level2'][-1],[[0,2],[-2,0]]);a=s.signature(u[:3]);b=s.signature(u[2:]);np.testing.assert_allclose(z['level2'][-1],a['level2'][-1]+b['level2'][-1]+np.outer(a['level1'][-1],b['level1'][-1]));np.testing.assert_allclose(z['level2']+z['level2'].transpose(0,2,1),np.einsum('ti,tj->tij',z['level1'],z['level1']))


@pytest.mark.parametrize('seed',[3,17,82])
def test_sde_fit(seed):
    rng=np.random.default_rng(seed);x=rng.uniform(-2,2,8192);a=np.tanh(x);dt=.2;p=np.array([.4,-.6,-.7,.2]);y=x+dt*(p[0]+p[1]*a)+np.sqrt(dt)*np.exp(p[2]+p[3]*a)*rng.standard_normal(len(x));z=s.neural_sde_fit(x,y,dt);np.testing.assert_allclose(z['parameters'],p,atol=.06);t=rng.uniform(-2,2,2048);b=np.tanh(t);q=z['parameters'];np.testing.assert_allclose(np.exp(q[2]+q[3]*b),np.exp(p[2]+p[3]*b),atol=.04)


@pytest.mark.parametrize('seed',[2,23,91])
def test_sde_moments(seed):
    z=s.neural_sde([.3,0,np.log(.4),0],.2,.125,8,8192,seed);assert z['mean']==pytest.approx(.5,abs=.015);assert z['variance']==pytest.approx(.16,abs=.01);assert z['coupled_rmse']<1e-12


def test_sde_refine():
    p=[0,-.8,-1,.2];a=s.neural_sde(p,.3,.125,8,4096,3);b=s.neural_sde(p,.3,.03125,32,4096,3);assert b['coupled_rmse']<a['coupled_rmse']*.7


@pytest.mark.parametrize('damping',[0,.3])
def test_physics(damping):
    rng=np.random.default_rng(7);q,p=rng.uniform(-2,2,(2,400));params=[1.2,.4,damping];z=s.physics_fit(q,p,-params[0]*q-params[1]*q**3-damping*p);np.testing.assert_allclose(z['parameters'],params,atol=1e-12);a=s.physics_sim(z['parameters'],.7,.3,.01,400);ref=solve_ivp(lambda t,x:[x[1],-params[0]*x[0]-params[1]*x[0]**3-damping*x[1]],(0,4),[.7,.3],t_eval=np.arange(401)*.01,rtol=1e-11,atol=1e-12).y.T;np.testing.assert_allclose(a['states'],ref,atol=8e-5);assert a['balance_residual']<1e-4;assert np.all(np.diff(a['dissipated'])>=-1e-14)
    if damping:assert a['energy'][-1]<a['energy'][0]


@pytest.mark.parametrize('fn',[lambda:s.neural_ode([[1]],[0],[[1]],[0],[0,0]),lambda:s.cde([[1]],[0],[[[1]]],[0],[0,1],[[0]]),lambda:s.neural_sde_fit([1]*64,[2]*64,.1),lambda:s.neural_sde([0,0,0,0],0,.1,4,10,-1),lambda:s.physics_fit([1]*3,[1]*3,[1]*3),lambda:s.physics_sim([1,0,-1],0,0,.1,2)])
def test_refuse(fn):
    with pytest.raises(ValueError):fn()
