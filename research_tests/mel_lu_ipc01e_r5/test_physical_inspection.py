"""Physical R5 host observation negative tests (never installed acceptance).

Native Windows CI runners do not contain a signed installed Cognitum SCM
service. Linux CI cgroups are not a delegated installed Cognitum hierarchy.
No test may fake an installed Core enrollment, sign a production stop receipt,
or substitute a Python mock for an OS service/kernel-positive acceptance.
"""
from __future__ import annotations

import os
import sys

import pytest

from cognitum.mel.ssm_r4_protected import NativeSSMCustodyRefused
from cognitum.mel import ssm_r5_physical_inspection as physical


def _unavailable_service():
    return dict(
        trusted_service_name="CognitumSSMWorkerAcceptanceMissing",
        trusted_image_path="C:\\Cognitum\\Uninstalled\\cognitum.exe",
        trusted_image_sha256="a"*64,
        trusted_binary_command='"C:\\Cognitum\\Uninstalled\\cognitum.exe"',
        trusted_service_account="NT SERVICE\\CognitumSSMWorkerAcceptanceMissing",
        trusted_service_sid_type=3,
    )


@pytest.mark.parametrize("bad", [
    {"trusted_service_name":"../foreign-service"},
    {"trusted_service_name":" "},
    {"trusted_service_name":"Cognitum\x00Worker"},
    {"trusted_image_path":"relative.exe"},
    {"trusted_image_sha256":"0"*64},
    {"trusted_image_sha256":"z"*64},
    {"trusted_binary_command":"exe\x00--inject"},
    {"trusted_service_account":""},
    {"trusted_service_sid_type":0},
    {"trusted_service_sid_type":4},
    {"trusted_service_sid_type":True},
])
def test_unreviewed_scm_pins_refused_without_os_credential_access(bad):
    data = dict(_unavailable_service(), **bad)
    if sys.platform != "win32":
        with pytest.raises(NativeSSMCustodyRefused, match="Windows SCM"):
            physical.inspect_running_windows_scm(**data)
        return
    with pytest.raises(NativeSSMCustodyRefused, match="physical custody refused"):
        physical.inspect_running_windows_scm(**data)


def test_missing_genuine_cognitum_scm_service_is_not_installed():
    if sys.platform != "win32":
        with pytest.raises(NativeSSMCustodyRefused, match="Windows SCM"):
            physical.inspect_running_windows_scm(**_unavailable_service())
        return
    # Uses the actual Windows SCM. No fake installed service or mock status.
    with pytest.raises(NativeSSMCustodyRefused,
                       match="reviewed Cognitum service is not installed"):
        physical.inspect_running_windows_scm(**_unavailable_service())


def test_linux_kernel_v2_readiness_is_not_publisher_or_restart_acceptance():
    if not sys.platform.startswith("linux"):
        with pytest.raises(NativeSSMCustodyRefused, match="Linux kernel"):
            physical.inspect_existing_linux_delegation(
                trusted_delegated_root="/sys/fs/cgroup")
        return
    data = physical.inspect_existing_linux_delegation(
        trusted_delegated_root="/sys/fs/cgroup")
    assert data["schema"].endswith("kernel_cgroup_preflight.v1")
    assert data["status"] in (
        "BLOCKED_DELEGATION","DELEGATED_FIXTURE_SCOPE_POSSIBLE_NOT_INSTALLED")
    assert isinstance(data["kernel_cgroup_v2_observed"],bool)
    assert not data["positive_original_job_restart_proven"]
    assert not data["installed_linux_service_manager_verified"]
    assert not data["independent_signed_stop_proven"]
    assert not data["real_core_health_exchange_verified"]
    assert not data["outbox_delivery_authorized"]


def test_fake_or_relative_delegation_denied_before_kernel_probe():
    if not sys.platform.startswith("linux"):
        return
    with pytest.raises(NativeSSMCustodyRefused,
                       match="externally selected absolute"):
        physical.inspect_existing_linux_delegation(
            trusted_delegated_root="fake/relative")


def test_linux_restart_only_accepts_real_original_recovery_adapter():
    if not sys.platform.startswith("linux"):
        with pytest.raises(NativeSSMCustodyRefused,match="Linux kernel"):
            physical.inspect_original_linux_restart(
                exact_original_recovery=object())
        return
    with pytest.raises(NativeSSMCustodyRefused,
                       match="genuine original-bound"):
        physical.inspect_original_linux_restart(
            exact_original_recovery=object())


def test_inspection_cannot_mint_scm_or_core_grants_or_sign_stop_receipts():
    for identifier in (
        "create_installed_scm_service",
        "mint_publisher_certificate",
        "sign_production_stop",
        "grant_core_pure_compute",
        "enroll_core_health",
        "acknowledge_output",
        "publish_output",
    ):
        assert not hasattr(physical, identifier)
