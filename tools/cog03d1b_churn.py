"""Research-only deterministic churn. Independent authoritative dict + scalar
reconstruction, periodic restart and C08 verification; no production route."""
import argparse, hashlib, json, time
from pathlib import Path
import numpy as np
from cognitum.research.hdc_associative_lifecycle import DerivedAssociations, relation_key, _value
from cognitum.research.hdc_canonical import CanonicalRelation


def run(steps):
    rng=np.random.default_rng(1240)
    # Include 16 exact fixture locations plus random hard locations. Radius
    # near the center for distributed writes; not an optimized address policy.
    keys=np.stack([relation_key('owns',f'e{i}') for i in range(16)])
    addresses=np.concatenate((keys,rng.choice(np.array([-1,1],np.int8),size=(16,256))))
    c=DerivedAssociations(addresses,116,'alice'); c.install('s1',1,[])
    host={}; times=[]; direct_times=[]; updates=dict(insert=0,replace=0,delete=0,rescope=0)
    checks=verified=abstained=rejected=0; restart=0
    start=time.perf_counter()
    for i in range(steps):
        rev=i+2; k=int(rng.integers(32)); id=f'id{k}'; e=f'e{int(rng.integers(16))}'
        mode=int(rng.integers(4)); dead=mode==0; scope='bob' if mode==1 else 'alice'
        old=host.get(id); row=CanonicalRelation(id,rev,scope,'owns',e,f'lu:{id}:{rev}',dead)
        if dead:updates['delete']+=1
        elif scope!='alice':updates['rescope']+=1
        elif old is None or old.tombstone or old.scope!='alice':updates['insert']+=1
        else:updates['replace']+=1
        t=time.perf_counter();host[id]=row;direct_times.append(time.perf_counter()-t)
        t=time.perf_counter();c.apply(snapshot=f's{rev-1}',revision=rev-1,next_snapshot=f's{rev}',next_revision=rev,changes=[row]);times.append(time.perf_counter()-t)
        if (i+1)%max(1,steps//100)==0 or i+1==steps:
            # Independent oracle: reconstruct with scalar membership counts and
            # explicit SHA-derived values, no SDM.write or incremental arithmetic.
            count=np.zeros(len(addresses),np.int64); counter=np.zeros((len(addresses),256),np.int64)
            for r in host.values():
                if r.tombstone or r.scope!='alice':continue
                key=relation_key(r.role,r.entity); val=_value(r).astype(np.int64)
                for j,addr in enumerate(addresses):
                    if np.count_nonzero(addr!=key)<=116:
                        count[j]+=1;counter[j]+=val
            np.testing.assert_array_equal(c._sdm._counts,count);np.testing.assert_array_equal(c._sdm._counters,counter);checks+=1
            probe=keys[(i//max(1,steps//100))%16]; ent=f'e{(i//max(1,steps//100))%16}'
            p=c.propose(probe,snapshot=f's{rev}',revision=rev)
            if p is None:abstained+=1
            else:
                hit=c.verify(p,probe,role='owns',entity=ent,authorized_scope='alice',canonical_snapshot_id=f's{rev}',current_snapshot_id=f's{rev}',required_revision=rev,canonical_records=tuple(host.values()))
                if hit is None:rejected+=1
                else:
                    truth=host[hit.source_id]; assert not truth.tombstone and truth.scope=='alice' and truth.entity==ent and truth.revision==hit.revision;verified+=1
            if checks%10==0 or i+1==steps:
                blob=c.checkpoint(snapshot=f's{rev}',revision=rev)
                c=DerivedAssociations(addresses,116,'alice');c.restore(blob,snapshot=f's{rev}',revision=rev,canonical_records=tuple(host.values()));restart+=1
    blob=c.checkpoint(snapshot=f's{steps+1}',revision=steps+1)
    metadata=json.dumps([vars(x) for x in c._rows.values()],sort_keys=True,separators=(',',':')).encode()
    return dict(steps=steps,mutations=updates,oracle_checks=checks,restarts=restart,verified=verified,abstained=abstained,rejected=rejected,verified_false_positives=0,elapsed_s=time.perf_counter()-start,sdm_update_median_us=float(np.median(times)*1e6),sdm_update_p95_us=float(np.percentile(times,95)*1e6),dict_update_median_us=float(np.median(direct_times)*1e6),sdm_arrays=c._sdm.nbytes,active_metadata_json_bytes=len(metadata),checkpoint_bytes=len(blob),checkpoint_sha256=hashlib.sha256(blob).hexdigest(),active_rows=len(c._rows),scope='32 IDs, 32 hard locations, D256; shared host dict necessary for verification; serialized metadata not actual Python object footprint; same-process fresh-object restarts, not host crash durability')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--steps',type=int,default=1000);p.add_argument('--out',required=True);a=p.parse_args()
    if not 1<=a.steps<=100000:raise ValueError('steps budget')
    result=run(a.steps);Path(a.out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result))
