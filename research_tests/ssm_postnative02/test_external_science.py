"""NIST independent StRD measurements and certified-reference comparison.

Real observed calibration data, not continuous-time dynamical measurements.
"""
from pathlib import Path
import numpy as np
import pytest
from cognitum.research import ssm_external_qualification as q
from cognitum.research.ssm_interop import digest,read,wire

DATA=Path(__file__).parent/'data'

def get(name):return (DATA/(name+'.csv')).read_bytes()

@pytest.mark.parametrize('name',['norris','misra1a'])
def test_source_exact_transcription_and_external_provenance(name):
    r=q.source_snapshot(name,get(name),q.SOURCES[name]['sha256'])
    assert r['source_url'].startswith('https://') and 'nist.gov' in r['source_url']
    assert len(r['observations'])==q.SOURCES[name]['n']
    assert r['source_type']=='observed-calibration-data' and not r['time_series']
    assert not r['license_scope_verified'] and not r['raw_upstream_bytes_authenticated']

@pytest.mark.parametrize('name',['norris','misra1a'])
def test_external_nist_certified_reference_full_dataset(name):
    z=q.certified_fit(name,get(name),q.SOURCES[name]['sha256'])
    assert z['pass_certified_numerics'] and z['not_dynamic_validation']
    assert z['max_relative_parameter_error']<1e-6 and z['relative_sse_error']<5e-7
    # Independent source certified values, not selected from fitted results.
    np.testing.assert_allclose(z['certified_parameters'],q.SOURCES[name]['certified'])

@pytest.mark.parametrize('name',['norris','misra1a'])
@pytest.mark.parametrize('seed',[7,29,89])
def test_real_observed_holdout_and_independent_falsification(name,seed):
    raw=get(name);P=q.freeze(name,raw,seed,alpha=.25,required_gain=.02)
    z=q.experiment(name,raw,P,digest(P));d=z['diagnostic']
    assert d['test_rmse']<d['predeclared_baseline_rmse']*.98
    assert not d['falsified'] and d['test_selection']=='test-only'
    assert d['conformal_abs_radius']>=0
    assert not d['coverage_guarantee_claimed'] and not d['real_world_calibration_verified']
    assert d['source_sha256']==q.SOURCES[name]['sha256']
    assert q.replay(name,raw,P,digest(P),z['evidence'])['replayed']

@pytest.mark.parametrize('name',['norris','misra1a'])
@pytest.mark.parametrize('seed',[7,29,89])
def test_preregistered_wrong_hypotheses_are_falsified(name,seed):
    raw=get(name);P=q.freeze(name,raw,seed,alpha=.25,required_gain=.02,candidate='negative-control')
    d=q.experiment(name,raw,P,digest(P))['diagnostic']
    assert d['falsified'] and d['test_rmse']>d['predeclared_baseline_rmse']
    assert d['execution_authorized'] is False

@pytest.mark.parametrize('name',['norris','misra1a'])
def test_different_splits_have_distinct_frozen_hashes(name):
    raw=get(name);A=q.freeze(name,raw,7);B=q.freeze(name,raw,29)
    assert digest(A)!=digest(B)
    with pytest.raises(ValueError,match='out-of-band'):q.experiment(name,raw,B,digest(A))
    with pytest.raises(ValueError,match='out-of-band'):q.experiment(name,raw,A,'1'*64)

@pytest.mark.parametrize('name',['norris','misra1a'])
def test_canonical_snapshot_has_custody_and_rejects_corruption(name):
    raw=get(name)
    with pytest.raises(ValueError,match='digest'):q.source_snapshot(name,raw.replace(b'.',b'_',1),q.SOURCES[name]['sha256'])
    with pytest.raises(ValueError,match='digest'):q.source_snapshot(name,raw,'a'*64)
    with pytest.raises(ValueError,match='digest'):q.source_snapshot(name,raw[:-1],q.SOURCES[name]['sha256'])

@pytest.mark.parametrize('name',['norris','misra1a'])
def test_protocol_tamper_rejected_even_if_fields_look_valid(name):
    raw=get(name);P=q.freeze(name,raw,7);D=read(P)
    D['seed']=29
    with pytest.raises(ValueError,match='out-of-band'):q.experiment(name,raw,wire(D),digest(P))
    # An independently supplied hash of a tampered but internally inconsistent plan also fails.
    D['seed']=7;D['test']=D['calibration']
    with pytest.raises(ValueError,match='split integrity'):q.experiment(name,raw,wire(D),digest(wire(D)))

@pytest.mark.parametrize('name',['norris','misra1a'])
def test_evidence_change_rejected_on_independent_replay(name):
    raw=get(name);P=q.freeze(name,raw,7);z=q.experiment(name,raw,P,digest(P))
    D=read(z['evidence']);D['test_rmse']+=1e-2
    with pytest.raises(ValueError,match='evidence artifact'):q.replay(name,raw,P,digest(P),wire(D))

@pytest.mark.parametrize('name',['norris','misra1a'])
def test_heldout_is_not_used_to_choose_model_parameters(name):
    # Fit from the frozen train set and verify the same fitted coefficients without test data.
    raw=get(name);p=read(q.freeze(name,raw,7));obs=q.source_snapshot(name,raw,q.SOURCES[name]['sha256'])['observations']
    a=q.fit(name,obs,np.asarray(p['train']))
    b=np.array(obs,copy=True);b[p['test'],0]+=100
    c=q.fit(name,b,np.asarray(p['train']))
    np.testing.assert_array_equal(a['parameters'],c['parameters'])
    assert a['sse']==c['sse']

@pytest.mark.parametrize('name',['norris','misra1a'])
def test_licensed_data_limitations_are_not_oversold(name):
    raw=get(name);P=q.freeze(name,raw,7);d=q.experiment(name,raw,P,digest(P))['diagnostic']
    assert d['independent_nist_certification_is_external_check_only']
    assert d['finite_sample_exchangeability_assumed'] and not d['coverage_guarantee_claimed']
    assert d['fit_selection']=='train-only' and d['calibration_selection']=='calibration-only'


def test_misra_parameter_sensitivity_is_detected():
    name='misra1a';raw=get(name);obs=q.source_snapshot(name,raw,q.SOURCES[name]['sha256'])['observations'];a=q.certified_fit(name,raw,q.SOURCES[name]['sha256'])
    x,y=obs[:,1],obs[:,0];sse0=np.sum((q.predict(name,a['parameters'],x)-y)**2)
    wrong=a['parameters']*np.array([.8,1.3]);sse1=np.sum((q.predict(name,wrong,x)-y)**2)
    assert sse1>10*sse0


def test_norris_outlier_negative_control():
    raw=get('norris');d=q.source_snapshot('norris',raw,q.SOURCES['norris']['sha256'])['observations'];z=q.fit('norris',d,np.arange(len(d)))
    fake=d.copy();fake[0,0]+=100
    a=q.fit('norris',fake,np.arange(len(fake)))
    assert abs(a['parameters'][0]-z['parameters'][0])>.5


def test_error_modes_not_falsely_promoted():
    raw=get('misra1a');P=q.freeze('misra1a',raw,7)
    d=q.experiment('misra1a',raw,P,digest(P))['diagnostic']
    assert not d['real_world_calibration_verified'] and not d['execution_authorized']
    assert d['required_gain']==.02 and d['test_count']>=3
