"""Portable source-level regression for Windows ACL validation ordering.
This is NOT Windows-native runtime evidence; it prevents accidental reordering.
"""
from pathlib import Path


def test_unknown_sid_checked_before_exact_full_control_mask():
    source = (Path(__file__).resolve().parents[1] /
              'standalone_windows_host' / 'acl_audit.py').read_text()
    fn = source.split('def audit_exact_acl(',1)[1]
    assert fn.index('if sid not in allowed or sid in actual:') < fn.index('if mask != 0x001F01FF:')
    assert "raise AclGateError('UNEXPECTED_ACE_ACCESS_MASK')" in fn
    assert "raise AclGateError('UNAUTHORIZED_OR_DUPLICATE_ACE:' + sid)" in fn
