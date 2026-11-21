"""SSM04-R6: authenticated, deterministic streaming restart and refusal tests."""
import hashlib
import hmac
import json
import os

import numpy as np
import pytest

from cognitum.research import ssm_stochastic_checkpoints as cp
from cognitum.research import ssm_stochastic_streaming as streaming

KEY = bytes(range(32))
OTHER_KEY = bytes(range(32, 64))
CONTEXT = b"approved:synthetic-model/A=-0.2/Q=0.3/H=1/R=0.5/N=0.1/m0=.1/P0=.7"
STREAM = "project-1:camera-01"


def _engine(*, duration=1., limit=8):
    return streaming.FixedDurationIncrementSmoother(
        [[-.2]], [[.3]], [[1.]], [[.5]], [.1], [[.7]],
        lag_duration=duration, noise_cross=[[.1]], max_pending_states=limit)


def _signed(engine, revision=3, cursor="log-001"):
    return cp.serialize_stream_checkpoint(
        engine, authentication_key=KEY, stream_id=STREAM,
        model_context=CONTEXT, revision=revision, source_cursor=cursor)


def _restore(blob, *, floor=1, digest=None):
    return cp.restore_stream_checkpoint(
        blob, authentication_key=KEY, expected_stream_id=STREAM,
        model_context=CONTEXT, minimum_revision=floor,
        expected_checkpoint_sha256=digest)


def _forge(blob, mutate, *, resign=True):
    obj = json.loads(blob)
    mutate(obj)
    if resign:
        obj['mac'] = hmac.new(KEY,
            cp.MAC_DOMAIN + cp._canonical(obj['payload']), hashlib.sha256).hexdigest()
    return cp._canonical(obj)


def _compare(a, b):
    assert a['total_increment_events'] == b['total_increment_events']
    assert a['total_released_states'] == b['total_released_states']
    assert a['pending_state_indices'] == b['pending_state_indices']
    assert a['pending_state_times'] == b['pending_state_times']
    assert a['event_time_watermark'] == b['event_time_watermark']
    assert a['last_observation_time'] == b['last_observation_time']
    assert a['missing_increments'] == b['missing_increments']
    assert a['numerical_eigen_clips'] == b['numerical_eigen_clips']
    np.testing.assert_array_equal(a['filter_mean'], b['filter_mean'])
    np.testing.assert_array_equal(a['filter_factor'], b['filter_factor'])
    assert a['log_likelihood'] == b['log_likelihood']


def test_exact_roundtrip_and_deterministic_canonical_bytes():
    e = _engine()
    e.push(.3, [.2]);e.push(.7, None);e.push(1.2, [.4])
    blob = _signed(e, revision=17)
    restored = _restore(blob)
    assert restored['revision'] == 17
    assert restored['source_cursor'] == 'log-001'
    assert restored['stream_id'] == STREAM
    assert restored['checkpoint_sha256'] == hashlib.sha256(blob).hexdigest()
    assert restored['execution_authorized'] is False
    assert restored['certified'] is False
    assert restored['caller_owned_exactly_once_journal_required'] is True
    _compare(e.status(), restored['engine'].status())
    assert blob == _signed(restored['engine'], revision=17)
    assert KEY not in blob


def test_irregular_missing_correlated_replay_equivalence_with_watermark():
    e = _engine(duration=1.25)
    for t, y in ((.3,[.2]),(.7,None),(1.4,[.4])):e.push(t,y)
    e.advance_watermark(1.5)
    restored = _restore(_signed(e, revision=11))['engine']
    for t, y in ((1.8,[.3]),(2.0,[-.2]),(3.1,None),(3.8,[.7]),(4.2,[.1])):
        orig_out = e.push(t,y)
        resumed_out = restored.push(t,y)
        assert len(orig_out) == len(resumed_out)
        for orig, res in zip(orig_out,resumed_out):
            assert orig['state_index'] == res['state_index']
            assert orig['state_time'] == res['state_time']
            assert orig['conditioned_through_time'] == res['conditioned_through_time']
            np.testing.assert_array_equal(orig['mean'], res['mean'])
            np.testing.assert_array_equal(orig['factor'], res['factor'])
        _compare(e.status(), restored.status())
    a=e.advance_watermark(5.8)
    b=restored.advance_watermark(5.8)
    assert len(a)==len(b)
    for x,y in zip(a,b):
        np.testing.assert_array_equal(x['covariance'], y['covariance'])
    _compare(e.status(),restored.status())


