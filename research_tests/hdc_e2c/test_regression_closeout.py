import os,sys,subprocess,json
from pathlib import Path
import numpy as np
import pytest
from sklearn.linear_model import Ridge
from cognitum.research.hdc_regression_closeout import ScaledEncoder,StreamingRidge,PackedRegHD

@pytest.mark.parametrize('dim',[1,7,9,65])
def test_packed_exact_and_padding(dim):
    rng=np.random.default_rng(44);c=rng.normal(size=(3,dim));w=rng.normal(size=c.shape);h=rng.normal(size=(12,dim));m=PackedRegHD(c,w)
    b=np.where(h>=0,1,-1);s=b@np.where(c>=0,1,-1).T/dim;q=np.exp(s-s.max(1,keepdims=True));q/=q.sum(1,keepdims=True);assert np.allclose(m.predict(h),np.sum(q*(b@np.where(w>=0,1,-1).T),axis=1));assert m.c.nbytes==3*((dim+7)//8)

def test_packed_calibration():
    rng=np.random.default_rng(1);c=rng.normal(size=(3,17));w=rng.normal(size=c.shape);h=rng.normal(size=(120,17));m=PackedRegHD(c,w);a=m._components(h);y=a@np.array([.3,-.5,.7])+2;m.calibrate(h,y,alpha=1e-8);assert np.max(np.abs(m.predict(h)-y))<1e-6

@pytest.mark.parametrize('kind',['reghd','rff'])
def test_streaming_ridge_exact(kind):
    rng=np.random.default_rng(3);x=rng.normal(size=(40,3));y=x[:,1]+2*x[:,0];e=ScaledEncoder(3,12,11,kind,.5);m=StreamingRidge(e,.3,8192).fit(x,y);r=Ridge(alpha=.3).fit(e.encode(x),y);assert np.allclose(m.predict(x),r.predict(e.encode(x)));assert m.numeric_bound<=8192

def test_budget_and_invalid_settings():
    with pytest.raises(ValueError):StreamingRidge(ScaledEncoder(3,64),1,8192)
    with pytest.raises(ValueError):ScaledEncoder(3,12,scale=0)
    with pytest.raises(ValueError):PackedRegHD(np.ones((1,3)),np.ones((2,3)))

def test_native_quantized_and_budget_subprocess(tmp_path):
    p=tmp_path/'close.json';subprocess.run([sys.executable,'-m','tools.cog03e2c_closeout','--wheel',os.environ['COG03E2C_HDLIB_WHEEL'],'--out',str(p),'--quick'],check=True,timeout=120);r=json.loads(p.read_text());assert len(r['rows'])==8;assert len(r['quantized_parity'])==1 and r['quantized_parity'][0]['max_error']<1e-8;assert all(a['explicit_training_bound_bytes']<=a['budget'] for a in r['rows'] if a['budget'])

def test_classification_and_stepwise_spawn(tmp_path):
    p=tmp_path/'class.json';subprocess.run([sys.executable,'-m','tools.cog03e2c_classification','--wheel',os.environ['COG03E2C_HDLIB_WHEEL'],'--out',str(p),'--quick','--stepwise'],check=True,timeout=120);r=json.loads(p.read_text());assert len(r['rows'])==1 and r['rows'][0]['oracle_disagreements']==0 and r['rows'][0]['fit_train_only'];assert r['native_stepwise']['models']>0 and r['native_stepwise']['outer_test_excluded'] and r['native_stepwise']['start_method']=='spawn';assert not r['quantum_imported']
