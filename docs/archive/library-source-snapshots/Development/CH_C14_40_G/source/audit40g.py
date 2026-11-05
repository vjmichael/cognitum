"""Read-only public CH40G research witness auditor.
Requires EXTERNAL signer and attestor public key fingerprints and terminal tip.
Verifies Ed25519 signatures (distinct research domains), original frozen policy,
CH40F original trace and cert hash pins, nonce/case uniqueness and ledger chain.
This does not redo the mathematical computation or establish any global optimum.
"""
from __future__ import annotations
import argparse,hashlib,json,pathlib,zipfile
from caps_policy40g import ORIGINAL_ARCHIVE_SHA256,PINNED
from protocol39 import canonical,sha,parse
from trust39 import audit_chain

def audit(public,archive,*,tip,signer_fp,attestor_fp):
    public=pathlib.Path(public);archive=pathlib.Path(archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=ORIGINAL_ARCHIVE_SHA256:
        raise ValueError('Externally pinned CH39 historical archive changed')
    with zipfile.ZipFile(archive) as z:
        source=json.loads(z.read('CH_C14_39/CH39_public_witness/frozen_pins.json'))
        f=json.loads(z.read('CH_C14_29/frozen_protocol.json'))
    frozen=parse((public/'frozen_pins.json').read_bytes())
    if source!=frozen or len(frozen)!=15 or set(frozen)!=set(PINNED):
        raise ValueError('Original frozen policy replaced')
    for case,data in PINNED.items():
        if data['original_case_sha256']!=f['original_case_sha256'][case]:
            raise ValueError('CH40-G accepted incorrect frozen original identity')
    sp=(public/'public.ed25519.pem').read_bytes()
    ap=(public/'attestor_public.ed25519.pem').read_bytes()
    v=audit_chain(public,sp,ap,signer_fingerprint=signer_fp,
          attestor_fingerprint=attestor_fp,expected_tip=tip,pins=frozen)
    revisions=list((public/'revisions').iterdir())
    if len(revisions)!=v['length'] or not 1<=v['length']<=15:
        raise ValueError('Orphan/missing research revisions')
    return {'milestone':'CH40G','status':'PASS_RESEARCH_SIGNED_CHAIN_ONLY',
      'signed_revisions':v['length'],'cases':v['cases'],'tips_pinned_externally':True,
      'signed_trace_caps_research_only':True,'original_CH23_cases_pinned':15,
      'attestor_signatures_verified':v['verified_attestor_tickets'],
      'signer_signatures_verified':v['verified_signer_signatures'],
      'terminal_tip_sha256':tip,'signer_fingerprint_sha256':signer_fp,
      'attestor_fingerprint_sha256':attestor_fp,'source_archive_sha256':ORIGINAL_ARCHIVE_SHA256,
      'public_audit_reexecutes_mathematics':False,'global_optimality_certified':False,
      'scientific_release':'NO_GO','production_admission':False}

def main():
    p=argparse.ArgumentParser()
    for k in ('public','archive','tip','signer-fingerprint','attestor-fingerprint'):
        p.add_argument('--'+k,required=True)
    a=p.parse_args();r=audit(a.public,a.archive,tip=a.tip,signer_fp=a.signer_fingerprint,
                                attestor_fp=a.attestor_fingerprint)
    print(json.dumps(r,indent=2,sort_keys=True))
if __name__=='__main__':main()