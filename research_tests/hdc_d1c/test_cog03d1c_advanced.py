import sqlite3,itertools
import numpy as np
import pytest
from cognitum.research.hdc_associative import SparseDistributed
from cognitum.research.hdc_memory_advanced import PackedSDM,SignedHopfieldSketch,HRRTable,TableProposal

@pytest.mark.parametrize('d',[33,128,257])
@pytest.mark.parametrize('seed',[12,33,44])
def test_packed_sdm_parity(d,seed):
    r=np.random.default_rng(seed);a=r.choice([-1,1],(112,d)).astype(np.int8);keys=r.choice([-1,1],(20,d)).astype(np.int8);v=r.choice([-1,1],(20,31)).astype(np.int8)
    x=SparseDistributed(a,31,d//2);y=PackedSDM(a,31,d//2)
    for i in range(20):
        np.testing.assert_array_equal(x.active(keys[i]),y.active(keys[i]));assert x.write(keys[i],v[i])==y.write(keys[i],v[i])
    for i in range(0,20,2): x.write(keys[i],v[i],subtract=True);y.write(keys[i],v[i],subtract=True)
    for q in keys:
        u,n=x.raw(q);w,m=y.raw(q);np.testing.assert_array_equal(u,w);assert n==m
    assert y.nbytes<x.nbytes

@pytest.mark.parametrize('d',[2,7,32])
@pytest.mark.parametrize('seed',[1,7,19])
def test_signed_hopfield_dense_oracle(d,seed):
    a=SignedHopfieldSketch(d,seed,[0,2,5,7]);b=SignedHopfieldSketch(d,seed,[0,1,7,8]);full=np.zeros((d,d),np.int64)
    for i in [0,2,5,7]:
        v,s=a.atom(i);full+=s*np.outer(v,v)
    np.testing.assert_array_equal(a.dense(),full)
    assert a.intersection(b)==pytest.approx(np.sum(full*b.dense())/d**2)
    for i in range(10):
        v,s=a.atom(i);assert a.score(i)==pytest.approx(s*v@full@v/d**2)

def test_signed_intersection_expectation():
    # Enumerate coefficient signs, separate from PRNG, fixed correlated atoms.
    a=np.array([[1,1,-1],[1,-1,1],[1,1,1]])
    vals=[]
    for s in itertools.product([-1,1],repeat=3):
        x=sum(s[i]*np.outer(a[i],a[i]) for i in [0,1]);y=sum(s[i]*np.outer(a[i],a[i]) for i in [1,2]);vals.append(np.sum(x*y)/9)
    assert np.mean(vals)==1

def test_hopfield_limits():
    with pytest.raises(ValueError):SignedHopfieldSketch(8,1,[1,1])
    with pytest.raises(ValueError):SignedHopfieldSketch(8,1,[2**20])
    with pytest.raises(ValueError):SignedHopfieldSketch(8,1,[1]).intersection(SignedHopfieldSketch(8,2,[1]))

ROWS=[('x',1,None),('x',1,None),('x',-1,'a'),('y',1,'a'),('z',None,'a'),(None,1,'z'),('q',5,'')]
@pytest.mark.parametrize('p',[((0,'=','x'),),((0,'!=','x'),),((2,'IS NULL',None),),((1,'IS NOT NULL',None),),((0,'=','x'),(1,'!=',-1)),((1,'=',-1),),((0,'=','absent'),)])
def test_sql_semantics(p):
    t=HRRTable(ROWS,512,3,'current',1);proposal=t.propose(p)
    db=sqlite3.connect(':memory:');db.execute('create table t(a,b,c)');db.executemany('insert into t values(?,?,?)',ROWS)
    clauses=[];args=[]
    for j,op,v in p:
        clauses.append('abc'[j]+' '+op+(' ?' if op in ('=','!=') else ''))
        if op in ('=','!='):args.append(v)
    exact=tuple((i-1,(a,b)) for i,a,b in db.execute('select rowid,a,b from t where '+' and '.join(clauses)+' order by rowid',args))
    kw=dict(canonical_rows=ROWS,current_snapshot='current',current_revision=1)
    assert t.verify(proposal,p,[0,1],complete=True,**kw)==exact
    assert set(t.verify(proposal,p,[0,1],**kw))<=set(exact)

def test_stale_and_forged():
    t=HRRTable(ROWS,128,3,'a',1);p=((0,'=','x'),);q=t.propose(p)
    for rows,s,r in [(ROWS,'b',1),(ROWS,'a',2),(ROWS[:-1],'a',1)]:
        with pytest.raises(ValueError):t.verify(q,p,[0],canonical_rows=rows,current_snapshot=s,current_revision=r)
    for ids in [(100,),(-1,),(0,0),(1,0)]:
        with pytest.raises(ValueError):t.verify(TableProposal('a',1,t.digest,ids),p,[0],canonical_rows=ROWS,current_snapshot='a',current_revision=1)

def test_projection():
    t=HRRTable([('x',),('y',)],1024,41,'a',1)
    assert t.project_candidates(0,0,['x','y',None])=='x'
    assert t.project_candidates(1,0,['x','y',None])=='y'
