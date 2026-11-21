"""R4 fixed SSM operation OS-custody and durable refusal tests.

Windows positive executes actual SSM math in a real spawned Job-owned Python
child; Linux positive requires kernel-delegated cgroup v2 + watchkeeper and
otherwise must explicitly refuse. A source-only host controls all scope keys;
no Lu Core installed peer, user grant, issuer or output release is simulated.
"""
from __future__ import annotations

import hashlib
import os
import sys
import uuid

import pytest

from cognitum.mel import admission as mel
from cognitum.mel import ssm_recovery as journal
from cognitum.mel import ssm_supervisor as supervisor
from cognitum.mel import ssm_r4_protected as native
from cognitum.mel import ssm_revision_cas as cas
from cognitum.mel import ssm_os_credentials as oskeys
from cognitum.mel.vendor.lu.workspace.v0 import workspace_pb2 as pb
from cognitum.research import ssm_stochastic_streaming as streaming
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.cgroup2_contract import preflight

SCOPE=mel.Scope("original-core-session","workspace","trusted-ssm-subject","turn")
ORIGIN=pb.OriginRefs(workspace_ref="workspace",conversation_ref="conversation",
                     user_turn_ref="turn",task_ref="task",
                     operation_ref="original-r4-event")
STREAM="stream-r4"
EVENT="event-r4"
KEY=bytes(range(1,33))
CTX=b"original-approved-SSM-model-r4-A=-.2-Q=.3-H=1-R=.5-N=.1-prior=.7"


def _engine():
    return streaming.FixedDurationIncrementSmoother(
        [[-.2]],[[.3]],[[1]],[[.5]],[.1],[[.7]],
        lag_duration=1.,noise_cross=[[.1]],max_pending_states=16)


def _root(tmp_path):
    root=tmp_path/"native-host"
    root.mkdir(mode=0o700)
    if os.name=="posix":
        root.chmod(0o700)
    return root


def _native_broker(tmp_path):
    root=_root(tmp_path)
    broker=oskeys.OSCredentialBroker(root,namespace="r4"+uuid.uuid4().hex)
    try:
        broker.provision(SCOPE,ORIGIN.operation_ref,KEY)
        broker.provision(SCOPE,STREAM,KEY)
    except oskeys.CredentialUnavailable:
        if sys.platform=="win32":
            pytest.fail("Required Windows DPAPI must not fall back")
        return root,None
    return root,broker


def _native_executor(root,broker,*,origin=ORIGIN,core_session=SCOPE.session,
                     event_id=EVENT,stream=STREAM,linux_root="/sys/fs/cgroup"):
    return native.ProtectedFixedSSMExecutor(
        original=origin,core_session_ref=core_session,
        mel_scope=SCOPE,expected_stream_id=stream,
        expected_event_id=event_id,credential_broker=broker,
        durable_directory=str(root),delegated_cgroup_root=linux_root)


def test_explicit_os_key_unavailability_never_executes_uncontained(tmp_path):
    root=_root(tmp_path)
    with pytest.raises(native.NativeSSMCustodyRefused,
                       match="genuine OS key"):
        _native_executor(root,object())
    assert not list(root.glob("ssm-r4-pending-*.json"))


def test_exact_original_scope_and_core_session_before_launch(tmp_path):
    root=_root(tmp_path)
    broker=oskeys.OSCredentialBroker(root,namespace="r4"+uuid.uuid4().hex)
    foreign=pb.OriginRefs(workspace_ref="other",conversation_ref="conversation",
                          user_turn_ref="turn",task_ref="task",
                          operation_ref=ORIGIN.operation_ref)
    with pytest.raises(native.NativeSSMCustodyRefused,match="original Lu"):
        _native_executor(root,broker,origin=foreign)
    with pytest.raises(native.NativeSSMCustodyRefused,match="original Lu"):
        _native_executor(root,broker,core_session="foreign-session")
    assert not list(root.glob("ssm-r4-pending-*.json"))


def test_prelaunch_written_once_and_restart_is_uncertain_until_kernel_witness(tmp_path):
    root,broker=_native_broker(tmp_path)
    if broker is None:
        return  # Genuine Linux kernel refusal; never a fixture key.
    try:
        owner=_native_executor(root,broker)
        assert owner.claim.restart_assessment()=="NOT_STARTED"
        nonce=owner.claim.before_worker("a"*64)
        assert len(nonce)==32
        assert owner.claim.restart_assessment().startswith("UNCERTAIN")
        duplicate=_native_executor(root,broker)
        assert duplicate.claim.restart_assessment().startswith("UNCERTAIN")
        with pytest.raises(native.NativeSSMCustodyRefused,match="reused original"):
            duplicate.claim.before_worker("a"*64)
        with pytest.raises(native.NativeSSMCustodyRefused,match="kernel stop"):
            owner.claim.after_kernel_stop(nonce,"a"*64,verified=False,
                                          mechanism="windows_job",
                                          kernel_worker_pid=123)
        assert owner.claim.restart_assessment().startswith("UNCERTAIN")
        assert KEY not in b"".join(x.read_bytes() for x in root.glob("*.json"))
    finally:
        broker.revoke(SCOPE,ORIGIN.operation_ref)
        broker.revoke(SCOPE,STREAM)


