"""C14 CH40-M.8: standalone exact-key memoized independent *rational* audit.

Zero imports from Arb/FLINT/MPFR producer modules. A cache entry is produced
ONLY by this auditor's independent rational/Decimal computation in this process.
An entry applies ONLY to the same pinned original trace SHA, exact parameter
box and bound formula. Reusing a proof of a box for a different producer's
numeric candidate is safe because each candidate is separately compared with
that independently computed sufficient upper bound.

No persistent cache, no accepting producer-authored proof receipts, no
scientific release. Original frozen source and signed chains stay read-only.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import resource
import sys
import time
from fractions import Fraction as F
from pathlib import Path

ROOT=Path(os.environ.get('CH40M8_WORKSPACE','/mnt/data')).resolve()
sys.path[:0]=[
    str(ROOT/'CH40L2'),str(ROOT/'CH40L'),str(ROOT/'CH40J/source'),
    str(ROOT/'CH40M5'),
]
from analyze40l import canon,sha
from continue40l2 import load_original,boxes,serialize,select
from independent_psd_check import independent_bound

PROTOCOL='CH40M8-EXACT-KEY-INPROCESS-INDEPENDENT-RATIONAL-AUDIT-V1'
M7_PROTOCOL='CH40M7-SAME-PSD-GRAM-FULL-PROCESS-RESEARCH-V1'
FORMULA='PSD_GRAM_DOMINANCE'
ENGINES=('arb_gram','mpfr_gram')

class Refusal(ValueError): pass


def _parse_f(value, label):
    # Keep untrusted fractions bounded. Frozen original fractions are much smaller.
    if type(value) is not str or len(value)>10000:
        raise Refusal('unbounded or non-string rational in '+label)
    try:
        v=F(value)
    except (ValueError, ZeroDivisionError, OverflowError) as e:
        raise Refusal('invalid rational in '+label) from e
    return v


def _prepare_original(case,pins):
    if case not in pins: raise Refusal('case not in pinned original set')
    p=ROOT/'CH40K/traces'/(case+'_127_original_mpfr_trace.json')
    if not p.is_file():raise Refusal('original fixture unavailable')
    # Load_original independently validates both original trace and cert sha256.
    trace,original=load_original(p,{'cases':list(pins.values())})
    if len(original)!=64:raise Refusal('missing frozen terminal boxes')
    return trace,original,sha(p.read_bytes())


def _load_pins():
    p=ROOT/'CH40K/CH40K_ACCEPTANCE.json'
    if not p.is_file():raise Refusal('original pinset unavailable')
    d=json.loads(p.read_text())
    entries=d.get('cases')
    if not isinstance(entries,list) or len(entries)!=15:
        raise Refusal('expected exact original 15 pinset')
    pins={x['case']:x for x in entries}
    if len(pins)!=15:raise Refusal('duplicate original case pins')
    return pins


class CertifiedBoxCache:
    """Volatile memo of validated sufficient rational Gram bounds.

    Only source: independent_bound(original_certificate, exact_box, original_checker).
    A hit is never trusted simply because a witness or JSON cache says so.
    """
    def __init__(self, enabled=True):
        self.enabled=bool(enabled)
        self._memo={}
        self._propositions={}
        self.requested=0
        self.computed=0
        self.hits=0
        self.cpu_math=0.0

    def get(self,trace_sha,cert,box):
        if type(trace_sha) is not str or len(trace_sha)!=64:
            raise Refusal('bad original source identity')
        key=(trace_sha, FORMULA, canon(serialize(box)))
        self.requested+=1
        if self.enabled and key in self._memo:
            self.hits+=1
            ref=self._memo[key]
        else:
            start=time.process_time()
            ref,_=independent_bound(cert,box,ROOT/'CH40J/source')
            self.cpu_math+=time.process_time()-start
            if not isinstance(ref,F):raise Refusal('independent result not exact rational')
            self.computed+=1
            if self.enabled:self._memo[key]=ref
        statement={'original_trace_sha256':trace_sha,'formula':FORMULA,
                   'exact_box':serialize(box),'independent_upper':str(ref)}
        proof_id=sha(canon(statement).encode())
        if key in self._propositions:
            if self._propositions[key]['proof_id']!=proof_id:
                raise Refusal('independent result inconsistency for exact proof key')
        else:
            self._propositions[key]={'proof_id':proof_id,**statement}
        return ref,proof_id

    @property
    def unique_entries(self):return len(self._propositions)

    def proposition_ledger(self):
        # An evidence ledger, NOT a future audit cache: never loaded by this verifier.
        return sorted(self._propositions.values(),key=lambda x:(x['original_trace_sha256'],canon(x['exact_box'])))


def audit_one(data, original, trace_sha, cert, cache):
    """Full structural journal replay with *one safe independent bound per box*.

    The auditor never accepts claimed proof booleans as mathematical proof.
    It rejects any producer cap below its independently established upper.
    """
    if (data.get('protocol')!=M7_PROTOCOL or
        data.get('release_status')!='RESEARCH_ONLY_NO_GO'):
        raise Refusal('invalid scientific status/protocol')
    case=data.get('case')
    engine=data.get('backend')
    if engine not in ENGINES or data.get('formula')!=FORMULA or data.get('precision_bits')!=256:
        raise Refusal('unrecognized producer/formula/precision')
    if data.get('trace_sha256')!=trace_sha:
        raise Refusal('original source hash mismatch')
    events=data.get('events')
    if not isinstance(events,list) or len(events)>1000:
        raise Refusal('unbounded invalid journal')
    frontier={k:{'box':v['box'],'cap':F(v['cap']),'depth':v['depth']} for k,v in original.items()}
    initial_upper=max(v['cap'] for v in frontier.values())
    prev='0'*64
    checks=0
    proof_ids=[]
    for seq,event in enumerate(events,1):
        if type(event) is not dict:
            raise Refusal('invalid event entry')
        body={k:v for k,v in event.items() if k!='digest'}
        if event.get('sequence')!=seq or event.get('prev')!=prev or sha(canon(body).encode())!=event.get('digest'):
            raise Refusal('event sequence/hash chain violation')
        parentid=select(frontier,'selective')
        if event.get('parent_id')!=parentid or event.get('backend')!=engine:
            raise Refusal('selection or backend violation')
        parent=frontier[parentid]
        if (event.get('parent_box')!=parent['box'] or
            _parse_f(event.get('parent_cap'),'parent_cap')!=parent['cap']):
            raise Refusal('parent witness changed')
        axis=max(range(3),key=lambda j:F(parent['box'][j][1])-F(parent['box'][j][0]))
        if event.get('axis')!=axis or not isinstance(event.get('children'),list) or len(event['children'])!=2:
            raise Refusal('invalid axis or binary split')
        # Do not mutate the frontier until *both* children have passed proof checks.
        kids=[]
        for idx,b in enumerate(boxes(parent['box'],axis)):
            child=event['children'][idx]
            if type(child) is not dict or child.get('id')!=parentid+'.'+str(idx) or child.get('box')!=serialize(b):
                raise Refusal('invalid partition or child identity')
            w=child.get('witness')
            if (type(w) is not dict or w.get('engine')!=engine or
                w.get('rule')!=FORMULA or w.get('precision_bits')!=256 or
                w.get('reference_satisfied') is not True or w.get('native_det_positive') is not True):
                raise Refusal('invalid native witness metadata')
            upper=_parse_f(child.get('local_hi'),'local_hi')
            reference,proof_id=cache.get(trace_sha,cert,b)
            if upper<reference:
                raise Refusal('local cap undercuts independent sufficient rational bound')
            effective=_parse_f(child.get('effective_cap'),'effective_cap')
            if effective!=min(upper,parent['cap']):
                raise Refusal('broken parent-bound inheritance')
            kids.append((child, effective))
            proof_ids.append(proof_id)
            checks+=1
        del frontier[parentid]
        for child,cap in kids:
            frontier[child['id']]={'box':child['box'],'cap':cap,'depth':parent['depth']+1}
        prev=event['digest']
    final_upper=max(v['cap'] for v in frontier.values())
    if (data.get('journal_tip')!=prev or data.get('splits')!=len(events) or
        data.get('children')!=checks or data.get('terminal_count')!=len(frontier) or
        _parse_f(data.get('initial_upper'),'initial_upper')!=initial_upper or
        _parse_f(data.get('final_upper'),'final_upper')!=final_upper or
        _parse_f(data.get('upper_reduction'),'upper_reduction')!=initial_upper-final_upper):
        raise Refusal('final summary does not match independently replayed frontier')
    return {'status':'PASS_INDEPENDENT_RATIONAL_BATCH_REPLAY',
            'case':case,'backend':engine,'original_trace_sha256':trace_sha,
            'children_checked':checks,'splits':len(events),
            'journal_tip':prev,'final_upper':str(final_upper),
            'checked_proposition_ids':proof_ids}


def run_batch(input_dir,mode='cache',cases=None):
    if mode not in ('cache','fresh'):raise Refusal('invalid audit mode')
    pins=_load_pins()
    if cases is None:
        selected=list(pins)
    else:
        if len(set(cases))!=len(cases) or not cases or any(c not in pins for c in cases):
            raise Refusal('case list not in frozen pinset or duplicate')
        selected=list(cases)
    input_dir=Path(input_dir)
    cache=CertifiedBoxCache(enabled=(mode=='cache'))
    start=time.process_time()
    receipts=[];audit_files=[]
    for case in selected:
        trace,original,trace_sha=_prepare_original(case,pins)
        for engine in ENGINES:
            f=input_dir/(case+'_'+engine+'.json')
            if not f.is_file():raise Refusal('original journal missing: '+f.name)
            raw=f.read_bytes()
            run=json.loads(raw)
            if run.get('case')!=case or run.get('backend')!=engine:
                raise Refusal('wrong file identity')
            result=audit_one(run,original,trace_sha,trace['certificate'],cache)
            result.update({'journal_file':f.name,'journal_sha256':sha(raw)})
            receipts.append(result)
            audit_files.append(f.name)
    elapsed=time.process_time()-start
    propositions=cache.proposition_ledger()
    if len(propositions)!=len({p['proof_id'] for p in propositions}):
        raise Refusal('collision or duplicate independent proposition')
    if sum(len(p['checked_proposition_ids']) for p in receipts)!=cache.requested:
        raise Refusal('incomplete proposition receipts')
    return {'protocol':PROTOCOL,'mode':mode,'status':'PASS_RESEARCH_ONLY',
            'scientific_release':'NO_GO','input_count':len(receipts),
            'cases':len(selected),'children_checked':sum(x['children_checked'] for x in receipts),
            'independent_rational_computations':cache.computed,'same_box_cache_hits':cache.hits,
            'distinct_case_box_propositions':cache.unique_entries,
            'proposition_ledger_sha256':sha(canon(propositions).encode()),
            'propositions':propositions,
            'rational_math_cpu_seconds':cache.cpu_math,'full_auditor_cpu_seconds':elapsed,
            'archive_sha256':sha(canon(receipts).encode()),
            'receipts':receipts}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--input',type=Path,default=ROOT/'CH40M7/accepted')
    ap.add_argument('--mode',choices=['cache','fresh'],default='cache')
    ap.add_argument('--cases',nargs='*')
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    result=run_batch(args.input,args.mode,args.cases)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    tmp=args.output.with_suffix('.tmp')
    tmp.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    os.replace(tmp,args.output)
    print(json.dumps({k:v for k,v in result.items() if k not in ('receipts','propositions')},sort_keys=True),flush=True)

if __name__=='__main__':main()
