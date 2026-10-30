"""Minimal Windows-native primitives. Windows execution is mandatory for acceptance.

NTFS write-through rename is not a claim of resilience to actual power loss.
No junction/reparse directory may be used for the harness's managed storage.
"""
from __future__ import annotations
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import secrets
import subprocess
import sys

class HostIOError(RuntimeError):
    pass


def reject_reparse(path: Path):
    p = Path(os.path.abspath(path))
    for part in (p, *p.parents):
        if not part.exists() and not part.is_symlink():
            continue
        if part.is_symlink() or (os.name == 'nt' and (
                (os.stat(part, follow_symlinks=False).st_file_attributes & 0x400) != 0)):
            raise HostIOError('REPARSE_POINT_OR_SYMLINK_REJECTED')


def win_move(source, target, *, replace):
    if os.name != 'nt':
        if not replace and Path(target).exists():
            raise FileExistsError(target)
        os.replace(source,target)
        fd = os.open(Path(target).parent, os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)
        return
    # MOVEFILE_WRITE_THROUGH; no cross-volume copy allowed.
    move = ctypes.WinDLL('kernel32', use_last_error=True).MoveFileExW
    move.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
    move.restype = wintypes.BOOL
    flags = 0x8 | (0x1 if replace else 0)
    if not move(str(source),str(target),flags):
        raise ctypes.WinError(ctypes.get_last_error())


def atomic_bytes(path, data: bytes):
    path=Path(path)
    reject_reparse(path.parent)
    tmp=path.with_name('.pending-'+secrets.token_hex(12))
    try:
        with tmp.open('xb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        win_move(tmp,path,replace=True)
    finally:
        if tmp.exists(): tmp.unlink()


def windows_p2y_writer(path, data):
    """Test-only Windows NTFS adapter to replace P2Y's POSIX directory fsync.

    Uses exclusive final-name publication via MoveFileExW with WRITE_THROUGH,
    without replace, after fsync of temporary data. Does not overwrite records.
    """
    from cognitum.spatial_durable_incremental_volume import DurableRejected, MAX_RECORD_BYTES
    if os.name != 'nt':
        raise HostIOError('WINDOWS_WRITER_ONLY')
    if not data or len(data)>MAX_RECORD_BYTES:
        raise DurableRejected('RECORD_SIZE_INVALID')
    path=Path(path)
    reject_reparse(path.parent)
    if path.exists(): raise DurableRejected('JOURNAL_RECORD_ALREADY_EXISTS')
    tmp=path.with_name('.tmp-'+secrets.token_hex(12))
    try:
        with tmp.open('xb') as f:
            f.write(data); f.flush();os.fsync(f.fileno())
        # No overwriting existing record; MOVEFILE_WRITE_THROUGH, same volume.
        win_move(tmp,path,replace=False)
    finally:
        # Deliberately preserve incomplete temporary files for crash diagnostics,
        # except a failed normal process path: any present tmp stays fail-closed.
        pass


def install_windows_writer():
    if os.name=='nt':
        from cognitum import spatial_durable_incremental_volume as dur
        dur._durable_write=windows_p2y_writer


if os.name == 'nt':
    class DATA_BLOB(ctypes.Structure):
        _fields_=[('cbData', wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_ubyte))]


def _blob(data):
    array = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    return DATA_BLOB(len(data), array), array


def dpapi_protect(plain: bytes) -> bytes:
    if os.name!='nt':raise HostIOError('DPAPI_REQUIRES_WINDOWS')
    crypt=ctypes.WinDLL('crypt32',use_last_error=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.LocalFree.argtypes=[ctypes.c_void_p]
    kernel.LocalFree.restype=ctypes.c_void_p
    f=crypt.CryptProtectData
    f.argtypes=[ctypes.POINTER(DATA_BLOB),wintypes.LPCWSTR,
        ctypes.POINTER(DATA_BLOB),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,
        ctypes.POINTER(DATA_BLOB)]
    f.restype=wintypes.BOOL
    entropy, ekeep=_blob(b'Cognitum-C15-T3-P2Z-WinHost-v1')
    src, skeep=_blob(plain)
    out=DATA_BLOB()
    if not f(ctypes.byref(src),None,ctypes.byref(entropy),None,None,0x1,ctypes.byref(out)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:return ctypes.string_at(out.pbData,out.cbData)
    finally:kernel.LocalFree(ctypes.cast(out.pbData,ctypes.c_void_p))


def dpapi_unprotect(ciphertext: bytes) -> bytes:
    if os.name!='nt':raise HostIOError('DPAPI_REQUIRES_WINDOWS')
    crypt=ctypes.WinDLL('crypt32',use_last_error=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.LocalFree.argtypes=[ctypes.c_void_p]
    kernel.LocalFree.restype=ctypes.c_void_p
    f=crypt.CryptUnprotectData
    f.argtypes=[ctypes.POINTER(DATA_BLOB),ctypes.c_void_p,
        ctypes.POINTER(DATA_BLOB),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,
        ctypes.POINTER(DATA_BLOB)]
    f.restype=wintypes.BOOL
    entropy, ekeep=_blob(b'Cognitum-C15-T3-P2Z-WinHost-v1')
    src, skeep=_blob(ciphertext)
    out=DATA_BLOB()
    if not f(ctypes.byref(src),None,ctypes.byref(entropy),None,None,0x1,ctypes.byref(out)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:return ctypes.string_at(out.pbData,out.cbData)
    finally:kernel.LocalFree(ctypes.cast(out.pbData,ctypes.c_void_p))


def windows_restrict_acl(path):
    """Install exact CurrentUser+SYSTEM DACL and independently re-read every ACE.

    Explicit pre-existing ACEs are removed, not merely appended to. Reject
    foreign ACEs, inherited ACLs and NULL DACLs. Actual Win32 execution is a
    pending Windows-native acceptance gate.
    """
    if os.name!='nt': return False
    from .acl_audit import apply_exact_acl
    return apply_exact_acl(path)


def windows_require_ntfs(directory):
    """Fail closed if a Windows runner is not on NTFS; no power-loss guarantee."""
    if os.name!='nt':raise HostIOError('NTFS_CHECK_REQUIRES_WINDOWS')
    kernel=ctypes.WinDLL('kernel32', use_last_error=True)
    get_root=kernel.GetVolumePathNameW
    get_root.argtypes=[wintypes.LPCWSTR,wintypes.LPWSTR,wintypes.DWORD]
    get_root.restype=wintypes.BOOL
    root=ctypes.create_unicode_buffer(1024)
    if not get_root(str(Path(directory).resolve()),root,len(root)):
        raise ctypes.WinError(ctypes.get_last_error())
    get_fs=kernel.GetVolumeInformationW
    get_fs.argtypes=[wintypes.LPCWSTR,wintypes.LPWSTR,wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),wintypes.LPWSTR,wintypes.DWORD]
    get_fs.restype=wintypes.BOOL
    fs=ctypes.create_unicode_buffer(64)
    if not get_fs(root.value,None,0,None,None,None,fs,len(fs)):
        raise ctypes.WinError(ctypes.get_last_error())
    if fs.value.upper()!='NTFS':raise HostIOError('NTFS_REQUIRED:'+fs.value)
    return fs.value
