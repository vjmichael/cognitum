"""MEL SSM R6-INT-01: trusted-host transactional recovery/journal tests.

Real MEL Admission session; no invented Lua/host privilege. Fake brokers and
anchors deliberately model the external protected OS services without claiming
they are installed or tamper resistant.
"""
import hashlib
import sqlite3

import numpy as np
import pytest

from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.mel import admission as mel
from cognitum.mel import ssm_recovery as j
from cognitum.research import ssm_stochastic_streaming as s


S = mel.Scope("session", "workspace", "subject", "turn")
CTX = b"approved-full-model+A=-.2+Q=.3+H=1+R=.5+N=.1+m0=.1+P0=.7"
KEY = bytes(range(32))


class KeyBroker:
    def __init__(self):
        self.key = KEY
        self.calls = []

    def borrow_key(self, scope, stream_id):
        self.calls.append((scope,stream_id))
        return self.key


class RevisionAnchor:
    def __init__(self):
        self.values = {}
        self.calls = []
        self.fail_next = False

    def read(self, scope, stream_id):
        return self.values.get((scope,stream_id),(0,None))

    def advance(self, scope, stream_id, old_rev, old_digest, revision, digest):
        before = self.read(scope,stream_id)
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("simulated external anchor service outage")
        assert before == (old_rev,old_digest), "protected CAS mismatch"
        assert revision > old_rev
        self.values[(scope,stream_id)] = (revision,digest)
        self.calls.append((old_rev,revision))


def _engine(lag=1.):
    return s.FixedDurationIncrementSmoother(
        [[-.2]], [[.3]], [[1]], [[.5]], [.1], [[.7]],
        lag_duration=lag, noise_cross=[[.1]], max_pending_states=16)


@pytest.fixture
def env(tmp_path):
    registry=Registry()
    runtime=Runtime(registry)
    admission=mel.Admission(runtime,S.session)
    broker=KeyBroker()
    anchor=RevisionAnchor()
    allowed={"active":True}
    allowed_calls=[]
    def allow(scope, operation):
        allowed_calls.append(operation)
        return allowed["active"] and scope == S
    path=tmp_path/"ssm-journal.sqlite"
    def open_journal(initial=None,scope=S,context=CTX,host=None):
        return j.HostSSMJournal(host or admission,scope,
            stream_id="ssm-session-01",approved_model_context=context,
            credential_broker=broker,revision_anchor=anchor,
            allow=allow,sqlite_path=path,initial_engine=initial)
    return dict(admission=admission,broker=broker,anchor=anchor,allowed=allowed,
                allowed_calls=allowed_calls,path=path,open=open_journal)


def _new(env,lag=1.):
    return env["open"](_engine(lag))


def _event(host,idx,time,increment,kind="increment"):
    return host.process("event-%03d"%idx,kind=kind,end_time=time,
                        increment=increment)


def test_host_mel_scope_and_fresh_custody_bootstrap(env):
    host=_new(env)
    st=host.status()
    assert st["revision"]==1
    assert st["pending_states"]==1
    assert st["pending_outputs"]==0
    assert st["admitted_by_existing_mel_scope"]
    assert not st["installed_MEL_route_authorized"]
    assert not st["installed_os_broker_qualified"]
    assert not st["external_exactly_once_qualified"]
    assert env["anchor"].read(S,"ssm-session-01")[0]==1
    assert env["broker"].calls
    host.close()
    with pytest.raises(ValueError,match="closed"):
        host.status()


def test_atomic_increment_snapshot_and_pending_release(env):
    host=_new(env)
    a=_event(host,1,.3,[.2])
    assert a["committed"] and a["revision"]==2 and a["emitted"]==0
    b=_event(host,2,1.,[.1])
    assert b["committed"] and b["revision"]==3 and b["emitted"]==1
    page=host.pending_outputs()
    assert len(page)==1
    o=page[0]
    assert o["receipt"]["state_index"]==0
    assert o["receipt"]["observation_cutoff_time"]==1.
    assert o["receipt"]["execution_authorized"] is False
    assert o["receipt"]["numerical_certified"] is False
    assert o["publish_authorized"] is False
    assert host.acknowledge(o["output_id"],o["body_sha"])
    assert host.acknowledge(o["output_id"],o["body_sha"])
    assert host.pending_outputs()==()
    assert host.status()["revision"]==3
    assert all(a < b for a,b in env["anchor"].calls)