def test_initial_pending_and_zero_lag_recovery_do_not_duplicate_release():
    for duration in (0., 1.):
        e=_engine(duration=duration)
        restored=_restore(_signed(e))['engine']
        assert restored.initial_releases == ()
        assert e.status()['total_released_states']==restored.status()['total_released_states']
        x=e.push(.2,[.4]);y=restored.push(.2,[.4])
        assert len(x)==len(y)
        _compare(e.status(), restored.status())


def test_older_revision_refused_and_exact_digest_anchor_enforced():
    e=_engine()
    blob=_signed(e,revision=8)
    with pytest.raises(ValueError,match='revision anti-rollback'):
        _restore(blob,floor=9)
    assert _restore(blob,floor=8)['revision']==8
    assert _restore(blob,digest=hashlib.sha256(blob).hexdigest())['revision']==8
    with pytest.raises(ValueError,match='digest anchor'):
        _restore(blob,digest='f'*64)


def test_wrong_mac_key_stream_model_or_key_size_refused():
    blob=_signed(_engine())
    with pytest.raises(ValueError,match='HMAC authentication'):
        cp.restore_stream_checkpoint(blob,authentication_key=OTHER_KEY,
                expected_stream_id=STREAM,model_context=CONTEXT)
    with pytest.raises(ValueError,match='stream identity'):
        cp.restore_stream_checkpoint(blob,authentication_key=KEY,
                expected_stream_id='other-stream',model_context=CONTEXT)
    with pytest.raises(ValueError,match='model context mismatch'):
        cp.restore_stream_checkpoint(blob,authentication_key=KEY,
                expected_stream_id=STREAM,model_context=b'different approved model bytes')
    with pytest.raises(ValueError,match='HMAC key'):
        cp.serialize_stream_checkpoint(_engine(), authentication_key=b'a',
                stream_id=STREAM,model_context=CONTEXT,revision=1)


def test_tampered_payload_and_mac_refused_without_state_reconstruction():
    blob=_signed(_engine())
    altered=_forge(blob,lambda e:e['payload'].__setitem__('source_cursor','evil'),resign=False)
    with pytest.raises(ValueError,match='HMAC authentication'):
        _restore(altered)
    altered=_forge(blob,lambda e:e.__setitem__('mac','0'*64),resign=False)
    with pytest.raises(ValueError,match='HMAC authentication'):
        _restore(altered)


def test_noncanonical_json_duplicate_keys_and_nonfinite_literal_refused():
    blob=_signed(_engine())
    obj=json.loads(blob)
    with pytest.raises(ValueError,match='noncanonical'):
        _restore(json.dumps(obj,indent=2).encode())
    duplicate=blob[:-1]+b',"mac":"'+b'0'*64+b'"}'
    with pytest.raises(ValueError,match='strict JSON decoding'):
        _restore(duplicate)
    with pytest.raises(ValueError,match='strict JSON decoding'):
        _restore(blob.replace(b'"revision":3',b'"revision":NaN'))


def test_signed_unsupported_schema_and_extra_fields_rejected():
    blob=_signed(_engine())
    v=_forge(blob,lambda e:e['payload'].__setitem__('schema','old-v0'))
    with pytest.raises(ValueError,match='payload version'):_restore(v)
    v=_forge(blob,lambda e:e['payload'].__setitem__('unknown','arbitrary'))
    with pytest.raises(ValueError,match='payload schema'):_restore(v)


def test_signed_retained_history_index_forgery_rejected():
    e=_engine();e.push(.1,[.2]);e.push(.3,[.5]);blob=_signed(e)
    v=_forge(blob,lambda e:e['payload']['state']['states'][-1].__setitem__('index',100))
    with pytest.raises(ValueError,match='retained index'):_restore(v)
    v=_forge(blob,lambda e:e['payload']['state'].__setitem__('released',999))
    with pytest.raises(ValueError,match='released count'):_restore(v)


def test_signed_wrong_correlated_pair_or_wrong_root_rejected():
    e=_engine();e.push(.1,[.2]);e.push(.3,[.5]);blob=_signed(e)
    v=_forge(blob,lambda e:e['payload']['state']['pairs'][0]['mean'].__setitem__(-1,42))
    with pytest.raises(ValueError,match='conditional joint pair'):_restore(v)
    v=_forge(blob,lambda e:e['payload']['state']['filter_factor'][0].__setitem__(0,20))
    with pytest.raises(ValueError,match='current filter'):_restore(v)


