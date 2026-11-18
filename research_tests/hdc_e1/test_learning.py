"""Real pinned TorchHD conformance and independent learning controls."""
import numpy as np
import pytest
import torch
import torchhd
from torchhd import classifiers,models
from torch.utils.data import DataLoader,TensorDataset
from importlib.metadata import version
from cognitum.research.hdc_learning import (Prototype,RandomFeatures,cosine_scores,neural_regeneration_scores,dist_regeneration_scores,density_ridge)

@pytest.mark.parametrize('rule',['vanilla','adapt','online'])
@pytest.mark.parametrize('seed',[41,73])
def test_native_batch_updates(rule,seed):
    assert version('torch-hd')=='5.8.4'
    rng=np.random.default_rng(seed);x=rng.normal(size=(48,32)).astype('float32');y=rng.integers(0,4,48)
    m=Prototype(4,32);n=models.Centroid(32,4)
    for start in range(0,48,8):
        z=x[start:start+8];t=y[start:start+8];method='add' if rule=='vanilla' else 'add_'+rule
        getattr(n,method)(torch.tensor(z),torch.tensor(t),lr=.2);m.update(z,t,rule=rule,lr=.2)
        np.testing.assert_allclose(m.weights,n.weight.detach(),rtol=2e-5,atol=2e-6)
        np.testing.assert_allclose(m.scores(z),n(torch.tensor(z)).detach(),rtol=2e-5,atol=2e-6)

@pytest.mark.parametrize('rule',['vanilla','adapt','online','margin'])
def test_complex_update_hermitian(rule):
    r=np.random.default_rng(90);x=np.exp(1j*r.normal(size=(12,16))).astype('complex64');y=np.arange(12)%3
    m=Prototype(3,16,np.complex64);m.update(x[:6],y[:6]);s=m.scores(x[6:]);w=m.weights;v=x[6:];t=y[6:]
    ref=np.zeros_like(s)
    for i,a in enumerate(v):
        for j,b in enumerate(w):ref[i,j]=np.vdot(a,b).real/max(np.linalg.norm(a)*np.linalg.norm(b),1e-8)
    np.testing.assert_allclose(s,ref,atol=2e-7)
    p=s.argmax(1);delta=np.zeros_like(w)
    for i in range(len(v)):
        j=t[i];k=p[i]
        if rule=='margin':k=max([k for k in range(3) if k!=j],key=lambda k:s[i,k]);use=s[i,j]-s[i,k]<.1
        else:use=k!=j
        if rule=='vanilla':delta[j]+=v[i]
        elif use:delta[j]+=v[i]*(1-s[i,j] if rule=='online' else 1);delta[k]+=v[i]*(s[i,k]-1 if rule=='online' else -1)
    m.update(v,t,rule=rule);np.testing.assert_allclose(m.weights,w+delta,atol=1e-6)

@pytest.mark.parametrize('kind',['linear','sinusoid','phase'])
def test_regeneration_changes_only_requested_rows(kind):
    e=RandomFeatures.seeded(6,32,3,kind=kind);x=np.ones((4,6),np.float32);h=e.encode(x);m=Prototype(2,32,h.dtype);m.update(h,[0,1,0,1]);before=m.weights;w,b=e.state();ids=np.array([2,7,9]);e.regenerate(ids,np.random.default_rng(18),m);a,c=e.state();untouched=np.setdiff1d(np.arange(32),ids)
    np.testing.assert_array_equal(w[untouched],a[untouched]);np.testing.assert_array_equal(b[untouched],c[untouched]);np.testing.assert_array_equal(m.weights[:,untouched],before[:,untouched]);assert np.all(m.weights[:,ids]==0) and np.all(np.any(w[ids]!=a[ids],axis=1))
    if kind=='phase':np.testing.assert_allclose(np.abs(e.encode(x)),1,atol=1e-6)
    else:assert np.any(e.encode(x)[:,ids]!=h[:,ids])

@pytest.mark.parametrize('kind',['linear','sinusoid'])
def test_native_initial_encoding(kind):
    torch.manual_seed(13);cls=classifiers.OnlineHD if kind=='sinusoid' else classifiers.DistHD;n=cls(6,32,3,epochs=2);w=n.encoder.weight.detach().numpy();b=n.encoder.bias.detach().numpy().ravel() if kind=='sinusoid' else None;e=RandomFeatures(w,b,kind=kind);x=np.random.default_rng(3).normal(size=(12,6)).astype('float32');np.testing.assert_allclose(e.encode(x),n.encoder(torch.tensor(x)).detach().numpy(),atol=2e-6)

@pytest.mark.parametrize('cls',[classifiers.NeuralHD,classifiers.DistHD])
def test_native_regeneration_defect_is_observed(cls):
    """Pin upstream behavior; do not mistake a completed fit for actual regeneration."""
    torch.manual_seed(21);r=np.random.default_rng(23);x=torch.tensor(r.random((64,8)).astype('float32'));y=torch.arange(64)%3;n=cls(8,32,3,epochs=3,regen_freq=2,regen_rate=.25);w=n.encoder.weight.detach().clone();n.fit(DataLoader(TensorDataset(x,y),batch_size=16));assert torch.count_nonzero(n.model.weight)>0;assert torch.equal(w,n.encoder.weight), 'upstream behavior changed; reaudit actual dimension regeneration'

