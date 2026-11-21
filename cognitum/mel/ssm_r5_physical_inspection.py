"""Read-only physical-host observations for Cognitum R5 acceptance.

This module deliberately does not install/start a service, create an issuer,
import a signing key, grant a Lu capability, or publish SSM output. A host may
observe a real Windows SCM service image and a genuine Linux cgroup2
delegation, but these *observations* are not installed publisher enrollment,
SCM-owned execution/stop receipts or independently signed Core authorization.

Acceptance needs separate signed installer/publisher evidence and a Core
enrollment contract. Never accept a host-supplied image hash or a locally
generated public key as an independent authority.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import re
import sys

from .ssm_r4_protected import NativeSSMCustodyRefused
from .ssm_r5_stop_receipt import _valid_sha


_SERVICE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,95}\Z", re.ASCII)
SC_MANAGER_CONNECT = 0x0001
SERVICE_QUERY_CONFIG = 0x0001
SERVICE_QUERY_STATUS = 0x0004
SC_STATUS_PROCESS_INFO = 0
SERVICE_WIN32_OWN_PROCESS = 0x0010
SERVICE_RUNNING = 0x0004
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SERVICE_CONFIG_SERVICE_SID_INFO = 5
MAX_CONFIG_BYTES = 16384


def _need(condition, detail):
    if not condition:
        raise NativeSSMCustodyRefused(
            "Cognitum physical custody refused: " + detail)


def _pin_service(name, image_path, image_sha256, config_command, account,
                 expected_sid_type):
    _need(type(name) is str and _SERVICE_NAME.fullmatch(name) is not None,
          "reviewed exact SCM service name required")
    _need(type(image_path) is str and Path(image_path).is_absolute() and
          not Path(image_path).is_symlink(),
          "reviewed absolute SCM service executable path")
    _need(_valid_sha(image_sha256), "reviewed executable SHA256 pin")
    _need(type(config_command) is str and
          1 <= len(config_command) <= 4096 and "\x00" not in config_command,
          "reviewed exact SCM command-line configuration")
    _need(type(account) is str and
          1 <= len(account) <= 256 and "\x00" not in account,
          "reviewed exact service account")
    _need(type(expected_sid_type) is int and expected_sid_type in (1, 3),
          "reviewed unrestricted or restricted service SID type")
    return image_path


def inspect_running_windows_scm(*, trusted_service_name,
                                trusted_image_path, trusted_image_sha256,
                                trusted_binary_command,
                                trusted_service_account,
                                trusted_service_sid_type):
    """Observe SCM+kernel process; never claim independent service publisher.

    The six pins MUST come from an installed owner whose signed manifest was
    independently validated beforehand. This function does not establish that
    fact. Reject a shared-process service, missing service SID, stopped service,
    process restart race, binary mismatch or unavailable process query.
    """
    _need(sys.platform == "win32", "Windows SCM kernel required")
    _pin_service(trusted_service_name, trusted_image_path,
                 trusted_image_sha256, trusted_binary_command,
                 trusted_service_account, trusted_service_sid_type)

    from ctypes import wintypes as w
    from .lu_ipc_windows_job_probe import _image_sha

    class SERVICE_STATUS_PROCESS(ctypes.Structure):
        _fields_ = [(name, w.DWORD) for name in (
            "dwServiceType", "dwCurrentState", "dwControlsAccepted",
            "dwWin32ExitCode", "dwServiceSpecificExitCode",
            "dwCheckPoint", "dwWaitHint", "dwProcessId", "dwServiceFlags")]

    class QUERY_SERVICE_CONFIG(ctypes.Structure):
        _fields_ = [
            ("dwServiceType", w.DWORD), ("dwStartType", w.DWORD),
            ("dwErrorControl", w.DWORD),
            ("lpBinaryPathName", w.LPWSTR), ("lpLoadOrderGroup", w.LPWSTR),
            ("dwTagId", w.DWORD), ("lpDependencies", w.LPWSTR),
            ("lpServiceStartName", w.LPWSTR), ("lpDisplayName", w.LPWSTR),
        ]

    class FILETIME(ctypes.Structure):
        _fields_ = [("dwLowDateTime", w.DWORD),
                    ("dwHighDateTime", w.DWORD)]

    a = ctypes.WinDLL("advapi32", use_last_error=True)
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    a.OpenSCManagerW.argtypes = [w.LPCWSTR, w.LPCWSTR, w.DWORD]
    a.OpenSCManagerW.restype = w.HANDLE
    a.OpenServiceW.argtypes = [w.HANDLE, w.LPCWSTR, w.DWORD]
    a.OpenServiceW.restype = w.HANDLE
    a.QueryServiceStatusEx.argtypes = [
        w.HANDLE, w.DWORD, ctypes.c_void_p, w.DWORD,
        ctypes.POINTER(w.DWORD)]
    a.QueryServiceStatusEx.restype = w.BOOL
    a.QueryServiceConfigW.argtypes = [
        w.HANDLE, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD)]
    a.QueryServiceConfigW.restype = w.BOOL
    a.QueryServiceConfig2W.argtypes = [
        w.HANDLE, w.DWORD, ctypes.c_void_p, w.DWORD,
        ctypes.POINTER(w.DWORD)]
    a.QueryServiceConfig2W.restype = w.BOOL
    a.CloseServiceHandle.argtypes = [w.HANDLE]
    a.CloseServiceHandle.restype = w.BOOL
    k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    k.OpenProcess.restype = w.HANDLE
    k.QueryFullProcessImageNameW.argtypes = [
        w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)]
    k.QueryFullProcessImageNameW.restype = w.BOOL
    k.GetProcessTimes.argtypes = [
        w.HANDLE, ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME)]
    k.GetProcessTimes.restype = w.BOOL
    k.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
    k.GetExitCodeProcess.restype = w.BOOL
    k.CloseHandle.argtypes = [w.HANDLE]
    k.CloseHandle.restype = w.BOOL

    manager = a.OpenSCManagerW(None, None, SC_MANAGER_CONNECT)
    _need(bool(manager), "SCM read-only access unavailable")
    service = None
    process = None
    try:
        service = a.OpenServiceW(
            manager, trusted_service_name, SERVICE_QUERY_CONFIG |
            SERVICE_QUERY_STATUS)
        _need(bool(service), "reviewed Cognitum service is not installed")
        needed = w.DWORD()

        def current_status():
            status = SERVICE_STATUS_PROCESS()
            _need(bool(a.QueryServiceStatusEx(
                service, SC_STATUS_PROCESS_INFO, ctypes.byref(status),
                ctypes.sizeof(status), ctypes.byref(needed))),
                "OS SCM process status unavailable")
            _need(status.dwServiceType == SERVICE_WIN32_OWN_PROCESS and
                  status.dwCurrentState == SERVICE_RUNNING and
                  status.dwProcessId > 0,
                  "running, dedicated SCM process required")
            return status

        first = current_status()
        config_storage = ctypes.create_string_buffer(MAX_CONFIG_BYTES)
        _need(bool(a.QueryServiceConfigW(
            service, ctypes.byref(config_storage), MAX_CONFIG_BYTES,
            ctypes.byref(needed))),
            "exact installed SCM service configuration unavailable")
        config = ctypes.cast(
            config_storage, ctypes.POINTER(QUERY_SERVICE_CONFIG)).contents
        _need(config.dwServiceType == SERVICE_WIN32_OWN_PROCESS and
              config.lpBinaryPathName == trusted_binary_command and
              config.lpServiceStartName == trusted_service_account,
              "SCM executable command or installed service identity mismatch")
        sid_setting = w.DWORD()
        _need(bool(a.QueryServiceConfig2W(
            service, SERVICE_CONFIG_SERVICE_SID_INFO,
            ctypes.byref(sid_setting), ctypes.sizeof(sid_setting),
            ctypes.byref(needed))) and
            sid_setting.value == trusted_service_sid_type,
            "service SID configuration missing or altered")

        process = k.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, first.dwProcessId)
        _need(bool(process), "kernel SCM process handle unavailable")
        path_buffer = ctypes.create_unicode_buffer(32768)
        path_length = w.DWORD(len(path_buffer))
        _need(bool(k.QueryFullProcessImageNameW(
            process, 0, path_buffer, ctypes.byref(path_length))) and
            path_length.value > 0,
            "kernel process executable image unavailable")
        observed_image = path_buffer.value
        _need(os.path.normcase(os.path.abspath(observed_image)) ==
              os.path.normcase(os.path.abspath(trusted_image_path)),
              "SCM process executable differs from independently pinned image")
        born = FILETIME()
        exit_at = FILETIME()
        kernel = FILETIME()
        user = FILETIME()
        _need(bool(k.GetProcessTimes(
            process, ctypes.byref(born), ctypes.byref(exit_at),
            ctypes.byref(kernel), ctypes.byref(user))),
            "kernel process creation time unavailable")
        created = (int(born.dwHighDateTime) << 32) | int(born.dwLowDateTime)
        _need(created > 0, "native SCM process creation identity unavailable")
        code = w.DWORD()
        _need(bool(k.GetExitCodeProcess(
            process, ctypes.byref(code))) and code.value == 259,
            "SCM process exited during observation")
        _need(_image_sha(observed_image) == trusted_image_sha256,
              "SCM executable image changed from pinned package source")
        last = current_status()
        _need(last.dwProcessId == first.dwProcessId and
              last.dwCurrentState == first.dwCurrentState,
              "SCM service process changed during observation")
        return {
            "schema": "cognitum.ssm_r5.scm_kernel_observation.v1",
            "status": "PASS_SCM_KERNEL_OBSERVATION_ONLY",
            "service_name": trusted_service_name,
            "service_pid": int(first.dwProcessId),
            "kernel_creation_filetime": created,
            "executable_sha256": trusted_image_sha256,
            "service_sid_configuration_observed": int(sid_setting.value),
            "configuration_pins_match": True,
            "running_process_image_matches": True,
            "installed_publisher_signature_independently_verified": False,
            "scm_service_owned_worker_job_verified": False,
            "independent_stop_signer_custody_verified": False,
            "installed_core_enrollment_verified": False,
            "real_core_health_exchange_verified": False,
            "model_tool_execution_authorized": False,
            "outbox_delivery_authorized": False,
        }
    finally:
        if process:
            k.CloseHandle(process)
        if service:
            a.CloseServiceHandle(service)
        a.CloseServiceHandle(manager)


def inspect_existing_linux_delegation(*, trusted_delegated_root):
    """Inspect actual kernel mount/delegation; no fabricated kernel fixture."""
    _need(sys.platform.startswith("linux"), "Linux kernel cgroup-v2 required")
    _need(type(trusted_delegated_root) is str and
          Path(trusted_delegated_root).is_absolute() and
          not Path(trusted_delegated_root).is_symlink(),
          "externally selected absolute cgroup delegation root")
    from cognitum.cgroup2_contract import preflight
    observed = preflight(trusted_delegated_root)
    return {
        "schema": "cognitum.ssm_r5.kernel_cgroup_preflight.v1",
        "status": ("DELEGATED_FIXTURE_SCOPE_POSSIBLE_NOT_INSTALLED"
                   if observed.admitted_for_fixture else "BLOCKED_DELEGATION"),
        "reason": observed.reason,
        "kernel_cgroup_v2_observed": bool(observed.kernel_cgroup2),
        "root_writable": bool(observed.writable),
        "cgroup_kill_available": bool(observed.scope_kill_supported),
        "positive_original_job_restart_proven": False,
        "installed_linux_service_manager_verified": False,
        "independent_signed_stop_proven": False,
        "automatic_replay_authorized": False,
        "real_core_health_exchange_verified": False,
        "outbox_delivery_authorized": False,
    }


def inspect_original_linux_restart(*, exact_original_recovery):
    """Read-only R5 original-linked restart: may not execute cgroup.kill."""
    _need(sys.platform.startswith("linux"), "Linux kernel required")
    from .ssm_r5_linux_recovery import OriginalLinuxCgroupRecovery
    _need(type(exact_original_recovery) is OriginalLinuxCgroupRecovery,
          "genuine original-bound recovery adapter required")
    result = exact_original_recovery.reconcile_after_restart(execute=False)
    _need(result["original_operation_bound"] is True and
          result["automatic_original_reexecution_authorized"] is False and
          result["installed_service_stop_verified"] is False and
          result["output_delivery_authorized"] is False,
          "untrusted original recovery observation")
    return result
