import numpy as np
import pytest
import torch
from torchhd import classifiers
from torch.utils.data import DataLoader,TensorDataset
from cognitum.research.hdc_compressed_learning import PackedTernary,PackedLevels,fold,prune,SparseRows,quant_train,lehdc_train
from cognitum.research.hdc_learning import cosine_scores

@pytest.mark.parametrize('d',[7,8,31,128])
def test_pack(d):
    r=np.random.default_rng(d);a=r.integers(-1,2,(9,d),dtype=np.int8);x=r.integers(-1,2,(11,d),dtype=np.int8);b=PackedTernary(a);q=PackedTernary(x);assert np.array_equal(a,b.decode());assert np.array_equal(b.scores(q),x.astype('int32')@a.astype('int32').T);assert b.bytes==2*len(a)*((d+7)//8)
    with pytest.raises(ValueError):b.planes()[0][0,0]=0

@pytest.mark.parametrize('cls',[classifiers.CompHD,classifiers.SparseHD,classifiers.QuantHD,classifiers.LeHDC])
def test_native_encoding(cls):
    torch.manual_seed(12);m=cls(8,64,3,n_levels=16,min_level=0,max_level=1);keys=getattr(m,'feat_keys',None) or m.keys;x=torch.rand(12,8);e=PackedLevels(keys.weight.detach().numpy(),m.levels.weight.detach().numpy());assert np.array_equal(e.encode(x.numpy()),m.encoder(x).detach().numpy());assert e.bytes==192

def test_native_fold():
    m=classifiers.CompHD(5,64,3,chunks=4);a=torch.randint(-9,10,(7,64)).float();assert np.array_equal(fold(a.numpy(),m.chunk_keys.numpy()),m.compress(a).numpy())

@pytest.mark.parametrize('s',[0,.25,.75,1])
@pytest.mark.parametrize('mode',['dimension','class'])
def test_sparse_exact(s,mode):
    w=(np.arange(48,dtype=np.float32).reshape(3,16)+1)**2;x=np.random.default_rng(18).normal(size=(8,16)).astype('float32');p=prune(w,s,mode);assert np.all((p==0).sum(1)==round(s*16));np.testing.assert_allclose(SparseRows(p).scores(x),cosine_scores(x,p),atol=1e-12)

def test_native_sparse_defects():
    w=torch.arange(1,49).reshape(3,16).float()**2
    for mode in ['dimension','class']:
        m=classifiers.SparseHD(8,16,3,sparsity=.25,sparsity_type=mode);m.model.weight.data.copy_(w);m.sparsify();assert (m.model.weight==0).sum().item()==(36 if mode=='dimension' else 0)
        assert (prune(w.numpy(),.25,mode)==0).sum()==12

@pytest.mark.parametrize('cls,trainer',[ (classifiers.QuantHD,quant_train),(classifiers.LeHDC,lehdc_train)])
def test_native_training(cls,trainer):
    torch.manual_seed(19);torch.set_num_threads(1);kw={'dropout_rate':0.} if cls is classifiers.LeHDC else {'lr':.035};m=cls(8,64,3,n_levels=16,min_level=0,max_level=1,epochs=4,**kw);x=torch.rand(48,8);y=torch.arange(48)%3;h=m.encoder(x).detach().numpy();data=DataLoader(TensorDataset(x,y),batch_size=8,shuffle=False);m.fit(data);m.eval();c,w=trainer(h,y.numpy(),3,epochs=4,batch=8,**({'lr':.035} if cls is classifiers.QuantHD else {}));native=m.model.weight.detach().numpy();np.testing.assert_array_equal(w,native);np.testing.assert_array_equal(PackedTernary(w).scores(PackedTernary(h)),m(x).detach().numpy())

@pytest.mark.parametrize('bad',[np.array([[2.]]),np.array([[np.nan]]),np.zeros((0,1))])
def test_reject(bad):
    with pytest.raises(ValueError):PackedTernary(bad)

@pytest.mark.parametrize('mode',['dimension','class'])
def test_sparse_train(mode):
    from cognitum.research.hdc_compressed_learning import sparse_train
    r=np.random.default_rng(5);x=r.integers(-1,2,(60,32)).astype('float32');y=np.repeat(np.arange(3),20);a=sparse_train(x,y,3,sparsity=.75,mode=mode);b=sparse_train(x,y,3,sparsity=.75,mode=mode);assert np.array_equal(a,b) and np.all((a==0).sum(1)>=24)
    np.testing.assert_allclose(SparseRows(a).scores(x),cosine_scores(x,a),atol=1e-12)

@pytest.mark.parametrize('d',[7,16,37])
def test_packed_fold(d):
    from cognitum.research.hdc_compressed_learning import PackedFold
    r=np.random.default_rng(21);a=r.integers(-30,31,(12,d*4),dtype=np.int16);k=r.choice([-1,1],(4,d));p=PackedFold(k);assert np.array_equal(p.fold(a),fold(a,k));assert p.bytes==4*((d+7)//8)
