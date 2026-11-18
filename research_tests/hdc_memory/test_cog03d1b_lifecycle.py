import dataclasses
import json
import numpy as np
import pytest
from cognitum.research.hdc_canonical import CanonicalRelation
from cognitum.research.hdc_associative_lifecycle import DerivedAssociations, relation_key


def rec(id='a',rev=1,role='owns',entity='ship',scope='alice',dead=False):
    return CanonicalRelation(id,rev,scope,role,entity,f'lu:{id}:{rev}',dead)


def cache(*,limit=32767,rows=None):
    a=np.stack([relation_key('owns','ship'),relation_key('owns','moon'),relation_key('visits','ship')])
    c=DerivedAssociations(a,0,'alice',limit=limit)
    c.install('s1',1,[rec()] if rows is None else rows)
    return c


def proposal(c,s='s1',r=1,role='owns',entity='ship'):
    return c.propose(relation_key(role,entity),snapshot=s,revision=r)


def verify(c,p,rows,s='s1',r=1,role='owns',entity='ship',scope='alice',canonical=None):
    return c.verify(p,relation_key('owns','ship'),role=role,entity=entity,authorized_scope=scope,
                    canonical_snapshot_id=canonical or s,current_snapshot_id=s,required_revision=r,canonical_records=rows)


def delta(c,*rows,s='s1',r=1):
    c.apply(snapshot=s,revision=r,next_snapshot=f's{r+1}',next_revision=r+1,changes=rows)


def checkpoint(c,s='s1',r=1):return c.checkpoint(snapshot=s,revision=r)


def test_actual_c08_exact_verified():
    c=cache();p=proposal(c);h=verify(c,p,[rec()]);assert h.source_id=='a' and h.citation_handle=='lu:a:1'


@pytest.mark.parametrize('records', [[],[rec(dead=True)],[rec(scope='bob')],[rec(entity='moon')], [dataclasses.replace(rec(),citation_handle='different')]])
def test_authoritative_mismatch_abstains(records):
    c=cache();assert verify(c,proposal(c),records) is None


@pytest.mark.parametrize('kwargs',[{'scope':'bob'},{'canonical':'other'},{'s':'s2','r':2}])
def test_stale_scope_refusal(kwargs):
    c=cache()
    with pytest.raises(ValueError):verify(c,proposal(c),[rec()],**kwargs)


def test_forgery_and_other_relation():
    c=cache();p=proposal(c)
    with pytest.raises(ValueError,match='forged'):verify(c,dataclasses.replace(p,score=p.score+.01),[rec()])
    assert verify(c,p,[rec()],entity='moon') is None


def test_replace_delete_and_rescope_rebuild():
    c=cache();p=proposal(c);delta(c,rec(rev=2,entity='moon'))
    assert proposal(c,'s2',2) is None
    q=proposal(c,'s2',2,entity='moon');assert q.source_revision==2
    with pytest.raises(ValueError):verify(c,p,[rec(rev=2,entity='moon')],s='s2',r=2)
    delta(c,rec(rev=3,entity='moon',scope='bob'),s='s2',r=2)
    assert proposal(c,'s3',3,entity='moon') is None
    delta(c,rec(rev=4),s='s3',r=3);assert proposal(c,'s4',4).source_revision==4
    delta(c,rec(rev=5,dead=True),s='s4',r=4);assert proposal(c,'s5',5) is None
    ref=cache(rows=[]);ref.invalidate();ref.install('s5',5,[rec(rev=5,dead=True)])
    assert checkpoint(ref,'s5',5)==checkpoint(c,'s5',5)


def test_overflow_transaction_rollback():
    c=cache(limit=1);before=checkpoint(c)
    with pytest.raises(OverflowError):delta(c,rec('a',2),rec('b',2))
    assert checkpoint(c)==before and proposal(c).source_revision==1


@pytest.mark.parametrize('kind',['duplicate','old','skip','snapshot'])
def test_invalid_delta_no_mutation(kind):
    c=cache();before=checkpoint(c); kw=dict(snapshot='s1',revision=1,next_snapshot='s2',next_revision=2,changes=[rec(rev=2)])
    if kind=='duplicate':kw['changes']*=2
    if kind=='old':kw['changes']=[rec()]
    if kind=='skip':kw['next_revision']=3
    if kind=='snapshot':kw['next_snapshot']='s1'
    with pytest.raises(ValueError):c.apply(**kw)
    assert checkpoint(c)==before


def test_restore_from_host_and_old_ticket_rejected():
    c=cache();p=proposal(c);blob=checkpoint(c);new=DerivedAssociations(c._sdm._addresses,0,'alice')
    new.restore(blob,snapshot='s1',revision=1,canonical_records=[rec()]);assert checkpoint(new)==blob
    assert proposal(new).source_id==p.source_id
    with pytest.raises(ValueError,match='forged'):verify(new,p,[rec()])


