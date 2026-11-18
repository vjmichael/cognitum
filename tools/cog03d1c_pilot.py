"""Paired fixed-seed research pilots, Linux per-arm process ceiling/RSS.
Logical model bytes include numeric arrays and descriptors; shared canonical
rows/IDs and Python overhead counted in process RSS, not model payload.
"""
import argparse,json,math,time,sqlite3,sys
import numpy as np
from cognitum.research.hdc_memory_advanced import PackedSDM,SignedHopfieldSketch,HRRTable
from cognitum.research.hdc_associative import SparseDistributed,classical_field,continuous_hopfield
from cognitum.research.hdc_encoders import CodebookSpec,PackedBank,pack
from cognitum.research.hdc_capacity import BloomSketch

def pilot(arm,seed,cap):
    r=np.random.default_rng(seed);t=time.perf_counter();results={'arm':arm,'seed':seed,'budget_bytes':cap}
    if arm in ('sdm','packed_sdm','nearest'):
        d=128;n=32;loc=256
        a=r.choice([-1,1],(loc,d)).astype(np.int8);k=r.choice([-1,1],(n,d)).astype(np.int8);v=r.choice([-1,1],(n,d)).astype(np.int8)
        if arm=='nearest':
            bank=PackedBank.from_bits(k<0);payload=bank.nbytes+v.nbytes+32
        else:
            m=(PackedSDM if arm=='packed_sdm' else SparseDistributed)(a,d,52);payload=m.nbytes+v.nbytes+32
            for i in range(n):m.write(k[i],v[i])
        if payload>cap:raise MemoryError('logical cap')
        build=time.perf_counter()-t; q0=time.perf_counter();correct=[];abstain=[]
        for flips in (0,16,32,48):
            c=ab=0
            for _ in range(64):
                i=int(r.integers(n));q=k[i].copy();q[r.choice(d,flips,replace=False)]*=-1
                if arm=='nearest':scores=-bank.distances(pack(q<0))
                else:
                    raw,count=m.raw(q)
                    if not count or not raw.any():ab+=1;continue
                    scores=v.astype(np.int64)@raw
                winners=np.flatnonzero(scores==scores.max())
                if len(winners)!=1:ab+=1
                else:c+=int(winners[0]==i)
            correct.append(c);abstain.append(ab)
        results.update(payload_bytes=payload,build_s=build,query_s=time.perf_counter()-q0,correct=correct,abstain=abstain,queries_per_noise=64)
    elif arm in ('signed','mapi','counting','exact'):
        per_set=cap//2; n=127; ids=r.choice(1024,n,False).tolist();other=ids[:n//2]+r.choice(np.setdiff1d(np.arange(1024),ids),n-n//2,False).tolist();neg=r.choice(np.setdiff1d(np.arange(1024),ids),128,False).tolist();queries=([ids[i] for i in r.integers(n,size=128)]+neg)
        if arm=='signed':
            d=min(256,int((1+math.sqrt(1+2*(per_set-32)))/2));a=SignedHopfieldSketch(d,seed,ids);b=SignedHopfieldSketch(d,seed,other);payload=a.payload_bytes;est=a.intersection(b);contains=a.contains
        elif arm=='counting':
            d=min(65536,(per_set-32)//2);a=BloomSketch(d,4,seed,ids,True);b=BloomSketch(d,4,seed,other,True);payload=a.payload_bytes;est=a.estimate_intersection(b);contains=a.contains
        elif arm=='mapi':
            d=min(65536,(per_set-32)//2);spec=CodebookSpec(d,seed)
            atom=lambda i:(1-2*spec.bits(1,i)[0].astype(np.int16))
            a=np.zeros(d,np.int16);b=a.copy()
            for i in ids:a+=atom(i)
            for i in other:b+=atom(i)
            payload=a.nbytes+32;est=int(a.astype(np.int64)@b.astype(np.int64))/d;contains=lambda i:int(a.astype(np.int64)@atom(i).astype(np.int64))/d>=.5
        else:
            d=None;a=np.sort(np.array(ids,np.uint32));b=np.sort(np.array(other,np.uint32));payload=a.nbytes+32;est=len(np.intersect1d(a,b));contains=lambda i:bool(np.any(a==i))
        payload*=2 # both retained representations are necessary for intersection
        assert payload<=cap;build=time.perf_counter()-t;q0=time.perf_counter();actual=[bool(contains(i)) for i in queries]
        results.update(payload_bytes=payload,dimension=d,build_s=build,query_s=time.perf_counter()-q0,fp=sum(actual[128:]),fn=128-sum(actual[:128]),intersection=float(est),truth=n//2,queries=256)
    elif arm in ('hrr','sqlite'):
        n=128;rows=[(int(r.integers(-4,5)),str(int(r.integers(5))),None if i%7==0 else int(r.integers(4)),int(r.integers(8))) for i in range(n)];rows[-1]=rows[0]
        qq=[]
        for i in range(30):
            x=rows[i];qq.extend([((0,'=',x[0]),),((0,'!=',x[0]),(1,'=',x[1])),((2,'IS NULL',None),),((0,'=',99),)])
        db=sqlite3.connect(':memory:');db.execute('create table a(a,b,c,d)');db.executemany('insert into a values(?,?,?,?)',rows);db.commit();db.execute('create index ix on a(a,b,c)');db.commit()
        shared=len(db.serialize())+len(json.dumps(rows,separators=(',',':')).encode())
        if arm=='hrr':
            d=min(1024,(cap-shared-128)//(4*(n+4)));m=HRRTable(rows,d,seed,'fixture',1);payload=m.payload_bytes+shared
        else:d=None;payload=shared
        assert payload<=cap;build=time.perf_counter()-t;tp=fp=fn=verified=wrong=proj=proj_n=0;candidate_s=verify_s=sql_s=0.
        for p in qq:
            sql=' and '.join('abcd'[j]+' '+op+(' ?' if op in ('=','!=') else '') for j,op,x in p);params=[x for j,op,x in p if op in ('=','!=')];q0=time.perf_counter();expected=tuple((i-1,(a,b)) for i,a,b in db.execute('select rowid,a,b from a where '+sql+' order by rowid',params));sql_s+=time.perf_counter()-q0
            if arm=='hrr':
                q0=time.perf_counter();p0=m.propose(p);candidate_s+=time.perf_counter()-q0;q0=time.perf_counter();actual=m.verify(p0,p,[0,1],canonical_rows=rows,current_snapshot='fixture',current_revision=1);verify_s+=time.perf_counter()-q0
                w=set(p0.ids);e={i for i,_ in expected};tp+=len(w&e);fp+=len(w-e);fn+=len(e-w);verified+=len(actual);wrong+=len(set(actual)-set(expected));assert m.verify(p0,p,[0,1],canonical_rows=rows,current_snapshot='fixture',current_revision=1,complete=True)==expected
            else:tp+=len(expected);verified+=len(expected)
        if arm=='hrr':
            for i in range(n):
                proj+=m.project_candidates(i,0,list(range(-4,5)))==rows[i][0];proj_n+=1
        results.update(payload_bytes=payload,dimension=d,build_s=build,queries=len(qq),tp=tp,fp=fp,fn=fn,verified=verified,verified_wrong=wrong,candidate_s=candidate_s,verify_s=verify_s,sql_s=sql_s,projection_correct=int(proj),projection_n=proj_n,shared_sqlite_bytes=len(db.serialize()))
    else:raise ValueError(arm)
    try:
        import resource;results['peak_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except ImportError:results['peak_rss_kib']=None
    return results

def main():
    p=argparse.ArgumentParser();p.add_argument('--arm',required=True);p.add_argument('--seed',type=int,required=True);p.add_argument('--cap',type=int,required=True);p.add_argument('--process-mib',type=int,default=0);args=p.parse_args()
    if args.process_mib:
        import resource;v=args.process_mib*1024**2;resource.setrlimit(resource.RLIMIT_AS,(v,v))
    print(json.dumps(pilot(args.arm,args.seed,args.cap),sort_keys=True))
if __name__=='__main__':main()
