"""CH40-M.6 original 15-case FLINT-Gram vs MPFR-direct search research.

Frozen 127-node frontier remains immutable. Producer experiments are new, and
read-only rational audits must succeed before published result is accepted.
Budget is per-arm search CPU, *not* exact equal-CPU accounting: an atomic final
split can overshoot the budget. No source trace or prior signed log is edited.
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys, time, resource
from pathlib import Path
from fractions import Fraction as F
ROOT=Path(os.environ.get('CH40M6_WORKSPACE',Path(__file__).resolve().parent.parent)).resolve()
sys.path[:0]=[str(ROOT/'CH40L2'),str(ROOT/'CH40L'),str(ROOT/'CH40L3'),str(ROOT/'CH40M5'),str(ROOT/'CH40J/source')]
from analyze40l import canon,sha
from continue40l2 import load_original,boxes,serialize,select
from native_mpfr40l3 import direct_upper as mpfr_direct
from gram_psd import native_cap
from rational_kernel40d import direct_upper as rational_direct
from independent_psd_check import independent_bound
TRACES=ROOT/'CH40K/traces';PINS=ROOT/'CH40K/CH40K_ACCEPTANCE.json'

class Refusal(ValueError): pass

def validate_original(case, pins=None, traces=None):
    pins=Path(pins or PINS);traces=Path(traces or TRACES)
    allpins=json.loads(pins.read_text())
    cases=allpins['cases'];key={x['case'] for x in cases}
    if len(cases)!=15 or len(key)!=15:raise Refusal('expected 15 unique original SHA pins')
    if case not in key:raise Refusal('case not in original CH40K pin set')
    p=traces/(case+'_127_original_mpfr_trace.json')
    trace,old=load_original(p,allpins)
    if len(old)!=64:raise Refusal('not the frozen 64-terminal partition')
    return trace,old,sha(p.read_bytes())

def peak_rss_kib():return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

def produce(backend,cert,b):
    if backend=='flint_gram':
        witness=native_cap(cert,b,prec=256)
        bound=witness['gram_upper']
        return bound,{'engine':'python-flint_arb_256','bound_rule':'PSD_GRAM_DOMINANCE','prec':256,
                      'weight_upper_sha256':sha(canon([str(x) for x in witness['weights_upper']]).encode()),
                      'det_gram_positive':witness['det_gram']>0}
    if backend=='mpfr_direct':
        v=mpfr_direct(cert,b)
        return F(v['upper']),{'engine':'libmpfr_256','bound_rule':'DIRECT_LIKELIHOOD_HADAMARD','prec':256}
    raise Refusal('unrecognized backend')

def advance(cert,original,backend,cpu_limit,max_splits=32):
    if not 0.10<=cpu_limit<=30.0 or not 1<=max_splits<=200:raise Refusal('unbounded benchmark budget')
    frontier={k:{'box':v['box'],'cap':F(v['cap']),'depth':v['depth']} for k,v in original.items()}
    first=max(v['cap'] for v in frontier.values())
    start=time.process_time();wall=time.monotonic();prev='0'*64;events=[]
    while len(events)<max_splits and (len(events)==0 or time.process_time()-start<cpu_limit):
        parent_id=select(frontier,'selective');parent=frontier[parent_id]
        widths=[F(hi)-F(lo) for lo,hi in parent['box']]
        axis=max(range(3),key=lambda j:widths[j])
        children=[]
        for j,b in enumerate(boxes(parent['box'],axis)):
            bound,witness=produce(backend,cert,b)
            if not isinstance(bound,F) or not isinstance(witness,dict):raise Refusal('native producer malformed')
            if witness['prec']!=256 or (backend=='flint_gram' and not witness['det_gram_positive']):raise Refusal('invalid witness precision/PSD')
            # Parent cap inheritance applies for each child; a worse native cap is never promoted.
            cap=min(parent['cap'],bound)
            children.append({'id':parent_id+'.'+str(j),'box':serialize(b),
                             'local_hi':str(bound),'effective_cap':str(cap),'witness':witness})
        body={'sequence':len(events)+1,'prev':prev,'parent_id':parent_id,
              'parent_box':parent['box'],'parent_cap':str(parent['cap']),
              'axis':axis,'children':children,'backend':backend}
        event={**body,'digest':sha(canon(body).encode())};events.append(event);prev=event['digest']
        del frontier[parent_id]
        for c in children:frontier[c['id']]={'box':c['box'],'cap':F(c['effective_cap']),'depth':parent['depth']+1}
    cpu=time.process_time()-start
    new=max(x['cap'] for x in frontier.values())
    return {'backend':backend,'initial_upper':str(first),'new_upper':str(new),
            'upper_decrease':str(first-new),'split_count':len(events),'child_count':2*len(events),
            'cpu_seconds':cpu,'wall_seconds':time.monotonic()-wall,'cpu_budget_requested':cpu_limit,
            'cpu_budget_overshoot':max(0,cpu-cpu_limit),'peak_process_rss_kib':peak_rss_kib(),
            'terminal_count':len(frontier),'journal_tip':prev,'events':events,
            'scientific_release':'NO_GO'}

def audit(original,cert,run,checker=ROOT/'CH40J/source'):
    """Recompute new child bounds independently; never import native producer here."""
    frontier={k:{'box':v['box'],'cap':F(v['cap']),'depth':v['depth']} for k,v in original.items()}
    prior='0'*64
    for seq,event in enumerate(run['events'],1):
        body={k:v for k,v in event.items() if k!='digest'}
        if event['sequence']!=seq or event['prev']!=prior or event['digest']!=sha(canon(body).encode()):raise Refusal('journal chain modified')
        if event['backend']!=run['backend']:raise Refusal('backend mismatch')
        pid=event['parent_id']
        if pid!=select(frontier,'selective'):raise Refusal('branch-selection policy mismatch')
        if pid not in frontier:raise Refusal('not a frontier parent')
        parent=frontier.pop(pid)
        if parent['box']!=event['parent_box'] or parent['cap']!=F(event['parent_cap']):raise Refusal('parent mutated')
        axis=event['axis'];widths=[F(b)-F(a) for a,b in parent['box']]
        if axis!=max(range(3),key=lambda j:widths[j]):raise Refusal('changed splitting policy')
        if len(event['children'])!=2:raise Refusal('non-binary partition')
        for j,b in enumerate(boxes(parent['box'],axis)):
            child=event['children'][j]
            if child['id']!=pid+'.'+str(j) or child['box']!=serialize(b):raise Refusal('invalid child box')
            witness=child['witness'];upper=F(child['local_hi'])
            if witness['prec']!=256:raise Refusal('witness precision mismatch')
            if run['backend']=='flint_gram':
                if witness['engine']!='python-flint_arb_256' or witness['bound_rule']!='PSD_GRAM_DOMINANCE' or witness['det_gram_positive'] is not True:raise Refusal('wrong Gram witness')
                checked,_=independent_bound(cert,b,checker)
            elif run['backend']=='mpfr_direct':
                if witness['engine']!='libmpfr_256' or witness['bound_rule']!='DIRECT_LIKELIHOOD_HADAMARD':raise Refusal('wrong MPFR witness')
                checked=rational_direct(cert,b).hi
            else:raise Refusal('wrong backend')
            if upper<checked:raise Refusal('new upper undercuts independent proof: refuse')
            if F(child['effective_cap'])!=min(upper,parent['cap']):raise Refusal('broken parent-bound inheritance')
            frontier[child['id']]={'box':child['box'],'cap':F(child['effective_cap']),'depth':parent['depth']+1}
        prior=event['digest']
    if (prior!=run['journal_tip'] or len(run['events'])!=run['split_count'] or
        str(max(v['cap'] for v in frontier.values()))!=run['new_upper'] or
        str(max(v['cap'] for v in original.values()))!=run['initial_upper']):raise Refusal('final result changed')
    return {'status':'PASS_INDEPENDENT_FULL_CHILD_BOUND_RECOMPUTATION',
            'verified_children':run['child_count'],'verified_splits':run['split_count'],
            'final_upper':run['new_upper'],'journal_tip':prior}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--cpu-budget',type=float,default=.45)
    p.add_argument('--max-splits',type=int,default=30)
    p.add_argument('--cases',nargs='*',default=None)
    args=p.parse_args()
    pins=json.loads(PINS.read_text())
    cases=args.cases or [x['case'] for x in pins['cases']]
    if len(set(cases))!=len(cases) or any(v not in {x['case'] for x in pins['cases']} for v in cases):raise Refusal('case list mismatch')
    args.output.mkdir(parents=True,exist_ok=True)
    results=[]
    for i,case in enumerate(cases,1):
        trace,original,trace_sha=validate_original(case)
        arms=[]
        for engine in ('mpfr_direct','flint_gram'):
            row=advance(trace['certificate'],original,engine,args.cpu_budget,args.max_splits)
            proof=audit(original,trace['certificate'],row)
            row['audit']=proof
            arms.append(row)
        initial=F(arms[0]['initial_upper']);changes=[float(initial-F(a['new_upper'])) for a in arms]
        summary={'case':case,'trace_sha256':trace_sha,'legacy':arms[0], 'flint':arms[1],
                 'mpfr_upper_decrease_float':changes[0],'flint_upper_decrease_float':changes[1]}
        results.append(summary)
        output=args.output/(case+'.json');output.write_text(json.dumps(summary,indent=2)+'\n')
        print(f'{i}/{len(cases)} {case} mpfr={arms[0]["split_count"]} splits, Δ={changes[0]:.8g}  flint={arms[1]["split_count"]} splits, Δ={changes[1]:.8g}',flush=True)
    status={'protocol':'CH40-M6-NATIVE-FLINT-GRAM-VS-MPFR-DIRECT-SEARCH-CPU-V1',
            'cpu_budget_search_per_arm_seconds':args.cpu_budget,'case_count':len(results),
            'cases':[{'case':c['case'],'mpfr_splits':c['legacy']['split_count'],'flint_splits':c['flint']['split_count'],
                      'mpfr_cpu':c['legacy']['cpu_seconds'],'flint_cpu':c['flint']['cpu_seconds'],
                      'mpfr_delta':c['mpfr_upper_decrease_float'],'flint_delta':c['flint_upper_decrease_float'],
                      'mpfr_child_checks':c['legacy']['audit']['verified_children'],'flint_child_checks':c['flint']['audit']['verified_children']} for c in results],
            'scientific_release':'NO_GO','limits':'Equal requested search CPU ceilings with atomic split overshoot; reference audits outside search budgets; different mathematical upper-bound methods, not interchangeable. No whole-process equal CPU proof.'}
    (args.output/'summary.json').write_text(json.dumps(status,indent=2)+'\n')
    print('SUMMARY',json.dumps({k:v for k,v in status.items() if k!='cases'}),flush=True)
    return status
if __name__=='__main__':main()
