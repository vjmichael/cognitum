import numpy as np
import pytest
from tools.cog04o.fixtures import elliptic
from cognitum.research import ssm_interop as s


def test_kan_derivative():
    c=elliptic();x,y=.25,.5;z=s.kan_eval(c,[x,y]);assert z['value']==pytest.approx(9*x*(1-x)*y*(1-y));np.testing.assert_allclose(z['gradient'],[9*(1-2*x)*y*(1-y),9*x*(1-x)*(1-2*y)],atol=1e-12)


def test_kan_evolution():
    c=elliptic();d=elliptic(scale=.5);x0=np.array([.1,.2]);z=s.kan_evolve([c,d],x0,.025,8);from scipy.integrate import solve_ivp
    ref=solve_ivp(lambda t,x:9*x[0]*(1-x[0])*x[1]*(1-x[1])*np.array([1,.5]),(0,.2),x0,t_eval=np.linspace(0,.2,9),rtol=1e-12,atol=1e-13).y.T;np.testing.assert_allclose(z['states'],ref,atol=1e-7)


def test_kan_observation():
    x=np.array([.25,.5]);P=np.eye(2)*.01;v=9*x[0]*(1-x[0])*x[1]*(1-x[1]);H=np.array([[1.125,0]]);R=.1+.02;K=P@H.T@np.linalg.inv(H@P@H.T+R);z=s.kan_observe(elliptic(),x,P,v+.1,.1,.02);np.testing.assert_allclose(z['mean'],x+K[:,0]*.1);np.testing.assert_allclose(z['covariance'],P-K@H@P)


def test_kan_domain_refusal():
    with pytest.raises(ValueError):s.kan_eval(elliptic(),[1.1,.2])
