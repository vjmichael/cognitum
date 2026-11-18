"""Fixed seed exploratory pilots. One arm per process optional; no task authority."""
import argparse,json,time,sys
from collections import Counter
import numpy as np
from cognitum.research.hdc_resonator_frontier import (CoupledResonator,RULES,iterate_classical,iterate_continuous,OrderedPaths,Edge)
from cognitum.research.hdc_algebra import Spec
from cognitum.research.hdc_ghrr import GHRRSpec

def rss():
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except ImportError:return None

def factor(seed,family,n,f,d,queries,rule):
    spec=Spec(family,d);rng=np.random.default_rng(seed)
    banks=[rng.choice([-1,1],(n,d)).astype(spec.dtype) if family=='MAP' else np.exp(1j*rng.uniform(-np.pi,np.pi,(n,d))).astype(spec.dtype) for _ in range(f)]
    r=CoupledResonator(spec,banks); payload=r.nbytes
    # Use a separate shared trial RNG: IDs identical across representations and methods.
    tr=np.random.default_rng(seed+145); noise_rng=np.random.default_rng(seed+246); rows=[]
    for corruption in (0,.125):
        c=Counter();projections=0;sweeps=0;t=time.perf_counter()
        for i in range(queries):
            ids=tuple(int(x) for x in tr.integers(n,size=f));q=r.compose(ids);q[noise_rng.choice(d,int(corruption*d),replace=False)]*=-1
            out=r.exhaustive(q) if rule=='exhaustive' else r.decode(q,rule=rule,steps=30,restarts=2,seed=seed+i,minimum=.5)
            c['correct' if out.ids==ids else 'abstained' if out.ids is None else 'wrong']+=1;c[out.status]+=1;c['raw_tuple_correct']+=int(out.decoded_ids==ids);c['spurious_fixed']+=int(out.status=='fixed' and out.decoded_ids!=ids)
            projections+=out.projections;sweeps+=out.sweeps
        rows.append(dict(arm=rule,seed=seed,family=family,dimension=d,factors=f,vocab=n,noise=corruption,queries=queries,payload_bytes=payload,elapsed_s=time.perf_counter()-t,projections=projections,sweeps=sweeps,counts=dict(c),peak_rss_kib=rss()))
    return rows

def hopfield(seed,n,d,queries):
    r=np.random.default_rng(seed);p=r.choice([-1,1],(n,d)).astype(np.int8);payload=p.nbytes;rows=[]
    qs=[]
    for flip in (0,.125,.25):
        for _ in range(queries):
            i=int(r.integers(n));q=p[i].copy();q[r.choice(d,int(flip*d),replace=False)]*=-1;qs.append((flip,i,q))
    for arm in ('nearest','classical','continuous'):
        c={};t=time.perf_counter();sweeps=0;viol=0
        for flip,i,q in qs:
            if arm=='nearest':x=q;fixed=True
            else:
                out=iterate_classical(p,q,steps=20) if arm=='classical' else iterate_continuous(p/np.sqrt(d),q/np.sqrt(d),beta=20.,steps=20,tolerance=1e-7)
                x=out.state;fixed=out.status=='fixed';sweeps+=out.sweeps;viol+=int(np.any(np.diff(out.energies)>1e-9))
            scores=p.astype(np.float64)@x;ix=np.flatnonzero(np.isclose(scores,scores.max(),atol=1e-7,rtol=0));k=c.setdefault(str(flip),{'correct':0,'wrong':0,'abstained':0,'fixed':0})
            k['fixed']+=int(fixed);k['abstained' if not fixed or len(ix)!=1 else 'correct' if ix[0]==i else 'wrong']+=1
        rows.append(dict(arm=arm,seed=seed,dimension=d,load=n,queries_per_noise=queries,counts=c,sweeps=sweeps,energy_violations=viol,retained_pattern_bytes=payload,elapsed_s=time.perf_counter()-t,peak_rss_kib=rss()))
    return rows

def graph(seed,queries):
    rng=np.random.default_rng(seed);rel=tuple('r'+str(i) for i in range(5));edges=[]
    for i in range(24):
        for j in range(3):edges.append(Edge(str(i),rel[int(rng.integers(5))],str(int(rng.integers(24))),f'e{i}-{j}'))
    # Use identical source graphs and relation-sequence queries; exact path witnesses independent.
    cases=[]
    for _ in range(queries):
        s=str(int(rng.integers(24)));path=[];node=s
        for _ in range(3):
            e=edges[int(node)*3+int(rng.integers(3))];path.append(e);node=e.target
        cases.append((s,tuple(e.relation for e in path)))
    rows=[];oracle=[];t=time.perf_counter()
    for s,rs in cases:
        paths=[(s,())]
        for r in rs:paths=[(e.target,ids+(e.witness,)) for node,ids in paths for e in edges if e.source==node and e.relation==r]
        oracle.append(set(paths))
    rows.append(dict(arm='exact_graph',seed=seed,queries=queries,truth_count=sum(map(len,oracle)),elapsed_s=time.perf_counter()-t))
    # FHRR D128 = GHRR D32 width2 at equal complex atom bytes.
    for name in ('FHRR','GHRR'):
        if name=='FHRR':s=Spec(name,128);a=np.exp(1j*rng.uniform(-np.pi,np.pi,(len(rel),128))).astype(s.dtype)
        else:s=GHRRSpec(32,2);a=s.random_atoms(len(rel),seed)
        p=OrderedPaths(s,dict(zip(rel,a)),edges,'graph1');found=wrong=miss=0;t=time.perf_counter()
        for (start,rs),truth in zip(cases,oracle):
            q=p.encode(rs);rank=p.candidates(start,q,3,k=8);v=set()
            for _,path in rank:
                result=p.verify(path,start=start,relations=rs,current_snapshot='graph1',canonical_edges=edges)
                if result is not None:v.add(result)
            found+=len(v&truth);wrong+=len(v-truth);miss+=len(truth-v)
        rows.append(dict(arm=name,seed=seed,queries=queries,truth_count=sum(map(len,oracle)),verified=found,wrong=wrong,miss=miss,atom_bytes=a.nbytes,graph_serialized_bytes=len(json.dumps([e.__dict__ for e in edges]).encode()),elapsed_s=time.perf_counter()-t,peak_rss_kib=rss()))
    return rows

def main():
    p=argparse.ArgumentParser();p.add_argument('--quick',action='store_true');p.add_argument('--out');p.add_argument('--seed',type=int);a=p.parse_args();rows={'factor':[],'hopfield':[],'graph':[]}
    seeds=[a.seed] if a.seed is not None else [301] if a.quick else [301,302,303,304,305]
    for seed in seeds:
        for n,f,d in ([(4,3,128)] if a.quick else [(4,3,256),(12,3,256),(6,4,512)]):
            for fam in ('MAP','FHRR'):
                for rule in (*RULES,'exhaustive'):
                    rows['factor']+=factor(seed,fam,n,f,d if fam=='MAP' else d//2,4 if a.quick else 12,rule)
        for n in ([8] if a.quick else [8,32,64]):rows['hopfield']+=hopfield(seed,n,128,4 if a.quick else 16)
        rows['graph']+=graph(seed,4 if a.quick else 32)
    payload=json.dumps(rows,indent=2,sort_keys=True)+'\n'
    if a.out:open(a.out,'w',encoding='utf8').write(payload)
    else:print(payload)
if __name__=='__main__':main()
