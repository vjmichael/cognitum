"""Repeated real os._exit() failures at compaction boundaries, original CH23.

Exit code 77 is a deliberately killed process, not a clean Python return.
Records the state recovered after each hard-exit without trusting receipts.
"""
from __future__ import annotations
import argparse,json,os,shutil,subprocess,sys,time
from pathlib import Path
D=Path(__file__).resolve().parent;ROOT=D.parent;sys.path[:0]=[str(D),str(ROOT/'CH_C14_31')]
from compaction33 import CompactProofJournal,SimulatedCrash
from verifier31 import load_original_case

CID='one_event_n80_i00'
SRC=ROOT/'CH_C14_32/journals'/CID
END_HEAD=json.loads((ROOT/'CH_C14_32/heads.json').read_text())[CID]

def kill_compact(event,active,archives):
    inp,proto,duals,arch=load_original_case(CID)
    try:
        with CompactProofJournal(active,inp,proto,duals,case_id=CID,archive_dir=archives) as j:
            j.compact(crash_at=event)
    except SimulatedCrash:
        os._exit(77)
    os._exit(99)

def main():
    active=D/'chaos_active'/CID;archives=D/'chaos_archives'/CID
    if active.exists() or archives.exists():raise ValueError('Chaos results must begin empty')
    active.mkdir(parents=True)
    inp,proto,duals,arch=load_original_case(CID)
    for n in (0,1):shutil.copy2(SRC/f'{n:06d}.json',active/f'{n:06d}.json')
    stages=[('before_snapshot_rename',1),('after_snapshot_fsync',2),
            ('during_prune',3),('after_snapshot_rename',4),('after_snapshot_fsync',5)]
    events=[]
    for event,additional in stages:
        if additional!=1:shutil.copy2(SRC/f'{additional:06d}.json',active/f'{additional:06d}.json')
        p=subprocess.run([sys.executable,str(__file__),'--kill',event,'--active',str(active),'--archives',str(archives)],capture_output=True,text=True,timeout=120)
        if p.returncode!=77:raise AssertionError('Expected os._exit 77, got '+str(p.returncode)+' '+p.stderr)
        with CompactProofJournal(active,inp,proto,duals,case_id=CID,archive_dir=archives) as j:
            was_pending=len(j._pending);covered=len(j._covered)
            removed_pending=j.discard_pending()
            removed_covered=j.cleanup_covered()
            if event=='before_snapshot_rename':
                if j._checkpoint is not None or j.seq!=2:raise AssertionError('Uncommitted checkpoint became active')
                compact=j.compact()
            else:
                compact=None
                if j._checkpoint is None or j._checkpoint['body']['upto_seq']!=additional:
                    raise AssertionError('Durably committed snapshot missing on fresh restart')
            current=j._checkpoint
            if current is None:raise AssertionError('Compaction did not recover')
            events.append({'event':event,'exit_code':p.returncode,'frame_index':additional,
                           'cold_recomputed_bounds':j.recovery_fresh,
                           'pending_found':was_pending,'covered_found':covered,
                           'pending_explicitly_discarded':removed_pending,
                           'covered_explicitly_pruned':removed_covered,
                           'recovered_checkpoint_sha256':current['sha256'],
                           'recovered_original_head_sha256':j.head})
            print('HARD_EXIT_RECOVERED',event,'node_count',len(j.cert['nodes']),
                  'fresh',j.recovery_fresh,'pending',was_pending,'covered',covered,flush=True)
    with CompactProofJournal(active,inp,proto,duals,case_id=CID,archive_dir=archives,
                             expected_head_sha256=END_HEAD) as j:
        final_checkpoint=j._checkpoint['sha256']
        assert j.seq==6 and len(j.cert['nodes'])==127
    proc=subprocess.run([sys.executable,str(D/'restart33.py'),'--case',CID,'--active',str(active),
        '--archives',str(archives),'--head',END_HEAD,'--checkpoint',final_checkpoint,'--full-history'],
        capture_output=True,text=True,check=True,timeout=600)
    independently=json.loads(proc.stdout)
    assert independently['fresh_MPFR_bounds']==127
    assert independently['full_archived_history']['replayed_frames']==6
    out={'case':CID,'hard_process_terminations':len(events),'events':events,
         'original_CH32_final_head_sha256':END_HEAD,'final_checkpoint_sha256':final_checkpoint,
         'independent_cold_restart_and_full_history':independently,
         'actual_os_exit_used':True,'no_power_loss_claim':True,'mathematical_proof_global':False}
    (D/'chaos_results.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print('SUCCESS',len(events),'hard process exits, full original proof reverified',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--kill');p.add_argument('--active',type=Path);p.add_argument('--archives',type=Path)
    a=p.parse_args()
    if a.kill:kill_compact(a.kill,a.active,a.archives)
    else:main()
