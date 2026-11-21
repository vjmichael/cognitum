"""Independent site-identity, chronological multi-horizon and uncertainty controls."""
from pathlib import Path
import csv
from io import StringIO
import json
import numpy as np
import pytest
from cognitum.research import ssm_multisite as m
from cognitum.research import ssm_observed_dynamics as prior

HERE=Path(__file__).parent/'data'
PRIOR=Path(__file__).parent.parent/'ssm_postnative03'/'data'
MANIFEST=(HERE/'sources.json').read_bytes()

def site(name):return m.ingest_site(name,(HERE/(name+'.csv')).read_bytes(),MANIFEST)

def older(name):return prior.ingest(name,(PRIOR/(name+'.csv')).read_bytes(),(PRIOR/'sources.json').read_bytes())

@pytest.mark.parametrize('name,missing',[('Changping',33),('Dingling',133),('Guanyuan',100)])
def test_site_source_authenticity_and_no_imputation(name,missing):
    s=site(name);assert s['site']==name and len(s['times'])==6144 and s['missing_target']==missing and s['target_unit']=='ug/m3'
    assert s['interval_seconds']==3600 and s['attribution'].startswith('Song Chen')
    assert np.isfinite(s['state']).sum()==6144-missing and np.isfinite(s['forcing']).all()
    assert s['archive_sha256']==m.BEIJING_ARCHIVE

@pytest.mark.parametrize('name',m.SITES)
def test_site_byte_mutation_and_cross_site_swap_rejected(name):
    orig=bytearray((HERE/(name+'.csv')).read_bytes());orig[100]=orig[100]^1
    with pytest.raises(ValueError,match='digest'):m.ingest_site(name,bytes(orig),MANIFEST)
    different=next(x for x in m.SITES if x!=name)
    with pytest.raises(ValueError,match='digest'):m.ingest_site(name,(HERE/(different+'.csv')).read_bytes(),MANIFEST)

@pytest.mark.parametrize('name',m.SITES)
def test_manifest_and_time_order_refusals(name):
    raw=(HERE/(name+'.csv')).read_bytes()
    bad=MANIFEST.replace(b'CC BY 4.0',b'unknown..')
    with pytest.raises(ValueError,match='manifest hash'):m.ingest_site(name,raw,bad)
    lines=raw.decode().splitlines(keepends=True);lines[1],lines[2]=lines[2],lines[1]
    with pytest.raises(ValueError,match='digest'):m.ingest_site(name,''.join(lines).encode(),MANIFEST)

@pytest.mark.parametrize('site_name',m.SITES)
def test_horizon_partitions_do_not_cross_boundaries(site_name):
    s=site(site_name);cfg=m.specs(s);train,cal,test=m.partitions(s,cfg['period'],max(cfg['horizons']))
    assert train[0]>=23 and train[-1]+24<cal[0] and cal[-1]+24<test[0] and test[-1]+24<6144
    assert len(train)>3000 and len(cal)>1000 and len(test)>1000
    assert len(set(train)&set(cal))==0 and len(set(cal)&set(test))==0

@pytest.mark.parametrize('name',m.SITES)
def test_causal_feature_train_only_and_future_perturbation(name):
    s=site(name);cfg=m.specs(s);train,_,test=m.partitions(s,24,24)
    a=m.direct_fit(s['state'],train,24,cfg['horizons']);pred=m.direct_forecast(a,s['state'],test[:40],cfg['horizons'])
    z=s['state'].copy();z[test[38]+1:]+=200
    b=m.direct_fit(z,train,24,cfg['horizons']);new=m.direct_forecast(b,z,test[:38],cfg['horizons'])
    for k in pred:np.testing.assert_allclose(pred[k][:38],new[k],rtol=0,atol=1e-12)
    for k in a['weights']:np.testing.assert_array_equal(a['weights'][k],b['weights'][k])

