import itertools
import numpy as np
import pytest
import torch
from cognitum.research.hdc_frontier_learning import *

def test_thdc_binding_grad_export():
    a=TrainableItems(4,3,2,8,19);x=np.array([[0,1,2,0],[2,1,0,2]])
    y=a(x);y.square().sum().backward()
    assert all(p.grad is not None and torch.count_nonzero(p.grad)>0 for p in a.parameters())
    np.testing.assert_allclose(y.detach(),exported_scores(x,*a.exported()),atol=1e-6)
    assert a.logical_inference_bytes()==226

def test_frozen_items():
    a=TrainableItems(4,3,2,8,19,learn_items=False);a(np.zeros((2,4),int)).sum().backward()
    assert a.position.grad is a.value.grad is None and a.classifier.grad is not None

@pytest.mark.parametrize('bits',[2,6,8])
def test_notch_exact_local(bits):
    q=np.array([0,2**bits-1,1,2],np.uint8);g=np.array([2,-3,.5,-.49]);tau=.5
    z=notch(q,g,bits,tau);np.testing.assert_equal(z,[2**bits-1,0,1,2]);d=np.array([-1,1,0,0]);objective=lambda t:g@t+tau*np.count_nonzero(t)
    assert objective(d)==min(objective(np.array(t)) for t in itertools.product([-1,0,1],repeat=4))

def test_phase_equations_and_gradient():
    a=PhaseMemory(3,4,2,8,seed=22);x=np.array([[0,1,3],[2,3,0]]);p,v,w=a.tables;u=2*np.pi/64
    h=np.exp(1j*u*(p[None,:,:].astype(float)+v[x])).sum(1);z=h@np.exp(-1j*u*w).T
    np.testing.assert_allclose(a.scores(x),np.abs(z)/(8*.3),rtol=1e-5,atol=1e-6)
    t=tuple(z.double().requires_grad_() for z in a.tensors());xx=torch.tensor(x);f=lambda *p:phase_logits(xx,*p,6).sum()
    assert torch.autograd.gradcheck(f,t,eps=1e-5,atol=1e-4)

@pytest.mark.parametrize('rule',['threshold','sgd','adam','adam6'])
def test_phase_state(rule):
    a=PhaseMemory(4,3,2,16,seed=2,rule=rule);before=[q.copy() for q in a.tables];loss,updates=a.update([[0,1,1,2],[1,0,2,1]],np.array([0,1]));assert np.isfinite(loss) and 0<=updates<=144
    if rule=='threshold':
        assert a.m is None and a.v is None and all(np.isin((q.astype(int)-p)%64,[0,1,63]).all() for q,p in zip(a.tables,before))
    assert a.persistent_array_bytes()==144*(9 if rule.startswith('adam') else 1)
    assert a.ideal_grid_bytes()==108
    with pytest.raises(ValueError):a.update([[3,0,0,0]],np.array([1]))

def test_hinge_finite_difference_and_svm():
    x=np.array([[2.,1.],[-2,-1],[1,0],[-1,0]]);y=np.array([1,-1,1,-1]);w=np.array([.2,.1]);loss,g=hinge(x,y,w,.2);e=np.eye(2)*1e-6
    np.testing.assert_allclose(g,[(hinge(x,y,w+a,.2)[0]-hinge(x,y,w-a,.2)[0])/2e-6 for a in e],atol=1e-8)
    fit=margin_fit(x,y,.2,500);assert np.all(np.sign(x@fit)==y);assert hinge(x,y,fit,.2)[0]<.13

def test_channel_and_informative():
    x=np.array([[[0,1],[1,0]]]);p=np.array([[1,-1],[-1,1]]);v=np.array([[1,1],[-1,1]]);np.testing.assert_equal(channel_bind(x,p,v),[[0,0]])
    z=np.array([[1,1],[1,-1],[-1,1],[-1,-1]]);y=np.array([0,0,1,1]);w=np.array([[1,1],[-1,1]])
    P,Q,D,S=informative(z,y,w);np.testing.assert_equal(D,[[1,0],[1,0]]);np.testing.assert_equal(S,D)

@pytest.mark.parametrize('m',[1,4,12])
def test_bit_expansion(m):
    rng=np.random.default_rng(5);x=rng.choice([-1,1],(9,17));k=rng.integers(0,m+1,(3,17));q=rng.choice([-1,1],(3,17))
    np.testing.assert_equal(expanded_dot(x,k,q,m),x@(q*(2*k-m)).T)
    with pytest.raises(ValueError):thermometer(k+m+1,q,m)

def test_absent_value_rows_do_not_move_without_history():
    a=PhaseMemory(3,5,2,8,seed=4,rule='threshold',tau=0)
    before=a.tables[1].copy();a.update([[0,1,0],[1,0,1]],np.array([0,1]))
    np.testing.assert_equal(a.tables[1][2:],before[2:])
    assert a.m is a.v is None

def test_gradient_rejection_and_atomic_state():
    a=PhaseMemory(2,3,2,4,seed=4);before=tuple(x.copy() for x in a.tables)
    with pytest.raises(ValueError):a.update([[0,1]],np.array([2]))
    assert a.step==0 and all(np.array_equal(x,y) for x,y in zip(a.tables,before))
    with pytest.raises(ValueError):notch(np.array([0],np.uint8),np.array([float('nan')]),6,0)