def test_wrong_event_and_stream_refused_without_native_spawn(tmp_path):
    root,broker=_native_broker(tmp_path)
    if broker is None:
        return
    owner=_native_executor(root,broker)
    payload=dict(state={},kind="increment",end_time=.3,increment=[.1])
    try:
        for scope,stream,event in (
            (mel.Scope("wrong","workspace","trusted-ssm-subject","turn"),STREAM,EVENT),
            (SCOPE,"other-stream",EVENT),
            (SCOPE,STREAM,"foreign-event"),
        ):
            with pytest.raises(native.NativeSSMCustodyRefused,
                               match="foreign original"):
                owner.execute(supervisor.SSMComputeFactory,supervisor.OP,payload,
                              8000,scope=scope,stream_id=stream,event_id=event)
        assert owner.claim.restart_assessment()=="NOT_STARTED"
    finally:
        broker.revoke(SCOPE,ORIGIN.operation_ref)
        broker.revoke(SCOPE,STREAM)


def test_os_contained_ssm_pure_compute_integrates_existing_R6_journal(tmp_path):
    root,broker=_native_broker(tmp_path)
    if broker is None:
        return
    runner=_native_executor(root,broker)
    assert not hasattr(runner,"grant_lu_permission")
    registry=Registry()
    admission=mel.Admission(Runtime(registry),SCOPE.session)
    anchor=cas.LocalAuthenticatedRevisionCAS(root,broker,
              namespace="r4native",create=True)
    host=None
    try:
        host=journal.HostSSMJournal(
            admission=admission,scope=SCOPE,stream_id=STREAM,
            approved_model_context=CTX,credential_broker=broker,
            revision_anchor=anchor,
            allow=lambda scope,action: scope==SCOPE,
            sqlite_path=root/"r4journal.db",
            initial_engine=_engine(),
            supervised_math=supervisor.SupervisedSSMCompute(
                timeout_ms=10000,protected_executor=runner),
        )
        if sys.platform.startswith("linux") and not preflight("/sys/fs/cgroup").admitted_for_fixture:
            with pytest.raises((native.NativeSSMCustodyRefused,RuntimeError),
                               match="CGROUP|DELEGATION|cgroup|NO_|READ_ONLY"):
                host.process(EVENT,kind="increment",end_time=.3,increment=[.2])
            assert runner.claim.restart_assessment().startswith("UNCERTAIN")
            assert host.status()["revision"]==1
            assert host.status()["pending_outputs"]==0
        else:
            original=host.process(EVENT,kind="increment",end_time=.3,
                                  increment=[.2])
            assert original["status"]=="committed" and original["revision"]==2
            assert not original["publish_authorized"]
            assert runner.claim.restart_assessment()=="STOP_LOCALLY_OBSERVED_REPLAY_STILL_DENIED"
            assert runner.last_evidence["native_stop_locally_observed"]
            assert not runner.last_evidence["installed_core_grant_verified"]
            assert not runner.last_evidence["independent_signed_executor_stop_receipt"]
            assert not host.status()["os_sandbox_supervision_qualified"]
            assert not host.status()["installed_MEL_route_authorized"]
            assert host.process(EVENT,kind="increment",end_time=.3,
                                increment=[.2])["status"]=="duplicate"
            recovered_runner=_native_executor(root,broker)
            with pytest.raises(native.NativeSSMCustodyRefused,match="reused original"):
                recovered_runner.execute(
                    supervisor.SSMComputeFactory,supervisor.OP,
                    {"state":{},"kind":"increment","end_time":.3,"increment":[.2]},
                    8000,scope=SCOPE,stream_id=STREAM,event_id=EVENT)
            host.close()
            host=None
            recovered=journal.HostSSMJournal(
                admission=admission,scope=SCOPE,stream_id=STREAM,
                approved_model_context=CTX,credential_broker=broker,
                revision_anchor=anchor,
                allow=lambda scope,action: scope==SCOPE,
                sqlite_path=root/"r4journal.db",
                initial_engine=None)
            try:
                assert recovered.status()["revision"]==2
                assert recovered.process(EVENT,kind="increment",end_time=.3,
                                         increment=[.2])["status"]=="duplicate"
                assert not recovered.status()["external_exactly_once_qualified"]
            finally:
                recovered.close()
    finally:
        if host is not None:
            host.close()
        anchor.close()
        broker.revoke(SCOPE,ORIGIN.operation_ref)
        broker.revoke(SCOPE,STREAM)


def test_native_execution_is_never_installed_core_health_or_output_authority():
    assert not hasattr(native,"register_lu_capability")
    assert not hasattr(native,"verify_lu_issuer")
    assert not hasattr(native,"publish_outbox")
    assert not hasattr(native,"acknowledge_output")
    assert not hasattr(native,"grant_permission")
