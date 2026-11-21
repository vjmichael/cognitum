"""R6-INT-02: real native broker + CAS + disposable MEL host compute tests.

Windows DPAPI is a REQUIRED native test on Windows. Linux kernel keyring is
qualified only when the runner allows libkeyutils and keyctl; on restrictive
CI hosts the test records a real OS refusal, not synthetic successful custody.
"""
import hashlib
import os
from pathlib import Path
import sqlite3
import sys
import uuid

import numpy as np
import pytest

from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.mel import admission as a
from cognitum.mel import ssm_os_credentials as oskeys
from cognitum.mel import ssm_revision_cas as cas
from cognitum.mel import ssm_supervisor as sp
from cognitum.mel import ssm_recovery as journal
from cognitum.research import ssm_stochastic_streaming as streaming


S=a.Scope("session", "workspace", "subject", "turn")
OTHER=a.Scope("session", "workspace", "other", "turn")
KEY=bytes(range(32))
CTX=b"R6-INT-02-approved-complete-model-A=-.2-Q=.3-H=1-R=.5-N=.1-prior=.7"


class FakeKeyProvider:
    def __init__(self):
        self.key=KEY

    def borrow_key(self,scope,sid):
        assert type(scope) is a.Scope
        return self.key


def _engine(duration=1.):
    return streaming.FixedDurationIncrementSmoother(
        [[-.2]],[[.3]],[[1]],[[.5]],[.1],[[.7]],
        lag_duration=duration,noise_cross=[[.1]],max_pending_states=16)


def _sandbox(tmp_path):
    d=tmp_path/"protected"
    d.mkdir(mode=0o700)
    if os.name=="posix":
        d.chmod(0o700)
    return d


def _supervised():
    return sp.SupervisedSSMCompute(timeout_ms=10000)


def test_supervised_worker_executes_actual_spawned_R5_process():
    direct=_engine()
    protected=_engine()
    worker=_supervised()
    for kind,time,increment in [
        ("increment",.3,[.1]),
        ("increment",1.,[.5]),
        ("increment",1.3,None),
        ("watermark",2.0,None),
        ("increment",2.3,[-.2]),
    ]:
        baseline=(direct.push(time,increment) if kind=="increment"
                  else direct.advance_watermark(time))
        protected,output=worker.apply(protected,kind,time,increment)
        assert len(baseline)==len(output)
        for a,b in zip(baseline,output):
            assert a["state_index"]==b["state_index"]
            np.testing.assert_array_equal(a["mean"],b["mean"])
            np.testing.assert_array_equal(a["covariance"],b["covariance"])
        left,right=direct.status(),protected.status()
        assert left["pending_state_indices"]==right["pending_state_indices"]
        np.testing.assert_array_equal(left["filter_mean"],right["filter_mean"])
        np.testing.assert_array_equal(left["filter_covariance"],
                                      right["filter_covariance"])


def test_supervisor_timeout_is_refused_without_state_mutation(monkeypatch):
    engine=_engine()
    before=engine.status()
    monkeypatch.setattr(sp.worker,"execute",lambda *x:("timed_out",None))
    with pytest.raises(ValueError,match="timed out"):
        _supervised().apply(engine,"increment",.3,[.2])
    np.testing.assert_array_equal(before["filter_mean"],engine.status()["filter_mean"])
    assert engine.status()["total_increment_events"]==0


def test_supervisor_rejects_forged_output_and_invalid_operation(monkeypatch):
    engine=_engine()
    monkeypatch.setattr(sp.worker,"execute",lambda *x:("ok",{"arbitrary":"result"}))
    with pytest.raises(ValueError,match="malformed response"):
        _supervised().apply(engine,"increment",.3,[.2])
    with pytest.raises(ValueError,match="operation"):
        sp.SSMComputeFactory().handle("bad",{})
    assert engine.status()["total_increment_events"]==0


