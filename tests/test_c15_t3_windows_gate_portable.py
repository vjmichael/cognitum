"""Linux test cannot certify Windows, but verifies gate refuses false passes."""
from pathlib import Path
import os
import pytest
from standalone_windows_host.acl_audit import apply_exact_acl, audit_exact_acl, AclGateError
from standalone_windows_host.preflight import preflight

@pytest.mark.skipif(os.name == 'nt', reason='Non-Windows rejection test')
def test_ntfs_dpapi_acl_gate_cannot_be_emulated_on_linux(tmp_path):
    with pytest.raises(RuntimeError, match='NATIVE_WINDOWS_REQUIRED'):
        preflight(tmp_path)
    with pytest.raises(AclGateError, match='WINDOWS_ACL_GATE_REQUIRES_WINDOWS'):
        apply_exact_acl(tmp_path)
    with pytest.raises(AclGateError, match='WINDOWS_ACL_GATE_REQUIRES_WINDOWS'):
        audit_exact_acl(tmp_path)
