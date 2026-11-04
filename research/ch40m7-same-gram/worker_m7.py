"""Frozen CH40-M7 per-case single-backend research worker.

No source fixture modifications. Every new child is checked against independent
rational/Decimal bounds *inside* measured process CPU budget. The stronger
original parent caps remain intact. Not a scientific release/production worker.
"""
from __future__ import annotations
import argparse,hashlib,json,os,resource,sys,time
from fractions import Fraction as F
from pathlib import Path
START_CPU=time.process_time()
START_WALL=time.monotonic()
ROOT=Path(os.environ.get('CH40M7_WORKSPACE','/mnt/data')).resolve()
sys.path[:0]=[str(ROOT/'CH40M7'),str(ROOT/'CH40M6'),str(ROOT/'CH40L2'),str(ROOT/'CH40L'),str(ROOT/'CH40L3'),str(ROOT/'CH40M5'),str(ROOT/'CH40J/source')]
from analyze40l import canon,sha
from compare_m6 import validate_original
from continue40l2 import select,boxes,serialize
from independent_psd_check import independent_bound
from gram_psd import native_cap
from mpfr_gram import upper as mpfr_gram

class Refusal(ValueError):pass

def run(case,engine,cpu_budget,max_splits):
    if engine not in ('arb_gram','mpfr_gram'):raise Refusal('invalid backend')
    if not 0.5<=cpu_budget<=30 or not 1<=max_splits<=1000:raise Refusal('invalid budget')
    trace,original,hashpin=validate_original(case)
    cert=trace['certificate']
    frontier={k:{'box':v['box'],'cap':F(v['cap']),'depth':v['depth']} for k,v in original.items()}
    old_upper=max(v['cap'] for v in frontier.values())
    events=[];prev='0'*64;verified=0
    while len(events)<max_splits and time.process_time()-START_CPU < cpu_budget:
        parentid=select(frontier,'selective');parent=frontier[parentid]
        widths=[F(hi)-F(lo) for lo,hi in parent['box']]
        axis=max(range(3),key=lambda j:widths[j])
        children=[]
        for index,b in enumerate(boxes(parent['box'],axis)):
            result=native_cap(cert,b,256) if engine=='arb_gram' else mpfr_gram(cert,b)
            bound=result['gram_upper']
            proof,_=independent_bound(cert,b,ROOT/'CH40J/source')
            # An independent checker must not be undercut by a producer.
            # Note both use conservative outward enclosures, so passing is
            # stronger than merely validating the common mathematical rule.
            if bound<proof:raise Refusal('native cap undercuts independent Gram reference')
            if result['det_gram']<=0:raise Refusal('invalid Fisher determinant witness')
            cap=min(parent['cap'],bound)
            children.append({'id':parentid+'.'+str(index),'box':serialize(b),
               'local_hi':str(bound),'effective_cap':str(cap),
               'witness':{'rule':'PSD_GRAM_DOMINANCE','engine':engine,'precision_bits':256,
                          'reference_satisfied':True,'native_det_positive':True}})
            verified+=1
        body={'sequence':len(events)+1,'prev':prev,'parent_id':parentid,
              'parent_box':parent['box'],'parent_cap':str(parent['cap']),
              'axis':axis,'children':children,'backend':engine}
        digest=sha(canon(body).encode());events.append({**body,'digest':digest});prev=digest
        del frontier[parentid]
        for child in children:
            frontier[child['id']]={'box':child['box'],'cap':F(child['effective_cap']),'depth':parent['depth']+1}
    final_upper=max(v['cap'] for v in frontier.values())
    return {'protocol':'CH40M7-SAME-PSD-GRAM-FULL-PROCESS-RESEARCH-V1',
        'case':case,'backend':engine,'trace_sha256':hashpin,
        'formula':'PSD_GRAM_DOMINANCE','precision_bits':256,
        'initial_upper':str(old_upper),'final_upper':str(final_upper),
        'upper_reduction':str(old_upper-final_upper),
        'splits':len(events),'children':verified,'terminal_count':len(frontier),
        'process_cpu_including_import_input_and_online_verification':time.process_time()-START_CPU,
        'wall_seconds':time.monotonic()-START_WALL,
        'peak_ru_maxrss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'requested_cpu_budget_seconds':cpu_budget,
        'budget_overshoot_seconds':max(0,time.process_time()-START_CPU-cpu_budget),
        'split_cap':max_splits,'journal_tip':prev,'events':events,
        'release_status':'RESEARCH_ONLY_NO_GO'}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--case',required=True);p.add_argument('--backend',required=True,choices=['arb_gram','mpfr_gram'])
    p.add_argument('--cpu-budget',type=float,default=1.25);p.add_argument('--max-splits',type=int,default=256)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    result=run(a.case,a.backend,a.cpu_budget,a.max_splits)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    tmp=a.out.with_suffix('.tmp');tmp.write_text(json.dumps(result,indent=2)+'\n');os.replace(tmp,a.out)
    print(f"{a.case} {a.backend} splits={result['splits']} cpu={result['process_cpu_including_import_input_and_online_verification']:.4f} reduction={float(F(result['upper_reduction'])):.9g}",flush=True)
if __name__=='__main__':main()
