"""Production-only SSM numerical child entrypoint, never a service or Core issuer.

The accepted R3-R1 installed service is deliberately *no-worker*. This source
is for its future, independently signed successor, NOT a hot patch to the
installed release. Only a native SCM supervisor may launch this fixed image
CREATE_SUSPENDED, attach it to its kill-on-close Job, verify token and pinned
files BEFORE resuming, and reconcile every original operation. This child
checks its own genuine Windows AppContainer token again before even parsing
the frame; it never authorizes numerical output to Lu.

No test-only PID, fake token, dynamic profile selection, network capability,
credential provisioning or SYSTEM-token fallback is accepted.
"""
from __future__ import annotations

import sys

# Installer/native host must independently provision EXACTLY this profile to
# a nonadministrator local account; it is not created by Python.
PROFILE = "CognitumSsmProductionV1"


class ProductionSSMRefused(RuntimeError):
    """No mathematical request has been read or admitted."""


def _need(ok: bool, reason: str) -> None:
    if not ok:
        raise ProductionSSMRefused("Cognitum protected production SSM refused: " + reason)


def require_genuine_appcontainer() -> None:
    """Inspect the executing process's kernel token; accept no caller claims."""
    _need(sys.platform == "win32", "native Windows worker required")
    import ctypes
    from ctypes import wintypes

    H = wintypes.HANDLE
    DWORD = wintypes.DWORD
    PVOID = ctypes.c_void_p
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    userenv = ctypes.WinDLL("userenv", use_last_error=True)

    kernel.GetCurrentProcess.argtypes = []
    kernel.GetCurrentProcess.restype = H
    kernel.LocalFree.argtypes = [PVOID]
    kernel.IsProcessInJob.argtypes = [H, H, ctypes.POINTER(wintypes.BOOL)]
    kernel.IsProcessInJob.restype = wintypes.BOOL
    kernel.LocalFree.restype = PVOID
    advapi.OpenProcessToken.argtypes = [H, DWORD, ctypes.POINTER(H)]
    advapi.OpenProcessToken.restype = wintypes.BOOL
    advapi.GetTokenInformation.argtypes = [
        H, DWORD, PVOID, DWORD, ctypes.POINTER(DWORD)
    ]
    advapi.GetTokenInformation.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [H]
    kernel.CloseHandle.restype = wintypes.BOOL
    advapi.IsWellKnownSid.argtypes = [PVOID, DWORD]
    advapi.IsWellKnownSid.restype = wintypes.BOOL
    advapi.EqualSid.argtypes = [PVOID, PVOID]
    advapi.EqualSid.restype = wintypes.BOOL
    advapi.ConvertSidToStringSidW.argtypes = [
        PVOID, ctypes.POINTER(PVOID)
    ]
    advapi.ConvertSidToStringSidW.restype = wintypes.BOOL
    advapi.FreeSid.argtypes = [PVOID]
    advapi.FreeSid.restype = PVOID
    userenv.DeriveAppContainerSidFromAppContainerName.argtypes = [
        wintypes.LPCWSTR, ctypes.POINTER(PVOID)
    ]
    userenv.DeriveAppContainerSidFromAppContainerName.restype = wintypes.LONG

    # A Job is necessary, but not sufficient: only the native service may
    # attest that THIS Job is its protected kill-on-close job before resume.
    job_member = wintypes.BOOL()
    _need(bool(kernel.IsProcessInJob(kernel.GetCurrentProcess(), H(),
                                    ctypes.byref(job_member))) and
          bool(job_member.value), "native Windows Job membership required")

    token = H()
    _need(bool(advapi.OpenProcessToken(kernel.GetCurrentProcess(), 0x0008,
                                     ctypes.byref(token))),
          "current worker token unavailable")

    def token_info(kind: int, lower_bound: int = 4):
        size = DWORD()
        advapi.GetTokenInformation(token, kind, None, 0, ctypes.byref(size))
        _need(lower_bound <= size.value <= 4096, "bounded OS token data absent")
        data = ctypes.create_string_buffer(size.value)
        _need(bool(advapi.GetTokenInformation(
            token, kind, ctypes.cast(data, PVOID),
            size.value, ctypes.byref(size)
        )), "kernel token query failed")
        return data

    try:
        # TOKEN_INFORMATION_CLASS: TokenIsAppContainer=29, TokenCapabilities=30,
        # TokenAppContainerSid=31, TokenElevation=20, TokenUser=1.
        app = token_info(29)
        _need(ctypes.c_uint32.from_buffer(app).value == 1,
              "TokenIsAppContainer was not true")
        elevation = token_info(20)
        _need(ctypes.c_uint32.from_buffer(elevation).value == 0,
              "worker has an elevated token")
        caps = token_info(30)
        _need(ctypes.c_uint32.from_buffer(caps).value == 0,
              "AppContainer capabilities, including network, are forbidden")

        user = token_info(1, ctypes.sizeof(PVOID))
        user_sid = PVOID.from_buffer(user).value
        _need(bool(user_sid) and not advapi.IsWellKnownSid(PVOID(user_sid), 22),
              "LocalSystem or missing TokenUser refused")
        raw_sid = PVOID()
        _need(bool(advapi.ConvertSidToStringSidW(
            PVOID(user_sid), ctypes.byref(raw_sid)
        )), "TokenUser SID unavailable")
        try:
            user_name = ctypes.wstring_at(raw_sid)
        finally:
            kernel.LocalFree(raw_sid)
        _need(user_name.startswith("S-1-5-21-") and len(user_name) <= 96,
              "expected local standard-user account token missing")

        package = token_info(31, ctypes.sizeof(PVOID))
        actual_sid = PVOID.from_buffer(package).value
        _need(bool(actual_sid), "AppContainer package SID absent")
        pinned_sid = PVOID()
        _need(userenv.DeriveAppContainerSidFromAppContainerName(
            PROFILE, ctypes.byref(pinned_sid)
        ) == 0 and bool(pinned_sid), "fixed production profile SID unavailable")
        try:
            _need(bool(advapi.EqualSid(PVOID(actual_sid), pinned_sid)),
                  "AppContainer SID does not equal fixed production profile")
        finally:
            advapi.FreeSid(pinned_sid)
    finally:
        kernel.CloseHandle(token)


def main() -> int:
    try:
        # Absolutely no filesystem, argv, Python scientific import or request
        # decoding happens until the real kernel token is admitted.
        require_genuine_appcontainer()
    except (ProductionSSMRefused, OSError, ValueError):
        return 4

    # This is the already-reviewed fixed mathematical operation. It emits an
    # untrusted numerical candidate only; native host still validates
    # cancellation, SCM Job emptiness, original grant and durable receipts.
    from pathlib import Path
    project_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root))
    from cognitum.mel.ssm_r5_fixed_child import main as fixed_math
    return fixed_math()


if __name__ == "__main__":
    raise SystemExit(main())
