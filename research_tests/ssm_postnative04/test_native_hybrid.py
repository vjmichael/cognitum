"""Actual integrated Cognitum KAN/HDC/SSM checks; require full repository."""
from pathlib import Path
import numpy as np
import pytest
from cognitum.research import ssm_multisite as m
from cognitum.research import ssm_observed_dynamics as prior
from cognitum.research.kan_trainable import load_snapshot
from cognitum.research.hdc_algebra import Spec
from cognitum.research.hdc_associative import Cleanup

ROOT=Path(__file__).parent/'data'
PREV=Path(__file__).parent.parent/'ssm_postnative03/data'

def load(site):
    if site=='building':return prior.ingest('uci374',(PREV/'uci374.csv').read_bytes(),(PREV/'sources.json').read_bytes())
    return m.ingest_site(site,(ROOT/(site+'.csv')).read_bytes(),(ROOT/'sources.json').read_bytes())

@pytest.mark.parametrize('site',['Changping','Dingling','Guanyuan','building'])
def test_independent_observed_domain_integrated_multistep(site):
    r=m.evaluate(load(site),include_hybrid=True)
    assert set(['HDC_KAN_SSM','SSM_KAN_without_HDC','SSM_HDC_without_KAN']).issubset(r['models'])
    assert r['hybrid_stats']['origin_count']==r['test_origins'] and not r['hybrid_stats']['reused_future_forcing']
    assert not r['hybrid_stats']['teacher_forced'] and not r['execution_authorized']
    assert r['kan_snapshot_sha256'] and len(r['kan_snapshot_sha256'])==64
    for h in r['horizons']:
        for name in ('HDC_KAN_SSM','SSM_KAN_without_HDC','SSM_HDC_without_KAN','persistence','direct_ridge'):
            values=r['models'][name][str(h)];assert np.isfinite(values['rmse']) and np.isfinite(values['mae'])
        c=r['intervals'][str(h)];assert 0<=c['simultaneous_block_coverage_empirical']<=1
        assert c['calibration_blocks']>=20
        assert not r['distribution_free_dependent_coverage_claim']

@pytest.mark.parametrize('site',['Changping','Dingling'])
def test_fitted_kan_and_hdc_ablation_is_real(site):
    s=load(site);train,cal,test=m.partitions(s,24,24)
    model=m.causal_model(s,train)
    raw,pin=model['network'].research_snapshot();loaded=load_snapshot(raw,pin)
    np.testing.assert_allclose(loaded.evaluate(np.full((1,3),.5))[0],model['network'].evaluate(np.full((1,3),.5))[0],atol=1e-12)
    p,stats=m.hybrid_forecast(model,s,test[:40],24)
    q,_=m.hybrid_forecast(model,s,test[:40],24,enable_hdc=False)
    z,_=m.hybrid_forecast(model,s,test[:40],24,enable_kan=False)
    assert p.shape==q.shape==z.shape==(24,40) and stats['origin_count']==40
    # Ablation methods retain identical origins and source/model identities; no guarantee of gain.
    assert np.isfinite(p).all() and np.isfinite(q).all() and np.isfinite(z).all()
    assert len(model['snapshot_sha'])==64 and model['train_n']>3000


def test_duplicate_hdc_prototypes_abstain():
    spec=Spec('MAP',256);q=np.ones(256,dtype=np.float32)
    bank=Cleanup(spec,np.stack((q,q)))
    assert bank.propose(q,minimum=0,margin=.01) is None
