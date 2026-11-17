"""Early COG-03C fixed-seed capacity/packing pilot. No production claim.
Run with one BLAS thread. Equal D and explicit retained arrays; no inference
about equal whole-process memory, equivalent corruption or generalization.
"""
import argparse,hashlib,json,platform,time
from pathlib import Path
import numpy as np
from cognitum.research.hdc_encoders import CodebookSpec,coherence,pack,PackedBank,phase8,PhaseBank,digest

SEEDS=[77013,77029,77041,77057,77069]
DIMS=[256,1024,2048]
LOADS=[8,32,128]
NOISE=[0,.1,.25]
Q=40

def measured(fn):
    t=time.perf_counter_ns();v=fn();return v,(time.perf_counter_ns()-t)/1e6

def stats(a):return {'p50_ms':float(np.median(a)),'p95_ms':float(np.percentile(a,95))}

def run(quick=False):
    out=[];geometry=[]
    for d in ([256] if quick else DIMS):
        for seed in (SEEDS[:1] if quick else SEEDS):
            for method in ('iid','sobol','halton','hadamard'):
                s=CodebookSpec(d,seed,method)
                a,ms=measured(lambda:s.bits(64));aud=coherence(a)
                geometry.append({'D':d,'seed':seed,'method':method,'digest':digest(a),'generation_ms':ms,**aud})
            rng=np.random.default_rng(seed)
            keys=CodebookSpec(d,seed).bits(128); values=CodebookSpec(d,seed+1).bits(128)
            bbank=PackedBank.from_bits(values);pk=pack(keys)
            kphase=np.exp(1j*rng.uniform(-np.pi,np.pi,keys.shape)).astype(np.complex64)
            vphase=np.exp(1j*rng.uniform(-np.pi,np.pi,values.shape)).astype(np.complex64)
            pb=PhaseBank(phase8(vphase))
            for load in ([8] if quick else LOADS):
                # Fixed accumulator and deterministic tie (false); not a lossless update store.
                counts=np.sum(keys[:load]^values[:load],axis=0,dtype=np.int32)*2-load
                bound=counts>0;bound_p=pack(bound)
                accum=np.sum(kphase[:load]*vphase[:load],axis=0,dtype=np.complex64)
                ids=rng.integers(0,load,Q);mismatch=0
                for noise in NOISE:
                    hit={x:0 for x in ('bsc_dense','bsc_packed','fhrr_raw','fhrr_projected','fhrr_phase8','nearest_key')};tim={x:[] for x in hit};diff=[];ranks=0
                    for i,key in enumerate(ids):
                        rg=np.random.default_rng(seed+19*i+1000*load)
                        bq=keys[key]^(rg.random(d)<noise);qp=pack(bq)
                        q=bound^bq
                        a,ms=measured(lambda:np.count_nonzero(values!=q,axis=1));tim['bsc_dense'].append(ms)
                        b,ms=measured(lambda:bbank.distances(bound_p^qp));tim['bsc_packed'].append(ms)
                        np.testing.assert_array_equal(a,b)
                        near,ms=measured(lambda:np.count_nonzero(keys[:load]!=bq,axis=1));tim['nearest_key'].append(ms)
                        # Different corruption geometry: phase perturbation sd=2*pi*noise, not same SNR as bit flips.
                        fq=kphase[key]*np.exp(1j*rg.normal(0,2*np.pi*noise,d)).astype(np.complex64)
                        u=fq.conj()*accum
                        unit=np.exp(1j*np.angle(u)).astype(np.complex64)
                        raw,ms=measured(lambda:(vphase*u.conj()).real.mean(axis=1));tim['fhrr_raw'].append(ms)
                        fp,ms=measured(lambda:(vphase*unit.conj()).real.mean(axis=1));tim['fhrr_projected'].append(ms)
                        f8,ms=measured(lambda:pb.scores(phase8(unit)));tim['fhrr_phase8'].append(ms)
                        diff.append(float(np.max(np.abs(fp-f8))));ranks+=int(np.argmax(fp)!=np.argmax(f8))
                        for arm,pred in [('bsc_dense',np.argmin(a)),('bsc_packed',np.argmin(b)),('nearest_key',np.argmin(near)),('fhrr_raw',np.argmax(raw)),('fhrr_projected',np.argmax(fp)),('fhrr_phase8',np.argmax(f8))]:hit[arm]+=int(pred==key)
                    out.append({'D':d,'seed':seed,'load':load,'noise':noise,'n':Q,'correct':hit,'latency':{k:stats(v) for k,v in tim.items()},'phase8_disagreements':ranks,'phase8_max_score_error':max(diff),'bsc_rank_disagreements':mismatch,
                                'read_only_array_bytes':{'bsc_dense':int(keys[:load].nbytes+values.nbytes+bound.nbytes),'bsc_packed':int(pk[:load].nbytes+bbank.nbytes+bound_p.nbytes),'fhrr_c64':int(kphase[:load].nbytes+vphase.nbytes+accum.nbytes),'fhrr_phase8':int(kphase[:load].nbytes+pb.nbytes+accum.nbytes)},'update_counter_bytes':counts.nbytes})
    return {'schema':'cognitum.cog03c.capacity-pilot.v1','platform':platform.platform(),'numpy':np.__version__,'quick':quick,'geometry':geometry,'rows':out,'scope':'known synthetic associations, independent seed cells; 40 queries/seed, 200 combined per cell in full pilot, not 200 per seed. BSC bit flips vs FHRR phase noise not equivalent SNR. Explicit retained array bytes, excludes shared LUT, Python/RSS/temp; phase8 only value bank compressed, key and accumulator c64 retained. Raw query encoding costs excluded; phase8 query encoding included in score timing. No physical energy or general capacity claim.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--quick',action='store_true');p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=run(a.quick);a.out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8');print('query count',sum(x['n'] for x in r['rows']),'geometry cases',len(r['geometry']),'BSC rank disagreements',sum(x['bsc_rank_disagreements'] for x in r['rows']),'phase8 rank disagreements',sum(x['phase8_disagreements'] for x in r['rows']))
