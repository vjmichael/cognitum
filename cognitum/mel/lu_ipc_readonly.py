"""COG-LU-IPC-01A-R1: bounded Lu workspace v0 authenticated read-only client.

Cognitum-side only; byte-stream framing and proof transcript match the pinned
Lu workspace_ipc.rs + workspace_ipc_transport.rs source. This module DOES NOT
create a server, announce a capability, issue a grant, invoke a tool, or start
model inference. It does not claim OS/package identity from an HMAC alone.

An installed trusted host must supply the OS-local connection, independently
approved 32-byte package hash and enrolled 32-byte session key. The only
post-auth operation accepted here is HealthRequest->HealthReport. Genuine Lu
Core Health dispatch and installer-enrolled credentials remain pending (#245,
#248). Tests with an in-process responder are contract tests, NOT Core tests.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import socket
import stat
import struct
import sys

from google.protobuf.message import DecodeError

from .vendor.lu.workspace.v0 import workspace_pb2 as pb

MODULE = "cognitum.mel"
MAX_FRAME = 256 * 1024
MAX_REQUEST_ID = 128
WIRE_MAJOR = 1
WIRE_MINOR = 0
TIMEOUT_SECONDS = 3.0
CLIENT_DOMAIN = b"lu.workspace.client.v0\x00"
SERVER_DOMAIN = b"lu.workspace.server.v0\x00"
REF_RE = re.compile(r"[A-Za-z0-9_.:/-]{1,128}\Z", re.ASCII)


class LuClientRefused(ValueError):
    pass


def _need(test, reason):
    if not test:
        raise LuClientRefused("Cognitum read-only Lu IPC refused: " + reason)


def _ref(value, what):
    _need(type(value) is str and REF_RE.fullmatch(value) is not None,
          what + " must be a bounded reference")
    return value


def _key(key):
    _need(type(key) is bytes and len(key) == 32 and any(key),
          "verified externally enrolled 32-byte handshake key required")
    return key


def _package_digest(value):
    _need(type(value) is bytes and len(value) == 32 and any(value),
          "host-attested installed package SHA-256 required")
    return value


def _mac(key, *parts):
    digest = hmac.new(key, digestmod=hashlib.sha256)
    for part in parts:
        digest.update(part)
    return digest.digest()


def _serialize(message):
    data = message.SerializeToString(deterministic=True)
    _need(0 < len(data) <= MAX_FRAME, "frame byte budget")
    return data


def _validate_frame(frame, expected_body, *, handshake, session=""):
    _need(type(frame) is pb.WorkspaceFrame and
          frame.protocol_major == WIRE_MAJOR and
          frame.protocol_minor == WIRE_MINOR and
          frame.sequence == 0, "wire version or event sequence")
    _ref(frame.request_id, "request ID")
    _need(frame.WhichOneof("body") == expected_body, "unexpected frame kind")
    if handshake:
        _need(frame.session_ref == "" or
              (expected_body == "welcome" and
               REF_RE.fullmatch(frame.session_ref) is not None),
              "untrusted handshake session")
    else:
        _need(frame.session_ref == session, "post-handshake session mismatch")
    return frame


class _Stream:
    """Strict bounded four-byte big-endian Lu framing over host-owned I/O."""

    def __init__(self, io):
        _need(callable(getattr(io, "read", None)) and
              callable(getattr(io, "write", None)), "host-owned byte stream required")
        self.io = io

    def _read_exact(self, n):
        chunks = bytearray()
        while len(chunks) < n:
            part = self.io.read(n - len(chunks))
            _need(type(part) is bytes and len(part) > 0 and
                  len(part) <= n - len(chunks), "truncated or invalid transport read")
            chunks.extend(part)
        return bytes(chunks)

    def recv(self):
        count = struct.unpack(">I", self._read_exact(4))[0]
        _need(0 < count <= MAX_FRAME, "bounded nonempty frame length")
        body = self._read_exact(count)
        message = pb.WorkspaceFrame()
        try:
            message.ParseFromString(body)
            message.DiscardUnknownFields()
        except (DecodeError, ValueError, RecursionError) as exc:
            raise LuClientRefused("Cognitum read-only Lu IPC refused: malformed Protobuf") from exc
        _need(_serialize(message) == body,
              "noncanonical/unknown Protobuf data refused")
        return message

    def send(self, message):
        data = _serialize(message)
        header = struct.pack(">I", len(data))
        frame = header + data
        offset = 0
        while offset < len(frame):
            n = self.io.write(frame[offset:])
            _need(type(n) is int and 0 < n <= len(frame) - offset,
                  "failed bounded transport write")
            offset += n
        if callable(getattr(self.io, "flush", None)):
            self.io.flush()


def _frame(request_id, body, kind, *, session=""):
    frame = pb.WorkspaceFrame(
        protocol_major=WIRE_MAJOR,
        protocol_minor=WIRE_MINOR,
        request_id=_ref(request_id, "request ID"),
        session_ref=session,
        sequence=0,
    )
    getattr(frame, kind).CopyFrom(body)
    return frame


class AuthenticatedReadOnlyLuClient:
    """Source-compatible Lu client handshake + Health exchange only.

    The caller provides a pre-connected OS-local duplex stream and *trusted*
    external enrollment material. This does not inspect/attest Windows package
    identity or Linux service ownership; the installer/host must do so.
    """

    def __init__(self, stream, *, enrolled_key, installed_package_sha256):
        self._io = _Stream(stream)
        self._key = _key(enrolled_key)
        self._package = _package_digest(installed_package_sha256)
        self._session = None
        self._core_epoch = None
        self._closed = False
        self._used_ids = set()

    @property
    def authenticated(self):
        return not self._closed and self._session is not None

    @property
    def session_ref(self):
        return self._session

    def _request_id(self):
        _need(len(self._used_ids) < 128, "bounded client request count")
        request_id = os.urandom(16).hex()
        while request_id in self._used_ids:
            request_id = os.urandom(16).hex()
        self._used_ids.add(request_id)
        return request_id

    def handshake(self, *, client_nonce=None):
        _need(not self._closed and self._session is None,
              "one-time handshake required")
        nonce = os.urandom(32) if client_nonce is None else client_nonce
        _need(type(nonce) is bytes and len(nonce) == 32 and any(nonce),
              "nonzero 32-byte client nonce")
        request = self._request_id()
        hello = _frame(request, pb.Hello(
            claimed_module_id=MODULE,
            claimed_role=pb.MODULE_ROLE_CORE_EXTENSION,
            claimed_package_sha256=self._package,
            minimum_major=WIRE_MAJOR,
            maximum_major=WIRE_MAJOR,
            maximum_minor=WIRE_MINOR,
            client_nonce=nonce,
        ), "hello")
        hello_bytes = _serialize(hello)
        self._io.send(hello)
        challenge = _validate_frame(self._io.recv(), "auth_challenge",
                                    handshake=True)
        _need(challenge.request_id == request and
              len(challenge.auth_challenge.server_nonce) == 32 and
              any(challenge.auth_challenge.server_nonce),
              "unmatched or weak host challenge")
        server_nonce = challenge.auth_challenge.server_nonce
        proof = _mac(self._key, CLIENT_DOMAIN, hello_bytes, server_nonce)
        self._io.send(_frame(request, pb.AuthProof(
            client_hmac_sha256=proof), "auth_proof"))
        welcome_frame = _validate_frame(self._io.recv(), "welcome",
                                        handshake=True)
        welcome = welcome_frame.welcome
        _need(welcome_frame.request_id == request and
              welcome.selected_major == WIRE_MAJOR and
              welcome.selected_minor == WIRE_MINOR and
              type(welcome.server_hmac_sha256) is bytes and
              len(welcome.server_hmac_sha256) == 32,
              "wrong welcome version, identity or MAC")
        _ref(welcome_frame.session_ref, "host session")
        _ref(welcome.core_epoch_ref, "host epoch")
        _need(len(welcome.enabled_features) <= 32 and
              all(REF_RE.fullmatch(f) is not None and len(f) <= 96
                  for f in welcome.enabled_features),
              "unapproved feature labels")
        unsigned = pb.Welcome()
        unsigned.CopyFrom(welcome)
        unsigned.ClearField("server_hmac_sha256")
        expected = _mac(self._key, SERVER_DOMAIN, hello_bytes, server_nonce,
                        welcome_frame.session_ref.encode("utf-8"),
                        unsigned.SerializeToString(deterministic=True))
        _need(hmac.compare_digest(welcome.server_hmac_sha256, expected),
              "server-authentication HMAC mismatch")
        self._session = welcome_frame.session_ref
        self._core_epoch = welcome.core_epoch_ref
        return dict(authenticated=True,
                    module_id=MODULE,
                    session_ref=self._session,
                    core_epoch_ref=self._core_epoch,
                    provider_registered=False,
                    tool_invocation_authorized=False,
                    os_peer_installed_qualified=False)

    def health(self):
        _need(self.authenticated, "authenticated session required")
        request = self._request_id()
        self._io.send(_frame(request, pb.HealthRequest(),
                             "health", session=self._session))
        report_frame = _validate_frame(self._io.recv(), "health_report",
                                       handshake=False, session=self._session)
        _need(report_frame.request_id == request,
              "health request correlation mismatch")
        report = report_frame.health_report
        _ref(report.module_id, "health module")
        _need(type(report.connected) is bool and
              type(report.status_code) is str and
              0 < len(report.status_code) <= 96 and
              REF_RE.fullmatch(report.status_code) is not None and
              report.epoch > 0, "invalid health report")
        return dict(module_id=report.module_id,connected=report.connected,
                    status_code=report.status_code,epoch=report.epoch,
                    authenticated_transport_session=True,
                    real_installed_core_verified=False,
                    tool_invocation_authorized=False)

    def close(self):
        self._closed = True
        self._session = None
        self._key = None
        self._package = None
        if callable(getattr(self._io.io, "close", None)):
            self._io.io.close()


def connect_linux_unix_socket(path, *, expected_uid):
    """Client-only OS-local socket opening; no server or implicit grant.

    Host independently selects a trusted endpoint, UID and enrollment key.
    Kernel peer UID confirms account only, NOT signed package identity.
    """
    _need(sys.platform.startswith("linux"), "Linux UDS only")
    _need(type(expected_uid) is int and expected_uid >= 0,
          "trusted expected Core service UID required")
    _need(type(path) is str and path.startswith("/") and "\x00" not in path,
          "host-owned absolute endpoint path required")
    parent = os.path.dirname(path)
    p = os.lstat(parent)
    sock_stat = os.lstat(path)
    _need(stat.S_ISDIR(p.st_mode) and not stat.S_ISLNK(p.st_mode)
          and p.st_uid == expected_uid and p.st_mode & 0o077 == 0,
          "untrusted endpoint directory")
    _need(stat.S_ISSOCK(sock_stat.st_mode) and
          sock_stat.st_uid == expected_uid and
          sock_stat.st_mode & 0o077 == 0,
          "untrusted socket identity")
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.settimeout(TIMEOUT_SECONDS)
        sock.connect(path)
        cred = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED,
                               struct.calcsize("3i"))
        _pid, uid, _gid = struct.unpack("3i", cred)
        _need(uid == expected_uid, "kernel observed Core peer UID mismatch")
        return sock.makefile("rwb", buffering=0)
    except BaseException:
        sock.close()
        raise
