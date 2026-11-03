"""Live Linux UID/IPC fail-closed tests, no original MPFR computation."""
from pathlib import Path
import os,shutil,sys
import pytest
HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE))
from harness38 import (BASE,make_root,launch,ready,stop,writer_request,verify_no_read,verify_no_connect,
    WRITER_UID,MATH_UID,ATTESTOR_UID,SIGNER_UID,SIGNER_TO_ATTESTOR_GID,ATTESTOR_TO_MATH_GID)
from protocol38 import parse,ZERO

@pytest.mark.skipif(os.geteuid()!=0 or not (BASE/'CH_C14_33/checkpoint_heads.json').is_file(),
                    reason='Root/Linux original CH23 test only')
def test_signer_with_attestor_offline_remains_genesis():
    s=make_root(BASE);sp=None
    try:
        sp=launch(SIGNER_UID,[s['root']/'signer/code/signer38.py','--socket',s['signer_sock'],
          '--store',s['signer_private'],'--attestor-socket',s['attestor_sock'],
          '--writer-uid',WRITER_UID,'--attestor-uid',ATTESTOR_UID],groups=SIGNER_TO_ATTESTOR_GID)
        ready(s['signer_sock'],sp)
        r=writer_request(s['signer_sock'],{'op':'verify','case_id':'one_event_n80_i00'},timeout=6)
        assert r['ok'] is False
        assert not (s['signer_private']/'HEAD').exists()
        assert not list((s['signer_private']/'revisions').iterdir())
        assert parse((s['signer_private']/'trusted_tip.json').read_bytes())['tip']==ZERO
    finally:
        stop(sp);shutil.rmtree(s['root'],ignore_errors=True)

@pytest.mark.skipif(os.geteuid()!=0 or not (BASE/'CH_C14_33/checkpoint_heads.json').is_file(),
                    reason='Root/Linux original CH23 test only')
def test_kernel_denies_math_account_from_both_signing_keys_and_direct_sockets():
    s=make_root(BASE)
    try:
        verify_no_read(MATH_UID,[s['attestor_private']/'attestor_secret.ed25519.pem',
                   s['signer_private']/'secret.ed25519.pem'])
        verify_no_read(ATTESTOR_UID,[s['signer_private']/'secret.ed25519.pem',
                   s['math_source']/'CH_C14_33/checkpoint_heads.json'],groups=str(ATTESTOR_TO_MATH_GID))
        verify_no_read(SIGNER_UID,[s['attestor_private']/'attestor_secret.ed25519.pem',
                   s['math_source']/'CH_C14_33/checkpoint_heads.json'],groups=str(SIGNER_TO_ATTESTOR_GID))
        verify_no_connect(MATH_UID,s['attestor_sock'])
        verify_no_connect(MATH_UID,s['signer_sock'])
    finally:shutil.rmtree(s['root'],ignore_errors=True)