def test_local_revision_cas_requires_creation_and_owner_only_directory(tmp_path):
    root=_sandbox(tmp_path)
    provider=FakeKeyProvider()
    with pytest.raises(ValueError,match="existing protected authority"):
        cas.LocalAuthenticatedRevisionCAS(root,provider,namespace="r6int02")
    anchor=cas.LocalAuthenticatedRevisionCAS(root,provider,
                    namespace="r6int02",create=True)
    assert anchor.read(S,"stream-1")== (0,None)
    anchor.advance(S,"stream-1",0,None,1,"a"*64)
    assert anchor.read(S,"stream-1")== (1,"a"*64)
    anchor.close()
    reopened=cas.LocalAuthenticatedRevisionCAS(root,provider,namespace="r6int02")
    assert reopened.read(S,"stream-1")== (1,"a"*64)
    assert reopened.read(OTHER,"stream-1")== (0,None)
    reopened.close()


def test_revision_cas_atomic_compare_exchange_and_no_rewind(tmp_path):
    root=_sandbox(tmp_path)
    provider=FakeKeyProvider()
    authority=cas.LocalAuthenticatedRevisionCAS(root,provider,
                      namespace="revisions",create=True)
    authority.advance(S,"stream-1",0,None,1,"a"*64)
    authority.advance(S,"stream-1",1,"a"*64,2,"b"*64)
    before=authority.read(S,"stream-1")
    for bad in ((1,"a"*64,3,"c"*64),(2,"a"*64,3,"c"*64),
                (2,"b"*64,2,"c"*64)):
        with pytest.raises(ValueError):
            authority.advance(S,"stream-1",*bad)
    assert authority.read(S,"stream-1")==before
    authority.close()


def test_revision_cas_rejects_direct_sqlite_tamper_and_wrong_key(tmp_path):
    root=_sandbox(tmp_path);provider=FakeKeyProvider()
    authority=cas.LocalAuthenticatedRevisionCAS(root,provider,
                      namespace="tamper",create=True)
    authority.advance(S,"stream-1",0,None,1,"a"*64)
    provider.key=bytes(range(32,64))
    with pytest.raises(ValueError,match="MAC mismatch"):
        authority.read(S,"stream-1")
    provider.key=KEY
    path=root/"cog_ssm_tamper.revisions.sqlite"
    with sqlite3.connect(path) as cx:
        cx.execute("UPDATE anchor SET checkpoint_sha=?",("b"*64,))
    with pytest.raises(ValueError,match="MAC mismatch"):
        authority.read(S,"stream-1")
    authority.close()


def test_revision_cas_rejects_scope_stream_mismatch(tmp_path):
    authority=cas.LocalAuthenticatedRevisionCAS(_sandbox(tmp_path),
         FakeKeyProvider(),namespace="scope",create=True)
    authority.advance(S,"stream-1",0,None,1,"a"*64)
    assert authority.read(OTHER,"stream-1")==(0,None)
    assert authority.read(S,"stream-2")==(0,None)
    with pytest.raises(ValueError):
        authority.advance(OTHER,"stream-1",1,"a"*64,2,"b"*64)
    authority.close()


def test_explicit_local_cas_is_not_hardware_monotonic_counter(tmp_path):
    root=_sandbox(tmp_path)
    authority=cas.LocalAuthenticatedRevisionCAS(root,FakeKeyProvider(),
                     namespace="limitation",create=True)
    authority.advance(S,"stream-1",0,None,1,"a"*64)
    authority.close()
    # A caller with write access to this separate authority can remove its
    # entire DB: this intentionally proves the local store is NOT rollback
    # authoritative. Do not promote it without an independent hardware/root.
    (root/"cog_ssm_limitation.revisions.sqlite").unlink()
    with pytest.raises(ValueError,match="existing protected authority"):
        cas.LocalAuthenticatedRevisionCAS(root,FakeKeyProvider(),
                               namespace="limitation")


def test_os_broker_native_storage_or_explicit_linux_os_refusal(tmp_path):
    root=_sandbox(tmp_path)
    broker=oskeys.OSCredentialBroker(root,namespace="native-"+uuid.uuid4().hex)
    sid="stream-1"
    try:
        broker.provision(S,sid,KEY)
    except oskeys.CredentialUnavailable:
        if sys.platform=="win32":
            pytest.fail("Windows DPAPI current-user protection is required")
        assert sys.platform.startswith("linux")
        with pytest.raises(oskeys.CredentialUnavailable):
            broker.borrow_key(S,sid)
        return
    assert broker.borrow_key(S,sid)==KEY
    assert KEY not in b"".join(p.read_bytes() for p in root.iterdir() if p.is_file())
    with pytest.raises((ValueError,oskeys.CredentialUnavailable)):
        broker.provision(S,sid,KEY)
    with pytest.raises((ValueError,oskeys.CredentialUnavailable)):
        broker.borrow_key(OTHER,sid)
    another=oskeys.OSCredentialBroker(root,namespace=broker._namespace)
    assert another.borrow_key(S,sid)==KEY
    assert broker.revoke(S,sid)
    with pytest.raises(oskeys.CredentialUnavailable):
        another.borrow_key(S,sid)