@pytest.mark.parametrize('name',m.SITES)
def test_genuine_multistep_hypotheses_and_falsification(name):
    r=m.evaluate(site(name),include_hybrid=False)
    assert r['horizons']==(1,6,24) and r['unit']=='ug/m3'
    assert r['source_sha256']==json.loads(MANIFEST)['entries'][m.SITES.index(name)]['excerpt_sha256']
    assert r['train_origins']>3000 and r['test_origins']>1000
    assert len(r['models'])==6 and set(r['models'])=={'persistence','seasonal_naive','ridge_AR24','daily_relaxation','wind_dilution','direct_ridge'}
    for h in ('1','6','24'):
        for metrics in r['models'].values():
            assert np.isfinite(metrics[h]['rmse']) and 0<metrics[h]['rmse']<1e6 and metrics[h]['mae']>0
        c=r['intervals'][h];assert 0<=c['coverage_empirical']<=1 and 0<=c['simultaneous_block_coverage_empirical']<=1
        assert c['block_max_radius']>=c['iid_radius']*0.75
        assert c['calibration_blocks']>=20
        assert c['shift_plus_3radius_coverage']<c['coverage_empirical']
        assert len(r['falsification'][h]['bootstrap_persistence_mae_gains_95'])==5
    assert r['future_forcing_or_target_used_in_forecast'] is False and not r['physical_law_discovered'] and not r['execution_authorized']

@pytest.mark.parametrize('name',['uci374','uci501'])
def test_original_independent_domains_multi_horizon(name):
    s=older(name);r=m.evaluate(s,include_hybrid=False)
    assert r['horizons']==((1,6,12) if name=='uci374' else (1,6,24))
    assert r['test_origins']>1000 and not r['distribution_free_dependent_coverage_claim']

@pytest.mark.parametrize('name',m.SITES)
def test_deterministic_replay_name_and_sha(name):
    a=m.evaluate(site(name),False);b=m.evaluate(site(name),False)
    assert a==b and a['source_sha256']==b['source_sha256']

@pytest.mark.parametrize('source,target',[('Changping','Dingling'),('Changping','Guanyuan'),('Dingling','Guanyuan')])
def test_zero_shot_site_transfer_with_site_holdout(source,target):
    a=m.cross_site_transfer(site(source),site(target));assert a['test_origins']>1000
    assert a['donor']!=a['recipient'] and a['donor_sha256']!=a['recipient_sha256']
    for h in ('1','6','24'):
        assert np.isfinite(a['zero_shot_direct'][h]['rmse'])
        assert np.isfinite(a['persistence'][h]['rmse'])
    assert not a['execution_authorized']


def test_block_conformal_is_more_cautious_on_spikes():
    r=np.zeros(1200);r[::24]=3.0;r[23::24]=1.5
    radius,blocks=m.block_radius(r,24);assert blocks==50 and radius==3
    iid=m.rank_radius(np.abs(r));assert iid==0
    assert radius>iid
    with pytest.raises(ValueError,match='block calibration budget'):m.block_radius(r[:100],24)


def test_moving_block_bootstrap_preserves_determinism_and_shift_direction():
    p=np.full(1200,2.0);q=np.full(1200,1.0)
    assert m.block_bootstrap_gain(p,q,24)==pytest.approx((1.,1.))
    assert m.block_bootstrap_gain(p,q,24)==m.block_bootstrap_gain(p,q,24)
    assert m.block_bootstrap_gain(q,p,24)==pytest.approx((-1.,-1.))


def test_no_future_forcing_or_targets_in_AR_rollout():
    y=np.arange(0,6000,dtype=float)*.01+np.sin(np.arange(6000)/13.)
    t=np.arange(200,400);fit=m.ar_fit(y,np.arange(23,170))
    a=m.ar_forecast(fit,y,t,24)
    z=y.copy();z[400:]+=1e5
    np.testing.assert_array_equal(a,m.ar_forecast(fit,z,t,24))
    assert a.shape==(24,len(t))


def test_pollution_cannot_transfer_to_temperature_as_same_target():
    with pytest.raises(ValueError,match='cross-site target-domain'):
        m.cross_site_transfer(site('Changping'),older('uci501'))


def test_block_methods_do_not_compress_missing_time_indices():
    ids=np.r_[np.arange(0,480),np.arange(520,1000)]
    errors=np.ones(len(ids));errors[:480:24]=3;errors[480::24]=2
    blocks=m.contiguous_blocks(errors,ids,24)
    assert blocks.shape==(40,24)
    assert m.block_radius(errors,24,origins=ids)[1]==40
    assert m.block_bootstrap_gain(errors,errors*.5,24,origins=ids)==pytest.approx((.5104,.5104),abs=.1)
    with pytest.raises(ValueError,match='chronological blocks'):
        m.contiguous_blocks(errors,ids[::-1],24)
