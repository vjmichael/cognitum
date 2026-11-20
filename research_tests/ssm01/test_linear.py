from fractions import Fraction as Q
import json, random
import pytest
import numpy as np
import mpmath as mp
from cognitum.research import ssm_linear as s

def model(a=((1,1),(0,1)),b=((0,),(1,)),c=((1,0),),d=((0,),),domain='discrete'):
    return s.Model(a,b,c,d,('x',)*len(a),('u',)*len(b[0]),('y',)*len(c),domain)

def aug_oracle(m,x,us):
    n=len(x); h=tuple(x)+(Q(1),); out=[]
    for u in us:
        out.append(tuple(sum((m.c[i][j]*h[j] for j in range(n)),Q(0))+sum((m.d[i][j]*u[j] for j in range(len(u))),Q(0)) for i in range(len(m.c))))
        F=[list(row)+[sum((v*w for v,w in zip(m.b[i],u)),Q(0))] for i,row in enumerate(m.a)]+[[Q(0)]*n+[Q(1)]]
        h=tuple(sum((v*w for v,w in zip(row,h)),Q(0)) for row in F)
    return h[:-1],tuple(out)

@pytest.mark.parametrize('n',[1,2,3,5,8])
def test_exact_coupled(n):
    rng=random.Random(20261120+n); q=lambda:Q(rng.randint(-3,3),4)
    m=model(tuple(tuple(q() for _ in range(n)) for _ in range(n)),tuple((q(),q()) for _ in range(n)),tuple(tuple(q() for _ in range(n)) for _ in range(2)),((Q(1,3),0),(0,Q(-1,2))))
    x=tuple(q() for _ in range(n));us=tuple((q(),q()) for _ in range(12));start=s.state(m,x,9)
    end,ys,raw=s.scan(m,start,us);assert (end.x,ys)==aug_oracle(m,x,us);assert end.index==21
    assert s.replay(m,start,us,raw);p,b=s.transition(m,us);assert tuple(sum((v*w for v,w in zip(row,x)),Q(0))+bias for row,bias in zip(p,b))==end.x
    for k in (1,5,11):
        mid,y1,_=s.scan(m,start,us[:k]);fin,y2,_=s.scan(m,mid,us[k:]);assert fin==end and y1+y2==ys
        assert s.compose(s.transition(m,us[:k]),s.transition(m,us[k:]))==(p,b)
    assert json.loads(raw)['execution_authorized'] is False
    with pytest.raises(ValueError):s.replay(m,start,us,raw+b' ')

def test_legacy_convention_and_impulse():
    m=model(a=((Q(1,2),0),(0,Q(1,4))),b=((1,),(2,)),c=((3,4),),d=((5,),));us=((1,),(0,),(0,),(0,));start=s.state(m,(Q(0),Q(0)))
    end,ys,_=s.scan(m,start,us);assert ys==tuple((h[0][0],) for h in s.markov(m,4));assert ys[0]==(Q(5),)
    post=model(m.a,m.b,((Q(3,2),1),),((16,),));assert s.scan(post,start=s.state(post,start.x),inputs=us)[1][0]==(Q(16),)
    assert s.scan(post,s.state(post,start.x),us)[1]==tuple((3*x+4*y+5*u[0],) for (x,y),u in zip([s.scan(m,start,us[:k])[0].x for k in range(1,5)],us))

def test_affine_noncommuting():
    a=(((Q(1),Q(2)),(Q(0),Q(1))),(Q(1),Q(0)));b=(((Q(1),Q(0)),(Q(3),Q(1))),(Q(0),Q(2)));c=(((Q(2),Q(0)),(Q(0),Q(2))),(Q(3),Q(4)))
    assert s.compose(a,b)!=s.compose(b,a);assert s.compose(s.compose(a,b),c)==s.compose(a,s.compose(b,c))
    assert s.compose(a,b)==(((Q(1),Q(2)),(Q(3),Q(7))),(Q(1),Q(5)))

