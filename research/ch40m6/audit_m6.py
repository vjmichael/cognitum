"""Standalone READ-ONLY verifier for CH40-M.6 producer journals.

This module imports NO native flint/MPFR producers and produces no new search
nodes. Frozen 127-node source identity is SHA-256 pinned before recomputation.
The old historical certificate's math is NOT re-proved by this research audit.
"""
from __future__ import annotations
import argparse, hashlib, json, sys, os
from fractions import Fraction as F
from pathlib import Path
ROOT=Path(os.environ.get('CH40M6_WORKSPACE',Path(__file__).resolve().parent.parent)).resolve()
sys.path[:0]=[str(ROOT/'CH40L2'),str(ROOT/'CH40L'),str(ROOT/'CH40M5'),str(ROOT/'CH40J/source')]
from analyze40l import canon,sha
from continue40l2 import load_original,boxes,serialize,select
from independent_psd_check import independent_bound
from rational_kernel40d import direct_upper as rational_direct
DEFAULT_PIN=ROOT/'CH40K/CH40K_ACCEPTANCE.json'
DEFAULT_TRACES=ROOT/'CH40K/traces'
CHECKER=ROOT/'CH40J/source'
class Refusal(ValueError):pass

def validate(record,original,cert,checker=CHECKER):
    audits=[]
    for arm,label in (('legacy','mpfr_direct'),('flint','flint_gram')):
        run=record[arm]
        if run['backend']!=label or run['scientific_release']!='NO_GO':raise Refusal('backend/status confusion')
        state={k:{'box':v['box'],'cap':F(v['cap']),'depth':v['depth']} for k,v in original.items()}
        prev='0'*64;count=0
        for seq,event in enumerate(run['events'],1):
            body={k:v for k,v in event.items() if k!='digest'}
            if event['sequence']!=seq or event['prev']!=prev or event['digest']!=sha(canon(body).encode()) or event['backend']!=label:raise Refusal('chain corrupted')
            pid=select(state,'selective')
            if event['parent_id']!=pid:raise Refusal('different branch-selection policy')
            parent=state.pop(pid)
            if event['parent_box']!=parent['box'] or F(event['parent_cap'])!=parent['cap']:raise Refusal('modified parent')
            widths=[F(z)-F(a) for a,z in parent['box']]
            axis=max(range(3),key=lambda j:widths[j])
            if event['axis']!=axis or len(event['children'])!=2:raise Refusal('wrong split policy')
            for j,box in enumerate(boxes(parent['box'],axis)):
                child=event['children'][j]
                if child['id']!=f'{pid}.{j}' or child['box']!=serialize(box):raise Refusal('bad child')
                hi=F(child['local_hi']);w=child['witness']
                if w.get('prec')!=256:raise Refusal('precision mismatch')
                if label=='flint_gram':
                    if w.get('engine')!='python-flint_arb_256' or w.get('bound_rule')!='PSD_GRAM_DOMINANCE' or w.get('det_gram_positive') is not True:raise Refusal('native witness type')
                    independently_recomputed,_=independent_bound(cert,box,checker)
                else:
                    if w.get('engine')!='libmpfr_256' or w.get('bound_rule')!='DIRECT_LIKELIHOOD_HADAMARD':raise Refusal('native witness type')
                    independently_recomputed=rational_direct(cert,box).hi
                if hi<independently_recomputed:raise Refusal('candidate upper below separately recomputed upper')
                cap=min(hi,parent['cap'])
                if cap!=F(child['effective_cap']):raise Refusal('parent inheritance violation')
                state[child['id']]={'box':child['box'],'cap':cap,'depth':parent['depth']+1}
                count+=1
            prev=event['digest']
        if count!=run['child_count'] or len(run['events'])!=run['split_count']:raise Refusal('bad count')
        if len(state)!=len(original)+run['split_count'] or run['terminal_count']!=len(state):raise Refusal('lost or duplicated region')
        if prev!=run['journal_tip'] or str(max(n['cap'] for n in state.values()))!=run['new_upper']:raise Refusal('ceiling or journal tampered')
        if str(max(n['cap'] for n in original.values()))!=run['initial_upper']:raise Refusal('frozen initial bound changed')
        if F(run['new_upper'])>F(run['initial_upper']):raise Refusal('upper ceiling grew')
        audits.append({'arm':label,'verified_children':count,'splits':run['split_count'],'frontier_upper':run['new_upper'],'status':'PASS_INDEPENDENT_RATIONAL_RECOMPUTATION'})
    return audits

def audit_file(file,traces=DEFAULT_TRACES,pins=DEFAULT_PIN):
    record=json.loads(Path(file).read_text());case=record['case']
    p=Path(traces)/(case+'_127_original_mpfr_trace.json')
    entry={v['case']:v for v in json.loads(Path(pins).read_text())['cases']}
    if len(entry)!=15 or case not in entry:raise Refusal('not 15 original cases')
    raw=p.read_bytes()
    if sha(raw)!=entry[case]['trace_sha256'] or sha(raw)!=record['trace_sha256']:raise Refusal('trace SHA pin failed')
    trace,frontier=load_original(p,json.loads(Path(pins).read_text()))
    audits=validate(record,frontier,trace['certificate'])
    return {'case':case,'status':'PASS_NEW_CHILD_MATH_AND_CHAIN_ONLY',
            'checkers':'rational fractions + CPython libmpdec (no native producer imports)',
            'audits':audits,'scientific_release':'NO_GO'}

def main():
    p=argparse.ArgumentParser();p.add_argument('files',nargs='+',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    out=[audit_file(f) for f in a.files]
    result={'protocol':'CH40M6-INDEPENDENT-AUDITOR-V1','files':len(out),'verified_children':sum(b['verified_children'] for x in out for b in x['audits']),
            'status':'PASS_NEW_MATH_ONLY','scientific_release':'NO_GO','items':out}
    if a.output:a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'files':len(out),'verified_children':result['verified_children']}))
if __name__=='__main__':main()
