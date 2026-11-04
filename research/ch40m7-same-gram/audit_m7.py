"""Standalone read-only rational replay; never imports native FLINT or MPFR producers."""
from __future__ import annotations
import argparse,json,os,sys
from pathlib import Path
from fractions import Fraction as F
ROOT=Path(os.environ.get('CH40M7_WORKSPACE','/mnt/data')).resolve()
sys.path[:0]=[str(ROOT/'CH40M6'),str(ROOT/'CH40L2'),str(ROOT/'CH40L'),str(ROOT/'CH40J/source'),str(ROOT/'CH40M5')]
from analyze40l import canon,sha
from continue40l2 import load_original,boxes,serialize,select
from independent_psd_check import independent_bound

class Refusal(ValueError):pass

def replay(path):
    r=json.loads(Path(path).read_text())
    if r.get('protocol')!='CH40M7-SAME-PSD-GRAM-FULL-PROCESS-RESEARCH-V1' or r.get('release_status')!='RESEARCH_ONLY_NO_GO':
        raise Refusal('invalid scientific status/protocol')
    case=r['case'];engine=r['backend']
    if engine not in ('arb_gram','mpfr_gram') or r['formula']!='PSD_GRAM_DOMINANCE' or r['precision_bits']!=256:
        raise Refusal('unknown producer semantics')
    pins=json.loads((ROOT/'CH40K/CH40K_ACCEPTANCE.json').read_text())
    if len({p['case'] for p in pins['cases']})!=15:raise Refusal('unfrozen source pinset')
    p=ROOT/'CH40K/traces'/(case+'_127_original_mpfr_trace.json')
    if not p.is_file() or case not in {v['case'] for v in pins['cases']} or sha(p.read_bytes())!=r['trace_sha256']:
        raise Refusal('original input SHA mismatch')
    trace,original=load_original(p,pins)
    if len(original)!=64:raise Refusal('invalid initial frontier')
    frontier={k:{'box':v['box'],'cap':F(v['cap']),'depth':v['depth']} for k,v in original.items()}
    previous='0'*64
    for seq,e in enumerate(r['events'],1):
        body={k:v for k,v in e.items() if k!='digest'}
        if e['sequence']!=seq or e['prev']!=previous or sha(canon(body).encode())!=e['digest']:
            raise Refusal('event chain mismatch')
        pid=select(frontier,'selective')
        if e['parent_id']!=pid or e['backend']!=engine:raise Refusal('policy/backend mismatch')
        parent=frontier[pid]
        if e['parent_box']!=parent['box'] or F(e['parent_cap'])!=parent['cap']:
            raise Refusal('parent record mismatch')
        axis=max(range(3),key=lambda j:F(parent['box'][j][1])-F(parent['box'][j][0]))
        if e['axis']!=axis or len(e['children'])!=2:raise Refusal('invalid split')
        del frontier[pid]
        for i,b in enumerate(boxes(parent['box'],axis)):
            c=e['children'][i];w=c['witness']
            if c['id']!=pid+'.'+str(i) or c['box']!=serialize(b):raise Refusal('changed partition')
            if (w.get('engine')!=engine or w.get('rule')!='PSD_GRAM_DOMINANCE' or
                w.get('precision_bits')!=256 or w.get('reference_satisfied') is not True or
                w.get('native_det_positive') is not True):raise Refusal('invalid witness')
            independent,_=independent_bound(trace['certificate'],b,ROOT/'CH40J/source')
            hi=F(c['local_hi'])
            if hi<independent:raise Refusal('producer undercuts independent upper bound')
            if F(c['effective_cap'])!=min(hi,parent['cap']):raise Refusal('parent inheritance wrong')
            frontier[c['id']]={'box':c['box'],'cap':F(c['effective_cap']),'depth':parent['depth']+1}
        previous=e['digest']
    if (previous!=r['journal_tip'] or len(r['events'])!=r['splits'] or
        2*len(r['events'])!=r['children'] or len(frontier)!=r['terminal_count'] or
        str(max(v['cap'] for v in frontier.values()))!=r['final_upper'] or
        str(max(v['cap'] for v in original.values()))!=r['initial_upper'] or
        F(r['initial_upper'])-F(r['final_upper'])!=F(r['upper_reduction'])):
        raise Refusal('reported final frontier incompatible with journal')
    return {'status':'PASS_INDEPENDENT_RATIONAL_REPLAY','case':case,'backend':engine,
            'children':r['children'],'splits':r['splits'],'original_trace_sha256':r['trace_sha256'],
            'journal_tip':previous,'final_upper':r['final_upper']}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('path',type=Path);ap.add_argument('--receipt',type=Path);a=ap.parse_args()
    result=replay(a.path)
    print(json.dumps(result,sort_keys=True))
    if a.receipt:a.receipt.write_text(json.dumps(result,indent=2)+'\n')
