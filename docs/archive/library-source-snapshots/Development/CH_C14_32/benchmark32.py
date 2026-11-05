"""CH32 original 15 CH23 datasets: durable 6-stage journal + real crash/restart.

Intermediate prefixes 7/15/31/95 are projections of unmodified CH29 proofs,
NOT new solver searches. Journal replay is full fresh MPFR verification.
"""
from __future__ import annotations
import argparse,concurrent.futures,json,os,subprocess,sys,time,traceback
from pathlib import Path
D=Path(__file__).resolve().parent;sys.path[:0]=[str(D),str(D.parent/'CH_C14_31')]
from journal32 import ProofJournal,SimulatedCrash,digest
from verifier31 import load_original_case,sha
from prefix31 import project_prefix
STAGES=(7,15,31,63,95,127)


def verify_case(cid):
    inp,proto,duals,archive=load_original_case(cid)
    c63,receipt63=archive(63);c127,receipt127=archive(127)
    def cert(n):return c63 if n==63 else c127 if n==127 else project_prefix(c63 if n<63 else c127,n)
    path=D/'journals'/cid
    if path.exists() and any(path.iterdir()):raise ValueError('Journal must start empty: '+str(path))
    logs=[];start=time.process_time();crash_type='none'
    with ProofJournal(path,inp,proto,duals,case_id=cid) as j:
        for n in STAGES[:4]:
            t=time.process_time();v=j.append(cert(n));logs.append({'nodes':n,'cpu_seconds':time.process_time()-t,'fresh':v['fresh_nodes'],'reused':v['reused_nodes'],'sha256':v['head_sha256']})
        if cid=='one_event_n80_i00':
            crash_type='before_rename'
            try:j.append(cert(95),crash_at=crash_type)
            except SimulatedCrash:pass
            else:raise AssertionError('Crash hook did not fire')
        elif cid=='zero_balanced_n80_i00':
            crash_type='after_dir_fsync'
            try:j.append(cert(95),crash_at=crash_type)
            except SimulatedCrash:pass
            else:raise AssertionError('Crash hook did not fire')
    resume_cmd=[sys.executable,str(D/'restart32.py'),'--case',cid,'--journal',str(path)]
    if crash_type=='before_rename':resume_cmd.append('--discard-uncommitted')
    rec_proc=subprocess.run(resume_cmd,check=True,text=True,capture_output=True,timeout=720)
    resumed=json.loads(rec_proc.stdout)
    if resumed['pid']==os.getpid() or resumed['imported_verified_state'] or resumed['final_nodes']!=127:
        raise AssertionError('Restart did not independently verify journal')
    if resumed['cold_recomputed_bounds']!=(95 if crash_type=='after_dir_fsync' else 63):
        raise AssertionError('Unexpected committed state at crash/restart boundary')
    final_proc=subprocess.run([sys.executable,str(D/'restart32.py'),'--case',cid,'--journal',str(path),
                            '--verify-only','--expected-head',resumed['head_sha256']],
                            check=True,text=True,capture_output=True,timeout=720)
    final=json.loads(final_proc.stdout)
    if (final['pid'] in (resumed['pid'],os.getpid()) or final['cold_recomputed_bounds']!=127 or
        final['initial_committed_stages']!=6 or final['head_sha256']!=resumed['head_sha256'] or
        abs(final['gap_upper_display']-receipt127['gap_upper_display'])>1e-10):
        raise AssertionError('Independent cold final replay disagrees with original CH29')
    files=sorted(path.glob('*.json'))
    if len(files)!=6:raise AssertionError('Missing durable stages')
    return {'case_id':cid,'original_case_sha256':proto['original_case_sha256'][cid],
            'original_data_identity':inp['original_CH23_identity'],'crash_injection':crash_type,
            'initial_stages':logs,'fresh_restart':resumed,'cold_final_replay':final,
            'committed_frames':len(files),'frame_sha256':[sha(p) for p in files],
            'original_63_gap':receipt63['gap_upper_display'],
            'original_127_gap':receipt127['gap_upper_display'],
            'duration_cpu_seconds':time.process_time()-start,
            'math_verified':True,'certified':False,'production_release':'NO_GO'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=4);p.add_argument('--case',action='append');a=p.parse_args()
    fp=D/'frozen_protocol.json';h=(D/'frozen_protocol.sha256').read_text().split()[0]
    if sha(fp)!=h:raise ValueError('CH32 frozen protocol digest changed')
    frozen=json.loads(fp.read_text());cases=sorted(frozen['original_case_sha256'])
    if a.case:cases=[x for x in cases if x in a.case]
    start=time.perf_counter();out=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
        fs={pool.submit(verify_case,c):c for c in cases}
        for future in concurrent.futures.as_completed(fs):
            try:r=future.result()
            except Exception:
                print('FAILED',fs[future],traceback.format_exc(),flush=True);raise
            out.append(r)
            print('PASS',r['case_id'],'frames',r['committed_frames'],'crash',r['crash_injection'],
                  'cold bounds',r['cold_final_replay']['cold_recomputed_bounds'],
                  'gap',format(r['original_127_gap'],'.6f'),flush=True)
    out.sort(key=lambda x:x['case_id'])
    study={'milestone':'CH-C14-32','frozen_protocol_sha256':h,'cases':len(out),
           'per_case':out,'journal_frames':sum(x['committed_frames'] for x in out),
           'total_fresh_final_replay_bounds':sum(x['cold_final_replay']['cold_recomputed_bounds'] for x in out),
           'crash_injections':{x['case_id']:x['crash_injection'] for x in out if x['crash_injection']!='none'},
           'total_writer_cpu_seconds':sum(sum(y['cpu_seconds'] for y in x['initial_stages']) for x in out),
           'total_resume_cpu_seconds':sum(x['fresh_restart']['cpu_seconds'] for x in out),
           'total_cold_final_replay_cpu_seconds':sum(x['cold_final_replay']['cpu_seconds'] for x in out),
           'elapsed_wall_seconds':time.perf_counter()-start,
           'original_ambiguous_case_refusals':sum(bool(x['original_data_identity'].get('ambiguous')) for x in out),
           'global_certificates':0,'scientific_release':'NO_GO',
           'derived_prefixes_not_new_optimizer_runs':True}
    outname='benchmark_results.json' if len(out)==len(frozen['original_case_sha256']) else 'benchmark_partial.json'
    (D/outname).write_text(json.dumps(study,indent=2,sort_keys=True,allow_nan=False)+'\n')
    (D/'heads.json').write_text(json.dumps({x['case_id']:x['cold_final_replay']['head_sha256'] for x in out},sort_keys=True,indent=2)+'\n')
    print('COMPLETE',len(out),'cases',study['journal_frames'],'durable frames,',
          study['total_fresh_final_replay_bounds'],'cold-recomputed MPFR nodes',flush=True)

if __name__=='__main__':main()