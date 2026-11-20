"""Actual published sensor readings; no time-reversed fitting, no test leakage."""
from pathlib import Path
import hashlib, json
import numpy as np
import pytest
from cognitum.research import ssm_observed_dynamics as m

ROOT=Path(__file__).parent/'data'
MANIFEST=(ROOT/'sources.json').read_bytes()

def data(name):return (ROOT/(name+'.csv')).read_bytes()

@pytest.mark.parametrize('name',['uci374','uci501'])
def test_original_derived_source_sha_and_observations(name):
    source=m.ingest(name,data(name),MANIFEST)
    assert source['sha256']==m.SOURCE[name]['sha']
    assert len(source['state'])==len(source['times'])==6144
    assert source['interval_seconds']==m.SOURCE[name]['interval']
    assert np.isfinite(source['state']).all() and np.isfinite(source['forcing']).all()

@pytest.mark.parametrize('name,missing',[('uci374',0),('uci501',9)])
def test_real_missingness_preserved_without_imputation(name,missing):
    assert m.ingest(name,data(name),MANIFEST)['missing_auxiliary']==missing

@pytest.mark.parametrize('name',['uci374','uci501'])
def test_strict_temporal_partition(name):
    s=m.ingest(name,data(name),MANIFEST);train,cal,test=m.split(s)
    assert (len(train),len(cal),len(test))==(3685,1228,1228)
    assert train[-1]+1<cal[0] and cal[-1]+1<test[0]
    assert set(train).isdisjoint(cal) and set(cal).isdisjoint(test)
    assert train[0]==0 and test[-1]==6142

@pytest.mark.parametrize('name',['uci374','uci501'])
def test_persistence_outperforms_learned_ssm_on_locked_heldout(name):
    a=m.experiment(name,data(name),MANIFEST,integrated=False);q=a['metrics']
    assert q['persistence_rmse']<q['ssm_rmse']
    assert q['wrong_sign_rmse']>q['persistence_rmse']
    assert q['kan_rmse'] is None and q['integrated_rmse'] is None
    assert a['execution_authorized'] is False and not a['verified_physical_law']

@pytest.mark.parametrize('name',['uci374','uci501'])
def test_independent_linear_fit_and_future_perturbation(name):
    s=m.ingest(name,data(name),MANIFEST);train,cal,test=m.split(s)
    d,t,_,sc=m.design(s,train);c=m.learn_ssm(d,t,train)
    z=s.copy();z['state']=s['state'].copy();z['forcing']=s['forcing'].copy()
    z['state'][test[40]:]+=500;z['forcing'][test[40]:]+=500
    d2,_,_,_=m.design(z,train);np.testing.assert_array_equal(d[:test[40],:],d2[:test[40],:])
    np.testing.assert_array_equal(c,m.learn_ssm(d2,t,train))

@pytest.mark.parametrize('name',['uci374','uci501'])
def test_deterministic_frozen_replay(name):
    a=m.experiment(name,data(name),MANIFEST,integrated=False)
    b=m.experiment(name,data(name),MANIFEST,integrated=False)
    assert a==b

@pytest.mark.parametrize('name',['uci374','uci501'])
def test_dataset_mutation_rejected(name):
    raw=bytearray(data(name));raw[150]=raw[150]^1
    with pytest.raises(ValueError,match='source digest'):m.ingest(name,bytes(raw),MANIFEST)

@pytest.mark.parametrize('name',['uci374','uci501'])
def test_manifest_mutation_rejected(name):
    data_json=json.loads(MANIFEST);data_json['license']='unknown';bad=json.dumps(data_json).encode()
    with pytest.raises(ValueError,match='source digest'):m.ingest(name,data(name),bad)

@pytest.mark.parametrize('name',['uci374','uci501'])
def test_uncertainty_under_shift_cannot_be_claimed(name):
    q=m.experiment(name,data(name),MANIFEST,integrated=False)['metrics']
    assert 0<q['coverage_90']<1
    assert q['counterfactual_shift_coverage_90']<q['coverage_90']
    assert len(q['bootstrap_mae_gain_95'])==2
    assert q['bootstrap_mae_gain_95'][1]<0

@pytest.mark.parametrize('alpha', [.05,.1,.2])
def test_conformal_order_statistic_not_asymptotic_guess(alpha):
    residual=np.array([1.,2.,3.,4.,5.,6.,7.,8.,9.,10.,11.,12.,13.,14.,15.,16.,17.,18.,19.,20.]);expected=int(np.ceil(21*(1-alpha)))-1
    assert m.rank_radius(residual,alpha)==residual[expected]

def test_no_source_swap():
    with pytest.raises(ValueError):m.ingest('uci404',data('uci374'),MANIFEST)

def test_distribution_shift_diagnostic_is_not_certification():
    a=m.experiment('uci501',data('uci501'),MANIFEST,False)
    assert a['metrics']['coverage_second_half']<a['metrics']['coverage_first_half']
    assert a['evidence_class']=='empirical-heldout-forecast'
