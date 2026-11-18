"""Paired synthetic D2B pilots; fixed params, exact controls, no promotion."""
import argparse,json,time
from collections import Counter
from itertools import product
import numpy as np
from cognitum.research.hdc_algebra import Spec
from cognitum.research.hdc_resonator_frontier import CoupledResonator,OrderedPaths,Edge
from cognitum.research.hdc_reasoning_advanced import (BlockFactorizer,coordinate_beam,correlated_banks,peel,graph_rank_features,rank_hv,GraphFingerprintIndex,synthesize,transfer_rule,verified_rule_paths,OPS,exact_equal_pair)


def factor(seed,quick):
    rows=[];rng=np.random.default_rng(seed)
    for n,corr in product([4] if quick else [8,16],[0.] if quick else [0.,.5,.85]):
        e=CoupledResonator(Spec('FHRR',256),correlated_banks(Spec('FHRR',256),3,n,corr,seed));samples=[]
        for _ in range(2 if quick else 8):
            ids=tuple(map(int,rng.integers(n,size=3)));samples.append((ids,e.compose(ids)))
        for arm in ('relu','beam','exhaustive'):
            c=Counter();work=0;t=time.perf_counter()
            for ids,q in samples:
                if arm=='relu':r=e.decode(q,rule='relu',project=False,restarts=3,steps=25,seed=seed,minimum=.5);guess=r.ids;work+=r.projections*n
                elif arm=='beam':guess,w=coordinate_beam(e,q,width=4,sweeps=4,seed=seed);work+=w
                else:r=e.exhaustive(q);guess=r.ids;work+=r.projections
                c['abstain' if guess is None else 'correct' if guess==ids else 'wrong']+=1
            rows.append(dict(seed=seed,n=n,correlation=corr,arm=arm,queries=len(samples),correct=c['correct'],wrong=c['wrong'],abstain=c['abstain'],work=work,seconds=time.perf_counter()-t,codebook_bytes=e.nbytes))
    return rows


def multi(seed,quick):
    rng=np.random.default_rng(seed);n=4 if quick else 8;s=Spec('FHRR',256);e=CoupledResonator(s,correlated_banks(s,3,n,.25,seed));rows=[];samples=[]
    for _ in range(2 if quick else 12):
        a,b=rng.choice(n**3,2,replace=False);ids=[tuple(map(int,np.unravel_index(i,(n,n,n)))) for i in (a,b)];samples.append((ids,2*e.compose(ids[0])+e.compose(ids[1])))
    for arm in ('iterative','exhaustive'):
        c=Counter();res=[];work=0;t=time.perf_counter()
        for ids,q in samples:
            out,r,w=peel(e,q,2,method=arm,seed=seed);work+=w;res.append(r);c['full' if set(out)==set(ids) else 'partial' if set(out)&set(ids) else 'none']+=1;c['spurious']+=len(set(out)-set(ids))
        rows.append(dict(seed=seed,arm=arm,queries=len(samples),full=c['full'],partial=c['partial'],none=c['none'],spurious=c['spurious'],mean_residual=float(np.mean(res)),seconds=time.perf_counter()-t,work=work,codebook_bytes=e.nbytes))
    return rows


def sparse(seed,quick):
    rng=np.random.default_rng(seed);rows=[]
    for n in [8] if quick else [8,16,32]:
        e=BlockFactorizer([rng.integers(0,32,(n,16)) for _ in range(3)],32)
        for noise in [0.] if quick else [0.,.2]:
            samples=[]
            for _ in range(2 if quick else 8):
                ids=tuple(map(int,rng.integers(n,size=3)));samples.append((ids,e.encode(ids)*(1-noise)+noise/32))
            for arm in ('linf','dot','exhaustive'):
                c=Counter();searches=0;t=time.perf_counter()
                for ids,q in samples:
                    r=e.exhaustive(q) if arm=='exhaustive' else e.decode(q,threshold=.005,detection=.5,sampling=2,steps=100,seed=seed,metric=arm);searches+=r.searches;c['abstain' if r.ids is None else 'correct' if r.ids==ids else 'wrong']+=1
                rows.append(dict(seed=seed,n=n,noise=noise,arm=arm,queries=len(samples),correct=c['correct'],wrong=c['wrong'],abstain=c['abstain'],searches=searches,seconds=time.perf_counter()-t,codebook_bytes=e.nbytes,dense_pmf_state_bytes=3*16*32*8))
    return rows


