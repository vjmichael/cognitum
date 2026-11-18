import hashlib
import json
from pathlib import Path
import numpy as np
import pytest
from tools.cog03e2g_cifar import rgb,split,compare,verify_asset,RawBank,nearest_threshold,RGBMobileNet


def test_split_no_leakage():
    y=np.repeat(range(10),12);t=np.repeat(range(10),8);i,c,j,p=split(y,t,7,5,3)
    assert len(i)==len(j)==50 and len(c)==6 and not set(i)&set(c) and set(y[c])==set(p[0]) and len(np.unique(np.concatenate(p)))==10

def test_split_replay():
    y=np.repeat(range(10),12);a=split(y,y,5,4,3);b=split(y,y,5,4,3)
    assert all(np.array_equal(x,z) for x,z in zip(a[:3],b[:3]))

def test_rgb_layout():
    a=np.zeros((2,3,32,32),np.uint8);a[:,0]=225;assert np.array_equal(rgb(a),a)
    with pytest.raises(ValueError):rgb(a.transpose(0,2,3,1))
    with pytest.raises(ValueError):rgb(a.astype(float))

def test_exact_asset(tmp_path):
    p=tmp_path/'file';p.write_bytes(b'correct');h=hashlib.sha256(b'correct').hexdigest();assert verify_asset(p,h,100)==h
    p.write_bytes(b'mutated')
    with pytest.raises(ValueError):verify_asset(p,h,100)

def test_checkpoint_reject_before_import(tmp_path):
    p=tmp_path/'fake';p.write_bytes(b'wrong')
    with pytest.raises(ValueError):RGBMobileNet(p,'ptq',None)

def test_centroid_numeric():
    a=RawBank(2,1,0,True);a.observe(np.array([0,2],np.uint8));a.observe(np.array([4,6],np.uint8));assert a.n==1 and np.allclose(a.a[0],[2,4]);assert a.numeric_bytes==16

def test_threshold():
    a=np.array([[0,0],[1,1],[3,3]],np.uint8);assert nearest_threshold(a)==pytest.approx(3.4)

def test_budget_and_phases():
    rng=np.random.default_rng(10);y=np.repeat(range(10),3);x=rng.random((30,64));c=rng.random((4,64));p=np.array_split(np.arange(10),5);rows=compare(x,y,x,y,c,p,3,32768,64,'fixture')
    assert len(rows)==5 and all(r['numeric_bytes']<=32768 and r['phases'][-1]['n']==30 for r in rows)