@pytest.mark.parametrize('z',[2,3,Q(5,2)])
def test_transfer(z):
    m=model(a=((0,1),(-2,3)),b=((1,2),(3,4)),c=((2,1),(1,0)),d=((0,1),(2,0)))
    den=z*(z-3)+2
    if den==0:
        with pytest.raises(ValueError):s.transfer(m,z)
    else:
        # Explicit two-by-two adjugate, independent of elimination.
        expected=tuple(tuple(Q(m.d[i][j])+((m.c[i][0]*(z-3)-2*m.c[i][1])*m.b[0][j]+(m.c[i][0]+z*m.c[i][1])*m.b[1][j])/den for j in range(2)) for i in range(2))
        assert s.transfer(m,z)==expected

CASES=[('singular',((0,1),(0,0)),((0,),(1,)),Q(1,2)),('oscillator',((0,1),(-1,0)),((0,),(1,)),Q(1,2)),('coupled',((-2,1),(3,-4)),((1,2),(0,1)),Q(1,4)),('nonnormal',((-1,7),(0,-1)),((1,),(2,)),Q(1,4)),('scalar',((-2,),),((3,),),Q(1,3)),('unstable',((1,2),(0,1)),((1,),(0,)),Q(1,2))]
@pytest.mark.parametrize('name,a,b,h',CASES)
def test_zoh(name,a,b,h):
    m=model(a,b,tuple(tuple(int(i==j) for j in range(len(a))) for i in range(len(a))),tuple((0,)*len(b[0]) for _ in a),'continuous');r=s.discretize(m,h);n,k=len(a),len(b[0])
    with mp.workdps(70):
        block=mp.zeros(n+k)
        for i in range(n):
            for j,v in enumerate(m.a[i]+m.b[i]):block[i,j]=mp.mpf(v.numerator)/v.denominator*mp.mpf(h.numerator)/h.denominator
        ref=mp.expm(block);af=np.array([[float(ref[i,j]) for j in range(n)] for i in range(n)]);bf=np.array([[float(ref[i,n+j]) for j in range(k)] for i in range(n)])
    np.testing.assert_allclose(r['a'],af,rtol=2e-12,atol=2e-13);np.testing.assert_allclose(r['b'],bf,rtol=2e-12,atol=2e-13)
    half=s.discretize(m,h/2);np.testing.assert_allclose(half['a']@half['a'],r['a'],atol=2e-12);np.testing.assert_allclose(half['a']@half['b']+half['b'],r['b'],atol=2e-12)
    if name=='singular':np.testing.assert_array_equal(r['a'],[[1,.5],[0,1]]);np.testing.assert_array_equal(r['b'],[[.125],[.5]])
    assert not r['certified'] and not r['execution_authorized']

def test_refusals():
    m=model();start=s.state(m,(Q(0),Q(0)))
    for fn in [lambda:model(a=((True,0),(0,1))),lambda:model(a=((1.,0),(0,1))),lambda:model(a=((Q(1,1025),0),(0,1))),lambda:model(a=((1,0),(0,33))),lambda:model(a=((1,),(0,1))),lambda:s.state(m,(Q(1),Q(1)),True),lambda:s.state(m,(1,Q(0))),lambda:s.state(m,(Q(1<<4096),Q(0))),lambda:s.scan(m,start,()),lambda:s.scan(m,start,((1,),)*65),lambda:s.scan(m,start,((1,2),)),lambda:s.scan(m,s.State('wrong',0,start.x),((1,),)),lambda:s.scan(m,s.state(m,start.x,s.CLOCK),((1,),)),lambda:s.discretize(m,Q(1)),lambda:s.discretize(model(domain='continuous'),Q(0)),lambda:s.discretize(model(a=((32,0),(0,32)),domain='continuous'),Q(1)),lambda:s.transfer(m,1)]:
        with pytest.raises(ValueError):fn()
