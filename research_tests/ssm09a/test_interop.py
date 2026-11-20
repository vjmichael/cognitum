import json
import numpy as np
import pytest
from cognitum.research import ssm_interop as s


def model():return s.model([[.8,.1],[0,.6]],[[1],[.4]],[[1,0]],.1,['m','m'],['N'],['m'],'a'*64)


@pytest.mark.parametrize('seed',[1,8,81])
def test_stream(seed):
    m=model();x=s.state(m,[.1,.2]);u=np.random.default_rng(seed).normal(size=(32,1));a=s.advance(m,x,u,s.digest(x),0);z=s.read(a['trajectory']);assert z['first_step']==1
    for cut in range(1,32):
        b=s.advance(m,x,u[:cut],s.digest(x),0);c=s.advance(m,b['state'],u[cut:],s.digest(b['state']),cut);assert c['state']==a['state'];np.testing.assert_array_equal(s.read(b['trajectory'])['outputs']+s.read(c['trajectory'])['outputs'],z['outputs'])
    assert s.advance(m,x,u,s.digest(x),0)['state']==a['state']


@pytest.mark.parametrize('wrong',['hash','step','model','noncanonical','schema'])
def test_refusal(wrong):
    m=model();x=s.state(m,[.1,.2]);h=s.digest(x);t=0
    if wrong=='hash':h='b'*64
    if wrong=='step':t=1
    if wrong=='model':m=s.model([[1]],[[1]],[[1]],.1,['m'],['N'],['m'],'b'*64)
    if wrong=='noncanonical':x=b' '+x
    if wrong=='schema':z=s.read(x);z['execution_authorized']=True;x=s.wire(z)
    with pytest.raises(ValueError):s.advance(m,x,[[1]],h,t)


def test_belief_control():
    m=model();x=s.state(m,[.2,.4],10);b=s.read(s.belief(m,x,[[1,.1],[.1,2]]));u=s.read(s.control_proposal(m,x,[[1],[2]]));assert b['state_sha256']==u['state_sha256']==s.digest(x);assert u['first_step']==10 and not u['execution_authorized'] and not b['execution_authorized']
    with pytest.raises(ValueError):s.belief(m,x,[[1,2],[2,1]])


@pytest.mark.parametrize('seed',[2,32,91])
def test_hdc(seed):
    m=model();rng=np.random.default_rng(seed);q=rng.choice([-1,1],64);records=[(s.state(m,[i/10,0],i),rng.choice([-1,1],64),'regime-'+str(i)) for i in range(10)];records.append((s.state(m,[1,0],10),q.copy(),'future'));z=s.regime_retrieve(m,records,q,9,5);r=sorted([(sum(int(a==b) for a,b in zip(q,v))*2-len(q),s.digest(x)) for x,v,_ in records[:-1]],key=lambda v:(-v[0],v[1]))[:5];assert [(a['dot'],a['state_sha256']) for a in z['candidates']]==r;assert z['candidate_only'] and all(a['step']<=9 for a in z['candidates'])


def test_hdc_tie():
    m=model();q=[1]*16;r=[(s.state(m,[0,0],2),q,'b'),(s.state(m,[0,0],1),q,'a')];a=s.regime_retrieve(m,r,q,2);assert a==s.regime_retrieve(m,r[::-1],q,2)
    with pytest.raises(ValueError):s.regime_retrieve(m,r+r,q,2)


@pytest.mark.parametrize('kind',s.KINDS)
def test_evidence(kind):
    z=s.read(s.evidence(kind,'a'*64,['domain-bounded'],'b'*64,'test metric'));assert z['classification']==kind and not z['verified'] and not z['execution_authorized']


def test_evidence_refuse():
    with pytest.raises(ValueError):s.evidence('certain','a'*64,['domain'],'b'*64,'metric')
