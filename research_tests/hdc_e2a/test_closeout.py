import numpy as np
import pytest
from cognitum.research.hdc_learning_closeout import FloatWindow,DriftPrototype,refine_stabilized

def test_float_window_distance_and_balance():
    e=FloatWindow(np.ones((1,8),np.float32));z=e.encode(np.array([[0],[.25],[.5],[1]],np.float32));assert np.all(z.sum(1)==0);assert np.array_equal(z[0],-z[-1]);assert np.array_equal((z!=z[0]).sum(1),[0,2,4,8]);assert np.all(np.linalg.norm(z,axis=1)>0)

def test_float_key_binding():
    keys=np.array([[1,-1,1,-1],[1,1,-1,-1]],np.float32);e=FloatWindow(keys);assert np.array_equal(e.encode(np.array([[0,1]],np.float32))[0],(keys[0]-keys[1])*[1,1,-1,-1])

@pytest.mark.parametrize('x',[[-.1],[1.1],[np.nan]])
def test_float_invalid(x):
    with pytest.raises(ValueError):FloatWindow(np.ones((1,8),np.float32)).encode(np.array([x],np.float32))

def test_drift_prequential_and_recovery():
    a=np.array([[1,0],[0,1]],np.float32);m=DriftPrototype(2,2,.9);assert (m.predict(a)==-1).all();m.update(np.tile(a,(20,1)),np.tile([0,1],20));assert np.array_equal(m.predict(a),[0,1]);m.update(np.tile(a,(20,1)),np.tile([1,0],20));assert np.array_equal(m.predict(a),[1,0])

def test_drift_atomic_and_bytes():
    m=DriftPrototype(2,2);a=m.w.copy();x=np.array([[1,0],[0,0]],np.float32)
    with pytest.raises(ValueError):m.update(x,[0,1])
    assert np.array_equal(m.w,a) and m.w.nbytes==16

def test_stability_separates_reversed_update():
    w=np.array([[1,0],[.8,.6],[0,1]],np.float32);h=np.array([[1,0]],np.float32);out,s,n,k=refine_stabilized(w,h,1,0.,0,threshold='true');assert np.array_equal(out,w) and np.isclose(s,.8) and n==1 and k=='error'

def test_paper_multiplicative_overflow_is_not_silently_stabilized():
    from cognitum.research.hdc_advanced_learning import refine_step
    w=np.array([[1e37,1e37],[0,-1e37]],np.float32);h=np.array([[1000,0]],np.float32);old=w.copy()
    with np.errstate(over='raise',invalid='raise'):
        with pytest.raises((FloatingPointError,ValueError)):refine_step(w,h,0,.9,1,correct_rule='literal')
    assert np.array_equal(w,old)
    out,*_=refine_stabilized(w,h,0,.9,1);assert np.isfinite(out).all()
