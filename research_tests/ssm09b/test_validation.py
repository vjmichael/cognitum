import numpy as np
import pytest
from cognitum.research import ssm_research_validation as v
from cognitum.research import ssm_interop as s


def make_data(seed=7,n=320,change_test=False):
    rng=np.random.default_rng(seed);u=rng.normal(size=n);x=np.empty(n);x[0]=.2
    for i in range(1,n):x[i]=.78*x[i-1]+.65*u[i-1]+rng.normal(0,.025)
    if change_test:x[245:]+=np.linspace(0,10,n-245)
    return ('time_seconds,observation,control\n'+''.join(f'{.1*i:.8f},{x[i]:.12f},{u[i]:.12f}\n' for i in range(n))).encode()


def make_manifest(raw):
    return v.manifest(raw,source='synthetic',declared_license='CC0-1.0',time_unit='s',observation_unit='m',control_unit='N',origin='known-simulator')


def prepare(raw):
    m=make_manifest(raw);p=v.protocol(m,train_end=160,val_end=240,seed=123,ridge_candidates=(0.,.01,.1),improvement_ratio=.98)
    return m,p


@pytest.mark.parametrize('seed',[1,17,81])
def test_frozen_identification(seed):
    raw=make_data(seed);m,p=prepare(raw);z=v.evaluate(raw,m,p,expected_protocol_sha256=s.digest(p))
    np.testing.assert_allclose(z['coefficients'][1:],[.78,.65],atol=.012)
    assert z['test_rmse']<.035 and z['test_rmse']<z['persistence_rmse']*.2
    assert z['train_count']==159 and z['val_count']==79 and z['test_count']==79
    assert z['model_selection_validation_only'] and z['test_not_used_for_fitting'] and not z['falsified']
    assert not z['certified'] and not z['execution_authorized']
    assert z['dataset_sha256']==s.digest(raw) and z['protocol_sha256']==s.digest(p)


def test_future_test_no_leakage():
    raw=make_data();new=make_data(change_test=True);m,p=prepare(raw);M,P=prepare(new)
    a=v.evaluate(raw,m,p,expected_protocol_sha256=s.digest(p));b=v.evaluate(new,M,P,expected_protocol_sha256=s.digest(P))
    np.testing.assert_array_equal(a['coefficients'],b['coefficients']);assert a['selected_ridge']==b['selected_ridge']
    assert a['validation_rmse']==b['validation_rmse'] and a['test_rmse']!=b['test_rmse']
    assert b['falsified']


def test_reproducible():
    r=make_data();m,p=prepare(r);a=v.evaluate(r,m,p,expected_protocol_sha256=s.digest(p));b=v.evaluate(r,m,p,expected_protocol_sha256=s.digest(p))
    np.testing.assert_array_equal(a['coefficients'],b['coefficients']);assert a==b if not isinstance(a['coefficients'],np.ndarray) else all((np.array_equal(a[k],b[k]) if isinstance(a[k],np.ndarray) else a[k]==b[k]) for k in a)
    assert m==make_manifest(r) and p==v.protocol(m,train_end=160,val_end=240,seed=123,ridge_candidates=(0.,.01,.1),improvement_ratio=.98)


def test_license_is_declared_only():
    m=s.read(make_manifest(make_data()));assert m['license_verified'] is False and m['raw_bytes_required'] is True and m['declared_origin']=='known-simulator'


@pytest.mark.parametrize('variant',['duplicate','reverse','missing','nan','inf','wrong-header','bom','bytes','extra-column'])
def test_dataset_refusals(variant):
    z=make_data().decode().splitlines(keepends=True)
    if variant=='duplicate':z[10]=z[9]
    if variant=='reverse':z[10]=z[3]
    if variant=='missing':z[10]=z[10].replace(',',',,',1)
    if variant=='nan':z[10]=z[10].replace(z[10].split(',')[1],'nan')
    if variant=='inf':z[10]=z[10].replace(z[10].split(',')[1],'inf')
    if variant=='wrong-header':z[0]='time,observation,control\n'
    if variant=='bom':z[0]='\ufeff'+z[0]
    if variant=='bytes':z[10]=z[10].replace('0','💯',1)
    if variant=='extra-column':z[10]=z[10].rstrip('\n')+',2\n'
    with pytest.raises(ValueError):v.parse_data(''.join(z).encode())


def test_provenance_tamper():
    raw=make_data();m,p=prepare(raw)
    bad=raw.replace(b'0.00000000',b'0.01000000',1)
    with pytest.raises(ValueError):v.validate_data(bad,m)
    with pytest.raises(ValueError):v.evaluate(raw,m,p.replace(b'"seed":123',b'"seed":124'),expected_protocol_sha256=s.digest(p))
    with pytest.raises(ValueError):v.validate_data(raw,b' '+m)
    with pytest.raises(ValueError):v.validate_data(raw,s.wire(dict(s.read(m),license_verified=True)))


@pytest.mark.parametrize('train,val',[(10,80),(170,180),(160,310),(160,450)])
def test_split_refusals(train,val):
    m=make_manifest(make_data())
    with pytest.raises(ValueError):v.protocol(m,train_end=train,val_end=val,seed=1)


def test_underexcited_refusal():
    raw=('time_seconds,observation,control\n'+''.join(f'{.1*i},{1.+.1*i},0\n' for i in range(150))).encode();m=make_manifest(raw);p=v.protocol(m,train_end=80,val_end=110,seed=1,ridge_candidates=(0.,))
    with pytest.raises(ValueError,match='rank'):v.evaluate(raw,m,p,expected_protocol_sha256=s.digest(p))


def get_stream():
    m=s.model([[.8,.1],[0,.6]],[[1],[.4]],[[1,0]],.1,['m','m'],['N'],['m'],'a'*64)
    q=s.state(m,[.1,.2]);u=np.random.default_rng(33).normal(size=(64,1));return m,q,u


def test_resource_accounting():
    m,q,u=get_stream();z=v.machine_profile(m,q,u,repeats=3,max_wall_ms=10000)
    assert z['source_model_sha256']==s.digest(m) and z['state_sha256']==s.digest(q)
    assert z['output_state_sha256']==s.digest(s.advance(m,q,u,s.digest(q),0)['state'])
    assert len(z['repeats_ms'])==2 and len(z['cpu_ms'])==3 and len(z['peak_python_bytes'])==3
    assert min(z['cpu_ms'])>=0 and max(z['peak_python_bytes'])>0
    assert 'no RSS/GPU/energy' in z['measurement_scope'] and not z['performance_baseline']


@pytest.mark.parametrize('bad',[(1,10000,8_000_000),(3,2,8_000_000),(3,10000,20)])
def test_resource_refuse(bad):
    m,q,u=get_stream()
    with pytest.raises(ValueError):v.machine_profile(m,q,u,repeats=bad[0],max_wall_ms=bad[1],max_peak_bytes=bad[2])
