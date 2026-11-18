import os, pathlib, subprocess, sys
import numpy as np
import pytest
from sklearn.linear_model import Ridge
from cognitum.research.hdc_regression import Encoder,Regression,split_conformal,mixture_reference,mixture_predict
from cognitum.research.hdlib_classical import load_classical

@pytest.mark.parametrize('kind',['reghd','rff'])
def test_encoder(kind):
    x=np.random.default_rng(2).normal(size=(8,3));e=Encoder(3,12,2,kind);assert np.array_equal(e.encode(x),Encoder(3,12,2,kind).encode(x));assert np.allclose(e.encode(x[:1]),e.encode(x)[:1]);assert x.nbytes>0
@pytest.mark.parametrize('n,d',[(20,5),(5,20)])
def test_ridge_primal_dual(n,d):
    rng=np.random.default_rng(3);h=rng.normal(size=(n,d));y=rng.normal(size=n);m=Regression('ridge',alpha=.4).fit(h,y);r=Ridge(alpha=.4,fit_intercept=False).fit(h,y-y.mean());assert np.allclose(m.w,r.coef_);assert np.allclose(m.predict(h),r.predict(h)+y.mean())
@pytest.mark.parametrize('kind',['associative','lms','ridge'])
def test_constant(kind):
    h=np.random.default_rng(1).normal(size=(20,8));m=Regression(kind).fit(h,np.full(20,3.));assert np.allclose(m.predict(h),3);assert m.nbytes>0
@pytest.mark.parametrize('kind',['associative','lms','ridge'])
def test_nonfinite(kind):
    h=np.ones((4,2));y=np.array([1.,2.,np.nan,4.]);with_error=Regression(kind)
    with pytest.raises(ValueError):with_error.fit(h,y)

def test_conformal_order_statistic():
    assert split_conformal(np.arange(10,dtype=float),np.zeros(10),.2)==8
    assert np.isinf(split_conformal(np.zeros(2),np.zeros(2),.1))

def test_online_lms_fits_orthogonal():
    h=np.eye(4);y=np.array([-2.,-1.,1.,2.]);m=Regression('lms',epochs=30).fit(h,y);assert np.max(abs(m.predict(h)-y))<1e-7

def test_mixture_update_oracle():
    h=np.array([[1.,-1.]]);y=np.array([2.]);init=np.array([[1.,-1.],[-1.,1.]]);c,w=mixture_reference(h,y,init,1,.1);q=np.exp([1.,-1.]);q/=q.sum();assert np.allclose(w,.2*q[:,None]*h);assert np.allclose(c[0],init[0]+(1-q[0])*h[0]);assert np.array_equal(c[1],init[1]);assert np.allclose(mixture_predict(h,c,w),.4*np.sum(q*q))

def test_bad_wheel(tmp_path):
    p=tmp_path/'fake.whl';p.write_bytes(b'fake')
    with pytest.raises(ValueError):load_classical(p)

def test_native_in_fresh_process():
    # No native model eager initializer, no quantum stubs; exact wheel execution.
    wheel=os.environ['COG03E2C_HDLIB_WHEEL'];code='''from tools.cog03e2c_pilot import run
import sys
r=run(sys.argv[1],True)
assert len(r['rows'])==8 and len(r['native_parity'])==1
assert max(r['native_parity'][0][k] for k in ('cluster_max_error','weight_max_error','max_prediction_error'))<1e-8
assert len(r['clustering'])==3 and len(r['graphs'])==1
assert not any(k.startswith('qiskit') for k in sys.modules)
''';subprocess.run([sys.executable,'-c',code,wheel],check=True,timeout=90)

def test_selection_matches_fisher_and_does_not_update_on_test():
    from cognitum.research.hdc_regression import FisherSelector
    from sklearn.feature_selection import f_classif
    x=np.random.default_rng(5).normal(size=(40,8));y=np.repeat([0,1],20);x[:,3]+=3*y
    m=FisherSelector(3).fit(x,y);q=f_classif(x,y)[0];assert np.array_equal(m.indices,np.argsort(-q)[:3]);initial=m.indices.copy();m.transform(x[:2]*1e5);assert np.array_equal(m.indices,initial)

def test_native_import_dependency_audit():
    import importlib.util
    if importlib.util.find_spec('qiskit') is not None:return # full dependency installations are separately qualified
    wheel=os.environ['COG03E2C_HDLIB_WHEEL'];p=subprocess.run([sys.executable,'-c','import sys;sys.path.insert(0,sys.argv[1]);import hdlib.model',wheel],capture_output=True,text=True);assert p.returncode!=0 and "No module named 'qiskit'" in p.stderr
