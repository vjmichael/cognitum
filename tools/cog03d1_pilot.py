"""Matched synthetic SDM/nearest-key cue experiment. No factual authority.
Array storage includes actual hard locations, counters and common value bank;
nearest-key retains explicit keys and ID mapping. Timings include score/argmax.
"""
import argparse,json,time
from pathlib import Path
import numpy as np
from cognitum.research.hdc_associative import SparseDistributed


def run(quick=False):
    rows=[];d=128;h=512;radius=52
    for seed in ([7401] if quick else [7401,7403,7411,7417,7421]):
        rng=np.random.default_rng(seed)
        hard=rng.choice(np.array([-1,1],np.int8),(h,d));keys=rng.choice(np.array([-1,1],np.int8),(128,d));vals=rng.choice(np.array([-1,1],np.int8),(128,d));val_i=vals.astype(np.int32)
        for load in ([32] if quick else [8,32,128]):
            s=SparseDistributed(hard,d,radius);start=time.perf_counter();activated=[s.write(k,v) for k,v in zip(keys[:load],vals[:load])];build=time.perf_counter()-start
            ki=keys[:load].astype(np.int32)
            for flips in ([0,32] if quick else [0,16,32,48]):
                ids=rng.integers(load,size=32 if quick else 64);queries=keys[ids].copy()
                for q in queries:q[rng.choice(d,flips,replace=False)]*=-1
                preds={};elapsed={};abstains={}
                for arm in ('exact_key','nearest','sdm'):
                    p=[];start=time.perf_counter()
                    for q in queries:
                        if arm=='exact_key':
                            hit=np.flatnonzero(np.all(keys[:load]==q,axis=1));p.append(int(hit[0]) if len(hit)==1 else -1);continue
                        if arm=='nearest':score=ki@q.astype(np.int32)
                        else:
                            raw,n=s.raw(q)
                            if n==0 or not raw.any():p.append(-1);continue
                            score=val_i[:load]@raw
                        best=np.flatnonzero(score==score.max());p.append(int(best[0]) if len(best)==1 else -1)
                    elapsed[arm]=time.perf_counter()-start;preds[arm]=p;abstains[arm]=p.count(-1)
                rows.append({'seed':seed,'load':load,'dimension':d,'flips':flips,'n':len(ids),'correct':{a:int(np.sum(np.array(p)==ids)) for a,p in preds.items()},'abstain':abstains,'seconds':elapsed,'array_bytes':{'exact_key':keys[:load].nbytes+load*4,'nearest':ki.nbytes+load*4,'sdm':s.nbytes+val_i[:load].nbytes+load*4},'activated_min':min(activated),'activated_max':max(activated),'sdm_build_seconds':build})
    return {'scope':'synthetic independent bipolar key/value pairs; identical queries across arms; explicit ID arrays logically counted; SDM value bank only for cleanup, exact/nearest retain key mappings; excludes interpreter, temporary arrays, generator fixtures and canonical verification; not full end-to-end budget','rows':rows}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--quick',action='store_true');p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.write_text(json.dumps(run(a.quick),indent=2)+'\n',encoding='utf8')
