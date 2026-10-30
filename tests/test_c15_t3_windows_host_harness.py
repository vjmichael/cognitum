"""Portable host control-flow gates; Windows-only checks run separately."""
import os
from pathlib import Path
import tempfile
import pytest
from cognitum.spatial_host_recovery_readiness import P2ZHostReadiness
from tests.test_c15_t3_p2w_map_lifecycle import request
from standalone_windows_host.authority import StandaloneAuthority, AuthorityError
from standalone_windows_host.runner import suite
from standalone_windows_host.platform_io import dpapi_protect, dpapi_unprotect

@pytest.mark.skipif(os.name=='nt', reason='portable backend deliberately forbidden on Windows')
def test_explicit_portable_process_crash_matrix():
    r=suite(insecure=True)
    assert r['windows_native_executed'] is False
    assert {v['post_crash_status'] for v in r['recovery_crashes'].values()} == {
        'REJECTED','AUTHENTIC_UNANCHORED_TAIL','CLEAN'}

@pytest.mark.skipif(os.name=='nt', reason='portable backend deliberately forbidden on Windows')
def test_portable_revocation_survives_reload():
    with tempfile.TemporaryDirectory() as d:
        root=Path(d)
        h=StandaloneAuthority(root/'host',insecure_test_backend=True)
        src=request().source_request.dynamic_request
        h.enroll(src.conversation_id,src.volume_id,journal_directory=root/'journal')
        h.revoke()
        fresh=StandaloneAuthority(root/'host',insecure_test_backend=True)
        with pytest.raises(AuthorityError,match='REVOKED'):
            fresh.read_binding()

@pytest.mark.skipif(os.name=='nt', reason='portable backend deliberately forbidden on Windows')
def test_portable_state_tamper_rejected():
    with tempfile.TemporaryDirectory() as d:
        root=Path(d)
        h=StandaloneAuthority(root/'host',insecure_test_backend=True)
        src=request().source_request.dynamic_request
        h.enroll(src.conversation_id,src.volume_id,journal_directory=root/'journal')
        h.state.write_bytes(b'not-valid-state')
        with pytest.raises(AuthorityError,match='AUTHORITY_STATE_INTEGRITY_FAILURE'):
            h.read_binding()

@pytest.mark.skipif(os.name!='nt', reason='DPAPI requires actual Windows')
def test_native_windows_dpapi_and_full_process_suite():
    plain=os.urandom(48)
    sealed=dpapi_protect(plain)
    assert sealed!=plain and dpapi_unprotect(sealed)==plain
    output=suite()
    assert output['windows_native_executed']
    assert output['dpapi']=='CURRENT_USER_ROUNDTRIP_AND_TAMPER_REJECTION'
