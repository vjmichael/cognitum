"""OS-backed SSM secret custody (host-side only; no model-facing authority).

Windows: real current-user DPAPI CryptProtectData/CryptUnprotectData; key
ciphertext persisted in a caller-protected directory. Linux: real kernel
'user' keyring through libkeyutils (volatile across reboot and possibly
unavailable in sandboxed runners). NO fallback to plaintext files, environment
variables, Python-only encryption, or fake keyrings.

The owner must provide OS service-account isolation and directory ACLs. DPAPI
does not provide TPM monotonic counters; Linux user keyrings are UID-scoped,
not per-process and not reboot-durable. Returning key bytes to the trusted
Python process necessarily permits copies in address-space; installed native
broker/worker memory isolation remains a separate security gate.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import hashlib
import hmac
import os
from pathlib import Path
import sys

from . import admission as mel
from cognitum.research import ssm_stochastic_checkpoints as cp

DOMAIN=b"cognitum.ssm.os_credential_broker.v1\x00"
MAX_SECRET=128
MAX_CIPHERTEXT=8192
DPAPI_MAGIC=b"cognitum.ssm.dpapi.credential.v1\x00"
USER_KEYRING=-4


class CredentialUnavailable(OSError):
    """OS credential service did not admit this caller; never use fallback."""


def _scope_key(scope, stream_id, namespace):
    if type(scope) is not mel.Scope:
        raise ValueError("native OS broker requires reviewed MEL Scope")
    cp._identifier(stream_id, "OS broker stream")
    cp._identifier(namespace, "OS broker namespace")
    material=(scope.session+"\x00"+scope.workspace+"\x00"+
              scope.subject+"\x00"+scope.turn+"\x00"+stream_id+"\x00"+
              namespace).encode("ascii")
    return hashlib.sha256(DOMAIN+material).hexdigest()


def _root(path):
    p=Path(path)
    if not p.is_absolute() or not p.is_dir() or p.is_symlink():
        raise ValueError("pre-created trusted absolute native credential directory required")
    if os.name=="posix" and (p.stat().st_mode & 0o077):
        raise ValueError("native credential directory must be owner-only")
    return p


def _dpapi(data, entropy, *, decrypt=False):
    if sys.platform!="win32":
        raise CredentialUnavailable("Windows DPAPI not available")
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_=[("size",wintypes.DWORD),
                  ("data",ctypes.POINTER(ctypes.c_ubyte))]

    def prepare(raw):
        buf=ctypes.create_string_buffer(raw)
        return BLOB(len(raw),ctypes.cast(buf,ctypes.POINTER(ctypes.c_ubyte))),buf

    inp,keep=prepare(data)
    ent,keep_ent=prepare(entropy)
    out=BLOB()
    crypt=ctypes.WinDLL("crypt32",use_last_error=True)
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    crypt.CryptProtectData.argtypes=[ctypes.POINTER(BLOB),ctypes.c_wchar_p,
       ctypes.POINTER(BLOB),ctypes.c_void_p,ctypes.c_void_p,
       wintypes.DWORD,ctypes.POINTER(BLOB)]
    crypt.CryptProtectData.restype=wintypes.BOOL
    crypt.CryptUnprotectData.argtypes=[ctypes.POINTER(BLOB),
       ctypes.POINTER(ctypes.c_wchar_p),ctypes.POINTER(BLOB),
       ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(BLOB)]
    crypt.CryptUnprotectData.restype=wintypes.BOOL
    kernel.LocalFree.argtypes=[ctypes.c_void_p]
    kernel.LocalFree.restype=ctypes.c_void_p
    try:
        if decrypt:
            result=crypt.CryptUnprotectData(ctypes.byref(inp),None,
                         ctypes.byref(ent),None,None,0x1,ctypes.byref(out))
        else:
            result=crypt.CryptProtectData(ctypes.byref(inp),None,
                         ctypes.byref(ent),None,None,0x1,ctypes.byref(out))
        if not result:
            raise CredentialUnavailable("Windows DPAPI protection/refusal: "+str(ctypes.get_last_error()))
        if not 0 < out.size <= MAX_CIPHERTEXT:
            raise CredentialUnavailable("DPAPI credential byte budget")
        return ctypes.string_at(out.data,out.size)
    finally:
        if out.data:
            kernel.LocalFree(ctypes.cast(out.data,ctypes.c_void_p))


def _keyutils():
    if not sys.platform.startswith("linux"):
        raise CredentialUnavailable("kernel keyring requires Linux")
    try:
        library=ctypes.CDLL(ctypes.util.find_library("keyutils") or
                           "libkeyutils.so.1", use_errno=True)
    except OSError as exc:
        raise CredentialUnavailable("libkeyutils unavailable; no fallback") from exc
    library.add_key.argtypes=[ctypes.c_char_p,ctypes.c_char_p,
                             ctypes.c_void_p,ctypes.c_size_t,ctypes.c_int32]
    library.add_key.restype=ctypes.c_int32
    library.keyctl_search.argtypes=[ctypes.c_int32,ctypes.c_char_p,
                                   ctypes.c_char_p,ctypes.c_int32]
    library.keyctl_search.restype=ctypes.c_int32
    library.keyctl_read.argtypes=[ctypes.c_int32,ctypes.c_void_p,ctypes.c_size_t]
    library.keyctl_read.restype=ctypes.c_long
    library.keyctl_revoke.argtypes=[ctypes.c_int32]
    library.keyctl_revoke.restype=ctypes.c_long
    return library


def _native_error(label):
    number=ctypes.get_errno()
    raise CredentialUnavailable(label+": "+os.strerror(number))


class OSCredentialBroker:
    """Provision-once native OS custody for one reviewed stream/scope.

    Windows key is DPAPI-current-user-encrypted on disk (not plaintext).
    Linux key is present in the kernel user keyring, never an on-disk key.
    Linux reboot loses the key: host must reprovision from a separately
    protected recovery service, not silently rotate a live checkpoint key.
    Same-UID programs remain in the OS trust boundary.
    """

    def __init__(self, credential_directory, *, namespace):
        self._directory=_root(credential_directory)
        self._namespace=cp._identifier(namespace,"OS broker namespace")
        if sys.platform=="win32":
            self.backend="windows-dpapi-current-user"
        elif sys.platform.startswith("linux"):
            self.backend="linux-kernel-user-keyring"
        else:
            raise CredentialUnavailable("unsupported OS credential mechanism")

    def _description(self,scope,sid):
        return "cog-ssm-r6:"+_scope_key(scope,sid,self._namespace)

    def _path(self,scope,sid):
        return self._directory/(_scope_key(scope,sid,self._namespace)+".dpapi")

    def provision(self,scope,stream_id,secret):
        cp._auth_key(secret)
        if sys.platform=="win32":
            path=self._path(scope,stream_id)
            ciphertext=_dpapi(secret,self._description(scope,stream_id).encode("ascii"))
            # Versioned whole-file integrity check; Windows DPAPI itself
            # protects the secret's confidentiality and authenticity.
            envelope=DPAPI_MAGIC+hashlib.sha256(ciphertext).digest()+ciphertext
            fd=None
            try:
                fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                with os.fdopen(fd,"wb") as file:
                    fd=None
                    file.write(envelope)
                    file.flush()
                    os.fsync(file.fileno())
            except FileExistsError as exc:
                raise ValueError("OS secret already provisioned; no silent rotation") from exc
            finally:
                if fd is not None:os.close(fd)
        else:
            library=_keyutils()
            desc=self._description(scope,stream_id).encode("ascii")
            existing=library.keyctl_search(USER_KEYRING,b"user",desc,0)
            if existing>=0:
                raise ValueError("OS keyring secret already provisioned")
            data=ctypes.create_string_buffer(secret)
            serial=library.add_key(b"user",desc,data,len(secret),USER_KEYRING)
            if serial<0:_native_error("kernel user keyring add refused")
            # An accepted add_key is not enough: keyctl_read can still be
            # refused by a runner's kernel/LSM. No unusable key provision.
            try:
                recovered=self.borrow_key(scope,stream_id)
                if not hmac.compare_digest(recovered,secret):
                    raise CredentialUnavailable("kernel keyring provision mismatch")
            except BaseException:
                try:library.keyctl_revoke(serial)
                except Exception:pass
                raise
        return True

    def borrow_key(self,scope,stream_id):
        if sys.platform=="win32":
            p=self._path(scope,stream_id)
            if p.is_symlink():
                raise CredentialUnavailable("OS credential symlink refused")
            try:
                with p.open("rb") as file:
                    ciphertext=file.read(MAX_CIPHERTEXT+1)
            except OSError as exc:
                raise CredentialUnavailable("OS DPAPI credential absent/inaccessible") from exc
            prefix=len(DPAPI_MAGIC)
            if not (prefix+32<len(ciphertext)<=MAX_CIPHERTEXT and
                    ciphertext.startswith(DPAPI_MAGIC)):
                raise CredentialUnavailable("DPAPI credential envelope version/size")
            digest=ciphertext[prefix:prefix+32]
            raw=ciphertext[prefix+32:]
            if not hmac.compare_digest(digest,hashlib.sha256(raw).digest()):
                raise CredentialUnavailable("DPAPI credential file integrity refused")
            return cp._auth_key(_dpapi(raw,
                  self._description(scope,stream_id).encode("ascii"),decrypt=True))
        library=_keyutils()
        serial=library.keyctl_search(USER_KEYRING,b"user",
                        self._description(scope,stream_id).encode("ascii"),0)
        if serial<0:_native_error("kernel keyring secret unavailable")
        size=library.keyctl_read(serial,None,0)
        if size<0:_native_error("kernel keyring read refused")
        if not 32<=size<=MAX_SECRET:
            raise CredentialUnavailable("kernel credential size")
        buf=ctypes.create_string_buffer(size)
        actual=library.keyctl_read(serial,buf,size)
        if actual!=size:_native_error("kernel keyring read refused")
        return cp._auth_key(buf.raw[:size])

    def revoke(self,scope,stream_id):
        """Explicit host revocation. Never implicitly reissue an old stream key."""
        if sys.platform=="win32":
            path=self._path(scope,stream_id)
            if path.is_symlink():
                raise CredentialUnavailable("OS credential symlink refused")
            try:path.unlink()
            except FileNotFoundError:return False
            return True
        lib=_keyutils()
        serial=lib.keyctl_search(USER_KEYRING,b"user",
                       self._description(scope,stream_id).encode("ascii"),0)
        if serial<0:return False
        if lib.keyctl_revoke(serial)<0:_native_error("kernel keyring revoke refused")
        return True
