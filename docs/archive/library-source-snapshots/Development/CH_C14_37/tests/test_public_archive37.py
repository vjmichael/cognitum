"""Reject contamination between independently provisioned witness authorities."""
import json, shutil, sys, tempfile
from pathlib import Path
import pytest
D=Path(__file__).resolve().parents[1];sys.path.insert(0,str(D))
from audit37 import check

def test_public_export_has_no_unreachable_or_mixed_authority_records():
    public=D/'CH37_public_witness'
    source=D.parent if (D.parent/'CH_C14_33').exists() else D.parent/'CH37_baseline'
    results=D/'original15_results.json'
    if not public.exists() or not results.exists() or not (source/'CH_C14_33').exists():
        pytest.skip('Requires completed original 15-case CH37 research evidence')
    meta=json.loads(results.read_text())
    args={'signer_fp':meta['public_signer_fingerprint'],
          'verifier_fp':meta['public_verifier_fingerprint'],
          'tip':meta['trusted_tip_sha256'],'case_count':15}
    assert check(public,source,**args)['signed_cases']==15
    with tempfile.TemporaryDirectory() as t:
        q=Path(t)/'witness';shutil.copytree(public,q)
        (q/'revisions'/'orphan.json').write_text('fake\n')
        with pytest.raises(ValueError,match='orphaned'):
            check(q,source,**args)