"""Cognitum-owned OS-local Lu workspace v0 *client* transports.

NO server, model permission, DLC registration, synthetic admission or Lu Core
source changes. Windows authenticates OS-observed named-pipe server PID, process
creation, token user SID and executable-byte SHA against a trusted external
host pin, then the existing read-only Lu HMAC protocol authenticates the Core
session. Image digest is NOT an Authenticode publisher verification. Linux
checks private endpoint owner/mode + post-connect SO_PEERCRED, then the same
Lu HMAC transcript. The installed host must supply trustworthy identity pins,
endpoint, and provisioned package-bound HMAC credentials.

These are native OS client carriers, not production installed Core acceptance.
"""
from __future__ import annotations

import ctypes
import hashlib
import os
from pathlib import Path
import re
import socket
import stat
import struct
import sys

from .lu_ipc_readonly import LuClientRefused, TIMEOUT_SECONDS

PIPE_PREFIX = "\\\\.\\pipe\\"
PIPE_RE = re.compile(r"lu-[A-Za-z0-9_.-]{1,96}\Z", re.ASCII)
HEX64 = re.compile(r"[a-f0-9]{64}\Z", re.ASCII)
SID_RE = re.compile(r"S-1-(?:[0-9]+-){1,15}[0-9]+\Z", re.ASCII)
ERROR_IO_PENDING = 997
ERROR_INSUFFICIENT_BUFFER = 122
WAIT_OBJECT_0 = 0
FILE_FLAG_OVERLAPPED = 0x40000000
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TOKEN_QUERY = 0x0008
OPEN_EXISTING = 3
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
MAX_WINDOWS_READ = 256 * 1024


def _need(ok, why):
    if not ok:
        raise LuClientRefused("Cognitum native Lu IPC refused: " + why)


class NativeOwnedDuplex:
    """Own the socket even when a buffering wrapper has been created."""

    def __init__(self, stream, sock=None):
        self._stream = stream
        self._sock = sock
        self._closed = False

    def read(self, n):
        _need(not self._closed and 1 <= n <= MAX_WINDOWS_READ, "closed/bounded read")
        try:
            return self._stream.read(n)
        except (OSError, TimeoutError) as exc:
            raise LuClientRefused("Cognitum native Lu IPC refused: OS-local read timeout/closed") from exc

    def write(self, data):
        _need(not self._closed and type(data) is bytes and
              0 < len(data) <= MAX_WINDOWS_READ + 4, "closed/bounded write")
        try:
            return self._stream.write(data)
        except (OSError, TimeoutError) as exc:
            raise LuClientRefused("Cognitum native Lu IPC refused: OS-local write timeout/closed") from exc

    def flush(self):
        if callable(getattr(self._stream, "flush", None)):
            self._stream.flush()

    def close(self):
        if not self._closed:
            self._closed = True
            try:
                self._stream.close()
            finally:
                if self._sock is not None:
                    self._sock.close()


def connect_linux_uds(path, *, trusted_core_uid):
    """Real AF_UNIX client; do NOT infer signed package identity from UID.

    A known path and UID must come from the installed owner, not a model. A
    changed inode between preflight and connected identity is refused.
    """
    _need(sys.platform.startswith("linux"), "native Linux UDS only")
    _need(type(path) is str and path.startswith("/") and
          "\x00" not in path and len(path.encode("utf-8")) <= 106,
          "host-pinned absolute UDS path")
    _need(type(trusted_core_uid) is int and trusted_core_uid >= 0,
          "trusted Core UID required")
    try:
        parent = os.lstat(str(Path(path).parent))
        endpoint = os.lstat(path)
    except OSError as exc:
        raise LuClientRefused("Cognitum native Lu IPC refused: endpoint unavailable") from exc
    _need(stat.S_ISDIR(parent.st_mode) and
          parent.st_uid == trusted_core_uid and (parent.st_mode & 0o077) == 0,
          "private Core-owned directory")
    _need(stat.S_ISSOCK(endpoint.st_mode) and
          endpoint.st_uid == trusted_core_uid and (endpoint.st_mode & 0o077) == 0,
          "private Core-owned socket")
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.settimeout(TIMEOUT_SECONDS)
        sock.connect(path)
        raw = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED,
                              struct.calcsize("3i"))
        pid, uid, gid = struct.unpack("3i", raw)
        current = os.lstat(path)
        _need(pid > 0 and uid == trusted_core_uid and
              (current.st_dev, current.st_ino, current.st_uid, current.st_mode) ==
              (endpoint.st_dev, endpoint.st_ino, endpoint.st_uid, endpoint.st_mode),
              "post-connect OS peer/endpoint mismatch")
        return NativeOwnedDuplex(sock.makefile("rwb", buffering=0), sock)
    except BaseException:
        sock.close()
        raise


