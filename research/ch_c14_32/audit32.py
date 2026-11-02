"""CH32 immutable provenance and journal integrity audit.

This quick structural audit is NOT an MPFR mathematics replay. Run the
restart32.py --verify-only --expected-head for independent cold verification.
"""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
D=Path(__file__).resolve().parent;sys.path[:0]=[str(D),str(D.parent/'CH_C14_31')]
from journal32 import _scan,_read_frame,GENESIS,apply_delta,digest
from verifier31 import load_original_case,sha
from prefix31 import project_prefix

STAGES=[7,15,31,63,95,127]
def audit(result_path=D/'benchmark_results.json'):
    prot=D/'frozen_protocol.json'
    if sha(prot)!=(D/'frozen_protocol.sha256').read_text().split()[0]:raise ValueError('CH32 protocol altered')
    frozen=json.loads(prot.read_text());study=json.loads(Path(result_path).read_text())
    if study['frozen_protocol_sha256']!=sha(prot):raise ValueError('Unbound results')
    entries=study['per_case'];headpin=json.loads((D/'heads.json').read_text())
    if len(entries)!=15 or set(headpin)!=set(frozen['original_case_sha256']):
        raise ValueError('Incomplete original case cohort')
    seen=set();ambiguous=0
    for r in entries:
        cid=r['case_id']
        if cid in seen or cid not in frozen['original_case_sha256']:
            raise ValueError('Duplicate/unknown CH23 identity')
        seen.add(cid);inp,proto,dual,archive=load_original_case(cid)
        c63,rec63=archive(63);c127,rec127=archive(127)
        if r['original_case_sha256']!=frozen['original_case_sha256'][cid] or r['original_data_identity']!=inp['original_CH23_identity']:
            raise ValueError('Original data swapped')
        files,pending=_scan(D/'journals'/cid)
        if pending or len(files)!=6 or r['committed_frames']!=6:raise ValueError('Incomplete journal')
        head=GENESIS;last=None
        for i,p in enumerate(files):
            entry=_read_frame(p);b=entry['body']
            if (b['seq']!=i or b['prev_sha256']!=head or b['stage_nodes']!=STAGES[i] or
                b['case_id']!=cid or (i==0)!=(b['kind']=='genesis')):
                raise ValueError('Journal continuity failure')
            cert=b['payload'] if i==0 else apply_delta(last,b['payload'])
            source=c63 if STAGES[i]<=63 else c127
            original=(source if STAGES[i] in (63,127) else project_prefix(source,STAGES[i]))
            if digest(cert)!=digest(original) or digest(cert)!=b['certificate_sha256']:
                raise ValueError('Journal not equal to frozen original CH29 proof')
            if sha(p)!=r['frame_sha256'][i]:raise ValueError('Committed frame checksum changed')
            head=entry['sha256'];last=cert
        if head!=headpin[cid] or head!=r['cold_final_replay']['head_sha256']:
            raise ValueError('Externally pinned head mismatch')
        if (r['fresh_restart']['imported_verified_state'] or r['cold_final_replay']['imported_verified_state'] or
            r['cold_final_replay']['cold_recomputed_bounds']!=127 or r['cold_final_replay']['initial_committed_stages']!=6 or
            abs(r['cold_final_replay']['gap_upper_display']-rec127['gap_upper_display'])>1e-10 or r['certified']):
            raise ValueError('Invalid cold verifier receipt')
        ambiguous+=bool(inp['original_CH23_identity']['ambiguous'])
    if ambiguous!=3 or study['journal_frames']!=90 or study['global_certificates']!=0:
        raise ValueError('Unexpected source cases or false promotions')
    if study['total_fresh_final_replay_bounds']!=15*127:raise ValueError('Missing cold replay coverage')
    print('CH32 provenance audit PASS: 15 original CH23 cases, 90 durable frames, externally pinned heads, 15 independently cold-replayed 127-node certificates, 3 historical refusals')
    return True
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('results',nargs='?',type=Path,default=D/'benchmark_results.json');a=ap.parse_args();audit(a.results)
