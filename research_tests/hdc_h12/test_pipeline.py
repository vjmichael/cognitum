import numpy as np
import pytest
from tools.h12.pipeline import pack_generated,fit,head,predict,compare
from cognitum.research.hdc_hardware import pack, scores
from tools.cog03f_dispatch_pilot import build
from threadpoolctl import threadpool_limits

@pytest.mark.parametrize('d',[1,7,63,64,65,256,1024,4097,10000,65536])
def test_generated_pack_exact(d):
    x=np.random.default_rng(d).integers(0,2,(3,d),dtype=np.uint8).astype(bool)
    a=pack_generated(x);b=pack(x.astype(np.uint8));np.testing.assert_array_equal(a,b)
    assert a.dtype==np.dtype('<u8') and a.shape==(3,(d+63)//64)

@pytest.mark.parametrize('x',[np.zeros((1,8),np.uint8),np.zeros((0,8),bool),np.zeros(8,bool),np.zeros((1,0),bool),np.zeros((1,65537),bool)])
def test_invalid_pack_contract(x):
    with pytest.raises(ValueError):pack_generated(x)

@pytest.mark.parametrize('d',[65,256,1024,4097])
def test_end_to_end_exact(tmp_path,d):
    rng=np.random.default_rng(d);x=rng.normal(size=(32,8)).astype(np.float32);y=np.arange(32)%4;t=x[:8];truth=y[:8]
    with threadpool_limits(limits=1):
        n,_=build(tmp_path);r,train=compare(x,t,y,truth,x,n,(d,),(1,8),'fixture',2)
        assert len(r)==6 and len(train)==1
        for b in (1,8):
            rows=[z for z in r if z['batch']==b];assert len({z['score_hash'] for z in rows})==len({z['prediction_hash'] for z in rows})==1
            for z in rows:assert z['score_parity'] and len(z['stages']['total']['samples_ns'])==2
        assert train[0]['head_bytes']['packed']==train[0]['head_bytes']['packed_generated']
