"""TorchHD user-source compatibility smoke/regression tests (CPU only).

Run: PYTHONPATH=<TorchHD-source-parent>:<ZogZoo-root> pytest -q test_torchhd_adapter.py
"""
import numpy as np
import pytest
import torchhd as hd
from hdc_backend import make_backend


@pytest.mark.parametrize('vsa', ['BSC', 'MAP', 'HRR', 'FHRR'])
def test_native_bind_unbind_preserves_model(vsa):
    model = make_backend('torchhd', D=512, vsa=vsa, seed=730241)
    x = model.generate(3, seed=123)
    recovered = model.unbind(x[0], model.bind(x[0], x[1]))
    score = model.score(x, recovered)
    assert np.argmax(score) == 1
    if vsa != 'HRR':
        assert model.similarity(recovered, x[1]) > 0.999


def test_bsc_native_xor_and_majority():
    model = make_backend('torchhd', D=1024, vsa='BSC', seed=730337)
    x = model.generate(5, seed=3)
    assert x.dtype == np.bool_
    np.testing.assert_array_equal(model.bind(x[0], x[1]), np.logical_xor(x[0], x[1]))
    b = model.bundle(x)
    np.testing.assert_array_equal(b, x.sum(axis=0) > 2)
    assert b.dtype == np.bool_


def test_bsc_even_tie_reproducible():
    model = make_backend('torchhd', D=256, vsa='BSC', seed=938)
    x = model.generate(4, seed=9)
    np.testing.assert_array_equal(model.bundle(x), model.bundle(x))


def test_bsc_noise_is_true_bit_flip():
    model = make_backend('torchhd', D=1024, vsa='BSC', seed=3)
    x = model.generate(1, seed=44)[0]
    y = model.perturb(x, 'bitflip', 1.0, np.random.default_rng(4))
    np.testing.assert_array_equal(y, ~x)


def test_bsc_bipolar_conversion_matches_zogzoo_binding():
    b = make_backend('torchhd', 512, 'BSC', 3)
    zz = make_backend('zogzoo', 512, 'BSC', 3)
    x = zz.generate(2, seed=56)
    # TorchHD bool True denotes -1 in the bipolar mapping.
    bs = b.bind(x[0], x[1])
    assert bs.dtype == np.bool_
    np.testing.assert_array_equal(np.where(bs, -1, 1), zz.bind(x[0], x[1]))


def test_bsc_invalid_values_fail_loudly():
    b = make_backend('torchhd', 100, 'BSC')
    with pytest.raises(ValueError):
        b.bind(np.full(100, 0.3), np.ones(100, dtype=np.bool_))


@pytest.mark.parametrize('vsa', ['MAP', 'HRR', 'FHRR'])
def test_multi_bundle_matches_native_torchhd(vsa):
    b = make_backend('torchhd', 256, vsa=vsa, seed=7)
    values = b.generate(7, seed=9)
    native = hd.multibundle(hd.ensure_vsa_tensor(values, vsa=vsa)).cpu().numpy()
    np.testing.assert_allclose(b.bundle(values), native, rtol=2e-6, atol=2e-6)


@pytest.mark.parametrize('vsa', ['BSC', 'MAP', 'HRR', 'FHRR'])
def test_minimal_capacity_task(vsa):
    model = make_backend('torchhd', D=2048, vsa=vsa, seed=31)
    keys = model.generate(16, seed=31)
    values = model.generate(16, seed=32)
    associations = np.array([model.bind(keys[i], values[i]) for i in range(16)])
    memory = model.bundle(associations)
    correct = sum(int(np.argmax(model.score(values, model.unbind(keys[i], memory))) == i)
                  for i in range(16))
    assert correct >= 12, (vsa, correct)


def test_hrr_bind_uses_circular_convolution_not_map_multiplication():
    backend = make_backend('torchhd', D=256, vsa='HRR', seed=892)
    vec = backend.generate(2, seed=19)
    a, b = vec
    expected = hd.bind(hd.ensure_vsa_tensor(a, vsa='HRR'),
                       hd.ensure_vsa_tensor(b, vsa='HRR')).cpu().numpy()
    actual = backend.bind(a, b)
    np.testing.assert_allclose(actual, expected, rtol=1e-5, atol=1e-5)
    # Old adapter silently inferred MAP here; verify we're not doing that.
    assert not np.allclose(actual, a * b, rtol=1e-3, atol=1e-3)