def graph(seed,quick):
    rng=np.random.default_rng(seed);rows=[];fixtures=[];cutoff=9 if quick else 14
    for label,n in product(range(3),range(6,11) if quick else range(6,20)):
        a=np.zeros((n,n),int)
        for i in range(n-1):
            j=0 if label==0 else i;a[j,i+1]=a[i+1,j]=1
        if label==2:a[0,-1]=a[-1,0]=1
        p=rng.permutation(n);fixtures.append((label,n,a[np.ix_(p,p)]))
    for enc in ('pagerank','degree'):
        t=time.perf_counter();f=[graph_rank_features(a,centrality=enc) for _,_,a in fixtures];encode=time.perf_counter()-t
        t=time.perf_counter();vocab=sorted({k for (_,n,_),x in zip(fixtures,f) if n<cutoff for k in x});x=np.array([[v.get(k,0) for k in vocab] for v in f],float);exact_encode=time.perf_counter()-t;t=time.perf_counter();h=np.array([rank_hv(v,256,seed) for v in f],float);hd_encode=time.perf_counter()-t;y=np.array([a for a,_,_ in fixtures]);train=np.array([n<cutoff for _,n,_ in fixtures]);
        for arm,z in [('exact_rank',x),('graphhd',h)]:
            t=time.perf_counter();norm=np.linalg.norm(z,axis=1,keepdims=True);z=z/np.maximum(norm,1e-12);bank=np.stack([z[train&(y==c)].sum(0) for c in range(3)]);bank/=np.maximum(np.linalg.norm(bank,axis=1,keepdims=True),1e-12);pred=np.argmax(z[~train]@bank.T,axis=1)
            rows.append(dict(seed=seed,centrality=enc,arm=arm,queries=len(pred),correct=int(np.sum(pred==y[~train])),seconds=time.perf_counter()-t,centrality_seconds=encode,feature_encoding_seconds=hd_encode if arm=='graphhd' else exact_encode,prototype_bytes=bank.nbytes))
    t=time.perf_counter();c=0;n_test=0
    for label,n,a in fixtures:
        if n<cutoff:continue
        d=a.sum(1);prediction=0 if d.max()==n-1 else 2 if (d==2).all() else 1;c+=prediction==label;n_test+=1
    rows.append(dict(seed=seed,centrality='degree',arm='exact_structure',queries=n_test,correct=int(c),seconds=time.perf_counter()-t,prototype_bytes=0))
    index=GraphFingerprintIndex(bits=8,seed=seed);reference={}
    for i,v in enumerate(f):index.insert(str(i),v);reference.setdefault(tuple(sorted(v.items())),[]).append(str(i))
    t=time.perf_counter()
    for v in f:assert index.lookup(v)==tuple(sorted(reference[tuple(sorted(v.items()))]))
    hash_seconds=time.perf_counter()-t;t=time.perf_counter()
    for v in f:assert reference[tuple(sorted(v.items()))]
    return rows,dict(seed=seed,queries=len(f),seconds=hash_seconds,dict_seconds=time.perf_counter()-t,buckets=len(index.buckets),records=len(index.rows))


def grid_oracle(scene,program):
    g=np.zeros(16,int)
    for p,c in scene:g[p]=c
    for op in program:
        if op=='shift_left':
            if g[0]:return None
            g=np.r_[g[1:],0]
        elif op=='shift_right':
            if g[-1]:return None
            g=np.r_[0,g[:-1]]
        elif op=='reverse':g=g[::-1]
        else:g=np.where(g>0,g%3+1,0)
    return tuple((int(i),int(g[i])) for i in g.nonzero()[0])


