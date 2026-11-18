import copy
import numpy as np
import pytest
from cognitum.research.hdc_cooperative_closeout import *

@pytest.mark.parametrize('d',[17,128])
@pytest.mark.parametrize('pairs',[False,True])
def test_record_stream_oracle(d,pairs):
    enc=RecordEncoder(5,d,8,11);x=np.array([0,.3,.6,.9,1.]);k=np.rint(x*7).astype(int)
    b=np.unpackbits(enc.ids^enc.bank[k],axis=1,count=d,bitorder='little')
    if pairs:b=np.concatenate([b,b[:-1]^np.roll(b[1:],1,axis=1)],axis=0)
    assert np.array_equal(enc.encode(x,pairs),packed_bits(b.sum(0)*2>=len(b)))
    assert enc.numeric_bytes==(5+8)*((d+7)//8)

def test_packed_search_exact_stochastic_reference():
    rng=np.random.default_rng(8);h=packed_bits(rng.integers(0,2,(8,19),dtype=np.uint8));y=np.repeat(np.arange(2),4);m=PackedSearch(h,y,19,3,2);before=m.p.copy();rr=copy.deepcopy(m.rng);q=h[1]
    p=np.unpackbits(before,axis=1,count=19,bitorder='little');v=np.unpackbits(q,count=19,bitorder='little');ids=np.flatnonzero(m.labels==0);d=np.sum(p[ids]!=v,axis=1);j=ids[d.argmin()];mask=rr.random(19)<.5*d.min()/19;p[j,mask]=v[mask]
    assert m.update(q,0,.5)==j
    assert np.array_equal(m.p,packed_bits(p));assert np.array_equal(m.p[m.labels==1],before[m.labels==1])
    assert m.numeric_bytes==m.p.nbytes+m.labels.nbytes

def test_packed_zero_alpha_and_padding():
    h=np.array([[1,0],[4,0],[5,1],[6,1]],np.uint8);m=PackedSearch(h,[0,0,1,1],9,2,3);old=m.p.copy();m.update(h[0],0,0);assert np.array_equal(old,m.p)
    with pytest.raises(ValueError):m.update(np.array([0,128],np.uint8),0,.5)

def test_seeded_search_reproducible():
    e=RecordEncoder(3,37,4,9);x=np.random.default_rng(1).random((20,3));y=np.repeat([0,1],10);h=e.batch(x);a=PackedSearch(h,y,37,4,3).fit(h,y);b=PackedSearch(h,y,37,4,3).fit(h,y);assert np.array_equal(a.p,b.p)
    oracle=a.labels[np.argmin(np.sum(np.unpackbits(h,axis=1,count=37,bitorder='little')[:,None]!=np.unpackbits(a.p,axis=1,count=37,bitorder='little')[None,:],axis=-1),axis=1)];assert np.array_equal(a.predict(h),oracle)

class MockEncoder:
    numeric_bytes=1
    def __init__(self):self.n=0
    def encode(self,x,pairs=False):self.n+=1;return x
class MockHead:
    numeric_bytes=2
    def __init__(self,decision):self.f=decision
    def decision(self,x):return self.f(x)

def test_lazy_route_only_uncertain():
    a,b=MockEncoder(),MockEncoder();h=LazyCascade(a,b,MockHead(lambda x:(0,x)),MockHead(lambda x:(1,1)),.5);assert h.predict([.2,.5,.7,.1]).tolist()==[1,0,0,1];assert a.n==4 and b.n==h.fine_calls==2;assert h.numeric_bytes==6

@pytest.mark.parametrize('packed',[False,True])
def test_frame_roundtrip(packed):
    u=np.array([[1.,-2.,3.],[-4.,5.,0.]],np.float32);f=encode_frame(u,10,packed);v,n=decode_frame(f,u.shape,packed);assert n==10
    if packed:assert len(f)==HEADER.size+1;assert np.allclose(v,np.sign(np.where(u==0,1,u))*abs(u).mean())
    else:assert len(f)==HEADER.size+u.nbytes;assert np.array_equal(u,v)
    with pytest.raises(ValueError):decode_frame(f+b'\x00',u.shape,packed)
    with pytest.raises(ValueError):decode_frame(f,(10,),packed)

def test_frame_padding_and_nonfinite():
    f=encode_frame(np.ones(9),1,True);bad=f[:-1]+bytes([255]);
    with pytest.raises(ValueError):decode_frame(bad,(9,),True)
    with pytest.raises(ValueError):encode_frame([np.inf],1,False)

@pytest.mark.parametrize('kind,d',[('tabular',64),('seeded',128),('bound',64),('fourier',128)])
def test_grid_q_terminal(kind,d):
    m=GridQ(15,kind,d,42);m.w[:]=.1;before=m.q(0).copy();err=m.update(0,1,2,1,True);assert np.isclose(err,2-before[1]);assert m.numeric_bytes<=4096;assert np.isclose(m.q(0)[1],before[1]+.18*err,atol=1e-6)

def test_softmax_and_hdc_local_updates_nonmutating():
    x=np.eye(3,dtype=np.float32);y=np.arange(3);w=np.zeros((3,3),np.float32)
    for f in (softmax_update,hdc_local_update):
        u=f(x,y,w);assert u.dtype==np.float32;assert np.all(w==0);assert (u@x.T).argmax(0).tolist()==[0,1,2]