def _windows_api():
    _need(sys.platform == "win32", "native Windows named pipe only")
    from ctypes import wintypes as wt
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel.WaitNamedPipeW.argtypes = [wt.LPCWSTR, wt.DWORD]
    kernel.WaitNamedPipeW.restype = wt.BOOL
    kernel.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD,
                                    ctypes.c_void_p, wt.DWORD, wt.DWORD, wt.HANDLE]
    kernel.CreateFileW.restype = wt.HANDLE
    kernel.CloseHandle.argtypes = [wt.HANDLE]
    kernel.CloseHandle.restype = wt.BOOL
    kernel.GetNamedPipeServerProcessId.argtypes = [wt.HANDLE, ctypes.POINTER(wt.ULONG)]
    kernel.GetNamedPipeServerProcessId.restype = wt.BOOL
    kernel.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
    kernel.OpenProcess.restype = wt.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD,
                                                   wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
    kernel.QueryFullProcessImageNameW.restype = wt.BOOL
    kernel.GetProcessTimes.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                       ctypes.c_void_p, ctypes.c_void_p]
    kernel.GetProcessTimes.restype = wt.BOOL
    kernel.CreateEventW.argtypes = [ctypes.c_void_p, wt.BOOL, wt.BOOL, wt.LPCWSTR]
    kernel.CreateEventW.restype = wt.HANDLE
    kernel.ReadFile.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD,
                                ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
    kernel.ReadFile.restype = wt.BOOL
    kernel.WriteFile.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD,
                                 ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
    kernel.WriteFile.restype = wt.BOOL
    kernel.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
    kernel.WaitForSingleObject.restype = wt.DWORD
    kernel.GetOverlappedResult.argtypes = [wt.HANDLE, ctypes.c_void_p,
                                           ctypes.POINTER(wt.DWORD), wt.BOOL]
    kernel.GetOverlappedResult.restype = wt.BOOL
    kernel.CancelIoEx.argtypes = [wt.HANDLE, ctypes.c_void_p]
    kernel.CancelIoEx.restype = wt.BOOL
    advapi.OpenProcessToken.argtypes = [wt.HANDLE, wt.DWORD, ctypes.POINTER(wt.HANDLE)]
    advapi.OpenProcessToken.restype = wt.BOOL
    advapi.GetTokenInformation.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                            wt.DWORD, ctypes.POINTER(wt.DWORD)]
    advapi.GetTokenInformation.restype = wt.BOOL
    advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wt.LPWSTR)]
    advapi.ConvertSidToStringSidW.restype = wt.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    return kernel, advapi, wt


def _close(kernel, handle):
    if handle:
        kernel.CloseHandle(handle)


