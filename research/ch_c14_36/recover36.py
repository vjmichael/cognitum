"""Read-only CH36 batch evidence reconstruction after an admission-test timeout.

The original 15 sealed cases were already independently signed and their
protected HEAD/tip committed; this tool only exports that *existing* signed
ledger. It NEVER signs, advances, or rewrites an attestation. Requires exact
separately supplied public-key fingerprint and latest tip, and exact original
CH32/CH33 input pins.
"""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
D=Path(__file__).resolve().parent
sys.path.insert(0,str(D))
from audit36 import check,canonical,sha

def export(store,original,expected_fp,expected_tip,out):
    store=Path(store);original=Path(original)
    pub=(store/'public.ed25519.pem').read_bytes()
    pinned=json.loads((store/'trusted_tip.json').read_text())
    if pinned != {'fingerprint':expected_fp,'tip':expected_tip}:
        raise ValueError('Protected authority pin does not match separately supplied expectation')
    entries=sorted((store/'revisions').glob('*.json'))
    if len(entries)!=15:raise ValueError('Signed ledger is not complete')
    records=[]
    for i,p in enumerate(entries):
        obj=json.loads(p.read_bytes())
        digest=sha(canonical(obj))
        if p.name!=f'{i:08d}_{digest}.json':raise ValueError('Revision file/number mismatch')
        records.append({'case_id':obj['body']['case_id'],'tip_sha256':digest,
                        'record_sha256':digest,'record':obj})
    heads=json.loads((original/'CH_C14_32/heads.json').read_text())
    checkpoints=json.loads((original/'CH_C14_33/checkpoint_heads.json').read_text())
    audit=check(records,pub,expected_fp,expected_tip,heads,checkpoints)
    result={'milestone':'CH-C14-36','status':'SIGNED_LEDGER_FULLY_VERIFIED',
            'scope':'original frozen CH23/CH29/CH32/CH33 numerical evidence',
            'source':'original_CH23_independent_MPFR_224',
            'original_case_count':15,'newly_covered_cases_vs_CH35':14,
            'signer_account_uid':65534,'journal_writer_uid':1000,
            'source_and_key_isolated_from_journal_writer':True,
            'original_127_node_replays_attested_by_signer':15,
            'historical_6_frame_replays_attested_by_signer':90,
            'signed_tip_sha256':expected_tip,'public_key_fingerprint_sha256':expected_fp,
            'signed_chain_audit':audit,'records':records,
            'scientific_release':'NO_GO','global_optimality_certifications':0,
            'storage_full_tests_are_separate':True,'power_loss_tested':False,
            'windows_tested':False,
            'harness_note':'Original batch completed 15 actual signed writes; the optional duplicate-request check timed out before JSON export. This export reconstructs only the existing authority ledger, with independently verified signatures and original CH32/CH33 pins.'}
    out=Path(out);out.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    (D/'witness_public_key.pem').write_bytes(pub)
    print(json.dumps({'status':result['status'],'cases':15,'signed_tip':expected_tip,
                      'signature_audit':audit['signatures_verified']},sort_keys=True))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ('store','original','expected-fingerprint','expected-tip','out'):p.add_argument('--'+k,required=True)
    a=p.parse_args()
    export(a.store,a.original,a.expected_fingerprint,a.expected_tip,a.out)
