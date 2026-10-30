"""Windows-only exact DACL creation and independent, SID-based inspection.

The test host limits its OWN directories and files to the current user and
LocalSystem. It does not authenticate a separate antirollback authority.
Avoid localized icacls output: inspect Win32 security descriptors directly.
"""
from __future__ import annotations
import ctypes
from ctypes import wintypes
import os
from pathlib import Path

class AclGateError(RuntimeError):
    pass


class ACL(ctypes.Structure):
    _fields_ = [('AclRevision', ctypes.c_ubyte), ('Sbz1', ctypes.c_ubyte),
                ('AclSize', wintypes.WORD), ('AceCount', wintypes.WORD),
                ('Sbz2', wintypes.WORD)]


def _libs():
    if os.name != 'nt':
        raise AclGateError('WINDOWS_ACL_GATE_REQUIRES_WINDOWS')
    adv = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    adv.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    adv.OpenProcessToken.restype = wintypes.BOOL
    adv.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                        wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    adv.GetTokenInformation.restype = wintypes.BOOL
    adv.GetLengthSid.argtypes = [ctypes.c_void_p]
    adv.GetLengthSid.restype = wintypes.DWORD
    adv.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
    adv.ConvertSidToStringSidW.restype = wintypes.BOOL
    adv.ConvertStringSidToSidW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p)]
    adv.ConvertStringSidToSidW.restype = wintypes.BOOL
    return adv, kernel


def _sid_string(adv, kernel, ptr):
    result = wintypes.LPWSTR()
    if not adv.ConvertSidToStringSidW(ctypes.c_void_p(ptr), ctypes.byref(result)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return result.value
    finally:
        kernel.LocalFree(ctypes.cast(result, ctypes.c_void_p))


def _current_sid(adv, kernel):
    token = wintypes.HANDLE()
    if not adv.OpenProcessToken(kernel.GetCurrentProcess(), 0x0008, ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        needed = wintypes.DWORD()
        adv.GetTokenInformation(token, 1, None, 0, ctypes.byref(needed))
        if needed.value < ctypes.sizeof(ctypes.c_void_p):
            raise AclGateError('TOKEN_USER_UNAVAILABLE')
        buf = ctypes.create_string_buffer(needed.value)
        if not adv.GetTokenInformation(token, 1, buf, needed.value, ctypes.byref(needed)):
            raise ctypes.WinError(ctypes.get_last_error())
        ptr = ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p))[0]
        if not ptr:
            raise AclGateError('TOKEN_USER_SID_MISSING')
        return _sid_string(adv, kernel, ptr)
    finally:
        kernel.CloseHandle(token)


def apply_exact_acl(path):
    """Overwrite (not merely add to) the DACL, protecting it from inheritance."""
    adv, kernel = _libs()
    path = Path(path)
    if path.is_symlink() or not path.exists():
        raise AclGateError('ACL_PATH_MUST_EXIST_AND_NOT_BE_SYMLINK')
    current = _current_sid(adv, kernel)
    sid_ptrs = []
    try:
        for sid_text in dict.fromkeys((current, 'S-1-5-18')):
            p = ctypes.c_void_p()
            if not adv.ConvertStringSidToSidW(sid_text, ctypes.byref(p)):
                raise ctypes.WinError(ctypes.get_last_error())
            sid_ptrs.append(p)
        size = ctypes.sizeof(ACL) + sum(8 + adv.GetLengthSid(p) for p in sid_ptrs)
        acl_storage = ctypes.create_string_buffer(size)
        adv.InitializeAcl.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD]
        adv.InitializeAcl.restype = wintypes.BOOL
        if not adv.InitializeAcl(acl_storage, size, 2):
            raise ctypes.WinError(ctypes.get_last_error())
        adv.AddAccessAllowedAceEx.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                                               wintypes.DWORD, ctypes.c_void_p]
        adv.AddAccessAllowedAceEx.restype = wintypes.BOOL
        flags = 0x03 if path.is_dir() else 0  # OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE
        for sid in sid_ptrs:
            if not adv.AddAccessAllowedAceEx(acl_storage, 2, flags, 0x001F01FF, sid):
                raise ctypes.WinError(ctypes.get_last_error())
        adv.SetNamedSecurityInfoW.argtypes = [wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD,
                                               ctypes.c_void_p, ctypes.c_void_p,
                                               ctypes.c_void_p, ctypes.c_void_p]
        adv.SetNamedSecurityInfoW.restype = wintypes.DWORD
        code = adv.SetNamedSecurityInfoW(str(path), 1, 0x80000004, None, None,
                                         ctypes.cast(acl_storage, ctypes.c_void_p), None)
        if code:
            raise ctypes.WinError(code)
    finally:
        for p in sid_ptrs:
            kernel.LocalFree(p)
    return audit_exact_acl(path)


