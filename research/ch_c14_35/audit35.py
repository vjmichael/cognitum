"""Independent CH35 evidence audit without accessing a signer private key.

Signature verification is NOT mathematical MPFR proof replay. The separate
Linux authority is required for that, with frozen trusted sources.
"""
import base64,hashlib,json,os,sys
from pathlib import Path
D=Path(__file__).resolve().parent;ROOT=Path(os.environ.get("CH35_REPRO_ROOT",D.parent))
if not (ROOT/"CH_C14_33").is_dir() and Path("/mnt/data/CH34_repro").is_dir():ROOT=Path("/mnt/data/CH34_repro")
sys.path[:0]=[str(D),str(ROOT/'CH_C14_33')]
from trust35 import DOMAIN,canonical,hashbytes,shaobj,pubkey_fingerprint,signature_ok
from cryptography.hazmat.primitives import serialization


def audit():
    results=json.loads((D/'independent_process_results.json').read_text())
    pem=(D/'witness_public_key.pem').read_bytes()
    signed=results['signed_original'];record=signed['record'];body=record['body']
    pub=serialization.load_pem_public_key(pem)
    if not hasattr(pub,'verify'):raise AssertionError('Wrong key type')
    signature_ok(record,pub)
    fp=pubkey_fingerprint(pem)
    assert body['witness_key_fingerprint']==fp==signed['public_key_fingerprint_sha256']
    assert shaobj(record)==signed['tip_sha256']==results['verified_chain']['tip']
    heads=json.loads((ROOT/'CH_C14_32/heads.json').read_text())
    checkpoints=json.loads((ROOT/'CH_C14_33/checkpoint_heads.json').read_text())
    cid=body['case_id']
    assert body['original_head_sha256']==heads[cid]
    assert body['checkpoint_sha256']==checkpoints[cid]
    assert body['nodes']==127 and body['archive_epochs']==2 and body['mpfr_replayed_frames']==6
    assert body['scientific_release']=='NO_GO' and results['global_certificate'] is False
    assert results['status']=='PASS' and results['key_read_and_write_denied'] is True
    assert results['tampered_journal_denied']['ok'] is False
    assert results['second_sign_refused']['ok'] is False
    print(json.dumps({'CH35_signature':'VALID','original_case':cid,'original_head_pin':'MATCH',
                      'original_checkpoint_pin':'MATCH','signer_fingerprint':fp,
                      'signed_tip':shaobj(record),'scientific_release':'NO_GO',
                      'trusted_math_replay':'ATTESTED_BY_ISOLATED_AUTHORITY_NOT_RERUN_HERE'},sort_keys=True))
    return True

if __name__=='__main__':audit()
