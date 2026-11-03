"""Linux root-controlled actual signer-no-verifier fail-closed acceptance."""
from __future__ import annotations
import json, os, shutil, sys
from pathlib import Path
import pytest
D=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(D))
from harness37 import (setup,launch,ready,stop,request_writer,ORIGINAL,SIGNER_UID,VERIFIER_UID,WRITER_UID,INTEROP_GID)
from protocol37 import parse,ZERO

@pytest.mark.skipif(os.geteuid()!=0 or not (ORIGINAL/'CH_C14_33/checkpoint_heads.json').is_file(),reason='Root-only original CH23 Linux test')
def test_signer_refuses_when_mathematical_verifier_unavailable():
    st=setup(ORIGINAL);ss=None
    try:
        ss=launch(SIGNER_UID,[st['signer']/'code'/'signer37.py','--socket',st['signer_sock'],
           '--store',st['signer_store'],'--verifier-socket',st['verifier_sock'],
           '--writer-uid',str(WRITER_UID),'--verifier-uid',str(VERIFIER_UID)],groups=INTEROP_GID)
        ready(st['signer_sock'],ss)
        result=request_writer(st['signer_sock'],{'op':'verify','case_id':'one_event_n80_i00'},timeout=10)
        assert result['ok'] is False
        assert not (st['signer_store']/'HEAD').exists()
        assert not list((st['signer_store']/'revisions').iterdir())
        assert parse((st['signer_store']/'trusted_tip.json').read_bytes())['tip']==ZERO
    finally:
        stop(ss);shutil.rmtree(st['root'],ignore_errors=True)