def _pid_identity(pid):
    """OS-observed process identity; data ONLY, not a signer trust decision."""
    kernel, advapi, wt = _windows_api()
    _need(type(pid) is int and 0 < pid <= 0xffffffff, "valid native server PID")
    process = kernel.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    _need(bool(process), "Core process handle refused")
    try:
        buf = ctypes.create_unicode_buffer(32768)
        count = wt.DWORD(len(buf))
        _need(kernel.QueryFullProcessImageNameW(process, 0, buf,
                                                ctypes.byref(count)),
              "Core process executable path unavailable")
        image_path = buf.value
        class FILETIME(ctypes.Structure):
            _fields_ = [("low", wt.DWORD), ("high", wt.DWORD)]
        created = FILETIME()
        exited = FILETIME()
        kernel_time = FILETIME()
        user_time = FILETIME()
        _need(kernel.GetProcessTimes(process, ctypes.byref(created),
                        ctypes.byref(exited), ctypes.byref(kernel_time),
                        ctypes.byref(user_time)), "Core process start time unavailable")
        creation = (created.high << 32) | created.low
        token = wt.HANDLE()
        _need(advapi.OpenProcessToken(process, TOKEN_QUERY, ctypes.byref(token)),
              "Core OS token unavailable")
        try:
            size = wt.DWORD()
            advapi.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
            _need(ctypes.get_last_error() == ERROR_INSUFFICIENT_BUFFER and
                  0 < size.value <= 65536, "Core token user bounds")
            raw = ctypes.create_string_buffer(size.value)
            _need(advapi.GetTokenInformation(token, 1, raw, size,
                                              ctypes.byref(size)), "Core SID unavailable")
            class SID_ATTR(ctypes.Structure):
                _fields_ = [("sid", ctypes.c_void_p), ("attributes", wt.DWORD)]
            sid_addr = ctypes.cast(raw, ctypes.POINTER(SID_ATTR)).contents.sid
            sid_text = wt.LPWSTR()
            _need(advapi.ConvertSidToStringSidW(sid_addr,
                                                  ctypes.byref(sid_text)),
                  "Core SID conversion unavailable")
            try:
                sid = sid_text.value
            finally:
                kernel.LocalFree(ctypes.cast(sid_text, ctypes.c_void_p))
        finally:
            _close(kernel, token)
        try:
            with open(image_path, "rb") as file:
                digest = hashlib.file_digest(file, "sha256").hexdigest()
        except OSError as exc:
            raise LuClientRefused("Cognitum native Lu IPC refused: Core image inaccessible") from exc
        return dict(pid=pid, creation_filetime=creation, user_sid=sid,
                    image_sha256=digest)
    finally:
        _close(kernel, process)


def observe_windows_process(pid):
    """Inspect a native Win32 process for *trusted-host pin preparation only*.

    Never promote values learned from an untrusted pipe to trusted pins.
    An installed host must choose these pins independently from its signer /
    service registry and package attestation.
    """
    return _pid_identity(pid)


class _WinOverlapped(ctypes.Structure):
    _fields_ = [("internal", ctypes.c_void_p),
                ("internal_high", ctypes.c_void_p),
                ("offset", ctypes.c_uint32),
                ("offset_high", ctypes.c_uint32),
                ("event", ctypes.c_void_p)]


class WindowsPipeDuplex:
    """Owner of authenticated-pinned Win32 pipe HANDLE; bounded async I/O."""

    def __init__(self, handle):
        self._handle = handle
        self._closed = False

    def _io(self, payload, n, *, reading):
        _need(not self._closed and 0 < n <= MAX_WINDOWS_READ + 4,
              "closed/bounded Windows pipe I/O")
        kernel, _, wt = _windows_api()
        event = kernel.CreateEventW(None, True, False, None)
        _need(bool(event), "native overlapped event refused")
        overlapped = _WinOverlapped()
        overlapped.event = event
        count = wt.DWORD()
        if reading:
            buf = ctypes.create_string_buffer(n)
            operation = kernel.ReadFile
        else:
            _need(type(payload) is bytes and len(payload) == n,
                  "Windows pipe write bytes")
            buf = ctypes.create_string_buffer(payload, n)
            operation = kernel.WriteFile
        try:
            success = operation(self._handle, buf, n,
                                ctypes.byref(count), ctypes.byref(overlapped))
            if not success:
                _need(ctypes.get_last_error() == ERROR_IO_PENDING,
                      "native overlapped pipe read/write refused")
                waiting = kernel.WaitForSingleObject(event,
                              int(TIMEOUT_SECONDS * 1000))
                if waiting != WAIT_OBJECT_0:
                    kernel.CancelIoEx(self._handle, ctypes.byref(overlapped))
                    self.close()
                    raise LuClientRefused("Cognitum native Lu IPC refused: pipe I/O timeout")
                _need(kernel.GetOverlappedResult(self._handle,
                        ctypes.byref(overlapped),ctypes.byref(count),False),
                      "native overlapped completion refused")
            _need(0 < count.value <= n, "pipe disconnected/empty result")
            return bytes(buf.raw[:count.value]) if reading else count.value
        finally:
            _close(kernel, event)

    def read(self, n):
        return self._io(None,n,reading=True)

    def write(self, data):
        _need(type(data) is bytes, "native pipe write type")
        return self._io(data,len(data),reading=False)

    def flush(self):
        return None

    def close(self):
        if not self._closed:
            self._closed = True
            kernel, _, _ = _windows_api()
            _close(kernel, self._handle)


