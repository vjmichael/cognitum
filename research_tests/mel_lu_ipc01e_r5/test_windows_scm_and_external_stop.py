"""R5 genuine Windows suspended fixed SSM and proposed external stop proof.

This test uses an *ephemeral test-only* Ed25519 signer, NEVER an accepted
Lu Core/SCM production issuer. Native Windows passes only after real kernel Job
ownership before the fixed child starts. Linux positive requires separately
delegated kernel cgroup and remains an installed-host acceptance gate.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

import pytest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from cognitum.mel import admission as mel
from cognitum.mel import ssm_r4_protected as r4
from cognitum.mel import ssm_r5_windows_job as win
from cognitum.mel import ssm_r5_stop_receipt as stop
from cognitum.mel import ssm_supervisor as sp
from cognitum.mel import ssm_recovery as journal
from cognitum.mel import ssm_revision_cas as cas
from cognitum.mel.ssm_os_credentials import OSCredentialBroker, CredentialUnavailable
from cognitum.mel.vendor.lu.workspace.v0 import workspace_pb2 as lu
from cognitum.research import ssm_stochastic_streaming as streaming
from cognitum.registry import Registry
from cognitum.runtime import Runtime

SCOPE = mel.Scope("original-r5-core", "r5-workspace", "trusted-ssm", "r5-turn")
ORIGIN = lu.OriginRefs(
    workspace_ref="r5-workspace", conversation_ref="r5-conversation",
    user_turn_ref="r5-turn", task_ref="r5-task", operation_ref="r5-original-operation",
)
KEY = bytes(range(1,33))
STREAM = "r5-stream"
EVENT = "r5-event"
MODEL = b"R5-approved-SSM-parameters-A=-.2-Q=.3-H=1-R=.5-N=.1-prior=.7"
NOW = 1_800_000_000_000


def _host(tmp_path):
    root = tmp_path / "host-owned"
    root.mkdir(mode=0o700)
    if os.name == "posix":
        root.chmod(0o700)
    broker = OSCredentialBroker(root, namespace="r5-" + uuid.uuid4().hex)
    try:
        broker.provision(SCOPE, ORIGIN.operation_ref, KEY)
        broker.provision(SCOPE, STREAM, KEY)
    except CredentialUnavailable:
        if sys.platform == "win32":
            pytest.fail("Windows DPAPI must be available")
        return root, None
    return root, broker


def _release(broker):
    broker.revoke(SCOPE, ORIGIN.operation_ref)
    broker.revoke(SCOPE, STREAM)


def _engine():
    return streaming.FixedDurationIncrementSmoother(
        [[-.2]], [[.3]], [[1]], [[.5]], [.1], [[.7]],
        lag_duration=1., noise_cross=[[.1]], max_pending_states=16)


def _claim(root,broker):
    return r4.DurableOriginalWorkerClaim(
        root, broker, SCOPE, ORIGIN, SCOPE.session, EVENT, STREAM)


def _external_claim(tmp_path):
    root, broker = _host(tmp_path)
    if broker is None:
        return root, broker, None
    claim = _claim(root, broker)
    nonce = claim.before_worker("a"*64)
    claim.after_kernel_stop(
        nonce, "a"*64, verified=True,
        mechanism="windows_job" if sys.platform=="win32" else "linux_cgroup2",
        kernel_worker_pid=1234,
    )  # Test fixture only; no real kernel stop asserted here.
    private = Ed25519PrivateKey.generate()  # TEST ONLY. No production signer API.
    public = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    issuer = stop.ExternallyPinnedStopSigner(
        public_key_ed25519=public, issuer_id="test-host-signer",
        issuer_epoch="test-epoch-1",
        service_package_sha256="b"*64, worker_source_sha256="c"*64,
    )
    body = {
        "schema": stop.SCHEMA,
        "issuer_id": issuer.issuer_id, "issuer_epoch": issuer.issuer_epoch,
        "service_package_sha256": issuer.service_package_sha256,
        "worker_source_sha256": issuer.worker_source_sha256,
        "original": claim._tuple, "identity": claim._identity,
        "request_sha256": "a"*64, "nonce": nonce,
        "mechanism": "windows_job" if sys.platform=="win32" else "linux_cgroup2",
        "worker_pid": 1234,
        "native_job_owned_before_release": True,
        "kernel_worker_exited": True,
        "kernel_scope_empty": True,
        "observed_unix_ms": NOW, "expires_unix_ms": NOW + 20000,
        "installed_authority": False,
    }
    return root,broker,(claim,issuer,private,body)


def _signed(private,body):
    raw = stop._canonical(body)
    return raw, private.sign(stop.DOMAIN + raw)


def test_external_signature_exact_original_only_and_no_authority(tmp_path):
    root, broker, data = _external_claim(tmp_path)
    if broker is None:
        return
    claim, issuer, private, body = data
    try:
        raw,signature = _signed(private,body)
        result = stop.verify_proposed_independent_stop(
            claim=claim,signed_bytes=raw,signature=signature,
            trusted_signer=issuer,trusted_now_ms=NOW)
        assert result["external_signature_checked"]
        assert result["locally_bound_original_operation"]
        assert not result["independently_installed_service_verified"]
        assert not result["installed_ssm_execution_authorized"]
        assert not result["durable_output_delivery_or_ack_authorized"]
        assert claim.restart_assessment() == "STOP_LOCALLY_OBSERVED_REPLAY_STILL_DENIED"
    finally:_release(broker)


@pytest.mark.parametrize("alter", [
    {"nonce": "0"*32},
    {"identity": "f"*64},
    {"worker_pid": 4321},
    {"mechanism": "other"},
    {"kernel_scope_empty": False},
    {"native_job_owned_before_release": False},
    {"installed_authority": True},
    {"expires_unix_ms": NOW + 70000},
    {"observed_unix_ms": NOW + 30000},
    {"issuer_epoch": "wrong-epoch"},
    {"service_package_sha256": "f"*64},
])
def test_signed_foreign_tampered_stale_or_overclaimed_stop_refused(tmp_path,alter):
    root, broker, data = _external_claim(tmp_path)
    if broker is None:
        return
    claim, issuer, private, body = data
    try:
        forged = dict(body,**alter)
        raw,signature = _signed(private,forged)
        with pytest.raises(r4.NativeSSMCustodyRefused,match="attestation refused"):
            stop.verify_proposed_independent_stop(
                claim=claim,signed_bytes=raw,signature=signature,
                trusted_signer=issuer,trusted_now_ms=NOW)
    finally:_release(broker)


def test_wrong_key_and_broken_signature_fail_and_cannot_publish(tmp_path):
    root, broker, data = _external_claim(tmp_path)
    if broker is None:
        return
    claim, issuer, private, body = data
    try:
        raw,signature = _signed(private,body)
        wrong = Ed25519PrivateKey.generate()
        public = wrong.public_key().public_bytes(
            serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        other = stop.ExternallyPinnedStopSigner(
            public_key_ed25519=public,issuer_id=issuer.issuer_id,
            issuer_epoch=issuer.issuer_epoch,
            service_package_sha256=issuer.service_package_sha256,
            worker_source_sha256=issuer.worker_source_sha256)
        with pytest.raises(r4.NativeSSMCustodyRefused,match="signature invalid"):
            stop.verify_proposed_independent_stop(
                claim=claim,signed_bytes=raw,signature=signature,
                trusted_signer=other,trusted_now_ms=NOW)
        damaged = bytearray(signature)
        damaged[3] ^= 2
        with pytest.raises(r4.NativeSSMCustodyRefused,match="signature invalid"):
            stop.verify_proposed_independent_stop(
                claim=claim,signed_bytes=raw,signature=bytes(damaged),
                trusted_signer=issuer,trusted_now_ms=NOW)
    finally:_release(broker)


def test_uncertain_restart_fails_closed_even_with_signed_fixture(tmp_path):
    root, broker = _host(tmp_path)
    if broker is None:return
    claim = _claim(root,broker)
    try:
        claim.before_worker("a"*64)
        key = Ed25519PrivateKey.generate()
        public = key.public_key().public_bytes(
            serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        issuer = stop.ExternallyPinnedStopSigner(
            public_key_ed25519=public,issuer_id="test",
            issuer_epoch="epoch",service_package_sha256="a"*64,
            worker_source_sha256="b"*64)
        with pytest.raises(r4.NativeSSMCustodyRefused,match="not locally observed"):
            stop.verify_proposed_independent_stop(
                claim=claim,signed_bytes=b"{}",signature=b"x"*64,
                trusted_signer=issuer,trusted_now_ms=NOW)
        assert claim.restart_assessment().startswith("UNCERTAIN")
    finally:_release(broker)


def test_windows_suspended_job_refuses_bad_pins_and_foreign_image(tmp_path):
    root, broker = _host(tmp_path)
    if broker is None:return
    try:
        if sys.platform != "win32":
            with pytest.raises(r4.NativeSSMCustodyRefused,match="Windows"):
                win.WindowsSuspendedFixedSSMJob(
                    installed_python_executable=sys.executable,
                    trusted_python_sha256="a"*64,
                    trusted_child_sha256="b"*64,
                    host_private_directory=root)
            return
        script = Path(win.__file__).with_name("ssm_r5_fixed_child.py")
        interpreter = hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest()
        with pytest.raises(r4.NativeSSMCustodyRefused,match="mismatch"):
            win.WindowsSuspendedFixedSSMJob(
                installed_python_executable=sys.executable,
                trusted_python_sha256="f"*64,
                trusted_child_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),
                host_private_directory=root)
        with pytest.raises(r4.NativeSSMCustodyRefused,match="mismatch"):
            win.WindowsSuspendedFixedSSMJob(
                installed_python_executable=sys.executable,
                trusted_python_sha256=interpreter,
                trusted_child_sha256="f"*64,
                host_private_directory=root)
    finally:_release(broker)


def test_windows_suspended_from_birth_fixed_ssm_R6_commit_and_restart(tmp_path):
    root, broker = _host(tmp_path)
    if broker is None:return
    if sys.platform != "win32":
        _release(broker)
        return
    script = Path(win.__file__).with_name("ssm_r5_fixed_child.py")
    runner = win.WindowsSuspendedFixedSSMJob(
        installed_python_executable=sys.executable,
        trusted_python_sha256=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
        trusted_child_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),
        host_private_directory=root)
    executor = r4.ProtectedFixedSSMExecutor(
        original=ORIGIN,core_session_ref=SCOPE.session,mel_scope=SCOPE,
        expected_stream_id=STREAM,expected_event_id=EVENT,
        credential_broker=broker,durable_directory=root,
        windows_suspended_runner=runner)
    admission = mel.Admission(Runtime(Registry()),SCOPE.session)
    anchor = cas.LocalAuthenticatedRevisionCAS(
        root,broker,namespace="r5native",create=True)
    journal_host = None
    try:
        journal_host = journal.HostSSMJournal(
            admission=admission,scope=SCOPE,stream_id=STREAM,
            approved_model_context=MODEL,credential_broker=broker,
            revision_anchor=anchor,allow=lambda scope,op: scope == SCOPE,
            sqlite_path=root/"journal.sqlite",initial_engine=_engine(),
            supervised_math=sp.SupervisedSSMCompute(
                timeout_ms=10000,protected_executor=executor))
        result = journal_host.process(EVENT,kind="increment",
                                     end_time=.3,increment=[.2])
        assert result["status"]=="committed" and result["revision"]==2
        assert result["publish_authorized"] is False
        assert runner.last_evidence["native_suspended_before_job_assignment"] is True
        assert runner.last_evidence["kernel_job_assigned_before_resume"] is True
        assert runner.last_evidence["kernel_job_empty_after_termination"] is True
        assert runner.last_evidence["installed_scm_service_verified"] is False
        assert executor.last_evidence["windows_worker_suspended_from_birth"]
        assert not executor.last_evidence["installed_core_grant_verified"]
        assert executor.claim.restart_assessment()=="STOP_LOCALLY_OBSERVED_REPLAY_STILL_DENIED"
        journal_host.close()
        journal_host = None
        reopened = journal.HostSSMJournal(
            admission=admission,scope=SCOPE,stream_id=STREAM,
            approved_model_context=MODEL,credential_broker=broker,
            revision_anchor=anchor,allow=lambda scope,op: scope == SCOPE,
            sqlite_path=root/"journal.sqlite",initial_engine=None)
        try:
            assert reopened.status()["revision"] == 2
            assert reopened.process(EVENT,kind="increment",end_time=.3,
                                    increment=[.2])["status"]=="duplicate"
            assert not reopened.status()["installed_MEL_route_authorized"]
        finally:reopened.close()
    finally:
        if journal_host is not None:journal_host.close()
        anchor.close()
        _release(broker)


def test_production_issuer_and_output_sender_still_absent():
    assert not hasattr(stop,"sign_installed_stop")
    assert not hasattr(stop,"enroll_installed_service")
    assert not hasattr(stop,"publish")
    assert not hasattr(stop,"acknowledge")
    assert not hasattr(win,"register_lu_tool")
    assert not hasattr(win,"grant_lu_effect")
