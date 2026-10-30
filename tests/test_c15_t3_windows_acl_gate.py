"""NTFS ACL red-team acceptance: executes ONLY on actual Windows."""
import os
from pathlib import Path
import subprocess
import tempfile
import pytest
from standalone_windows_host.acl_audit import apply_exact_acl, audit_exact_acl, AclGateError

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Windows ACL API requires native Windows')


def test_exact_acl_on_fresh_directory_and_file():
    with tempfile.TemporaryDirectory(prefix='cognitum-acl-gate-') as tmp:
        root = Path(tmp)
        report = apply_exact_acl(root)
        assert report['ace_count'] == 2 and report['protected_dacl']
        child = root / 'key-state.bin'
        child.write_bytes(b'test-only')
        report = apply_exact_acl(child)
        assert report['ace_count'] == 2
        assert audit_exact_acl(root)['acl_policy'] == 'CURRENT_USER_AND_SYSTEM_ONLY'


def test_extra_ace_fails_even_when_correct_user_and_system_exist():
    with tempfile.TemporaryDirectory(prefix='cognitum-acl-gate-') as tmp:
        root = Path(tmp)
        apply_exact_acl(root)
        # Local BUILTIN\\Users is an extra reader; the independent auditor
        # must reject this rather than claiming icacls succeeded.
        p = subprocess.run(['icacls', str(root), '/grant', '*S-1-5-32-545:(RX)'],
                           capture_output=True, text=True, timeout=15)
        if p.returncode:
            pytest.fail('Cannot inject test ACE on the test-owned directory: ' + p.stderr)
        try:
            # A newly injected ACE without OI/CI can be rejected on its flags
            # before the auditor reaches its unauthorized SID. Both are safe
            # reasons to reject the modified security descriptor.
            with pytest.raises(AclGateError) as exc:
                audit_exact_acl(root)
            assert str(exc.value).split(':', 1)[0] in {
                'UNEXPECTED_OR_INHERITED_ACE',
                'UNAUTHORIZED_OR_DUPLICATE_ACE',
            }
        finally:
            apply_exact_acl(root)


def test_extra_inheritable_ace_rejected_by_sid_policy():
    """An extra ACE with valid directory inheritance must still be rejected."""
    with tempfile.TemporaryDirectory(prefix='cognitum-acl-gate-') as tmp:
        root = Path(tmp)
        apply_exact_acl(root)
        # Match the directory's expected OI + CI ACE flags so the SID
        # authorization check, not the inheritance-flags check, is exercised.
        p = subprocess.run(['icacls', str(root), '/grant', '*S-1-5-32-545:(OI)(CI)(RX)'],
                           capture_output=True, text=True, timeout=15)
        if p.returncode:
            pytest.fail('Cannot inject inheritable test ACE: ' + p.stderr)
        try:
            with pytest.raises(AclGateError, match='UNAUTHORIZED_OR_DUPLICATE_ACE'):
                audit_exact_acl(root)
        finally:
            apply_exact_acl(root)


def test_authorized_user_with_reduced_access_mask_is_rejected():
    """Known principal is not sufficient: allowed ACE must remain exact full control."""
    from standalone_windows_host.acl_audit import _libs, _current_sid
    with tempfile.TemporaryDirectory(prefix='cognitum-acl-gate-') as tmp:
        root = Path(tmp)
        apply_exact_acl(root)
        adv, kernel = _libs()
        user_sid = _current_sid(adv, kernel)
        # /grant:r replaces this SID's existing full-control ACE with RX.
        p = subprocess.run(['icacls', str(root), '/grant:r',
                            '*' + user_sid + ':(OI)(CI)(RX)'],
                           capture_output=True, text=True, timeout=15)
        if p.returncode:
            pytest.fail('Cannot replace current-user test ACE: ' + p.stderr)
        try:
            with pytest.raises(AclGateError, match='UNEXPECTED_ACE_ACCESS_MASK'):
                audit_exact_acl(root)
        finally:
            apply_exact_acl(root)
