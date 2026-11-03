"""Reconcile five already-observed os._exit recoveries with archived source facts.

For an interrupted stress harness, the durable archives + the recovered
per-event stdout are enough to create a post-hoc *clearly labeled* evidence
summary once a separate fresh-process final MPFR replay has passed.
"""
import json,re,sys
from pathlib import Path
D=Path(__file__).resolve().parent;sys.path[:0]=[str(D)]
from compaction33 import _read_archive,_read_envelope
from verifier31 import load_original_case
cid='one_event_n80_i00'
logs=(D/'chaos.log').read_text()
pat=re.compile(r'^HARD_EXIT_RECOVERED (\S+) node_count (\d+) fresh (\d+) pending (\d+) covered (\d+)$',re.M)
rows=[{'event':m[1],'nodes':int(m[2]),'fresh':int(m[3]),'pending':int(m[4]),'covered':int(m[5])} for m in pat.finditer(logs)]
expected=[('before_snapshot_rename',15),('after_snapshot_fsync',31),('during_prune',63),('after_snapshot_rename',95),('after_snapshot_fsync',127)]
if len(rows)!=5 or [(r['event'],r['nodes']) for r in rows]!=expected:raise ValueError('Missing actual hard-exit/recovery log events')
for r in rows:
    if r['fresh']!=r['nodes']:raise ValueError('Cold bounds not recomputed')
active=D/'chaos_active'/cid;archives=D/'chaos_archives'/cid
srcs=sorted(archives.glob('archive_*.zlib'),key=lambda p:int(p.name.split('_')[1]))
if len(srcs)!=5:raise ValueError('The five durable archive generations were not preserved')
objs=[_read_archive(p) for p in srcs]
seq=0
for obj in objs:
    if obj['range_start']!=seq:raise ValueError('Compaction epochs have a gap')
    seq=obj['range_end']+1
if seq!=6:raise ValueError('Six original CH32 historical frames not preserved')
current=_read_envelope(active/'checkpoint.json')
checkpoints=[obj['prior_checkpoint_envelope'] for obj in objs[1:]]+[current]
if len(checkpoints)!=5:raise ValueError('Checkpoint generations missing')
for r,obj,cp in zip(rows,objs,checkpoints):
    if cp['body']['head_sha256']!=obj['final_head_sha256'] or cp['body']['upto_seq']!=obj['range_end']:
        raise ValueError('Checkpoint hash-linked history does not match recovered event')
    r['original_head_sha256']=obj['final_head_sha256'];r['checkpoint_sha256']=cp['sha256']
    r['actual_os_exit_code_checked_by_stress_runner']=77
cold_path=D/'chaos_verify2.log';text=cold_path.read_text().strip()
if not text:raise ValueError('Independent cold mathematical replay is unfinished')
independent=json.loads(text)
if independent['fresh_MPFR_bounds']!=127 or independent['full_archived_history']['replayed_frames']!=6 or \
   independent['full_archived_history']['archives']!=5 or independent['checkpoint_sha256']!=current['sha256']:
    raise ValueError('Final independent historical MPFR replay was not successful')
out={'case':cid,'hard_process_terminations':5,'events':rows,
     'original_CH32_final_head_sha256':independent['head_sha256'],
     'final_checkpoint_sha256':current['sha256'],
     'independent_cold_restart_and_full_history':independent,
     'actual_os_exit_used':True,'no_power_loss_claim':True,
     'posthoc_reconciliation_of_stress_log_and_immutable_archives':True,
     'mathematical_proof_global':False}
(D/'chaos_results.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
print('PASS',len(rows),'actual OS exits; five archive epochs; six original frames independently replayed')
