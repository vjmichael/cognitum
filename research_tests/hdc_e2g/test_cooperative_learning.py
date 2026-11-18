import numpy as np
import pytest
from cognitum.research.hdc_cooperative_learning import *

def test_terminal_q():
    q=OfflineQ(np.eye(3),2,alpha=1);q.w[0,1]=10
    assert q.update(0,0,2,1,True)==2 and q.q(0)[0]==2

def test_bootstrap():
    q=OfflineQ(np.eye(3),2,alpha=1,gamma=.5);q.w[1,1]=4
    assert q.update(0,0,1,1,False)==3

def test_factored():
    a=grid_features(4,128,1);assert a.shape==(16,128) and np.array_equal(a,grid_features(4,128,1));assert len(np.unique(a,axis=0))==16

def test_sufficient_stats():
    h=codebook(20,19,1);y=np.arange(20)%3
    assert np.array_equal(sums(h,y,3),sums(h[:8],y[:8],3)+sums(h[8:],y[8:],3))

def test_local_delta():
    h=np.eye(2);p=np.zeros((2,2));assert np.array_equal(local_update(h,np.array([0,1]),p),[[0,-.25],[0,.25]]) and not p.any()

def test_weighted():
    u=np.array([[[1.,2.]],[[3.,4.]]]);assert np.array_equal(aggregate(u,[1,3]),[[2.5,3.5]])

def test_robust():
    u=np.array([[[1.,1.]],[[1.,1.]],[[99.,-99.]]]);assert np.array_equal(aggregate(u,[1]*3,'median'),[[1,1]]) and np.array_equal(aggregate(u,[1]*3,'trimmed'),[[1,1]])

def test_clip():
    assert np.allclose(aggregate([[[3.,4.]]],[1],clip=1),[[.6,.8]])

@pytest.mark.parametrize('d',[1,8,9,257])
def test_wire(d):
    u=np.arange(d).reshape(1,d)-d/2;v,n=pack_update(u);assert n==(d+7)//8+4;assert np.allclose(v,np.where(u>=0,1,-1)*np.mean(abs(u)));assert np.array_equal(pack_update(u,1)[0],-v)

def test_pseudo_no_double_count():
    h=np.array([[1,1],[-1,-1]]);u=np.repeat(h,5,axis=0);p,ids,y=pseudo_train(h,np.arange(2),u,2,.1,10,2);assert len(ids)==len(set(ids))==10;assert np.array_equal(p,6*h)

def test_pseudo_abstain():
    h=np.array([[1,1],[-1,-1]]);p,i,y=pseudo_train(h,np.arange(2),np.array([[1,-1]]),2,.1);assert len(i)==0

def test_missing_class():
    h=np.array([[1,1]]);p,i,y=pseudo_train(h,np.array([0]),h,3);assert len(i)==0

def test_packed_oracle():
    p=codebook(7,37,1);h=codebook(13,37,2);assert np.array_equal(packed_predict(h,p,np.arange(7)),(h.astype(int)@p.astype(int).T).argmax(1))

def test_multi():
    h=codebook(16,32,2);y=np.arange(16)%4;p,l=multiprototype(h,y,4,2,3);assert p.shape==(8,32) and len(l)==8

@pytest.mark.parametrize('fn',[lambda:aggregate([[[1.]]],[0]),lambda:aggregate([[[1.]]],[1],'trimmed'),lambda:sums(np.ones((1,2)),np.array([3]),2),lambda:pack_update(np.array([np.nan]))])
def test_invalid(fn):
    with pytest.raises(ValueError):fn()

def test_stochastic_binary():
    h=codebook(8,32,1);y=np.arange(8)%2;p,l=multiprototype(h,y,2,1,1);q=stochastic_binary_train(h,y,p,l,2);assert np.array_equal(q,stochastic_binary_train(h,y,p,l,2));assert np.all(abs(q)==1);assert np.array_equal(p,stochastic_binary_train(h,y,p,l,2,alpha=0))

def test_task_binding():
    m=codebook(4,17,1).reshape(2,2,17);k=codebook(2,17,2);s=task_superpose(m,k);assert np.array_equal(task_recover(s,k[0]),m[0]+m[1]*k[0]*k[1]);assert np.array_equal(task_recover(task_superpose(m[:1],k[:1]),k[0]),m[0])

def test_cascade():
    a=np.array([[.9,.1],[.4,.5]]);b=np.array([[.1,.9],[.7,.3]]);p,r=cascade_predict(a,b,.2);assert p.tolist()==[0,0] and r.tolist()==[False,True]

def test_cluster():
    h=np.repeat(np.array([[1,-1],[-1,1]]),6,axis=0);p=binary_cluster(h,2,2);assert p.shape==(2,2) and np.all(abs(p)==1);assert np.array_equal(p,binary_cluster(h,2,2))
