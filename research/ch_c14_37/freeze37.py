"""Reproducibly freeze CH37 protocol and method/source hashes after acceptance."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
D=Path(__file__).resolve().parent;ORIGINAL=Path('/mnt/data/CH37_baseline')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    results=json.loads((D/'original15_results.json').read_text())
    base=json.loads((ORIGINAL/'CH_C14_33/frozen_protocol.json').read_text())
    caseids=sorted(json.loads((ORIGINAL/'CH_C14_33/checkpoint_heads.json').read_text()))
    if results['case_count']!=15 or sorted(results['original_CH23_cases_tested'])!=caseids or len(caseids)!=15:
        raise ValueError('CH37 cannot freeze without 15 accepted original CH23 cases')
    methods=['protocol37.py','trust37.py','verifier37.py','signer37.py','harness37.py','audit37.py',
             'tests/test_protocol37.py','tests/test_fail_closed_live.py','tests/test_public_archive37.py',
             'freeze37.py','package37.py','make_report37.py']
    frozen={'milestone':'CH-C14-37','date':'2026-11-02','status':'research_Linux_acceptance',
            'parent_commit':'9a783e35dc76e7c3699a1cd0e6975608af4cf10b',
            'frozen_original_CH23_cases':caseids,'case_count':15,
            'precision_bits':224,'nodes_per_case':127,'archived_frames_per_case':6,
            'global_optimality_certifications':0,'scientific_release':'NO_GO',
            'original_CH33_protocol_sha256':sha(ORIGINAL/'CH_C14_33/frozen_protocol.json'),
            'unchanged_original_CH32_heads_sha256':sha(ORIGINAL/'CH_C14_32/heads.json'),
            'unchanged_original_CH33_checkpoint_pins_sha256':sha(ORIGINAL/'CH_C14_33/checkpoint_heads.json'),
            'original_CH35_math_verifier_source_sha256':sha(ORIGINAL/'CH_C14_35/trust35.py'),
            'method_sha256':{path:sha(D/path) for path in methods},
            'OS_accounts':{'untrusted_journal_writer_uid':1000,'math_verifier_uid':1002,'witness_signer_uid':65534,
                           'verifier_to_signer_group':3101},
            'signer_witness_format_version':2,
            'signer_public_key_fingerprint':results['public_signer_fingerprint'],
            'verifier_public_key_fingerprint':results['public_verifier_fingerprint'],
            'signer_protected_policy_sha256':results['frozen_policy_sha256'],
            'externally_recorded_tip_sha256':results['trusted_tip_sha256'],
            'private_keys_distributed':False,'off_host_root_of_trust_implemented':False,
            'windows_tested':False,'hardware_power_cut_tested':False,
            'C14_G25_Lu_production_modified':False,
            'recovery_and_replay_behavior':'deny unpinned HEAD, orphan revisions, duplicates and recycled verifier nonces'}
    (D/'frozen_protocol.json').write_text(json.dumps(frozen,sort_keys=True,indent=2)+'\n')
    print('Frozen CH37 original',len(caseids),'cases',frozen['externally_recorded_tip_sha256'])
if __name__=='__main__':main()