def test_exact_duplicate_is_idempotent_not_reexecuted(env):
    host=_new(env)
    _event(host,1,.3,[.2]);result=_event(host,2,1.,[.4])
    before=host.status()
    again=_event(host,2,1.,[.4])
    assert again["status"]=="duplicate" and not again["committed"]
    assert again["revision"]==result["revision"]
    assert host.status()==before
    assert len(host.pending_outputs())==1
    with pytest.raises(ValueError,match="different payload"):
        _event(host,2,1.,[9.])
    assert host.status()==before


def test_cross_restart_deterministic_math_and_redelivery(env):
    uninterrupted=_engine()
    host=_new(env)
    for idx,t,y in ((1,.3,[.2]),(2,.9,None),(3,1.4,[.4])):
        uninterrupted.push(t,y)
        _event(host,idx,t,y)
    pending=host.pending_outputs()
    before=host.status()
    host.close()
    recovered=env["open"]()
    assert recovered.status()==before
    assert recovered.pending_outputs()==pending
    for idx,t,y in ((4,1.8,[-.2]),(5,2.2,[.4]),(6,3.0,None),
                    (7,3.5,[.7])):
        expected=uninterrupted.push(t,y)
        res=_event(recovered,idx,t,y)
        rows=[x for x in recovered.pending_outputs() if x["event_id"]=="event-%03d"%idx]
        assert res["emitted"]==len(expected)==len(rows)
        for row,x in zip(rows,expected):
            np.testing.assert_array_equal(row["receipt"]["mean"],x["mean"])
            np.testing.assert_array_equal(row["receipt"]["covariance"],x["covariance"])
    assert recovered.status()["revision"]==8
    assert recovered.status()["pending_outputs"]>=len(pending)


def test_watermark_recovery_and_no_phantom_increment(env):
    host=_new(env)
    _event(host,1,.4,[.2])
    r=_event(host,2,1.2,None,kind="watermark")
    assert r["emitted"]==1
    old=host.status()
    host.close()
    restored=env["open"]()
    assert restored.status()==old
    with pytest.raises(ValueError,match="unwatermarked"):
        _event(restored,3,.8,[.1])
    assert restored.status()==old
    res=_event(restored,3,1.5,[.1])
    assert res["committed"]
    assert restored.status()["revision"]==4


def test_host_revocation_and_mel_session_close_refused(env):
    host=_new(env)
    env["allowed"]["active"]=False
    with pytest.raises(ValueError,match="unauthorized"):
        _event(host,1,.1,[.1])
    with pytest.raises(ValueError,match="unauthorized"):
        host.pending_outputs()
    env["allowed"]["active"]=True
    assert _event(host,1,.1,[.1])["revision"]==2
    env["admission"].close()
    with pytest.raises(ValueError,match="closed"):
        _event(host,2,.2,[.1])


def test_mel_scope_and_approved_model_bind_across_reopen(env):
    host=_new(env);host.close()
    wrong=mel.Scope(S.session,S.workspace,"other",S.turn)
    with pytest.raises(ValueError,match="binding"):
        env["open"](scope=wrong)
    with pytest.raises(ValueError,match="binding"):
        env["open"](context=b"other approved model version 2")


def test_restoration_fails_on_trusted_floor_rollback_and_bad_pin(env):
    host=_new(env);_event(host,1,.2,[.1]);host.close()
    sid=(S,"ssm-session-01")
    floor,digest=env["anchor"].values[sid]
    env["anchor"].values[sid]=(floor+1,"f"*64)
    with pytest.raises(ValueError,match="revision rollback"):
        env["open"]()
    env["anchor"].values[sid]=(floor,"f"*64)
    with pytest.raises(ValueError,match="checkpoint pin mismatch"):
        env["open"]()
    env["anchor"].values[sid]=(floor,digest)
    assert env["open"]().status()["revision"]==2


def test_checkpoint_and_journal_head_tamper_refusal(env):
    host=_new(env);_event(host,1,.2,[.1]);host.close()
    with sqlite3.connect(env["path"]) as conn:
        conn.execute("UPDATE stream_snapshot SET checkpoint=?",
                     (b'{"forged":true}',))
    with pytest.raises(ValueError,match="snapshot byte digest"):
        env["open"]()