def test_signed_expired_pending_state_and_future_watermark_refused():
    e=_engine(duration=1.)
    e.push(.2,[.2])
    blob=_signed(e)
    v=_forge(blob,lambda x:x['payload']['state'].__setitem__('watermark',2.))
    with pytest.raises(ValueError,match='expired pending'):_restore(v)
    v=_forge(blob,lambda x:x['payload']['state'].__setitem__('watermark',.1))
    with pytest.raises(ValueError,match='watermark'):_restore(v)


def test_source_cursor_is_signed_and_restored_from_trusted_envelope():
    e=_engine();e.push(.2,[.1]);blob=_signed(e,revision=99,cursor='inputlog:offset-0009')
    result=_restore(blob,floor=99)
    assert result['source_cursor']=='inputlog:offset-0009'
    assert _signed(result['engine'],revision=99,cursor='inputlog:offset-0009')==blob


def test_atomic_checkpoint_storage_read_and_recover(tmp_path):
    p=tmp_path/'checkpoint.json'
    a=_signed(_engine(),revision=1)
    cp.atomic_write_checkpoint(p,a)
    assert cp.read_checkpoint(p)==a
    e=_engine();e.push(.2,[.1]);b=_signed(e,revision=2)
    cp.atomic_write_checkpoint(p,b)
    assert cp.read_checkpoint(p)==b
    restored=_restore(cp.read_checkpoint(p),floor=2)
    _compare(e.status(),restored['engine'].status())
    assert not list(tmp_path.glob('.*.tmp'))
    if os.name=='posix':assert (p.stat().st_mode & 0o077)==0


def test_interrupted_replace_preserves_previous_file_and_cleans_temporary(tmp_path,monkeypatch):
    p=tmp_path/'checkpoint.json';a=_signed(_engine(),revision=1)
    cp.atomic_write_checkpoint(p,a)
    b=_signed(_engine(),revision=2)
    def fail(*args):raise OSError('simulated interrupted replace')
    monkeypatch.setattr(cp.os,'replace',fail)
    with pytest.raises(OSError,match='simulated interrupted replace'):
        cp.atomic_write_checkpoint(p,b)
    assert cp.read_checkpoint(p)==a
    assert not list(tmp_path.glob('.*.tmp'))


def test_symlink_refusal_and_oversized_checkpoint(tmp_path):
    p=tmp_path/'checkpoint.json';cp.atomic_write_checkpoint(p,_signed(_engine()))
    alias=tmp_path/'alias'
    try:alias.symlink_to(p)
    except (OSError,NotImplementedError):
        assert not alias.exists()  # Windows without symlink privilege
    else:
        with pytest.raises(ValueError,match='symlink'):
            cp.read_checkpoint(alias)
        with pytest.raises(ValueError,match='symlink'):
            cp.atomic_write_checkpoint(alias,b'123')
    with pytest.raises(ValueError,match='byte budget'):
        _restore(b' '* (cp.MAX_CHECKPOINT_BYTES+1))


def test_synthetic_large_retained_window_and_bounded_serialized_size():
    e=_engine(duration=8.,limit=64)
    for j in range(31):e.push((j+1)*.1,[.2])
    blob=_signed(e)
    result=_restore(blob)
    _compare(e.status(),result['engine'].status())
    assert len(blob)<cp.MAX_CHECKPOINT_BYTES
    assert len(result['engine']._states)==32
    assert len(result['engine']._pairs)==31


@pytest.mark.parametrize('seed',range(6))
def test_randomized_split_point_deterministic_continuation(seed):
    rng=np.random.default_rng(seed+1206)
    times=np.cumsum(rng.uniform(.13,.45,size=30)).tolist()
    obs=[[float(rng.normal())] for _ in times]
    for j in range(seed%5,30,9):obs[j]=None
    e=_engine(duration=.9,limit=16)
    split=10+seed
    for t,y in zip(times[:split],obs[:split]):e.push(float(t),y)
    out=_restore(_signed(e,revision=seed+1))['engine']
    for t,y in zip(times[split:],obs[split:]):
        before=e.push(float(t),y);after=out.push(float(t),y)
        assert len(before)==len(after)
        for x,z in zip(before,after):
            assert x['state_index']==z['state_index']
            np.testing.assert_array_equal(x['mean'],z['mean'])
            np.testing.assert_array_equal(x['covariance'],z['covariance'])
    _compare(e.status(),out.status())
