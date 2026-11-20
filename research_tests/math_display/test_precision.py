import json
from decimal import Decimal
from fractions import Fraction
from dataclasses import FrozenInstanceError

import pytest
from cognitum.math_display import MathDisplaySettings, render_number, render_vector


def test_default_on():
    s = MathDisplaySettings()
    assert s.simplify_near_zero and s.cutoff_exponent == 3
    assert str(s.threshold) == '0.001'
    assert render_number(0.0008).shown == '≈ 0'
    assert render_number(-0.0008).shown == '≈ 0'


@pytest.mark.parametrize('n,shown', [
    (0, '0'), (0.0, '0.0'), (-0.0, '-0.0'),
    (0.001, '0.001'), (-0.001, '-0.001'),
    (0.00100001, '0.00100001'), (123.0000001, '123.0000001'),
    (1e-10, '≈ 0'), (-1e-10, '≈ 0'),
])
def test_boundaries(n, shown):
    a = render_number(n)
    assert a.shown == shown and (a.approximate_zero == (shown == '≈ 0'))
    assert a.full_precision == str(n)


def test_scientific_mode():
    s = MathDisplaySettings(simplify_near_zero=False)
    result = render_number(1.2345678912345678e-20, s)
    assert result.shown == result.full_precision == '1.2345678912345678e-20'
    assert not result.approximate_zero


@pytest.mark.parametrize('exponent,number,near_zero', [
    (1, Decimal('.09'), True), (3, Decimal('.0009'), True),
    (6, Decimal('.0009'), False), (12, Decimal('1e-13'), True),
    (308, Decimal('1e-309'), True), (308, Decimal('1e-308'), False)
])
def test_exponents(exponent, number, near_zero):
    a = render_number(number, MathDisplaySettings(True, exponent))
    assert a.approximate_zero is near_zero


def test_exact_evidence_not_suppressed():
    assert render_number('1/100000000', exact=True).shown == '1/100000000'
    assert render_number(Fraction(1, 1000000000)).shown == '1/1000000000'
    assert render_number(0.0000001, exact=True).shown == '1e-07'


def test_complex_and_nonfinite_not_suppressed():
    a = render_number(complex(0, 1e-20))
    assert '1e-20' in a.shown and not a.approximate_zero
    for n in (float('nan'), float('inf'), -float('inf'), Decimal('NaN')):
        z = render_number(n)
        assert z.nonfinite and not z.approximate_zero and z.shown == z.full_precision


def test_settings_roundtrip():
    s = MathDisplaySettings(False, 19)
    assert MathDisplaySettings.from_json(s.to_json()) == s
    assert json.loads(s.to_json()) == {'schema_version': 1, 'simplify_near_zero': False, 'cutoff_exponent': 19}


@pytest.mark.parametrize('raw', [
    '{}', '{"schema_version":2,"simplify_near_zero":true,"cutoff_exponent":3}',
    '{"schema_version":1,"simplify_near_zero":true,"cutoff_exponent":3,"unknown":1}',
    '{"schema_version":1,"simplify_near_zero":"true","cutoff_exponent":3}',
    '{"schema_version":1,"simplify_near_zero":true,"cutoff_exponent":true}',
    '{"schema_version":1,"simplify_near_zero":true,"cutoff_exponent":309}',
    '{"schema_version":1,"simplify_near_zero":true,"cutoff_exponent":0}',
    'not json', ' '*1025,
])
def test_settings_reject(raw):
    with pytest.raises(ValueError):
        MathDisplaySettings.from_json(raw)


def test_readonly_and_no_mutation():
    s = MathDisplaySettings(True, 3)
    with pytest.raises(FrozenInstanceError):
        s.cutoff_exponent = 12
    data = [0.0001, -0.0004, 0.8]
    unchanged = data[:]
    a = render_vector(data, s)
    assert data == unchanged
    assert tuple(x.shown for x in a) == ('≈ 0', '≈ 0', '0.8')
    assert tuple(x.full_precision for x in a) == ('0.0001', '-0.0004', '0.8')


def test_bad_arguments():
    for value in (True, {}, [1], '0.001'):
        with pytest.raises(ValueError):
            render_number(value)
    with pytest.raises(ValueError):
        render_number(0.1, 'not settings')
    with pytest.raises(ValueError):
        render_vector([0]*4097)
    with pytest.raises(ValueError):
        render_number('', exact=True)
