import numpy as np
import pytest
from cognitum.research.hdc_advanced_learning import MultiPrototype,budget_dimension,refine_step,train_projection,_projection_grad


def test_multimodal_and_future_unseen():
    m=MultiPrototype(3,2,2);x=np.array([[1,0],[-1,0],[0,1]],np.float32)
    assert (m.predict(x)==-1).all();m.update(x,np.array([0,0,1]));assert np.array_equal(m.predict(x),[0,0,1]);assert m.count[2].sum()==0
    old=m.w.copy();m.update(np.array([[0,-1]],np.float32),np.array([2]));assert np.array_equal(old[:2],m.w[:2]);assert m.predict(np.array([[0,-1]],np.float32))[0]==2

@pytest.mark.parametrize('bad',[np.array([[0,0]],np.float32),np.array([[np.nan,0]],np.float32),np.ones((1,3),np.float32)])
def test_invalid_atomic(bad):
    m=MultiPrototype(2,2,2);old=m.w.copy()
    with pytest.raises(ValueError):m.update(bad,np.array([0]))
    assert np.array_equal(m.w,old) and m.count.sum()==0

@pytest.mark.parametrize('slots',[1,2,4])
def test_budget(slots):
    d=budget_dimension(13,3,slots,4096);m=MultiPrototype(3,d,slots);size=4*d*14+m.numeric_bytes+16*13
    assert size<=4096<size+4*(14+3*slots)


def test_refine_formula_and_negative_factor():
    w=np.array([[1,0],[.8,.6],[0,1]],np.float32);h=np.array([[1,0]],np.float32)
    out,s,n,kind=refine_step(w,h,1,0.,0);assert kind=='error' and n==1 and s==1
    # top two 1,.8 -> factor -.8, target delta .2 * -.8
    assert np.allclose(out[1],w[1]-.16*h[0]);assert np.array_equal(out[0],w[0]);assert np.array_equal(out[2],w[2])


def test_refine_correct_ambiguity():
    w=np.array([[1,1],[-1,0]],np.float32);h=np.array([[1,0]],np.float32)
    a,_,_,k=refine_step(w,h,0,.9,1);b,_,_,_=refine_step(w,h,0,.9,1,correct_rule='literal');assert k=='correct' and not np.allclose(a,b)
    a,_,_,k=refine_step(w,h,0,.1,1);assert k=='skip' and np.array_equal(a,w)


def test_gradient_matches_torch():
    import torch
    rng=np.random.default_rng(21);x=rng.normal(size=(6,3)).astype('float32');p=rng.normal(size=(4,3)).astype('float32');b=rng.normal(size=4).astype('float32');w=rng.normal(size=(2,4)).astype('float32');y=np.arange(6)%2
    pt,bt,wt=[torch.tensor(v,requires_grad=True) for v in (p,b,w)];z=torch.tensor(x)@pt.T;h=(z+bt).cos()*z.sin();loss=torch.nn.functional.cross_entropy(h@wt.T,torch.tensor(y));loss.backward();a=_projection_grad(x,y,p,b,w)
    assert np.allclose(a[0],loss.item(),atol=1e-6)
    for ref,t in zip(a[1:],(pt,bt,wt)):assert np.allclose(ref,t.grad.numpy(),atol=2e-6)
    q,c,v,l=train_projection(x,y,p,b,w,epochs=3);assert not np.array_equal(q,p) and np.isfinite(l).all()
    q,c,v,l=train_projection(x,y,p,b,w,epochs=3,learn=False);assert np.array_equal(q,p) and np.array_equal(c,b)

@pytest.mark.parametrize('rate',[0.,.3,.6])
def test_dropout_native_training_parity(rate):
    import torch
    from torchhd import classifiers
    from torch.utils.data import DataLoader,TensorDataset
    from cognitum.research.hdc_advanced_learning import lehdc_dropout_reference
    r=np.random.default_rng(7);a=torch.tensor(r.uniform(size=(31,5)).astype('float32'));y=torch.tensor(np.arange(31)%3);torch.manual_seed(19)
    m=classifiers.LeHDC(5,29,3,n_levels=16,min_level=0.,max_level=1.,epochs=4,dropout_rate=rate);h=m.encoder(a).detach().numpy();loader=DataLoader(TensorDataset(a,y),batch_size=8,shuffle=False)
    torch.manual_seed(77);m.fit(loader);state=torch.random.get_rng_state().clone();shadow,w,opt=lehdc_dropout_reference(h,y.numpy(),3,epochs=4,seed=77,rate=rate,batch=8)
    assert torch.equal(torch.random.get_rng_state(),state)
    assert np.allclose(shadow,m.grad_model.weight.detach().numpy(),atol=1e-6)
    assert np.array_equal(w,m.model.weight.detach().numpy()) and opt==2*w.nbytes+4
    m.eval();assert np.array_equal((h@w.T).argmax(1),m(a).detach().numpy().argmax(1))
