"""R3 independent OS credential/Job prerequisite tests, NOT installed Lu Core.

A mocked Health responder is explicitly SOURCE TEST ONLY. Real Windows Job
kernel tests launch a fixed, harmless Python process in a suspended state
and prove assignment, termination and empty Job. Linux tests reuse actual
cgroup-v2 preflight and never claim a fixture worker is an installed service.
"""
from __future__ import annotations

import hashlib
import os
import sys
import uuid

import pytest

from cognitum.mel import admission as mel
from cognitum.mel import lu_ipc_install_host as host
from cognitum.mel import lu_ipc_native as native
from cognitum.mel import lu_ipc_readonly as readonly
from cognitum.mel import lu_ipc_windows_job_probe as job
from cognitum.mel.ssm_os_credentials import OSCredentialBroker, CredentialUnavailable

SCOPE = mel.Scope("core-session", "workspace", "trusted-host", "health-turn")
PACKAGE = b"\xa5" * 32
KEY = bytes(range(1, 33))


def _broker(tmp_path):
    root = tmp_path / "os-owned"
    root.mkdir(mode=0o700)
    if os.name == "posix":
        root.chmod(0o700)
    return OSCredentialBroker(root, namespace="r3" + uuid.uuid4().hex)


def _pinned_transport():
    if sys.platform == "win32":
        return dict(
            endpoint=native.PIPE_PREFIX + "lu-cog-health-r3-absent",
            windows_process_pin={
                "pid": 424242, "creation_filetime": 1,
                "user_sid": "S-1-5-18", "image_sha256": "a" * 64,
            })
    return dict(endpoint="/nonexistent/private/lu-r3.sock", expected_uid=os.getuid())


def test_refuse_untrusted_non_native_broker_before_peer_contact(monkeypatch):
    def never_connect(**kwargs):
        raise AssertionError("invalid provider attempted a Core connection")
    monkeypatch.setattr(native, "installed_core_health_preflight", never_connect)
    with pytest.raises(readonly.LuClientRefused, match="native OS-backed broker"):
        host.probe_enrolled_core_health(
            broker=object(), trusted_scope=SCOPE, credential_ref="core-health",
            package_hash=PACKAGE, **_pinned_transport())


def test_native_broker_does_not_bootstrap_a_core_enrollment(tmp_path, monkeypatch):
    broker = _broker(tmp_path)
    def never_connect(**kwargs):
        raise AssertionError("unprovisioned key attempted Core connection")
    monkeypatch.setattr(native, "installed_core_health_preflight", never_connect)
    with pytest.raises(CredentialUnavailable):
        host.probe_enrolled_core_health(
            broker=broker, trusted_scope=SCOPE, credential_ref="core-health",
            package_hash=PACKAGE, **_pinned_transport())


def test_wrong_peer_pin_refuses_before_native_credential_borrow(tmp_path):
    broker = _broker(tmp_path)
    def never_borrow(*args, **kwargs):
        raise AssertionError("bad peer pin read the enrolled secret")
    broker.borrow_key = never_borrow
    pin = _pinned_transport()
    if sys.platform == "win32":
        pin["windows_process_pin"] = {}
    else:
        pin["expected_uid"] = -1
    with pytest.raises(readonly.LuClientRefused, match="host-selected"):
        host.probe_enrolled_core_health(
            broker=broker, trusted_scope=SCOPE, credential_ref="core-health",
            package_hash=PACKAGE, **pin)


def test_genuine_os_broker_can_supply_preexisting_secret_without_grant(
        tmp_path, monkeypatch):
    broker = _broker(tmp_path)
    try:
        broker.provision(SCOPE, "core-health", KEY)
    except CredentialUnavailable:
        if sys.platform == "win32":
            pytest.fail("Windows native DPAPI custody should be available")
        assert sys.platform.startswith("linux")
        with pytest.raises(CredentialUnavailable):
            broker.borrow_key(SCOPE, "core-health")
        return

    observed = []
    def source_only_health(**kwargs):
        observed.append(kwargs)
        return {
            "installed_acceptance": "BLOCKED_CORE_ISSUER_AND_ENROLLMENT",
            "output_delivery_authorized": False,
            "output_acknowledgment_authorized": False,
            "model_tool_execution_authorized": False,
            "source_fixture_excluded": False,
        }
    monkeypatch.setattr(native, "installed_core_health_preflight", source_only_health)
    try:
        result = host.probe_enrolled_core_health(
            broker=broker, trusted_scope=SCOPE, credential_ref="core-health",
            package_hash=PACKAGE, **_pinned_transport())
        assert len(observed) == 1
        assert observed[0]["enrolled_key"] == KEY
        assert observed[0]["package_hash"] == PACKAGE
        assert result["installed_acceptance"] != "PASS_INSTALLED"
        assert not result["output_delivery_authorized"]
    finally:
        assert broker.revoke(SCOPE, "core-health")


