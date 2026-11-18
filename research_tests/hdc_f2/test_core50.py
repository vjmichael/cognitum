import numpy as np
import pytest
from PIL import Image
from tools.cog03f2_core50 import NAME, crop_box, pack, predict_packed, evaluate

def test_session_identity():
    assert NAME.fullmatch('test/img/C_10_01_103.png').groups()==('test','C','10','01','103')
    assert not NAME.fullmatch('../test/img/C_10_01_103.png')

def test_inclusive_crop():
    a=Image.new('RGB',(350,350),(255,0,0));b=np.asarray(crop_box(a,(-1,-1,126,126)))
    assert b.shape==(128,128,3) and list(b[0,0])==[0,0,0] and list(b[1,1])==[255,0,0]

def test_bad_crop():
    with pytest.raises(ValueError):crop_box(Image.new('RGB',(350,350)),(0,0,126,128))

def test_bit_order_and_parity():
    rng=np.random.default_rng(92);q=rng.choice([-1,1],(5,256));p=rng.choice([-1,1],(4,256));assert np.array_equal(predict_packed(pack(q),pack(p)),(q@p.T).argmax(1))

def test_seen_coverage():
    x=np.array([[0.,0.],[.1,0.],[1.,1.],[.9,1.]],np.float32);y=np.array([1,1,2,2]);g=np.array([1,1,2,2]);r=evaluate(x,y,g,x,y,3,'fixture',256)
    assert r[0]['covered_n']==2 and r[-1]['covered_n']==4 and r[-1]['seen_classes']==2

def test_exact_repeat():
    x=np.array([[0.,0.],[.1,0.],[1.,1.],[.9,1.]],np.float32);y=np.array([1,1,2,2]);g=np.array([1,1,2,2]);assert evaluate(x,y,g,x,y,3,'fixture',512)==evaluate(x,y,g,x,y,3,'fixture',512)
