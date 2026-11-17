"""Bounded CPU pilot: ordered tuple retrieval, not model generalization or capacity proof.
Single-thread BLAS set by caller; run from candidate root.
"""
import itertools,json,platform,time,resource,hashlib,os
from pathlib import Path
import numpy as np
from cognitum.research.hdc_ghrr import GHRRSpec,FlatBank
from cognitum.research.hdc_algebra import Spec

SEQ=list(itertools.permutations(range(8),3))
SEEDS=[41031,41047,41061]
CELLS=[(32,2),(128,2),(32,4)]
NOISE=[0.,1.,2.,4.]
Q=48

def clock(fn):
    a=time.perf_counter_ns(); out=fn();return out,(time.perf_counter_ns()-a)/1e6

def stats(a): return {'p50_ms':float(np.median(a)),'p95_ms':float(np.percentile(a,95))}

def noisy(x,r,ratio):
    if ratio==0:return x.copy()
    n=(r.normal(size=x.shape)+1j*r.normal(size=x.shape)).astype(x.dtype)
    return (x+n*(ratio*np.linalg.norm(x)/np.linalg.norm(n))).astype(x.dtype)

def encg(s,a,z):
    out=s.identity()
    for v in z:out=s.bind(out,a[v])
    return out

def encf(s,a,z):
    out=np.ones(s.dimension,s.dtype)
    for i,v in enumerate(z):out=s.bind(out,s.permute(a[v],i))
    return out

def matrix_scores(bank,q,d,m):
    # Naive but correctly vectorized matrix trace, native complex64.
    return np.trace(bank@q.conj().swapaxes(-1,-2),axis1=-2,axis2=-1).sum(axis=1).real/(d*m)

def one(d,m,seed):
    s=GHRRSpec(d,m); rng=np.random.default_rng(seed); queries=rng.integers(0,len(SEQ),Q)
    g,atomic_ms=clock(lambda:s.random_atoms(8,seed)); bank,encode_ms=clock(lambda:np.stack([encg(s,g,z) for z in SEQ])); flat,build=clock(lambda:FlatBank(s,bank,accumulator='native'))
    arms={}; times={}; truths={}; maxerr=0.; disagreements=0
    for label,fd in [('FHRR_equal_D',d),('FHRR_equal_bytes',s.scalar_count)]:
        f=Spec('FHRR',fd); r=np.random.default_rng(seed+31)
        a,t=clock(lambda:np.exp(1j*r.uniform(-np.pi,np.pi,(8,fd))).astype(np.complex64)); b,e=clock(lambda:np.stack([encf(f,a,z) for z in SEQ])); v,u=clock(lambda:np.frombuffer(b.view(np.float32).tobytes(),np.float32).reshape(len(b),-1)); arms[label]=(f,a,v);times[label]={'atomic_ms':t,'encode_bank_ms':e,'build_ms':u,'retained_array_bytes':int(a.nbytes+v.nbytes),'matrix_bank_bytes':int(b.nbytes)}
    # Each query is encoded anew. Timings separate query encoding and resident scoring; NO IPC or host claims.
    labels=['GHRR_flat','GHRR_matrix','GHRR_contraction',*arms];times['GHRR_flat']={'atomic_ms':atomic_ms,'encode_bank_ms':encode_ms,'build_ms':build,'retained_array_bytes':int(g.nbytes+flat.nbytes),'matrix_bank_bytes':int(bank.nbytes)};times['GHRR_matrix']={'atomic_ms':atomic_ms,'encode_bank_ms':encode_ms,'build_ms':0,'retained_array_bytes':int(g.nbytes+bank.nbytes),'matrix_bank_bytes':int(bank.nbytes)}
    times['GHRR_contraction']=dict(times['GHRR_matrix'])
    for noise in NOISE:
        scores={label:[] for label in labels}; elapsed={label:[] for label in labels}; enct={label:[] for label in labels}; total={label:[] for label in labels}
        for i,idx in enumerate(queries):
            z=SEQ[idx]; v,et=clock(lambda:encg(s,g,z)); q=noisy(v,np.random.default_rng(seed+1000+i),noise)
            a,t=clock(lambda:flat.scores(q)); b,u=clock(lambda:matrix_scores(bank,q,d,m)); c,w=clock(lambda:np.einsum('nijk,ijk->n',bank,q.conj(),optimize=False).real/(d*m))
            err=float(max(np.max(np.abs(a-b)),np.max(np.abs(a-c)))); maxerr=max(err,maxerr); assert err<2e-5,(d,m,err)
            pa,pb,pc=int(np.argmax(a)),int(np.argmax(b)),int(np.argmax(c));disagreements+=int(pa!=pb or pa!=pc)
            for label,p,ms in [('GHRR_flat',pa,t),('GHRR_matrix',pb,u),('GHRR_contraction',pc,w)]:
                scores[label].append(p==idx);elapsed[label].append(ms);enct[label].append(et);total[label].append(et+ms)
            for label,(f,fa,fbank) in arms.items():
                fv,etf=clock(lambda:encf(f,fa,z)); fq=noisy(fv,np.random.default_rng(seed+1000+i),noise)
                score,ms=clock(lambda:(fbank@np.ascontiguousarray(fq).view(np.float32))/f.dimension)
                scores[label].append(int(np.argmax(score))==idx);elapsed[label].append(ms);enct[label].append(etf);total[label].append(etf+ms)
        truths[str(noise)]={l:{'correct':int(sum(scores[l])),'n':Q,'score':stats(elapsed[l]),'encode':stats(enct[l]),'encode_plus_score':stats(total[l])} for l in labels}
    return {'D':d,'m':m,'seed':seed,'max_score_error':maxerr,'rank1_disagreements':disagreements,'timings_and_bytes':times,'results':truths}

if __name__=='__main__':
    rows=[one(d,m,s) for d,m in CELLS for s in SEEDS]
    assert not sum(r['rank1_disagreements'] for r in rows)
    report={'schema':'cognitum.cog03b2.ordered_retrieval.v1','python':platform.python_version(),'platform':platform.platform(),'numpy':np.__version__,'threads':{k:os.getenv(k) for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']},'vocab':8,'candidates':len(SEQ),'queries_per_noise_seed':Q,'noise':'relative L2 norm of additive complex perturbation; shared tuple IDs and seed, representation-specific dimensions, not real sensor noise','scope':'known finite codebook, clean re-encoding and synthetic query corruption; no learned/generalization/hardware claim; times include encoding and resident score, omit simulated perturbation/argmax/host; array bytes only, both comparison banks held by benchmark, not per-arm RSS','process_peak_rss_kib_linux':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'rows':rows,'source_sha256':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in ['cognitum/research/hdc_ghrr.py','cognitum/research/hdc_algebra.py','tools/cog03b2_ordered_retrieval.py']}}
    Path('ghrr_pilot.json').write_text(json.dumps(report,indent=2)+'\n')
    for d,m in CELLS:
        rr=[r for r in rows if (r['D'],r['m'])==(d,m)]
        print(d,m,'score_err',max(r['max_score_error'] for r in rr),'bank bytes', {k:v['retained_array_bytes'] for k,v in rr[0]['timings_and_bytes'].items()})
        for noise in NOISE:
            print('noise',noise,{l:(sum(r['results'][str(noise)][l]['correct'] for r in rr),round(float(np.median([r['results'][str(noise)][l]['score']['p50_ms'] for r in rr])),4)) for l in rr[0]['results'][str(noise)]})