def connect_windows_named_pipe(path, *, trusted_core_process_pin):
    """Win32 client-only CreateFileW/ReadFile/WriteFile/OS server identity.

    Pin is independently supplied by the installed host. A matching PID, SID,
    creation time and executable hash are still not Authenticode verification.
    Only Core-owned signed enrollment + HMAC handshake may admit IPC.
    """
    kernel, _, wt = _windows_api()
    _need(type(path) is str and path.startswith(PIPE_PREFIX) and
          PIPE_RE.fullmatch(path[len(PIPE_PREFIX):]) is not None,
          "trusted local Lu named-pipe path")
    pin = trusted_core_process_pin
    _need(type(pin) is dict and set(pin) ==
          {"pid", "creation_filetime", "user_sid", "image_sha256"},
          "host-selected Core process identity pin")
    _need(type(pin["pid"]) is int and pin["pid"] > 0 and
          type(pin["creation_filetime"]) is int and
          pin["creation_filetime"] > 0 and
          type(pin["user_sid"]) is str and SID_RE.fullmatch(pin["user_sid"]) and
          type(pin["image_sha256"]) is str and
          HEX64.fullmatch(pin["image_sha256"]),
          "complete independent process pin required")
    _need(kernel.WaitNamedPipeW(path, int(TIMEOUT_SECONDS * 1000)),
          "trusted named-pipe endpoint absent")
    handle = kernel.CreateFileW(path,GENERIC_READ|GENERIC_WRITE,0,
                                None,OPEN_EXISTING,FILE_FLAG_OVERLAPPED,None)
    invalid = ctypes.c_void_p(-1).value
    _need(handle and handle != invalid, "native pipe connection refused")
    try:
        actual_pid = wt.ULONG()
        _need(kernel.GetNamedPipeServerProcessId(handle,ctypes.byref(actual_pid)),
              "OS named-pipe server PID unavailable")
        _need(actual_pid.value == pin["pid"], "named-pipe Core server PID mismatch")
        actual = _pid_identity(actual_pid.value)
        _need(actual == pin, "OS server identity, image or creation mismatch")
        return WindowsPipeDuplex(handle)
    except BaseException:
        _close(kernel,handle)
        raise


def installed_core_health_preflight(*, endpoint, enrolled_key, package_hash,
                                    expected_uid=None, windows_process_pin=None):
    """Host-supplied installed endpoint attempt; NEVER auto-discovers secrets.

    No secret environment variables, fixed /tmp path, automatic test server,
    fallback to user-controlled certificate, or unpinned connection. Fail
    closed if genuine host contract is not available.
    """
    from .lu_ipc_readonly import (
        AuthenticatedReadOnlyLuClient, _key, _package_digest,
    )
    # Reject unenrolled material before connecting to any OS endpoint.
    _key(enrolled_key)
    _package_digest(package_hash)
    if sys.platform == "win32":
        carrier = connect_windows_named_pipe(
            endpoint, trusted_core_process_pin=windows_process_pin)
    elif sys.platform.startswith("linux"):
        carrier = connect_linux_uds(endpoint,trusted_core_uid=expected_uid)
    else:
        raise LuClientRefused("unsupported OS-local Lu transport")
    client = None
    try:
        client = AuthenticatedReadOnlyLuClient(carrier,
             enrolled_key=enrolled_key, installed_package_sha256=package_hash)
        handshake = client.handshake()
        health = client.health()
        _need(handshake["authenticated"] and
              health["authenticated_transport_session"],
              "missing original Lu authenticated health session")
        return dict(
            handshake=handshake, health=health,
            native_os_transport_path_selected=True,
            core_health_module_verified=health["module_id"] == "lu.core",
            core_service_connected=health["connected"],
            # The native peer and HMAC transcript alone cannot distinguish
            # fixture credentials from independently installed Core custody.
            source_fixture_excluded=False,
            real_installed_core_evidence_supplied_by_host=False,
            installed_signed_publisher_verified_by_client=False,
            accepted_lu_core_issuer_receipt_contract=False,
            genuine_per_turn_pure_compute_grant_verified=False,
            independent_revision_authority_verified=False,
            installed_acceptance="BLOCKED_CORE_ISSUER_AND_ENROLLMENT",
            model_tool_execution_authorized=False,
            output_delivery_authorized=False,
            output_acknowledgment_authorized=False,
        )
    finally:
        if client is not None:
            client.close()
        else:
            carrier.close()
