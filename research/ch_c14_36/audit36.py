"""CH36 independent *public* receipt/signature/pin audit, no signing secret.

This validates the signer artifact's chain and exact CH32/CH33 identities.
It does NOT independently re-run MPFR mathematics and cannot establish an
external root of trust absent a separately pinned public-key fingerprint/tip.
"""
from __future__ import annotations
import argparse,base64,hashlib,json,sys
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
ROOT=Path(__file__).resolve().parents[1]
DOMAIN=b'Cognitum/CH35/independent-CH23-proof-attestation/v1\x00'
ZERO='0'*64

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def check(records,pub_pem,expected_fp,expected_tip,heads,checkpoints):
    if sha(pub_pem)!=expected_fp:raise ValueError('Substituted public key')
    pub=serialization.load_pem_public_key(pub_pem)
    if not isinstance(pub,Ed25519PublicKey):raise ValueError('Non-Ed25519 witness key')
    seen=set();parent=ZERO
    if len(records)!=len(heads) or len(heads)!=len(checkpoints) or len(heads)!=15:
        raise ValueError('Not exactly the original 15 cases')
    for index,wr in enumerate(records):
        r=wr['record'];b=r['body']
        if not isinstance(b,dict) or set(r)!={'body','signature'}:raise ValueError('Forged record schema')
        pub.verify(base64.b64decode(r['signature'],validate=True),DOMAIN+canonical(b))
        tip=sha(canonical(r));case=b['case_id']
        if wr['tip_sha256']!=tip or wr['record_sha256']!=tip:
            raise ValueError('Receipt or signature hash does not match')
        if b['generation']!=index or b['parent']!=parent:raise ValueError('Noncontiguous signed history')
        if case in seen or case not in heads:raise ValueError('Case duplicate or substituted')
        seen.add(case)
        if b['original_head_sha256']!=heads[case] or b['checkpoint_sha256']!=checkpoints[case]:
            raise ValueError('Wrong frozen original source or checkpoint pin')
        if b['witness_key_fingerprint']!=expected_fp or b['proof_replayed'] is not True or \
           b['nodes']!=127 or b['archive_epochs']!=2 or b['mpfr_replayed_frames']!=6 or \
           b['scientific_release']!='NO_GO' or b['verified_source']!='original_CH23_independent_MPFR_224':
            raise ValueError('Signed scope is unsupported')
        parent=tip
    if parent!=expected_tip or seen!=set(heads):raise ValueError('Signed final tip or source coverage mismatch')
    return {'status':'PASS','signatures_verified':15,'source_pins_matched':15,
            'latest_signed_tip_sha256':parent,'public_key_fingerprint_sha256':expected_fp,
            'mathematical_proofs_recomputed_by_this_auditor':False,
            'global_optimality_certifications':0}

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--results',type=Path,default=ROOT/'CH_C14_36/original15_results.json')
    parser.add_argument('--public-key',type=Path,default=ROOT/'CH_C14_36/witness_public_key.pem')
    parser.add_argument('--original-root',type=Path,default=ROOT)
    parser.add_argument('--expected-fingerprint',required=True)
    parser.add_argument('--expected-tip',required=True)
    a=parser.parse_args(argv)
    v=json.loads(a.results.read_text())
    heads=json.loads((a.original_root/'CH_C14_32/heads.json').read_text())
    cp=json.loads((a.original_root/'CH_C14_33/checkpoint_heads.json').read_text())
    audit=check(v['records'],a.public_key.read_bytes(),a.expected_fingerprint,a.expected_tip,heads,cp)
    print(json.dumps(audit,indent=2,sort_keys=True))
    return 0
if __name__=='__main__':raise SystemExit(main())