def test_dist_score_matches_actual_native():
    torch.manual_seed(234);r=np.random.default_rng(25);n=classifiers.DistHD(5,32,4,epochs=2);w=r.normal(size=(4,32)).astype('float32');n.model.weight.data.copy_(torch.tensor(w));x=r.normal(size=(32,5)).astype('float32');y=r.integers(0,4,32);h=n.encoder(torch.tensor(x)).detach().numpy();np.testing.assert_allclose(dist_regeneration_scores(h,y,w),n.regen_score(torch.tensor(x),torch.tensor(y)).detach().numpy(),rtol=2e-5,atol=2e-5)

def test_dist_all_correct_vector():
    w=np.eye(3,dtype=np.float32);np.testing.assert_array_equal(dist_regeneration_scores(w,np.arange(3),w),np.zeros(3))

def test_neural_variance():
    w=np.random.default_rng(4).normal(size=(4,32)).astype('float32');np.testing.assert_allclose(neural_regeneration_scores(w),torch.var(torch.nn.functional.normalize(torch.tensor(w),dim=1),dim=0),rtol=1e-5,atol=1e-7)

@pytest.mark.parametrize('cls',[classifiers.Vanilla,classifiers.AdaptHD,classifiers.OnlineHD,classifiers.IntRVFL])
def test_full_native_fit(cls):
    torch.manual_seed(34);r=np.random.default_rng(7);x=torch.tensor(r.random((60,8)).astype('float32'));y=torch.arange(60)%3;kwargs={'epochs':2} if cls in (classifiers.AdaptHD,classifiers.OnlineHD) else {};n=cls(8,32,3,**kwargs);n.fit(DataLoader(TensorDataset(x,y),batch_size=10));out=n(x);assert out.shape==(60,3) and torch.isfinite(out).all() and torch.count_nonzero(n.model.weight)>0

@pytest.mark.parametrize('alpha',[.1,1.])
def test_native_rvfl_readout(alpha):
    torch.manual_seed(52);r=np.random.default_rng(5);x=torch.tensor(r.random((64,8)).astype('float64'));y=torch.tensor(np.arange(64)%3);n=classifiers.IntRVFL(8,16,3,alpha=alpha,dtype=torch.float64);h=n.model.encode(x).detach().numpy();n.fit(DataLoader(TensorDataset(x,y),batch_size=8));w=density_ridge(h,y.numpy(),3,alpha);np.testing.assert_allclose(w,n.model.weight.detach(),rtol=1e-7,atol=1e-7);np.testing.assert_allclose(h@w.T,n(x).detach(),atol=1e-7)

def test_atomic_rejection_abstention():
    m=Prototype(2,4);x=np.ones((1,4),np.float32);assert m.predict(x)[0]==-1;m.update(x,[0]);assert m.predict(x)[0]==0;assert m.predict(np.zeros_like(x))[0]==-1;m.update(x,[1]);assert m.predict(x)[0]==-1;w=m.weights
    for bad in [np.full_like(x,np.nan),np.full_like(x,np.inf),x.astype('float64')]:
        with pytest.raises(ValueError):m.update(bad,[0])
    with pytest.raises(ValueError):m.update(x,[9])
    with pytest.raises(ValueError):m.update(x,[0],lr=float('nan'))
    np.testing.assert_array_equal(m.weights,w);assert m.updates==2

def test_native_dist_all_correct_fit_failure():
    torch.manual_seed(47);n=classifiers.DistHD(4,16,3,epochs=2,regen_freq=2,regen_rate=.25);x=torch.ones((8,4));y=torch.zeros(8,dtype=torch.long);h=n.encoder(x)[0];n.model.weight.data[0]=h;n.model.weight.data[1]=-h;n.model.weight.data[2]=-h
    assert n.regen_score(x,y)==0
    with pytest.raises(TypeError,match='topk.*Tensor.*int'):
        n.fit(DataLoader(TensorDataset(x,y),batch_size=4))


def test_native_cutoff_near_rank_deficiency():
    # Controlled singular spectrum; the smallest direction should be
    # discarded only in the native float32 relative-cutoff policy.
    x=np.array([[1,0,0],[-1,0,0],[0,1e-5,0],[0,-1e-5,0]],np.float32);y=np.array([0,1,0,1]);a=density_ridge(x,y,2,alpha=0,cutoff='native_rank');b=density_ridge(x,y,2,alpha=0,cutoff='full_rank');assert np.all(a[:,1]==0) and np.all(np.abs(b[:,1])>1e3)
    t=torchhd.functional.ridge_regression(torch.tensor(x),torch.nn.functional.one_hot(torch.tensor(y),2).float(),alpha=0);np.testing.assert_allclose(a,t,atol=1e-6)
    with pytest.raises(ValueError):density_ridge(x,y,2,cutoff='silent')
