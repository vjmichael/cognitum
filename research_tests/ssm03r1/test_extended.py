import numpy as np
import pytest
from cognitum.research import ssm_extended as d


def test_dae():
    z=d.constrained([[1,0],[0,0]],[[-2,1],[2,-1]],[1,2],.25,12)
    np.testing.assert_allclose(z['states'],np.tile([1,2],(13,1)),atol=1e-12)
    assert z['algebraic_residual']<1e-12 and not z['execution_authorized']


def test_dae_decay():
    z=d.constrained([[1,0],[0,0]],[[-3,1],[2,-1]],[1,2],.125,16)
    np.testing.assert_allclose(z['states'],np.exp(-z['times'][:,None])*[1,2],atol=1e-12)

@pytest.mark.parametrize('E,A,x', [([[1,0],[0,0]],[[-1,0],[1,0]],[1,0]),([[1,0],[0,0]],[[-1,0],[1,-1]],[1,0]),([[0,1],[0,0]],[[-1,0],[1,-1]],[1,1])])
def test_dae_refuse(E,A,x):
    with pytest.raises(ValueError):d.constrained(E,A,x,.125,4)


def test_hybrid():
    z=d.hybrid([[[-1]],[[-2]]],[([1],.5,-1,[[2]],[0])],[1],.125,16)
    t=z['times'];ev=z['events'][0];assert ev[0]==pytest.approx(np.log(2),abs=1e-9)
    np.testing.assert_allclose(ev[2],[.5],atol=1e-9);np.testing.assert_allclose(ev[3],[1],atol=1e-9)
    np.testing.assert_allclose(z['states'][:,0],np.where(t<np.log(2),np.exp(-t),np.exp(-2*(t-np.log(2)))),atol=1e-8)
    assert not z['event_completeness_certified']


def test_no_event():
    z=d.hybrid([[[-1]],[[-2]]],[([1],.01,-1,[[1]],[0])],[1],.125,4)
    assert z['events']==[]


def test_bad_guard():
    with pytest.raises(ValueError):d.hybrid([[[-1]],[[-2]]],[([1],1,-1,[[1]],[0])],[1],.125,4)

@pytest.mark.parametrize('mesh',[4,16,32])
def test_delay(mesh):
    z=d.delay([[0]],[[1]],[1],1,mesh,2);t=z['times'];expected=1+t+np.maximum(t-1,0)**2/2
    np.testing.assert_allclose(z['states'][:,0],expected,atol=1e-9)
    assert not z['certified']


def test_delay_zero():
    with pytest.raises(ValueError):d.delay([[0]],[[1]],[1],0,8,2)

@pytest.mark.parametrize('velocity',[None,[0],[3]])
def test_modal(velocity):
    z=d.weak_evolution([[2]],[[8]],[1],.125,16,velocity);t=z['times'];assert z['eigenvalues'][0]==pytest.approx(4)
    ref=np.exp(-4*t) if velocity is None else np.cos(2*t)+velocity[0]*np.sin(2*t)/2
    np.testing.assert_allclose(z['states'][:,0],ref,atol=1e-10)
    if velocity is None:assert np.all(np.diff(z['energy'])<=0)
    else:np.testing.assert_allclose(z['energy'],z['energy'][0],atol=1e-10)


def test_wave_zero():
    z=d.weak_evolution([[2]],[[0]],[1],.125,8,[3]);np.testing.assert_allclose(z['states'][:,0],1+3*z['times'])

@pytest.mark.parametrize('M,K',[([[0]],[[1]]),([[1]],[[-1]]),([[1,1],[0,1]],[[1,0],[0,1]])])
def test_weak_refuse(M,K):
    with pytest.raises(ValueError):d.weak_evolution(M,K,[1]*len(M),.125,4)


def test_pod_exact():
    z=d.pod([[-1,0],[0,-2]],[[1,.5,.25],[0,0,0]],1,[1,0],.125,16)
    assert z['trajectory_error']<1e-12 and z['snapshot_error']<1e-12


def test_pod_heldout():
    z=d.pod([[-1,0],[0,-2]],[[1,.5,.25],[0,0,0]],1,[0,1],.125,16)
    assert z['trajectory_error']==pytest.approx(1) and z['snapshot_error']<1e-12


def test_pod_rank():
    with pytest.raises(ValueError):d.pod([[-1,0],[0,-2]],[[1,.5,.25],[0,0,0]],2,[1,0],.125,16)

@pytest.mark.parametrize('partition',[[[0],[1,2]],[[2,0],[1]],[[0,1,2]]])
def test_network(partition):
    z=d.network([[0,1,0],[1,0,1],[0,1,0]],[3,0,0],.125,32,partition)
    assert z['mass_error']<1e-12 and z['partition_error']<1e-8
    assert np.min(z['states'])>=-1e-12
    assert np.all(np.diff(np.sum(z['states']**2,axis=1))<=1e-12)

@pytest.mark.parametrize('partition',[[[0],[0]],[[0]],[[0,1,2]],[[False,1]]])
def test_partition_refuse(partition):
    with pytest.raises(ValueError):d.network([[0,1],[1,0]],[1,0],.125,4,partition)


def test_network_refuse():
    with pytest.raises(ValueError):d.network([[0,1],[2,0]],[1,0],.125,4,[[0,1]])


def test_balanced():
    A=np.diag([-1.,-4.]);B=np.diag([2.,1.]);C=np.diag([2.,1.]);z=d.balanced_reduction(A,B,C,1)
    np.testing.assert_allclose(z['hankel_values'],[2,.125]);assert z['estimated_hinf_bound']==pytest.approx(.25)
    assert z['A'][0,0]==pytest.approx(-1) and z['gramian_residual']<1e-12
    for w in [0,.1,1,10,100]:
        ref=C@np.linalg.solve(1j*w*np.eye(2)-A,B);reduced=z['C']@np.linalg.solve(1j*w*np.eye(1)-z['A'],z['B'])
        assert np.linalg.norm(ref-reduced,2)<=z['estimated_hinf_bound']+1e-12

@pytest.mark.parametrize('A,B,C',[(np.diag([1.,-4.]),np.eye(2),np.eye(2)),(np.diag([-1.,-4.]),[[1],[0]],np.eye(2)),(-np.eye(2),np.eye(2),np.eye(2))])
def test_balanced_refuse(A,B,C):
    with pytest.raises(ValueError):d.balanced_reduction(A,B,C,1)


def test_coupled_oscillator():
    z=d.weak_evolution(np.eye(2),[[1,-1],[-1,1]],[1,-1],.125,16,[0,0]);t=z['times']
    np.testing.assert_allclose(z['states'],np.cos(np.sqrt(2)*t[:,None])*[1,-1],atol=1e-10)
    np.testing.assert_allclose(z['energy'],z['energy'][0],atol=1e-10)
