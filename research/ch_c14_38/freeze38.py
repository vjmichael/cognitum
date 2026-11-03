"""CH38 frozen security/mathematical acceptance ledger (requires exact 15 originals)."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
D=Path(__file__).resolve().parent;BASE=Path('/mnt/data/CH37_baseline')
def filehash(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
    result=json.loads((D/'original15_results.json').read_text())
    cases=sorted(json.loads((BASE/'CH_C14_33/checkpoint_heads.json').read_text()))
    if result['test_status']!='PASS' or result['case_count']!=15 or \
      sorted(result['original_CH23_cases_tested'])!=cases:
        raise ValueError('CH38 cannot freeze partial/non-original verification results')
    if result['audit']['signed_cases']!=15 or result['audit']['signer_signatures_verified']!=15 or \
       result['audit']['attestor_signatures_verified']!=15:
        raise ValueError('CH38 external two-signature audit incomplete')
    import sys;sys.path.insert(0,str(D))
    from audit38 import check
    audited=check(D/'CH38_public_witness',BASE,signer_fp=result['public_signer_fingerprint'],
                  attestor_fp=result['public_attestor_fingerprint'],tip=result['tip_sha256'])
    if audited!=result['audit']:raise ValueError('External audit differs from original results')
    names=['protocol38.py','trust38.py','math38.py','attestor38.py','signer38.py','harness38.py','audit38.py',
           'freeze38.py','package38.py','make_report38.py','README.md','tests/test_protocol38.py','tests/test_attestor38.py',
           'tests/test_live_denial.py']
    final={'milestone':'CH-C14-38','date':'2026-11-02','disposition':'Linux scoped research PASS',
           'previous_GitHub_CH37_commit':'fc1d6f220f0cfef34f868007d7a2745192cb0a66',
           'original_cases':cases,'original_case_count':len(cases),'MPFR_precision_bits':224,
           'checkpoint_nodes_each':127,'archived_frames_each':6,
           'original_CH32_heads_file_sha256':filehash(BASE/'CH_C14_32/heads.json'),
           'original_CH33_checkpoint_pins_file_sha256':filehash(BASE/'CH_C14_33/checkpoint_heads.json'),
           'original_CH35_math_verifier_source_sha256':filehash(BASE/'CH_C14_35/trust35.py'),
           'source_sha256':{name:filehash(D/name) for name in names},
           'account_UIDs':{'writer':1000,'math':1002,'attestor':1003,'signer':65534},
           'attestor_key_fingerprint':result['public_attestor_fingerprint'],
           'signer_key_fingerprint':result['public_signer_fingerprint'],
           'trusted_final_tip_sha256':result['tip_sha256'],'pinned_original_policy_sha256':result['policy_sha256'],
           'signed_original_cases':15,'mathematical_truth_independent_of_math_uid':False,
           'attestor_holds_MPFR_original_source':False,'two_private_keys_distributed':False,
           'external_off_host_anchor_deployed':False,'windows_tested':False,'power_cut_tested':False,
           'scientific_global_certifications':0,'scientific_release':'NO_GO',
           'C14_G25_Lu_production_modified':False}
    (D/'frozen_protocol.json').write_text(json.dumps(final,sort_keys=True,indent=2)+'\n')
    print('CH38 source and results frozen, original cases',len(cases))
if __name__=='__main__':main()