def test_native_key_material_cannot_be_recovered_after_ciphertext_tamper(tmp_path):
    if sys.platform!="win32":
        return  # kernel keyring has no user file ciphertext to tamper with
    root=_sandbox(tmp_path)
    broker=oskeys.OSCredentialBroker(root,namespace="cipher-"+uuid.uuid4().hex)
    broker.provision(S,"stream-2",KEY)
    blob=next(root.glob("*.dpapi"))
    contents=blob.read_bytes()
    assert KEY not in contents
    blob.write_bytes(contents[:12]+b"tamper"+contents[18:])
    with pytest.raises(oskeys.CredentialUnavailable):
        broker.borrow_key(S,"stream-2")


def test_trusted_host_integration_with_local_anchor_and_supervised_worker(tmp_path):
    registry=Registry()
    runtime=Runtime(registry)
    admission=a.Admission(runtime,S.session)
    root=_sandbox(tmp_path)
    provider=FakeKeyProvider()
    anchor=cas.LocalAuthenticatedRevisionCAS(root,provider,
                    namespace="test-host",create=True)
    policy={"authorized":True}
    def allow(scope,action):
        return policy["authorized"] and scope==S
    args=dict(admission=admission,scope=S,stream_id="test-host",
              approved_model_context=CTX,credential_broker=provider,
              revision_anchor=anchor,allow=allow,
              sqlite_path=tmp_path/"journal.db",
              supervised_math=_supervised())
    host=journal.HostSSMJournal(initial_engine=_engine(),**args)
    assert host.status()["disposable_native_worker_used"] is True
    assert host.status()["os_sandbox_supervision_qualified"] is False
    one=host.process("event-1",kind="increment",end_time=.3,increment=[.2])
    assert one["status"]=="committed" and one["revision"]==2
    two=host.process("event-2",kind="increment",end_time=1.,increment=[.5])
    assert two["emitted"]==1 and host.status()["pending_outputs"]==1
    saved=host.status()
    host.close()
    recovered=journal.HostSSMJournal(initial_engine=None,**args)
    assert recovered.status()==saved
    assert recovered.process("event-2",kind="increment",
                             end_time=1.,increment=[.5])["status"]=="duplicate"
    policy["authorized"]=False
    with pytest.raises(ValueError,match="unauthorized"):
        recovered.process("event-3",kind="increment",end_time=1.2,increment=[.1])
    policy["authorized"]=True
    assert recovered.process("event-3",kind="increment",
                              end_time=1.2,increment=[.1])["revision"]==4
    assert recovered.pending_outputs()
    recovered.close()
    anchor.close()


def test_os_credential_and_local_revision_cas_integration_when_available(tmp_path):
    root=_sandbox(tmp_path)
    broker=oskeys.OSCredentialBroker(root,namespace="combined-"+uuid.uuid4().hex)
    try:
        broker.provision(S,"stream-native",KEY)
    except oskeys.CredentialUnavailable:
        if sys.platform=="win32":
            pytest.fail("required Windows DPAPI backend unavailable")
        return
    anchor=cas.LocalAuthenticatedRevisionCAS(root,broker,
                         namespace="combinedcas",create=True)
    assert anchor.read(S,"stream-native")==(0,None)
    anchor.advance(S,"stream-native",0,None,1,"f"*64)
    assert anchor.read(S,"stream-native")==(1,"f"*64)
    anchor.close()
    broker.revoke(S,"stream-native")
    new=cas.LocalAuthenticatedRevisionCAS(root,broker,
                         namespace="combinedcas")
    with pytest.raises(oskeys.CredentialUnavailable):
        new.read(S,"stream-native")
    new.close()
