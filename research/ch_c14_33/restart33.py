"""CH33 cold, independent MPFR replay and complete historical archive audit."""
import argparse,json,os,sys,time
from pathlib import Path
D=Path(__file__).resolve().parent;sys.path[:0]=[str(D),str(D.parent/'CH_C14_31')]
from compaction33 import CompactProofJournal
from verifier31 import load_original_case

def cold(case,active,archives,head,checkpoint,full_history=False):
    inp,proto,duals,archived=load_original_case(case)
    _,source_receipt=archived(127)
    tick=time.process_time()
    with CompactProofJournal(active,inp,proto,duals,case_id=case,
                             archive_dir=archives,expected_head_sha256=head,
                             expected_checkpoint_sha256=checkpoint) as j:
        assert j.cert is not None and len(j.cert['nodes'])==127
        assert j.full_mathematical_replay and j.recovery_fresh==127
        assert abs(j.session._last_cap-source_receipt['gap_upper_display'])<1e-10
        metadata=j.verify_archive_chain_metadata()
        t=time.process_time()
        history=j.verify_archived_history() if full_history else None
        audit_cpu=time.process_time()-t
        assert history is None or (history['replayed_frames']==6 and history['archives']==len(list(Path(archives).glob('archive_*.zlib'))))
        return {'pid':os.getpid(),'case_id':case,'nodes':127,'head_sha256':j.head,
                'checkpoint_sha256':j._checkpoint['sha256'],'fresh_MPFR_bounds':j.recovery_fresh,
                'trusted_cache_imported':False,'checkpoint_math_reverified':True,
                'checkpoint_gap':j.session._last_cap,'original_CH29_gap':source_receipt['gap_upper_display'],
                'archive_chain':metadata,'full_archived_history':history,
                'full_archive_audit_cpu_seconds':audit_cpu,'total_process_cpu_seconds':time.process_time()-tick,
                'global_certificate':False,'scientific_release':'NO_GO'}
if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--case',required=True);p.add_argument('--active',required=True,type=Path)
    p.add_argument('--archives',required=True,type=Path)
    p.add_argument('--head',required=True);p.add_argument('--checkpoint',required=True)
    p.add_argument('--full-history',action='store_true')
    a=p.parse_args()
    print(json.dumps(cold(a.case,a.active,a.archives,a.head,a.checkpoint,a.full_history),sort_keys=True,allow_nan=False))
