import numpy as np
import pytest
from cognitum.research.hdc_visual_closeout import *

def test_subject_split():
    a,b,c=group_partition(np.arange(21),np.arange(21,30),3)
    assert len(a)==11 and len(b)==10 and len(c)==9 and not set(a)&set(b)
    with pytest.raises(ValueError):group_partition(np.arange(21),[20],3)

def test_imu_shape_and_replay():
    x=np.random.default_rng(3).normal(size=(4,128,9));e=IMUEncoder(32,3).fit(x)
    a=e.encode(x);assert a.shape==(4,15,32) and np.isin(a,[-1,1]).all();np.testing.assert_array_equal(a,e.encode(x))

def test_perturb_does_not_mutate():
    x=np.ones((2,128,9));a=perturb(x,'gain');assert np.allclose(a,1.35) and np.all(x==1)
    with pytest.raises(ValueError):perturb(x,'bogus')

def test_robust_envelope():
    a=np.zeros((2,20,2));a[1,:,0]=.8;y=np.zeros(20,int);g=np.arange(20)
    m=robust_calibration(a,y,g);assert m.cutoffs[0]==.8 and m.predict([[.8,2]])[0,0]

def test_quantizer_train_only():
    x=np.array([[0.,0,9],[1,10,9],[2,20,9]]);q=FeatureQuantizer().fit(x,2)
    assert q.indices.tolist()==[1,0] and q.numeric_bytes==24
    assert q.transform([[999,-999,9]]).tolist()==[[0,15]]
    assert q.lo.tolist()==[0,0]

def test_mobile_no_fallback(tmp_path):
    with pytest.raises(ValueError):FrozenMobileNet()
    p=tmp_path/'bad.pth';p.write_bytes(b'not weights')
    with pytest.raises(ValueError):FrozenMobileNet(p)

def test_feature_width_and_nonfinite():
    q=FeatureQuantizer().fit([[1,2],[3,4]],2)
    with pytest.raises(ValueError):q.transform([[1,2,3]])
    with pytest.raises(ValueError):q.transform([[1,np.nan]])
