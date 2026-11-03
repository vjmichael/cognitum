"""Public/offline cryptographic audit of original CH37 dual-UID witnesses.

Requires two independently pinned Ed25519 fingerprints and a latest signed
tip. Checks original CH32/CH33 frozen digests byte-for-byte. Does NOT replay
MPFR, trust a self-asserted fingerprint, or claim an off-host anchor.
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
D=Path(__file__).resolve().parent;sys.path.insert(0,str(D))
from protocol37 import parse,sha
from trust37 import audit_chain

def check(public_witness,original_root,*,signer_fp,verifier_fp,tip,case_count=15):
    p=Path(public_witness);original_root=Path(original_root)
    pins=parse((p/'frozen_pins.json').read_bytes())
    heads=json.loads((original_root/'CH_C14_32/heads.json').read_text())
    checkpoints=json.loads((original_root/'CH_C14_33/checkpoint_heads.json').read_text())
    if len(heads)!=15 or set(heads)!=set(checkpoints) or set(heads)!=set(pins):
        raise ValueError('Original 15 CH23 cases do not match signer manifest')
    for case in sorted(heads):
        expect={'original_head_sha256':heads[case],
                'checkpoint_sha256':checkpoints[case],
                'checkpoint_file_sha256':sha((original_root/'CH_C14_33/active'/case/'checkpoint.json').read_bytes()),
                'nodes':127}
        if pins[case]!=expect:raise ValueError('Signer policy changed the original source: '+case)
    audited=audit_chain(p,(p/'public.ed25519.pem').read_bytes(),(p/'verifier_public.ed25519.pem').read_bytes(),
                        signer_fingerprint=signer_fp,verifier_fingerprint=verifier_fp,expected_tip=tip,pins=pins)
    if audited['length']!=case_count:raise ValueError('Unexpected signed-original case count')
    records=list((p/'revisions').iterdir())
    if len(records)!=case_count or any(not f.is_file() or not f.name.endswith('.json') for f in records):
        raise ValueError('Unreachable, orphaned or unknown public witness revisions')
    return {'status':'PASS','original_source_cases':15,'signed_cases':audited['length'],
            'signed_case_names':audited['cases'],
            'signer_signatures_verified':audited['verified_signer_signatures'],
            'verifier_signatures_verified':audited['verified_verifier_tickets'],
            'expected_signer_fingerprint':signer_fp,'expected_verifier_fingerprint':verifier_fp,
            'expected_tip':tip,'original_CH32_CH33_pins_matched':15,
            'fresh_MPFR_in_this_public_audit':False,'production_release':'NO_GO','global_certifications':0}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--public',type=Path,default=D/'CH37_public_witness')
    p.add_argument('--original',type=Path,default=Path('/mnt/data/CH37_baseline'))
    p.add_argument('--signer-fingerprint',required=True)
    p.add_argument('--verifier-fingerprint',required=True)
    p.add_argument('--tip',required=True)
    p.add_argument('--expected-count',type=int,default=15)
    a=p.parse_args();v=check(a.public,a.original,signer_fp=a.signer_fingerprint,
        verifier_fp=a.verifier_fingerprint,tip=a.tip,case_count=a.expected_count)
    print(json.dumps(v,sort_keys=True,indent=2))
if __name__=='__main__':main()
