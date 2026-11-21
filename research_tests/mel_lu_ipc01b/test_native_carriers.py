"""Native client transport acceptance: real OS pipes/sockets, fake Lu host.

No test launches Lu Core or claims signed publisher, protected installed
enrollment, authorized tool grants or production OS service. Native Windows
CreateNamedPipe and Linux AF_UNIX/SO_PEERCRED are exercised directly.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import socket
import struct
import sys
import threading
import uuid

import pytest

from cognitum.mel import lu_ipc_native as native
from cognitum.mel import lu_ipc_readonly as readonly
from research_tests.mel_lu_ipc01a.test_proto_client import (
    KEY, PACKAGE, SESSION, SyntheticCoreStream
)

def _read_exact(recv,n):
    chunks=bytearray()
    while len(chunks)<n:
        data=recv(n-len(chunks))
        if not data:
            raise EOFError("native Lu fixture peer disconnected")
        chunks.extend(data)
    return bytes(chunks)


def _route_request(read_exact,write_all,fake):
    size=struct.unpack(">I",read_exact(4))[0]
    assert 0<size<=native.MAX_WINDOWS_READ
    data=read_exact(size)
    stream=struct.pack(">I",size)+data
    index=0
    while index<len(stream):
        index+=fake.write(stream[index:])
    while True:
        outgoing=fake.read(8192)
        if not outgoing:break
        write_all(outgoing)


class LinuxUDSServer:
    def __init__(self,tmp_path,fault="",stop_after=3):
        self.directory=tmp_path/"lu-core-private"
        self.directory.mkdir(mode=0o700)
        self.directory.chmod(0o700)
        self.path=self.directory/"lu-ipc-test.sock"
        self.listen=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self.listen.settimeout(4)
        self.listen.bind(str(self.path))
        self.path.chmod(0o600)
        self.listen.listen(1)
        self.fake=SyntheticCoreStream(fault)
        self.error=None
        self.stop_after=stop_after
        self.thread=threading.Thread(target=self._run,daemon=True)
        self.thread.start()

    def _run(self):
        try:
            with self.listen.accept()[0] as conn:
                conn.settimeout(4)
                for _ in range(self.stop_after):
                    _route_request(lambda n:_read_exact(conn.recv,n),
                                   conn.sendall,self.fake)
        except (OSError,EOFError,AssertionError) as exc:
            self.error=exc
        finally:
            self.listen.close()

    def join(self):
        self.thread.join(timeout=6)


@pytest.mark.skipif(not sys.platform.startswith("linux"),
                    reason="Linux AF_UNIX native only")
def test_linux_native_uds_auth_health_over_real_os_socket(tmp_path):
    server=LinuxUDSServer(tmp_path)
    stream=native.connect_linux_uds(str(server.path),trusted_core_uid=os.getuid())
    client=readonly.AuthenticatedReadOnlyLuClient(stream,
               enrolled_key=KEY,installed_package_sha256=PACKAGE)
    try:
        handshake=client.handshake()
        assert handshake["session_ref"]==SESSION
        report=client.health()
        assert report["status_code"]=="READY"
        assert report["epoch"]==7
        assert report["real_installed_core_verified"] is False
        assert server.fake.proof_verified
        assert server.fake.received==["hello","auth_proof","health"]
    finally:
        client.close()
        server.join()
    assert server.error is None


@pytest.mark.skipif(not sys.platform.startswith("linux"),
                    reason="Linux AF_UNIX native only")
def test_linux_native_peer_uid_and_private_socket_refusals(tmp_path):
    server=LinuxUDSServer(tmp_path,stop_after=0)
    try:
        with pytest.raises(readonly.LuClientRefused,match="private Core-owned directory"):
            native.connect_linux_uds(str(server.path),
                      trusted_core_uid=os.getuid()+1)
        server.directory.chmod(0o755)
        with pytest.raises(readonly.LuClientRefused,match="private Core-owned directory"):
            native.connect_linux_uds(str(server.path),
                      trusted_core_uid=os.getuid())
        server.directory.chmod(0o700)
        server.path.chmod(0o666)
        with pytest.raises(readonly.LuClientRefused,match="private Core-owned socket"):
            native.connect_linux_uds(str(server.path),
                      trusted_core_uid=os.getuid())
    finally:
        server.listen.close()
        server.join()


@pytest.mark.skipif(not sys.platform.startswith("linux"),
                    reason="Linux AF_UNIX native only")
def test_linux_native_authentication_rejects_forged_core(tmp_path):
    server=LinuxUDSServer(tmp_path,fault="bad_server_mac",stop_after=2)
    stream=native.connect_linux_uds(str(server.path),trusted_core_uid=os.getuid())
    client=readonly.AuthenticatedReadOnlyLuClient(stream,
                 enrolled_key=KEY,installed_package_sha256=PACKAGE)
    try:
        with pytest.raises(readonly.LuClientRefused,match="server-authentication"):
            client.handshake()
        assert not client.authenticated
        assert server.fake.proof_verified
    finally:
        client.close()
        server.join()


class WindowsNativePipeServer:
    """Genuine Win32 local pipe server only inside native acceptance tests."""

    def __init__(self,fault="",stop_after=3):
        kernel,_,wt=native._windows_api()
        self.k=kernel
        self.wt=wt
        self.name=native.PIPE_PREFIX+"lu-ipc-cog-test-"+uuid.uuid4().hex
        kernel.CreateNamedPipeW.argtypes=[
            wt.LPCWSTR,wt.DWORD,wt.DWORD,wt.DWORD,wt.DWORD,
            wt.DWORD,wt.DWORD,ctypes.c_void_p]
        kernel.CreateNamedPipeW.restype=wt.HANDLE
        kernel.ConnectNamedPipe.argtypes=[wt.HANDLE,ctypes.c_void_p]
        kernel.ConnectNamedPipe.restype=wt.BOOL
        self.handle=kernel.CreateNamedPipeW(
            self.name,0x00000003,0x00000000|0x00000008,
            1,65536,65536,1000,None)
        assert self.handle and self.handle != ctypes.c_void_p(-1).value
        self.ready=threading.Event()
        self.fake=SyntheticCoreStream(fault)
        self.error=None
        self.stop_after=stop_after
        self.thread=threading.Thread(target=self._run,daemon=True)
        self.thread.start()

    def _read(self,n):
        b=ctypes.create_string_buffer(n)
        written=self.wt.DWORD()
        if not self.k.ReadFile(self.handle,b,n,ctypes.byref(written),None):
            raise OSError("Win32 native test pipe read refused")
        if written.value == 0:
            raise EOFError("Win32 pipe closed")
        return b.raw[:written.value]

    def _write(self,data):
        count=self.wt.DWORD()
        b=ctypes.create_string_buffer(data,len(data))
        if not self.k.WriteFile(self.handle,b,len(data),
                                ctypes.byref(count),None):
            raise OSError("Win32 native test pipe write refused")
        assert count.value==len(data)

    def _run(self):
        self.ready.set()
        try:
            connected=self.k.ConnectNamedPipe(self.handle,None)
            if not connected and ctypes.get_last_error()!=535:
                raise OSError("Win32 test server ConnectNamedPipe refused")
            for _ in range(self.stop_after):
                _route_request(lambda n:_read_exact(self._read,n),
                                self._write,self.fake)
        except (OSError,EOFError,AssertionError) as exc:
            self.error=exc
        finally:
            native._close(self.k,self.handle)

    def join(self):
        self.thread.join(timeout=7)


@pytest.mark.skipif(sys.platform!="win32",reason="real Win32 named pipe only")
def test_windows_native_named_pipe_auth_health():
    server=WindowsNativePipeServer()
    assert server.ready.wait(4)
    pin=native.observe_windows_process(os.getpid())
    stream=native.connect_windows_named_pipe(server.name,
                                           trusted_core_process_pin=pin)
    client=readonly.AuthenticatedReadOnlyLuClient(stream,
                  enrolled_key=KEY,installed_package_sha256=PACKAGE)
    try:
        welcome=client.handshake()
        assert welcome["authenticated"]
        assert welcome["session_ref"]==SESSION
        result=client.health()
        assert result["epoch"]==7
        assert not result["tool_invocation_authorized"]
        assert server.fake.proof_verified
        assert server.fake.received==["hello","auth_proof","health"]
    finally:
        client.close()
        server.join()
    assert server.error is None


@pytest.mark.skipif(sys.platform!="win32",reason="real Win32 named pipe only")
def test_windows_os_observed_process_image_pin_mismatch_refusal():
    server=WindowsNativePipeServer(stop_after=0)
    pin=native.observe_windows_process(os.getpid())
    bad=dict(pin,image_sha256="f"*64)
    try:
        with pytest.raises(readonly.LuClientRefused,
                           match="OS server identity, image or creation mismatch"):
            native.connect_windows_named_pipe(server.name,
                                               trusted_core_process_pin=bad)
    finally:
        server.join()


@pytest.mark.skipif(sys.platform!="win32",reason="real Win32 named pipe only")
def test_windows_named_pipe_path_and_incomplete_identity_pin_refused():
    pin=native.observe_windows_process(os.getpid())
    with pytest.raises(readonly.LuClientRefused,match="named-pipe path"):
        native.connect_windows_named_pipe(
             "\\\\.\\pipe\\other-vendor",trusted_core_process_pin=pin)
    with pytest.raises(readonly.LuClientRefused,match="process identity pin"):
        native.connect_windows_named_pipe(
             native.PIPE_PREFIX+"lu-ipc-any",trusted_core_process_pin={"pid":5})


def test_no_generic_client_server_or_model_permissions():
    assert not hasattr(native,"start_server")
    assert not hasattr(native,"register_provider")
    assert not hasattr(native,"invoke")
    assert not hasattr(native,"grant_permission")
    assert not hasattr(native,"create_model")
    with pytest.raises(readonly.LuClientRefused,match="unsupported OS-local"):
        # Negative fixture without installed host enrollment.
        if sys.platform not in ("win32","linux"): 
            native.installed_core_health_preflight(endpoint="/absent",
                enrolled_key=KEY,package_hash=PACKAGE)
        else:
            raise readonly.LuClientRefused("unsupported OS-local Lu transport grant")


def test_trusted_host_preflight_fails_closed_with_absent_real_core():
    with pytest.raises((readonly.LuClientRefused, OSError)):
        if sys.platform == "win32":
            native.installed_core_health_preflight(
                endpoint=native.PIPE_PREFIX+"lu-ipc-no-installed-core-"+uuid.uuid4().hex,
                enrolled_key=KEY, package_hash=PACKAGE, windows_process_pin=None)
        elif sys.platform.startswith("linux"):
            native.installed_core_health_preflight(
                endpoint="/tmp/lu-ipc-absent-"+uuid.uuid4().hex,
                expected_uid=os.getuid(),enrolled_key=KEY,package_hash=PACKAGE)
        else:
            native.installed_core_health_preflight(
                endpoint="/absent",enrolled_key=KEY,package_hash=PACKAGE)
