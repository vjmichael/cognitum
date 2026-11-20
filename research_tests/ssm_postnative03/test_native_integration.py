"""Requires real KAN/HDC/SSM Cognitum modules; do not replace with stubs."""
from pathlib import Path
import numpy as np
import pytest
from cognitum.research import ssm_observed_dynamics as m
from cognitum.research.kan_trainable import load_snapshot
from cognitum.research.hdc_algebra import Spec
from cognitum.research.hdc_associative import Cleanup

ROOT=Path(__file__).parent/'data'
MANIFEST=(ROOT/'sources.json').read_bytes()

def data(n):return (ROOT/(n+'.csv')).read_bytes()

@pytest.mark.parametrize('name',['uci374','uci501'])
def test_real_hdc_kan_ssm_heldout_hypothesis(name):
    out=m.experiment(name,data(name),MANIFEST,True);v=out['metrics']
    assert out['integrated'] and out['kan_snapshot_sha256'] and len(out['kan_snapshot_sha256'])==64
    assert v['hdc_accepted']+v['hdc_abstained']==out['test_size']
    assert v['domain_ood_count']>=0
    assert np.isfinite([v['kan_rmse'],v['integrated_rmse'],v['coverage_90']]).all()
    assert not out['verified_physical_law'] and not out['execution_authorized']
    # Falsification is allowed, never force a trained model to beat persistence.
    assert v['wrong_sign_rmse']>=v['persistence_rmse']

@pytest.mark.parametrize('name',['uci374','uci501'])
def test_fitted_genuine_kan_gradient_against_finite_difference(name):
    s=m.ingest(name,data(name),MANIFEST);train,_,_=m.split(s)
    D,delta,_,sd=m.design(s,train);c=m.learn_ssm(D,delta,train)
    x,ok=m.normalized(s,train);model,pin=m.kan_fit(x,(s['state'][1:]-(s['state'][:-1]+sd[0]*(D[:-1]@c)))/sd[0],train)
    raw,expected=model.research_snapshot();assert expected==pin
    again=load_snapshot(raw,expected)
    p=np.full((1,3),.5);v,j=again.evaluate(p,order=1);step=1e-6
    for k in range(3):
        d=np.eye(3)[k:k+1]*step
        fd=(again.evaluate(p+d)[0]-again.evaluate(p-d)[0])/(2*step)
        np.testing.assert_allclose(fd,j[:,:,k],atol=1e-7)

def test_hdc_ambiguous_candidate_abstains_not_factual_claim():
    s=Spec('MAP',256);q=np.ones(256,dtype=np.float32)
    bank=Cleanup(s,np.stack((q,q)));assert bank.propose(q,minimum=0,margin=.01) is None

def test_actual_kan_refuses_outside_training_domain():
    from cognitum.research.kan_trainable import Layer,Network
    l=Layer('chebyshev',2,np.tile([0.,1.],(3,1)),np.zeros((1,3,3)),np.ones((1,3)),np.zeros(1))
    with pytest.raises(ValueError,match='outside layer domain'):
        Network((l,)).evaluate(np.array([[.2,.4,1.1]]))