def audit_exact_acl(path):
    """Reject extra users/groups, deny ACEs, inherited DACLs, and NULL DACLs."""
    adv, kernel = _libs()
    path = Path(path)
    adv.GetNamedSecurityInfoW.argtypes = [wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p)]
    adv.GetNamedSecurityInfoW.restype = wintypes.DWORD
    dacl = ctypes.c_void_p()
    descriptor = ctypes.c_void_p()
    code = adv.GetNamedSecurityInfoW(str(path), 1, 4, None, None, ctypes.byref(dacl),
                                      None, ctypes.byref(descriptor))
    if code:
        raise ctypes.WinError(code)
    try:
        adv.GetSecurityDescriptorControl.argtypes = [ctypes.c_void_p,
                                                       ctypes.POINTER(wintypes.WORD),
                                                       ctypes.POINTER(wintypes.DWORD)]
        adv.GetSecurityDescriptorControl.restype = wintypes.BOOL
        control = wintypes.WORD()
        revision = wintypes.DWORD()
        if not adv.GetSecurityDescriptorControl(descriptor, ctypes.byref(control),
                                                ctypes.byref(revision)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not (control.value & 0x0004):
            raise AclGateError('DACL_MISSING_FROM_SECURITY_DESCRIPTOR')
        if not (control.value & 0x1000):
            raise AclGateError('DACL_IS_NOT_PROTECTED_FROM_INHERITANCE')
        if not dacl:
            raise AclGateError('NULL_DACL_REJECTED')
        count = ctypes.cast(dacl, ctypes.POINTER(ACL)).contents.AceCount
        adv.GetAce.argtypes = [ctypes.c_void_p, wintypes.DWORD,
                               ctypes.POINTER(ctypes.c_void_p)]
        adv.GetAce.restype = wintypes.BOOL
        allowed = {_current_sid(adv, kernel), 'S-1-5-18'}
        actual = set()
        for idx in range(count):
            ace = ctypes.c_void_p()
            if not adv.GetAce(dacl, idx, ctypes.byref(ace)):
                raise ctypes.WinError(ctypes.get_last_error())
            header = ctypes.string_at(ace, 4)
            expected_flags = 0x03 if path.is_dir() else 0
            if header[0] != 0 or header[1] != expected_flags:
                raise AclGateError('UNEXPECTED_OR_INHERITED_ACE')
            # Check principal membership before the access mask. An unknown SID
            # must have a deterministic rejection reason even when icacls maps
            # its requested access (e.g. RX) to a non-full-control bitmask.
            # Both SID and exact access-mask validation remain mandatory.
            sid = _sid_string(adv, kernel, ace.value + 8)
            if sid not in allowed or sid in actual:
                raise AclGateError('UNAUTHORIZED_OR_DUPLICATE_ACE:' + sid)
            mask = ctypes.c_uint32.from_address(ace.value + 4).value
            if mask != 0x001F01FF:
                raise AclGateError('UNEXPECTED_ACE_ACCESS_MASK')
            actual.add(sid)
        if actual != allowed:
            raise AclGateError('REQUIRED_USER_OR_SYSTEM_ACE_MISSING')
        return {'acl_policy':'CURRENT_USER_AND_SYSTEM_ONLY', 'ace_count':count,
                'protected_dacl':True, 'user_sid':_current_sid(adv,kernel)}
    finally:
        kernel.LocalFree(descriptor)
