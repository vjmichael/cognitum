"""SSM chunk-resume quality gates: near-production state validity and numerical parity."""
from __future__ import annotations
import math
import random

import pytest

from cognitum.specialists.ssm import DiagonalSSM, InvalidSSM, MAX_ELEMENT, MAX_STATE


def example_model():
    return DiagonalSSM.from_mapping({
        'a': [1.0], 'b': [[1000.0]], 'c': [[1.0]], 'd': [[0.0]],
    })


def test_resume_legal_latent_state_above_coefficient_bound():
    model = example_model()
    first = model.scan([[2.0]])
    assert first['final_state'] == [2000.0]
    # Old code rejected this *valid computed state* as an invalid coefficient.
    second = model.scan([[1.0]], first['final_state'])
    whole = model.scan([[2.0], [1.0]])
    assert second['outputs'] == whole['outputs'][1:]
    assert second['final_state'] == whole['final_state']


def test_resume_at_exact_max_state_when_next_step_decays():
    model = DiagonalSSM.from_mapping({
        'a': [0.5], 'b': [[1.0]], 'c': [[1.0]], 'd': [[0.0]],
    })
    result = model.scan([[0.0]], [MAX_STATE])
    assert result['final_state'] == [MAX_STATE / 2]


@pytest.mark.parametrize('bad', [MAX_STATE + 1, -MAX_STATE - 1, math.inf, -math.inf, math.nan, True, '1000', 10**400])
def test_resume_rejects_invalid_state_without_escaping(bad):
    with pytest.raises(InvalidSSM):
        example_model().scan([[0.0]], [bad])


def test_resume_state_limit_does_not_widen_input_or_coefficient_limits():
    m = example_model()
    with pytest.raises(InvalidSSM, match='COEFFICIENT_OUT_OF_RANGE'):
        m.scan([[MAX_ELEMENT + 0.01]])
    with pytest.raises(InvalidSSM):
        DiagonalSSM.from_mapping({'a':[1.0], 'b':[[MAX_ELEMENT + 1]],'c':[[1]],'d':[[0]]})


@pytest.mark.parametrize('args', [
    ((1.5,), ((1.0,),), ((1.0,),), ((0.0,),)),
    ((0.5,), ((1.0, 1.0),), ((1.0,),), ((0.0,),)),
    ((0.5,), ((float('nan'),),), ((1.0,),), ((0.0,),)),
    ((0.5,), ((1.0,),), ((1.0, 1.0),), ((0.0,),)),
    ((0.5,), ((1.0,),), ((1.0,),), ((float('inf'),),)),
])
def test_direct_dataclass_constructor_enforces_bounds(args):
    with pytest.raises(InvalidSSM):
        DiagonalSSM(*args)


def test_chunking_is_bitwise_identical_to_single_scan_for_250_fresh_cases():
    rng = random.Random(88000421)
    for _ in range(250):
        state_dim = rng.randint(1, 8)
        input_dim = rng.randint(1, 8)
        output_dim = rng.randint(1, 8)
        params = {
            'a': [rng.random() for _ in range(state_dim)],
            'b': [[rng.uniform(-3, 3) for _ in range(input_dim)] for _ in range(state_dim)],
            'c': [[rng.uniform(-3, 3) for _ in range(state_dim)] for _ in range(output_dim)],
            'd': [[rng.uniform(-3, 3) for _ in range(input_dim)] for _ in range(output_dim)],
        }
        x = [[rng.uniform(-8, 8) for _ in range(input_dim)] for _ in range(64)]
        model = DiagonalSSM.from_mapping(params)
        full = model.scan(x)
        # Split into several chunks, including state-carrying boundaries.
        cuts = sorted(rng.sample(range(1, 64), rng.randint(1, 8))) + [64]
        state = None
        pos = 0
        outputs = []
        for cut in cuts:
            part = model.scan(x[pos:cut], state)
            outputs.extend(part['outputs'])
            state = part['final_state']
            pos = cut
        assert outputs == full['outputs']
        assert state == full['final_state']


def test_public_constructor_never_leaks_overflow_for_huge_integer():
    with pytest.raises(InvalidSSM):
        DiagonalSSM((10**400,), ((1.0,),), ((1.0,),), ((0.0,),))
    with pytest.raises(InvalidSSM):
        DiagonalSSM((0.5,), ((10**400,),), ((1.0,),), ((0.0,),))


def test_public_constructor_denies_non_tuple_and_bad_dimensions():
    with pytest.raises(InvalidSSM):
        DiagonalSSM(None, ((1.0,),), ((1.0,),), ((0.0,),))
    with pytest.raises(InvalidSSM):
        DiagonalSSM((0.5,), ((1.0,),), ((1.0,),), None)
