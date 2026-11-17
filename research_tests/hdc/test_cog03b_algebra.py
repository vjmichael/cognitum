import numpy as np
import pytest
from cognitum.research.hdc_algebra import Spec, FAMILIES, MODULAR

@pytest.mark.parametrize('family', FAMILIES)
@pytest.mark.parametrize('seed', [19, 541, 873])
def test_independent_bind_inverse_permute(family, seed):
    s = Spec(family, 16, 17 if family in MODULAR else 0)
    rng = np.random.default_rng(seed)
    if family == 'BSC': a,b = rng.integers(0,2,(2,16)).astype(bool)
    elif family in MODULAR: a,b = rng.integers(0,17,(2,16),dtype=np.int64)
    elif family == 'FHRR': a,b = np.exp(1j*rng.uniform(-np.pi,np.pi,(2,16))).astype(np.complex64)
    else: a,b = rng.choice([-1,1],(2,16)).astype(np.float32) if family=='MAP' else rng.normal(size=(2,16)).astype(np.float32)/4
    if family in MODULAR: expected = [(int(x)+int(y))%17 for x,y in zip(a,b)]
    elif family == 'BSC': expected = [bool(x)!=bool(y) for x,y in zip(a,b)]
    elif family == 'HRR': expected = [sum(float(a[j])*float(b[(i-j)%16]) for j in range(16)) for i in range(16)]
    elif family == 'VTB': expected = [2*sum(float(a[4*(i//4)+j])*float(b[4*(i%4)+j]) for j in range(4)) for i in range(16)]
    else: expected = [complex(x)*complex(y) for x,y in zip(a,b)]
    np.testing.assert_allclose(s.bind(a,b),expected,atol=2e-6)
    np.testing.assert_array_equal(s.permute(s.permute(a,3),-3),a)
    np.testing.assert_allclose(s.inverse(s.inverse(a)),a,atol=1e-6)
    if family not in ('HRR','VTB'):
        np.testing.assert_allclose(s.unbind(b,s.bind(a,b)),a,atol=2e-6)
    with pytest.raises(ValueError): s.bind(a[:-1],b)
    with pytest.raises(ValueError): s.bind(a.astype(np.complex128),b)

@pytest.mark.parametrize('args',[('MAP',0,0),('VTB',15,0),('CGR',16,0),('BSC',16,4),('unknown',16,0)])
def test_bad_specs(args):
    with pytest.raises(ValueError): Spec(*args)

def test_vtb_role_direction():
    s=Spec('VTB',4); value=np.array([1,2,3,4],np.float32); role=np.array([0,-1,1,0],np.float32)/np.float32(np.sqrt(2))
    assert not np.allclose(s.bind(value,role),s.bind(role,value))
    np.testing.assert_allclose(s.unbind(role,s.bind(value,role)),value,atol=1e-6)

def test_modular_symbol_bounds():
    s=Spec('BSBC',4,3)
    with pytest.raises(ValueError): s.bind(np.array([0,1,2,3],np.int64),np.zeros(4,np.int64))

def test_nonfinite_rejected():
    s=Spec('HRR',4)
    with pytest.raises(ValueError): s.inverse(np.array([0,0,0,np.nan],np.float32))

@pytest.mark.parametrize('family', FAMILIES)
def test_native_shared_operands(family):
    # Mandatory separate gate: absence of the actual dependency is a failure.
    s=Spec(family,16,17 if family in MODULAR else 0)
    r=np.random.default_rng(143)
    if family=='BSC': a,b=r.integers(0,2,(2,16)).astype(bool)
    elif family in MODULAR: a,b=r.integers(0,17,(2,16),dtype=np.int64)
    elif family=='FHRR': a,b=np.exp(1j*r.uniform(-np.pi,np.pi,(2,16))).astype(np.complex64)
    else: a,b=r.normal(size=(2,16)).astype(np.float32)/4
    np.testing.assert_allclose(s.native('bind',a,b),s.bind(a,b),atol=2e-6)
    np.testing.assert_allclose(s.native('inverse',a),s.inverse(a),atol=2e-6)
    np.testing.assert_array_equal(s.native('permute',a,shift=3),s.permute(a,3))
    np.testing.assert_allclose(s.native('bundle',np.stack([a,a,b])),s.bundle([a,a,b]),atol=2e-6)
    np.testing.assert_allclose(s.native('similarity',a,b),s.similarity(a,b),atol=2e-6)

@pytest.mark.parametrize('family', FAMILIES)
def test_bundle_conventions(family):
    s=Spec(family,4,8 if family in MODULAR else 0)
    if family=='BSC':
        a=np.array([True,False,True,False]); b=~a
        np.testing.assert_array_equal(s.bundle([a,b],tie=a),a)
        with pytest.raises(ValueError): s.bundle([a,b])
        np.testing.assert_array_equal(s.bundle([a,a,b]),a)
    elif family in MODULAR:
        a=np.array([7,2,3,0],np.int64); b=np.array([1,2,3,0],np.int64)
        expected=np.array([0,2,3,0] if family=='MCR' else [1,2,3,0],np.int64)
        np.testing.assert_array_equal(s.bundle([a,b]),expected)
    else:
        a=np.ones(4,s.dtype); b=a*2
        np.testing.assert_array_equal(s.bundle([a,b]),a+b)
    with pytest.raises(ValueError): s.bundle(np.empty((0,4),s.dtype))

@pytest.mark.parametrize('family', FAMILIES)
def test_similarity_conventions(family):
    s=Spec(family,4,8 if family in MODULAR else 0)
    if family=='BSC': a=np.array([True,False,True,False]); b=~a; expected=-1
    elif family in MODULAR:
        a=np.array([7,0,1,2],np.int64); b=np.array([0,0,5,2],np.int64)
        expected=.5 if family=='BSBC' else .375
    elif family=='FHRR': a=np.ones(4,np.complex64); b=a*1j; expected=0
    else: a=np.ones(4,np.float32); b=-a; expected=-1
    assert s.similarity(a,b)==pytest.approx(expected)
    assert s.similarity(a,a)==pytest.approx(1)
