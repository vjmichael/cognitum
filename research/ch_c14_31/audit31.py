"""CH31 read-only original-data and receipt audit; NOT a substitute for MPFR replay.

Run benchmark31.py for new independent mathematics; this audit verifies
provenance, stage accounting, real restart proofs and release refusals.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
D=Path(__file__).resolve().parent;sys.path.insert(0,str(D))
from verifier31 import load_original_case,sha

def audit(path:Path):
    proto=json.loads((D/'frozen_protocol.json').read_text())
    if sha(D/'frozen_protocol.json')!=(D/'frozen_protocol.sha256').read_text().split()[0]:
        raise ValueError('Research protocol hash changed')
    if sha(D.parent/'CH_C14_29/frozen_protocol.json')!=proto['parent_protocol_sha256']:
        raise ValueError('Historical source changed')
    study=json.loads(path.read_text());seen=set();ambiguous=0
    if study['frozen_protocol_sha256']!=sha(D/'frozen_protocol.json'):
        raise ValueError('Benchmark not bound to frozen protocol')
    for result in study['per_case']:
        cid=result['case_id']
        if cid in seen or cid not in proto['original_case_sha256']:
            raise ValueError('Wrong or duplicate CH23 case')
        seen.add(cid)
        inp,original,duals,archived=load_original_case(cid)
        if result['original_case_sha256']!=proto['original_case_sha256'][cid] or result['original_data_identity']!=inp['original_CH23_identity']:
            raise ValueError('Input substitution')
        ambiguous+=bool(inp['original_CH23_identity'].get('ambiguous'))
        stages=result['stages'];budgets=[s['nodes'] for s in stages]
        if budgets!=proto['research_budget_series']:raise ValueError('Wrong progressive budgets')
        last=0;gap=float('inf')
        for s in stages:
            if s['reused']!=last or s['fresh']!=s['nodes']-last or s['gap_upper_display']>gap+1e-10:
                raise ValueError('Invalid incremental proof accounting')
            if s['projection'] != (s['nodes'] not in (63,127)):
                raise ValueError('Projected proof misrepresented as original search')
            last=s['nodes'];gap=s['gap_upper_display']
        for n in (63,127):
            cert,old=archived(n)
            recorded=next(s for s in stages if s['nodes']==n)
            if abs(old['gap_upper_display']-recorded['gap_upper_display'])>1e-10:
                raise ValueError('Cold original replay mismatch')
        if result['global_certified'] or not result['verified']:
            raise ValueError('Unwarranted research certification')
        resumed=result.get('fresh_process_restart')
        if resumed is None:continue
        chain=resumed['chain']
        if (not resumed['verified'] or resumed['imported_cache'] or
            resumed['restart_reverified_from_scratch']!=63 or
            resumed['pid']==result['same_process_pid'] or
            [s['nodes'] for s in chain]!=[63,95,127] or
            [s['fresh'] for s in chain]!=[63,32,32] or
            [s['reused'] for s in chain]!=[0,63,95] or
            abs(chain[-1]['gap_upper_display']-gap)>1e-10):
            raise ValueError('Unverified state imported after restart')
    if study['cases']==len(seen)!=len(proto['original_case_sha256']):
        raise ValueError('Not the complete original 15-case cohort')
    if seen!=set(proto['original_case_sha256']) or ambiguous!=3:
        raise ValueError('Original CH23 ambiguity cohort changed')
    if study['restart_reverified_cases']!=len(seen) or study['global_certificates']!=0:
        raise ValueError('False release or incomplete restart coverage')
    if study['total_reused_caps_during_chain']!=len(seen)*211 or study['total_fresh_caps_during_chain']!=len(seen)*127:
        raise ValueError('Stage work accounting invalid')
    print('CH31 AUDIT PASS: 15 original CH23 inputs; 6-stage chains; 15 cold process restarts; three ambiguous refusals; no release')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('result',nargs='?',type=Path,default=D/'benchmark_results.json');a=p.parse_args();audit(a.result)