def test_source_only_health_cannot_claim_installed_or_publish(tmp_path, monkeypatch):
    broker = _broker(tmp_path)
    try:
        broker.provision(SCOPE, "core-health", KEY)
    except CredentialUnavailable:
        if sys.platform == "win32":
            pytest.fail("Windows DPAPI backend unavailable")
        return
    monkeypatch.setattr(native, "installed_core_health_preflight",
                        lambda **kwargs: {
                            "installed_acceptance": "PASS_INSTALLED",
                            "model_tool_execution_authorized": True,
                            "output_delivery_authorized": True,
                            "output_acknowledgment_authorized": True,
                        })
    try:
        with pytest.raises(readonly.LuClientRefused,
                           match="unauthorized installed Health authority escalation"):
            host.probe_enrolled_core_health(
                broker=broker, trusted_scope=SCOPE,
                credential_ref="core-health", package_hash=PACKAGE,
                **_pinned_transport())
    finally:
        broker.revoke(SCOPE, "core-health")


def test_linux_existing_cgroup_is_kernel_observed_but_not_ssm_installed():
    if not sys.platform.startswith("linux"):
        with pytest.raises(readonly.LuClientRefused, match="Linux cgroup-v2"):
            host.linux_existing_worker_cgroup_readiness()
        return
    status = host.linux_existing_worker_cgroup_readiness()
    assert isinstance(status["kernel_cgroup2"], bool)
    assert isinstance(status["delegated_fixture_scope_available"], bool)
    assert not status["installed_ssm_worker_protected"]
    assert not status["actual_installed_core_health_verified"]
    assert not status["output_delivery_authorized"]


def test_windows_pinned_fixed_worker_job_exits_and_reaps():
    if sys.platform != "win32":
        with pytest.raises(job.WorkerCustodyUnavailable, match="Windows-only"):
            job.WindowsFixedJobProbe(
                trusted_python_executable=sys.executable,
                trusted_image_sha256="a" * 64)
        return
    image = hashlib.sha256(open(sys.executable, "rb").read()).hexdigest()
    witness = job.WindowsFixedJobProbe(
        trusted_python_executable=sys.executable,
        trusted_image_sha256=image)
    result = witness.run(mode="exit", deadline_ms=8000)
    assert result["job_assigned_before_resume"]
    assert result["kernel_membership_observed"]
    assert result["kernel_job_empty_after_cleanup"]
    assert witness.last_kernel_reap_verified
    assert not result["installed_production_ssm_worker_qualified"]
    assert not result["model_tool_execution_authorized"]


def test_windows_job_timeout_kills_kernel_owned_process():
    if sys.platform != "win32":
        return
    image = hashlib.sha256(open(sys.executable, "rb").read()).hexdigest()
    witness = job.WindowsFixedJobProbe(
        trusted_python_executable=sys.executable,
        trusted_image_sha256=image)
    with pytest.raises(job.WorkerCustodyUnavailable, match="fixed worker timeout"):
        witness.run(mode="timeout", deadline_ms=150)
    assert witness.last_kernel_reap_verified


def test_windows_job_refuses_bad_image_and_arbitrary_worker():
    if sys.platform != "win32":
        return
    with pytest.raises(job.WorkerCustodyUnavailable, match="image does not match"):
        job.WindowsFixedJobProbe(
            trusted_python_executable=sys.executable,
            trusted_image_sha256="b" * 64)
    image = hashlib.sha256(open(sys.executable, "rb").read()).hexdigest()
    witness = job.WindowsFixedJobProbe(
        trusted_python_executable=sys.executable, trusted_image_sha256=image)
    with pytest.raises(job.WorkerCustodyUnavailable, match="closed fixed"):
        witness.run(mode="invoke_untrusted_command")
    assert not witness.last_kernel_reap_verified
