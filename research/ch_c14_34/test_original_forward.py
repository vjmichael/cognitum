"""CH34 real CH23 two-generation anchor integration (no synthetic data).

Uses original CH33 63-node archived checkpoint and 127-node final
checkpoint, replaying mathematical proofs on both and testing explicit
roll-forward after interrupted HEAD publication.
"""
from __future__ import annotations
import errno, json, shutil, sys, tempfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
D=Path(__file__).resolve().parent
sys.path[:0]=[str(D),str(ROOT/'CH_C14_33'),str(ROOT/'CH_C14_31')]
from anchor34 import AnchorLedger,GENESIS,publish_verified_ch33,reconcile_after_head_interruption,attestation_from_verified_ch33
from compaction33 import CompactProofJournal,_read_archive,canonical
from verifier31 import load_original_case

def run():
    case='one_event_n80_i00';t=time.process_time()
    inp,proto,duals,_=load_original_case(case)
    src_active=ROOT/'CH_C14_33/active'/case
    src_arch=ROOT/'CH_C14_33/archives'/case
    current=json.loads((src_active/'checkpoint.json').read_text())
    latest_archive=_read_archive(src_arch/current['body']['archive_file'])
    previous=latest_archive['prior_checkpoint_envelope']
    assert previous['body']['stage_nodes']==63 and current['body']['stage_nodes']==127
    assert current['body']['prior_checkpoint_sha256']==previous['sha256']
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp);active=root/'active';archives=root/'archives';anchor=root/'external_anchor'
        active.mkdir();shutil.copytree(src_arch,archives)
        (active/'checkpoint.json').write_bytes(canonical(previous)+b'\n')
        ledger=AnchorLedger(anchor)
        with CompactProofJournal(active,inp,proto,duals,case_id=case,archive_dir=archives,
                                 expected_head_sha256=previous['body']['head_sha256'],
                                 expected_checkpoint_sha256=previous['sha256']) as j:
            assert j.recovery_fresh==63
            first=publish_verified_ch33(ledger,j,expected_tip_sha256=GENESIS,
                                        expected_source_head=previous['body']['head_sha256'],
                                        expected_checkpoint_sha256=previous['sha256'])
        # Real CH33 127-node checkpoint is durable, but external anchor still pins 63.
        (active/'checkpoint.json').write_bytes(canonical(current)+b'\n')
        with CompactProofJournal(active,inp,proto,duals,case_id=case,archive_dir=archives,
                                 expected_head_sha256=current['body']['head_sha256'],
                                 expected_checkpoint_sha256=current['sha256']) as j:
            assert j.recovery_fresh==127
            proof=attestation_from_verified_ch33(j,trusted_prior=ledger.read(expected_tip_sha256=first))
            try:
                ledger.publish(proof,expected_tip_sha256=first,fail_at='after_head_rename')
            except OSError as e:
                assert e.errno==errno.ENOSPC
            else:raise AssertionError('Injected failure did not occur')
            try:ledger.read(expected_tip_sha256=first)
            except ValueError:pass
            else:raise AssertionError('Externally pinned earlier tip improperly accepted')
            recovered=reconcile_after_head_interruption(ledger,j,trusted_prior_tip_sha256=first)
            assert recovered['status']=='REQUIRES_EXTERNAL_REPIN'
            final=ledger.read(expected_tip_sha256=recovered['tip_sha256'])
            assert final['body']['generation']==1
            assert final['body']['parent_sha256']==first
            assert final['body']['checkpoint_sha256']==current['sha256']
            assert final['body']['mpfr_replayed_frames']==6
            print(json.dumps({'original_case':case,'first_checkpoint_nodes':63,'final_checkpoint_nodes':127,
                              'first_tip_sha256':first,'final_proposed_tip_sha256':recovered['tip_sha256'],
                              'archive_epochs':2,'archived_frames_reverified':6,
                              'cpu_seconds':time.process_time()-t,
                              'durable_repin_executed':False,'scientific_go':False},sort_keys=True),flush=True)
if __name__=='__main__':run()