def arc(seed,quick):
    rng=np.random.default_rng(seed);rows=[];s=Spec('FHRR',128);samples=[]
    for p in list(product(OPS,repeat=2))[:4 if quick else 16]:
        scenes=[tuple(sorted((int(i),int(rng.integers(1,4))) for i in rng.choice(np.arange(3,13),3,replace=False))) for _ in range(4)]
        samples.append(([(x,grid_oracle(x,p)) for x in scenes[:2]],[(x,grid_oracle(x,p)) for x in scenes[2:]]))
    for budget in [20] if quick else [4,20]:
        for arm in ('symbolic','fhrr_rank'):
            c=checks=rank=0;t=time.perf_counter()
            for train,held in samples:
                p,n,k=synthesize(train,spec=s if arm=='fhrr_rank' else None,budget=budget,seed=seed);checks+=n;rank+=k
                if p is not None and all(grid_oracle(x,p)==y for x,y in held):c+=1
            rows.append(dict(seed=seed,arm=arm,budget=budget,queries=len(samples),correct=c,exact_checks=checks,rank_programs=rank,seconds=time.perf_counter()-t,all_programs=20))
    return rows


def rules(seed,quick):
    rng=np.random.default_rng(seed);s=Spec('FHRR',128);rv={r:np.exp(1j*rng.uniform(-np.pi,np.pi,s.dimension)).astype(s.dtype) for r in ('a','b','c','d')}
    def make(prefix,n,holdout):
        es=[]
        for i in range(n):
            v=prefix+str(i);es.extend([Edge(v,'a',v+'x',v+'1'),Edge(v+'x','b',v+'y',v+'2'),Edge(v,'d',v+'z',v+'3'),Edge(v+'z','b',v+'w',v+'4')])
            if not holdout or i%3:es.append(Edge(v,'c',v+'y',v+'5'))
        return OrderedPaths(s,rv,es,prefix)
    train=make('train',5,False);assert transfer_rule(train,('a','b'),'c',['train'+str(i) for i in range(5)])
    n=6 if quick else 24;test=make('hold',n,True);truth=[];found=[];t=time.perf_counter()
    for i in range(n):
        v='hold'+str(i);truth.extend((y.target,(x.witness,y.witness),z.witness) for x in test.edges if x.source==v and x.relation=='a' for y in test.edges if y.source==x.target and y.relation=='b' for z in test.edges if z.source==v and z.target==y.target and z.relation=='c')
    exact=time.perf_counter()-t;t=time.perf_counter()
    for i in range(n):found.extend(verified_rule_paths(test,'hold'+str(i),('a','b'),'c',current_snapshot='hold',canonical_edges=test.edges))
    return dict(seed=seed,queries=n,truth=len(truth),correct=len(set(found)&set(truth)),wrong=len(set(found)-set(truth)),miss=len(set(truth)-set(found)),seconds=time.perf_counter()-t,exact_seconds=exact)


def run(seeds,quick=False):
    out={k:[] for k in ('factor','multi','sparse','graph','hash','arc','rules','equal_pair')}
    for seed in seeds:
        for name,fn in [('factor',factor),('multi',multi),('sparse',sparse),('arc',arc)]:out[name].extend(fn(seed,quick))
        rows,h=graph(seed,quick);out['graph'].extend(rows);out['hash'].append(h);out['rules'].append(rules(seed,quick))
        e=CoupledResonator(Spec('FHRR',128),correlated_banks(Spec('FHRR',128),3,4,0,seed));a=(0,1,2);b=(3,2,1);q=e.compose(a)+e.compose(b);t=time.perf_counter();ids,res,pairs=exact_equal_pair(e,q);out['equal_pair'].append(dict(seed=seed,correct=bool(ids is not None and set(ids)=={a,b}),pairs=pairs,residual=res,seconds=time.perf_counter()-t))
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--quick',action='store_true');p.add_argument('--seed',type=int,action='append');p.add_argument('--out',required=True);a=p.parse_args();r=run(a.seed or ([601] if a.quick else list(range(601,606))),a.quick)
    with open(a.out,'w',encoding='utf8') as f:json.dump(r,f,indent=2,allow_nan=False);f.write('\n')
