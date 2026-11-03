"""Run CH34 external-anchor publication against CH33's fifteen ORIGINAL CH23 proofs.

Each case performs independent CH33 cold MPFR checkpoint replay and COMPLETE
archived-history MPFR replay, then commits the new independently pinned ledger.
No optimizer reruns, no synthetic numerical inputs, no production admission.
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys, time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
D=Path(__file__).resolve().parent
ROOT=D.parent
sys.path[:0]=[str(D),str(ROOT/'CH_C14_33'),str(ROOT/'CH_C14_31')]
from anchor34 import AnchorLedger, GENESIS, publish_verified_ch33
from compaction33 import CompactProofJournal
from verifier31 import load_original_case


def case_run(cid, destination):
    active=ROOT/'CH_C14_33/active'/cid
    archives=ROOT/'CH_C14_33/archives'/cid
    original=json.loads((ROOT/'CH_C14_32/heads.json').read_text())[cid]
    checkpoint=json.loads((ROOT/'CH_C14_33/checkpoint_heads.json').read_text())[cid]
    inp,proto,duals,archive=load_original_case(cid)
    _, expected=archive(127)
    start=time.process_time()
    with CompactProofJournal(active,inp,proto,duals,case_id=cid,
                             archive_dir=archives,
                             expected_head_sha256=original,
                             expected_checkpoint_sha256=checkpoint) as j:
        if j.recovery_fresh != 127 or len(j.cert['nodes']) != 127 or not j.full_mathematical_replay:
            raise ValueError('Original 127-node CH33 proof was not replayed from scratch')
        if abs(j.session._last_cap - expected['gap_upper_display']) > 1e-10:
            raise ValueError('CH29 original display gap disagrees')
        root=destination/cid
        ledger=AnchorLedger(root,max_ledger_bytes=65536)
        proposed=publish_verified_ch33(ledger,j,expected_tip_sha256=GENESIS,
                                       expected_source_head=original,
                                       expected_checkpoint_sha256=checkpoint)
        witnessed=ledger.read(expected_tip_sha256=proposed)
        if (witnessed['body']['mpfr_replayed_frames'],witnessed['body']['archive_epochs']) != (6,2):
            raise ValueError('Archived mathematical history audit incomplete')
        if witnessed['body']['checkpoint_sha256'] != checkpoint:
            raise ValueError('Anchored checkpoint differs from CH33 frozen digest')
        return {'case_id':cid,'nodes':len(j.cert['nodes']),
                'fresh_MPFR_checkpoint_nodes':j.recovery_fresh,
                'MPFR_historical_frames':witnessed['body']['mpfr_replayed_frames'],
                'archive_epochs':witnessed['body']['archive_epochs'],
                'original_head_sha256':original,'checkpoint_sha256':checkpoint,
                'externally_retain_tip_sha256':proposed,
                'checkpoint_gap':j.session._last_cap,
                'previous_CH29_gap':expected['gap_upper_display'],
                'cpu_seconds':time.process_time()-start,
                'scientific_disposition':'UNRESOLVED_NO_GLOBAL_CERTIFICATE'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--case');p.add_argument('--workers',type=int,default=1)
    p.add_argument('--output',type=Path,default=D/'anchor_storage');a=p.parse_args()
    heads=json.loads((ROOT/'CH_C14_32/heads.json').read_text())
    ids=[a.case] if a.case else sorted(heads)
    if any(cid not in heads for cid in ids):raise ValueError('Unknown ORIGINAL CH23 case')
    a.output.mkdir(exist_ok=True,parents=True)
    results=[]
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        jobs={pool.submit(case_run,cid,a.output):cid for cid in ids}
        for job in as_completed(jobs):
            r=job.result();results.append(r)
            print(f"CH34 VERIFIED {r['case_id']} nodes={r['nodes']} full_frames={r['MPFR_historical_frames']} tip={r['externally_retain_tip_sha256'][:16]}",flush=True)
    results.sort(key=lambda x:x['case_id'])
    evidence={'protocol':'CH34 independently anchored CH33/CH23 ORIGINAL frozen',
              'case_count':len(results),'scientific_go':False,
              'results':results}
    path=D/'anchor_results.json'
    path.write_text(json.dumps(evidence,sort_keys=True,indent=2,allow_nan=False)+'\n')
    print('COMPLETE',len(results),'original cases, full MPFR audit each',flush=True)

if __name__=='__main__':main()