def test_joint_event_mac_head_tamper_refusal(env):
    host=_new(env);_event(host,1,.2,[.1]);host.close()
    with sqlite3.connect(env["path"]) as conn:
        conn.execute("UPDATE event_journal SET request_sha=?",("0"*64,))
    with pytest.raises(ValueError,match="journal head MAC"):
        env["open"]()


def test_outbox_body_tamper_and_ack_refusal(env):
    host=_new(env);_event(host,1,1.,[.4])
    row=host.pending_outputs()[0]
    with sqlite3.connect(env["path"]) as conn:
        conn.execute("UPDATE output_outbox SET body=?",
                     (b'{"forged":true}',))
    with pytest.raises(ValueError,match="outbox record authentication"):
        host.pending_outputs()
    with pytest.raises(ValueError,match="outbox authentication"):
        host.acknowledge(row["output_id"],row["body_sha"])


def test_outbox_mac_tamper_refusal(env):
    host=_new(env);_event(host,1,1.,[.4])
    with sqlite3.connect(env["path"]) as conn:
        conn.execute("UPDATE output_outbox SET body_mac=?",("0"*64,))
    with pytest.raises(ValueError,match="outbox record authentication"):
        host.pending_outputs()


def test_bad_input_rollback_does_not_advance_snapshot(env):
    host=_new(env)
    before=host.status()
    with pytest.raises(ValueError):
        _event(host,1,4.,[1.,2.])
    assert host.status()==before
    assert env["anchor"].read(S,"ssm-session-01")[0]==1
    assert _event(host,1,.2,[.1])["revision"]==2


def test_broker_outage_after_sqlite_commit_is_recoverable_without_reexecution(env):
    host=_new(env)
    env["anchor"].fail_next=True
    with pytest.raises(RuntimeError,match="anchor service outage"):
        _event(host,1,1.,[.2])
    with pytest.raises(ValueError,match="requires recovery"):
        host.status()
    host.close()
    restored=env["open"]()
    assert restored.status()["revision"]==2
    assert env["anchor"].read(S,"ssm-session-01")[0]==2
    assert _event(restored,1,1.,[.2])["status"]=="duplicate"
    assert len(restored.pending_outputs())==1


def test_wrong_key_cannot_restore_but_does_not_mutate_stored_snapshot(env):
    host=_new(env);_event(host,1,.2,[.1]);host.close()
    env["broker"].key=bytes(range(32,64))
    with pytest.raises(ValueError,match="HMAC authentication"):
        env["open"]()
    env["broker"].key=KEY
    assert env["open"]().status()["revision"]==2


def test_no_key_or_model_bytes_in_database_pages(env):
    host=_new(env);_event(host,1,.2,[.1]);host.close()
    raw=env["path"].read_bytes()
    assert KEY not in raw
    assert CTX not in raw


def test_trusted_path_symlink_rejected(env,tmp_path):
    path=env["path"];alias=tmp_path/"alias.db"
    try:alias.symlink_to(path)
    except (OSError,NotImplementedError):return
    with pytest.raises(ValueError,match="nonsymlink"):
        j.HostSSMJournal(env["admission"],S,stream_id="other",
            approved_model_context=CTX,credential_broker=env["broker"],
            revision_anchor=env["anchor"],allow=lambda *x:True,
            sqlite_path=alias,initial_engine=_engine())


@pytest.mark.parametrize("seed",range(6))
def test_stream_restart_repeated_irregular_and_missing(seed,env):
    rng=np.random.default_rng(seed+21001)
    times=np.cumsum(rng.uniform(.18,.5,size=24)).tolist()
    values=[[float(rng.normal())] if i%5 else None for i in range(24)]
    expected=_engine()
    host=_new(env)
    for i,(t,y) in enumerate(zip(times,values),1):
        gold=expected.push(float(t),y)
        result=_event(host,i,float(t),y)
        assert result["emitted"]==len(gold)
        if i in (5,9,14,20):
            old_status=host.status()
            host.close()
            host=env["open"]()
            assert host.status()==old_status
        output=[r for r in host.pending_outputs(limit=256)
                if r["event_id"]=="event-%03d"%i]
        assert len(output)==len(gold)
        for a,b in zip(output,gold):
            np.testing.assert_array_equal(a["receipt"]["mean"],b["mean"])
            np.testing.assert_array_equal(a["receipt"]["covariance"],b["covariance"])
    assert host.status()["revision"]==25
