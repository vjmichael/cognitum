"""Cognitum-side host-load tests. No Lu binary, IPC endpoint or release key."""
from concurrent.futures import ThreadPoolExecutor
import json

import pytest

from cognitum.mel import admission as a, lu_adapter as lu, model_reference as r


SCOPE = a.Scope('lu-test-session', 'workspace', 'user', 'turn')
BIND = json.dumps({
    'tool': 'mel_hdc_bind',
    'arguments': {'left': '101', 'right': '110'},
})
QUERY = json.dumps({
    'tool': 'mel_hdc_query',
    'arguments': {'probe': '101', 'candidates': ['101', '101', '110']},
})


def test_host_can_load_and_invoke_real_verified_hdc():
    with lu.load(SCOPE, r.Allowed(('hdc.bind',))) as engine:
        catalog = engine.catalog()
        assert catalog['profile'] == lu.PROFILE
        assert catalog['registered_with_lu'] is False
        assert catalog['execution_authorized_by_lu'] is False
        assert catalog['one_call_per_session'] is True
        assert tuple(x['operation'] for x in catalog['routes']) == ('hdc.bind',)
        assert catalog['tool_schemas'] == engine.schemas()
        assert [x['function']['name'] for x in engine.schemas()] == ['mel_hdc_bind']
        # Schemas expose neither a host grant nor a private worker token.
        offered = json.dumps(catalog, sort_keys=True)
        assert 'mel_hdc_query' not in offered and 'session_secret' not in offered
        out = engine.dispatch(BIND)
        assert out['ok'] and out['result']['bits'] == '011'
        assert out['publication_authorized'] is False
        assert engine.dispatch(BIND)['error'] == 'turn_attempt_limit'
    assert engine.dispatch(BIND)['error'] == 'session_closed'


def test_separately_approved_operation_can_be_loaded():
    with lu.load(SCOPE, r.Allowed(('hdc.query',))) as engine:
        result = engine.dispatch(QUERY)
        assert result['ok'], result
        assert result['result']['best_index'] == [0, 1]
        assert result['publication_authorized'] is False


def test_model_cannot_escape_host_selected_allowlist():
    with lu.load(SCOPE, r.Allowed(('hdc.bind',))) as engine:
        out = engine.dispatch(QUERY)
        assert not out['ok'] and out['error'] == 'not_authorized'
        assert out['publication_authorized'] is False
        assert engine.dispatch(BIND)['error'] == 'turn_attempt_limit'


@pytest.mark.parametrize('bad', [
    '{"tool":"shell_exec","arguments":{"command":"whoami"}}',
    '{"tool":"mel_hdc_bind","arguments":{"left":"101","right":"110"},"grant":true}',
    '{"tool":"mel_hdc_bind","arguments":{"left":"101","left":"001","right":"110"}}',
])
def test_untrusted_requests_never_become_host_authority(bad):
    with lu.load(SCOPE, r.Allowed(('hdc.bind',))) as engine:
        out = engine.dispatch(bad)
        assert out['ok'] is False
        assert out['publication_authorized'] is False


def test_empty_catalog_cannot_execute():
    with lu.load(SCOPE, r.Allowed(())) as engine:
        assert engine.schemas() == []
        assert engine.catalog()['routes'] == []
        assert engine.dispatch(BIND)['error'] == 'not_authorized'


def test_closed_session_and_double_close_are_safe():
    session = lu.load(SCOPE, r.Allowed(('hdc.bind',)))
    session.close()
    session.close()
    with pytest.raises(ValueError, match='closed'):
        session.catalog()
    with pytest.raises(ValueError, match='closed'):
        session.schemas()
    assert session.dispatch(BIND) == {
        'ok': False, 'error': 'session_closed', 'result': None,
        'publication_authorized': False,
    }


def test_only_real_host_scope_and_explicit_allowed_are_accepted():
    for scope, allowed in ((None, r.Allowed(('hdc.bind',))),
                           (SCOPE, ('hdc.bind',)),
                           ({'session': 'forged'}, r.Allowed(('hdc.bind',)))):
        with pytest.raises(ValueError, match='trusted host'):
            lu.load(scope, allowed)
    # A KAN checkpoint cannot be invented by the loaded model.
    with pytest.raises(ValueError):
        r.Allowed(('kan.evaluate',))


def test_concurrent_model_calls_consume_at_most_one_local_execution():
    with lu.load(SCOPE, r.Allowed(('hdc.bind',))) as engine:
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(engine.dispatch, (BIND, BIND)))
        assert sum(x['ok'] is True for x in responses) == 1
        assert sorted(x.get('error', '') for x in responses) == ['', 'turn_attempt_limit']


def test_original_proposal_still_never_claims_lu_installation():
    p = lu.proposal()
    assert p['installable'] is False
    assert p['registered'] is False
    assert p['model_advertised'] is False
    assert p['execution_authorized'] is False