@pytest.mark.parametrize('kind',['changed','tampered','truncated','stale','scope'])
def test_restore_fails_closed(kind):
    c=cache();blob=checkpoint(c);rows=[rec()];s='s1';r=1;scope='alice'
    if kind=='changed':rows=[rec(entity='moon')]
    if kind=='tampered':doc=json.loads(blob);doc['counts']='0'*64;blob=json.dumps(doc).encode()
    if kind=='truncated':blob=blob[:-1]
    if kind=='stale':s='s2';r=2
    if kind=='scope':scope='bob'
    new=DerivedAssociations(c._sdm._addresses,0,scope)
    with pytest.raises(ValueError):new.restore(blob,snapshot=s,revision=r,canonical_records=rows)
    with pytest.raises(ValueError):proposal(new)


def test_invalidate_drops_and_replay_refused():
    c=cache();c.invalidate()
    with pytest.raises(ValueError):proposal(c)
    with pytest.raises(ValueError):c.install('s1',1,[rec()])
    c.install('s2',2,[rec(rev=2)]);assert proposal(c,'s2',2).source_revision==2


def test_current_host_newer_revision_cannot_verify_old_write():
    c=cache();delta(c)  # unrelated delta advances global snapshot
    p=proposal(c,'s2',2);assert p.source_revision==1
    assert verify(c,p,[rec(),rec(rev=2)],s='s2',r=2) is None


def test_replayed_canonical_and_future_fail():
    c=cache();p=proposal(c)
    for rows in [[rec(),rec()],[rec(rev=2)]]:
        with pytest.raises(ValueError):verify(c,p,rows)


def test_reentrant_revocation_during_verification_refuses():
    c=cache();p=proposal(c)
    def rows():
        yield rec()
        c.invalidate()
    with pytest.raises(ValueError):verify(c,p,rows())


def test_reentrant_mutation_cannot_overwrite_newer_state():
    c=cache()
    def changes():
        yield rec(rev=2)
        c.invalidate()
    with pytest.raises(ValueError,match='snapshot changed'):c.apply(snapshot='s1',revision=1,next_snapshot='s2',next_revision=2,changes=changes())
    with pytest.raises(ValueError):proposal(c)


def test_fresh_process_restart_and_interrupted_host_checkpoint(tmp_path):
    import os, subprocess, sys
    c=cache();path=tmp_path/'checkpoint';path.write_bytes(checkpoint(c))
    # Explicit test-only host checkpoint custody: a crash before replacement
    # must leave the last committed artifact unchanged. The engine has no I/O.
    fault="""import os,sys
from pathlib import Path
p=Path(sys.argv[1]); q=p.with_suffix('.tmp')
with q.open('wb') as f: f.write(b'partial next checkpoint'); f.flush(); os.fsync(f.fileno())
os._exit(13)
"""
    assert subprocess.run([sys.executable,'-c',fault,str(path)],timeout=30).returncode==13
    assert path.read_bytes()==checkpoint(c)
    restore="""import sys
from pathlib import Path
import numpy as np
from cognitum.research.hdc_associative_lifecycle import DerivedAssociations,relation_key
from cognitum.research.hdc_canonical import CanonicalRelation
addrs=np.stack([relation_key('owns','ship'),relation_key('owns','moon'),relation_key('visits','ship')])
row=CanonicalRelation('a',1,'alice','owns','ship','lu:a:1')
c=DerivedAssociations(addrs,0,'alice')
blob=Path(sys.argv[1]).read_bytes()
c.restore(blob,snapshot='s1',revision=1,canonical_records=[row])
assert c.checkpoint(snapshot='s1',revision=1)==blob
p=c.propose(relation_key('owns','ship'),snapshot='s1',revision=1)
assert c.verify(p,relation_key('owns','ship'),role='owns',entity='ship',authorized_scope='alice',canonical_snapshot_id='s1',current_snapshot_id='s1',required_revision=1,canonical_records=[row]).source_id=='a'
# With a newer canonical source, an old checkpoint cannot be restored.
new=DerivedAssociations(addrs,0,'alice'); updated=CanonicalRelation('a',2,'alice','owns','moon','lu:a:2')
try: new.restore(blob,snapshot='s2',revision=2,canonical_records=[updated])
except ValueError: pass
else: raise AssertionError('stale checkpoint accepted')
new.install('s2',2,[updated]); assert new.propose(relation_key('owns','ship'),snapshot='s2',revision=2) is None
"""
    subprocess.run([sys.executable,'-c',restore,str(path)],check=True,timeout=30,env=os.environ.copy())
