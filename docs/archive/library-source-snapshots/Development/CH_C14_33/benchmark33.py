"""Original 15-case CH32 journal => two compacted epochs, cold restart, full replay.

Copies exact CH32 frames and original CH29 proof provenance; intermediate
7/15/31/95-node stages are archived projections, NOT new optimizer runs.
"""
import argparse,concurrent.futures,hashlib,json,os,shutil,subprocess,sys,time,traceback
from pathlib import Path
D=Path(__file__).resolve().parent;ROOT=D.parent
sys.path[:0]=[str(D),str(ROOT/'CH_C14_31')]
from compaction33 import CompactProofJournal
from verifier31 import load_original_case,sha

PINNED_HEADS=json.loads((ROOT/'CH_C14_32/heads.json').read_text())

def one_case(cid):
    inp,proto,duals,arch=load_original_case(cid)
    c127,source_receipt=arch(127)
    original=ROOT/'CH_C14_32/journals'/cid
    active=D/'active'/cid;archives=D/'archives'/cid
    if active.exists() or archives.exists():raise ValueError('Benchmark destination must be empty: '+cid)
    active.mkdir(parents=True)
    src_files=[original/f'{i:06d}.json' for i in range(6)]
    if any(not p.is_file() for p in src_files):raise ValueError('Missing CH32 original journal')
    src_sha=[sha(p) for p in src_files]
    baseline=sum(p.stat().st_size for p in src_files)
    for p in src_files[:4]:shutil.copy2(p,active/p.name)
    initial_active=sum(p.stat().st_size for p in active.glob('*.json'))
    before=time.process_time()
    with CompactProofJournal(active,inp,proto,duals,case_id=cid,archive_dir=archives,max_active_bytes=100*1024) as j:
        assert (j.seq,len(j.cert['nodes']),j.recovery_fresh)==(4,63,63)
        first=j.compact()
        assert first['compacted_frames']==4
        active_after_first=j._active_bytes()
    first_cpu=time.process_time()-before
    for p in src_files[4:]:shutil.copy2(p,active/p.name)
    before=time.process_time()
    with CompactProofJournal(active,inp,proto,duals,case_id=cid,archive_dir=archives,
                             expected_checkpoint_sha256=first['checkpoint_sha256'],
                             expected_head_sha256=PINNED_HEADS[cid],
                             max_active_bytes=100*1024) as j:
        assert j.seq==6 and len(j.cert['nodes'])==127 and j.recovery_fresh==127
        second=j.compact()
        assert second['compacted_frames']==2 and second['head_sha256']==PINNED_HEADS[cid]
        active_after_second=j._active_bytes()
    second_cpu=time.process_time()-before
    cmd=[sys.executable,str(D/'restart33.py'),'--case',cid,'--active',str(active),'--archives',str(archives),
         '--head',PINNED_HEADS[cid],'--checkpoint',second['checkpoint_sha256'],'--full-history']
    proc=subprocess.run(cmd,text=True,capture_output=True,check=True,timeout=960)
    final=json.loads(proc.stdout)
    if final['pid']==os.getpid() or final['fresh_MPFR_bounds']!=127 or final['full_archived_history']['replayed_frames']!=6:
        raise AssertionError('No independent cold proof replay')
    if abs(final['checkpoint_gap']-source_receipt['gap_upper_display'])>1e-10:
        raise AssertionError('Compacted gap changed vs original CH29')
    if any(sha(original/p.name)!=src_sha[i] for i,p in enumerate(src_files)):
        raise AssertionError('Original CH32 source mutated')
    archived_bytes=sum(p.stat().st_size for p in archives.glob('*.zlib'))
    return {'case_id':cid,'original_case_sha256':proto['original_case_sha256'][cid],
            'historical_ambiguous':bool(inp['original_CH23_identity'].get('ambiguous')),
            'source_frames_sha256':src_sha,'CH32_external_original_head_sha256':PINNED_HEADS[cid],
            'first_compaction':first,'second_compaction':second,'cold_restart':final,
            'source_original_active_bytes_6_frames':baseline,
            'pre_first_compaction_bytes':initial_active,
            'after_63_compaction_active_bytes':active_after_first,
            'after_127_compaction_active_bytes':active_after_second,
            'retained_external_archive_bytes':archived_bytes,
            'total_local_bytes_after_compaction':active_after_second+archived_bytes,
            'active_storage_reduction_percent':100*(1-active_after_second/baseline),
            'total_local_storage_reduction_percent':100*(1-(active_after_second+archived_bytes)/baseline),
            'first_write_and_recovery_cpu_seconds':first_cpu,
            'second_write_and_recovery_cpu_seconds':second_cpu,
            'original_CH29_127_gap':source_receipt['gap_upper_display'],
            'false_certifications':0,'production':'NO_GO'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=3)
    p.add_argument('--case',action='append');a=p.parse_args()
    orig=json.loads((ROOT/'CH_C14_29/frozen_protocol.json').read_text())
    cases=sorted(orig['original_case_sha256']);cases=[x for x in cases if a.case is None or x in a.case]
    start=time.perf_counter();rows=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
        fs={pool.submit(one_case,c):c for c in cases}
        for future in concurrent.futures.as_completed(fs):
            try:row=future.result()
            except BaseException:
                print('FAILED',fs[future],traceback.format_exc(),flush=True);raise
            rows.append(row)
            print('PASS',row['case_id'],'active',row['after_127_compaction_active_bytes'],
                  'archive',row['retained_external_archive_bytes'],
                  'head',row['CH32_external_original_head_sha256'][:12],flush=True)
    rows.sort(key=lambda x:x['case_id'])
    study={'milestone':'CH-C14-33','date':'2026-11-02','cases':len(rows),'per_case':rows,
           'compacted_epoch_count':sum(2 for _ in rows),'archived_original_frames':sum(6 for _ in rows),
           'total_original_active_bytes':sum(x['source_original_active_bytes_6_frames'] for x in rows),
           'total_compacted_active_bytes':sum(x['after_127_compaction_active_bytes'] for x in rows),
           'total_retained_external_archives_bytes':sum(x['retained_external_archive_bytes'] for x in rows),
           'full_history_mathematical_replays':len(rows),'cold_final_replays':len(rows),
           'original_ambiguity_refusals':sum(x['historical_ambiguous'] for x in rows),
           'global_optimality_certifications':0,'production_release':'NO_GO',
           'unbounded_archive_growth_caveat':True,
           'derived_CH32_projected_stages_not_new_solver_runs':True,
           'elapsed_wall_seconds':time.perf_counter()-start}
    target=D/('benchmark_results.json' if len(rows)==15 else 'benchmark_partial.json')
    target.write_text(json.dumps(study,indent=2,sort_keys=True,allow_nan=False)+'\n')
    (D/'checkpoint_heads.json').write_text(json.dumps({r['case_id']:r['second_compaction']['checkpoint_sha256'] for r in rows},indent=2,sort_keys=True)+'\n')
    print('COMPLETE',len(rows),'cases','active reduction',100*(1-study['total_compacted_active_bytes']/study['total_original_active_bytes']),flush=True)
if __name__=='__main__':main()