from fractions import Fraction as Q
import numpy as np
import pytest
from scipy.integrate import solve_ivp
from scipy.signal import cont2discrete
from cognitum.research import ssm_linear as s, ssm_foundations as f


def model(a,b,c,d,domain='discrete'):
    return s.Model(a,b,c,d,('x',)*len(a),('u',)*len(b[0]),('y',)*len(c),domain)


@pytest.mark.parametrize('domain',['discrete','continuous'])
def test_similarity(domain):
    m=model(((1,2),(0,-1)),((1,0),(2,1)),((1,1),(0,1)),((0,1),(2,0)),domain)
    t=((1,1),(0,1));new,inv=f.similarity(m,t,('z','z'))
    assert inv==((1,-1),(0,1))
    for z in (3,4,Q(5,2)):assert s.transfer(m,z)==s.transfer(new,z)
    assert f.moments(m,5)==f.moments(new,5)
    if domain=='discrete':
        x=(Q(2),Q(3));u=((1,2),(-1,0),(2,-2));z=(Q(-1),Q(3))
        end,y,_=s.scan(m,s.state(m,x),u);newend,newy,_=s.scan(new,s.state(new,z),u)
        assert newy==y and end.x==(newend.x[0]+newend.x[1],newend.x[1])
    with pytest.raises(ValueError):f.similarity(m,((1,1),(1,1)),('z','z'))


@pytest.mark.parametrize('domain',['discrete','continuous'])
@pytest.mark.parametrize('case,rank', [('minimal',2),('unreachable',1),('unobservable',1),('zero',0),('mixed',2),('mimo',2)])
def test_minimal(domain,case,rank):
    args={
      'minimal':(((0,1),(-2,3)),((0,),(1,)),((1,0),),((0,),)),
      'unreachable':(((1,0),(0,2)),((1,),(0,)),((1,1),),((2,),)),
      'unobservable':(((1,0),(0,2)),((1,),(1,)),((1,0),),((2,),)),
      'zero':(((1,0),(0,2)),((0,),(1,)),((1,0),),((2,),)),
      'mixed':(((0,1,0),(-2,3,0),(0,0,4)),((0,),(1,),(0,)),((1,0,1),),((0,),)),
      'mimo':(((1,0,0),(0,2,0),(0,0,3)),((1,0),(0,1),(0,0)),((1,0,1),(0,1,1)),((1,0),(0,2)))
    }[case]
    m=model(*args,domain);r=f.minimal(m);assert r['rank']==rank and not r['execution_authorized']
    if rank==0:
        assert r['model'] is None and s.transfer(m,3)==m.d;return
    new=r['model'];assert len(new.a)==rank
    for z in (5,6,7,Q(9,2)):assert s.transfer(m,z)==s.transfer(new,z)
    if domain=='discrete':
        u=tuple(tuple((i+j)%3-1 for j in range(len(m.input_units))) for i in range(11))
        assert s.scan(m,s.state(m,(Q(0),)*len(m.a)),u)[1]==s.scan(new,s.state(new,(Q(0),)*rank),u)[1]
    if case in ('unreachable','unobservable'):
        with pytest.raises(ValueError):s.transfer(m,2)
        assert s.transfer(new,2)==((Q(3),),)


def test_varying_bilinear():
    a=model(((1,2),(0,1)),((1,),(0,)),((1,0),),((1,),));b=model(((1,0),(3,1)),((0,),(1,)),((1,0),),((1,),));x=(Q(1),Q(2));u=((1,),(2,));bias=((1,0),(0,1))
    r=f.varying((a,b),x,u,bias,(8,9));assert r['outputs']==((Q(2),),(Q(9),));assert r['final']==(Q(7),Q(26));assert r['next_index']==10
    t,g=r['transition'];assert s.va(s.mv(t,x),g)==r['final']
    r=f.bilinear(a,(((0,1),(0,0)),),x,u);assert r['outputs']==((Q(2),),(Q(10),));assert r['final']==(Q(18),Q(2))
    with pytest.raises(ValueError):f.varying((a,b),x,u,bias,(8,10))
    with pytest.raises(ValueError):f.bilinear(a,(),x,u)


@pytest.mark.parametrize('method,scipy_method',[('euler','euler'),('tustin','bilinear')])
def test_approximation(method,scipy_method):
    m=model(((-1,1),(0,-2)),((1,),(1,)),((1,2),),((1,),),'continuous');h=Q(1,4);r=f.approximate_discrete(m,h,method)
    ref=cont2discrete(tuple(np.array(v,float) for v in (m.a,m.b,m.c,m.d)),float(h),method=scipy_method)
    for a,b in zip((r.a,r.b,r.c,r.d),ref[:4]):np.testing.assert_allclose(np.array(a,float),b,atol=1e-14)
    assert all(type(v) is Q for a in (r.a,r.b,r.c,r.d) for row in a for v in row)
    if method=='tustin':
        with pytest.raises(ValueError):f.approximate_discrete(model(((2,),),((1,),),((1,),),((0,),),'continuous'),Q(1),'tustin')


@pytest.mark.parametrize('a,b',[(((0,1),(0,0)),((0,),(1,))),(((-2,1),(1,-3)),((1,0),(0,1))),(((0,1),(-1,0)),((1,),(0,)))])
def test_foh(a,b):
    n=len(a);m=len(b[0]);m0=model(a,b,((1,0),),((0,)*m,),'continuous');h=Q(1,2);r=f.foh(m0,h)
    x=np.array([.5,-.2]);u0=np.arange(m)+.3;u1=-np.arange(m)-.4;A=np.array(a,float);B=np.array(b,float)
    ref=solve_ivp(lambda t,x:A@x+B@(u0+(u1-u0)*t/float(h)),(0,float(h)),x,rtol=1e-12,atol=1e-14,method='DOP853').y[:,-1]
    np.testing.assert_allclose(r['a']@x+r['b0']@u0+r['b1']@u1,ref,atol=2e-12)
    z=s.discretize(m0,h);np.testing.assert_allclose(r['b0']+r['b1'],z['b'],atol=1e-14);assert not r['certified']


def test_descriptor():
    m=model(((-1,2),(3,-2)),((1,),(4,)),((2,1),),((1,),),'continuous');e=((2,0),(0,0));r=f.descriptor(m,1,e);q=r['model']
    assert q.a==((Q(1),),) and q.b==((Q(5,2),),) and q.c==((Q(7,2),),) and q.d==((Q(3),),)
    for x,u in [(Q(2),Q(1)),(Q(-1,3),Q(1,2)),(Q(0),Q(0))]:
        z=Q(3,2)*x+2*u
        assert f.consistent_state(m,1,e,(x,z),(u,))==(x,)
        assert 3*x-2*z+4*u==0
        assert 2*(q.a[0][0]*x+q.b[0][0]*u)==-x+2*z+u
        assert q.c[0][0]*x+q.d[0][0]*u==2*x+z+u
    for E in (((0,0),(0,0)),((1,1),(0,0)),((1,0),(0,1))):
        with pytest.raises(ValueError):f.descriptor(m,1,E)
    with pytest.raises(ValueError):f.consistent_state(m,1,e,(Q(0),Q(1)),(0,))
    with pytest.raises(ValueError):f.descriptor(model(((-1,2),(3,0)),((1,),(4,)),((2,1),),((1,),),'continuous'),1,e)
