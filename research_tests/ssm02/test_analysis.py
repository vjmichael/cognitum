from fractions import Fraction as Q
import itertools
import json
import numpy as np
import pytest
from scipy.linalg import expm
from scipy.integrate import quad
from cognitum.research import ssm_linear as s, ssm_analysis as a


def model(A,B,C,D=None,domain='discrete'):
    D=D if D is not None else tuple((0,)*len(B[0]) for _ in C)
    return s.Model(A,B,C,D,('x',)*len(A),('u',)*len(B[0]),('y',)*len(C),domain)


@pytest.mark.parametrize('domain',['continuous','discrete'])
@pytest.mark.parametrize('case,r,o,st,de', [('full',2,2,True,True),('stable_hidden',1,1,True,True),('unstable_hidden',1,1,False,False),('unstable_observed',1,2,False,True),('unstable_reachable',2,1,True,False),('zero',0,0,False,False)])
def test_ranks_quotients(domain,case,r,o,st,de):
    stable=Q(-1) if domain=='continuous' else Q(1,2);unstable=Q(2);A=((stable,0),(0,stable if case=='stable_hidden' else unstable));B=((1,0),(0,1)) if r==2 else ((1,),(0,)) if r==1 else ((0,),(0,));C=((1,0),(0,1)) if o==2 else ((1,0),) if o==1 else ((0,0),)
    m=model(A,B,C,domain=domain);rank=a.ranks(m);assert (rank['reach_rank'],rank['observe_rank'])==(r,o);d=a.stabilizability(m);assert (d['stabilizable'],d['detectable'])==(st,de)
    assert a.pbh(m,stable)['reach_rank']<=2
    if case=='unstable_hidden':assert a.pbh(m,2)['reach_rank']==a.pbh(m,2)['observe_rank']==1


def test_pbh_complex():
    m=model(((0,-1),(1,0)),((1,),(0,)),((1,0),),domain='continuous');r=a.pbh(m,0,1);assert r['reach_rank']==r['observe_rank']==2
    m=model(m.a,((0,),(0,)),((0,0),),domain='continuous');r=a.pbh(m,0,1);assert r['reach_rank']==r['observe_rank']==1


def test_reach_reconstruct():
    m=model(((1,1),(0,1)),((0,),(1,)),((1,0),),((2,),));x=(Q(1),Q(2));target=(Q(5),Q(4));r=a.reachability(m,x,target,2);assert r['reachable'] and r['witness_within_input_bounds'];u=r['inputs'];end,y,_=s.scan(m,s.state(m,x),u);assert end.x==target;assert a.reconstruct(m,u,y)['initial']==x
    assert not a.reachability(m,x,target,1)['reachable'];r=a.reachability(m,x,(Q(100),Q(100)),2);assert r['reachable'] and not r['witness_within_input_bounds']
    u=((1,),(2,),(3,));_,y,_=s.scan(m,s.state(m,x),u);assert not a.reconstruct(m,u,y[:-1]+((y[-1][0]+1,),))['consistent'];assert not a.reconstruct(m,u[:1],y[:1])['unique']


@pytest.mark.parametrize('domain,A,expected',[('discrete',((Q(1,2),),),True),('discrete',((1,),),False),('discrete',((-1,),),False),('discrete',((2,),),False),('discrete',((Q(1,2),8),(0,Q(1,2))),True),('discrete',((0,-1),(1,0)),False),('continuous',((-2,),),True),('continuous',((0,),),False),('continuous',((2,),),False),('continuous',((-1,8),(0,-1)),True),('continuous',((0,-1),(1,0)),False)])
def test_stability(domain,A,expected):
    n=len(A);m=model(A,tuple((1,) for _ in A),(tuple(1 for _ in A),),domain=domain);r=a.stability(m);assert r['strictly_stable']==expected
    if expected:
        p=r['p'];z=a.lyapunov_certificate(m,p);assert a.replay_lyapunov(m,p,z);j=json.loads(z);assert j['strict_stability'] and not j['execution_authorized'];assert j['difference']==[[str(int(i==k)) for k in range(n)] for i in range(n)]
        with pytest.raises(ValueError):a.replay_lyapunov(m,p,z+b' ')
    else:
        with pytest.raises(ValueError):a.lyapunov_certificate(m,s.eye(n))


@pytest.mark.parametrize('domain',['discrete','continuous'])
def test_gramians(domain):
    v=Q(1,2) if domain=='discrete' else Q(-2);m=model(((v,0),(0,v)),((1,),(2,)),((1,3),),domain=domain);r=a.gramians(m);den=1-v*v if domain=='discrete' else -2*v;assert r['reach']==tuple(tuple(Q(x*y)/den for y in (1,2)) for x in (1,2));assert r['observe']==tuple(tuple(Q(x*y)/den for y in (1,3)) for x in (1,3));assert a.h2_squared(m)==49/den
    if domain=='discrete':
        f=a.gramians(m,3);factor=1+v*v+v**4;assert f['reach'][1][1]==4*factor
        assert a.h2_squared(model(m.a,m.b,m.c,((2,),)))==49/den+4
    else:
        with pytest.raises(ValueError):a.h2_squared(model(m.a,m.b,m.c,((2,),),domain))


@pytest.mark.parametrize('domain',['discrete','continuous'])
def test_nonnormal(domain):
    v=Q(1,2) if domain=='discrete' else Q(-1);m=model(((v,8),(0,v)),((0,),(1,)),((1,0),),domain=domain);r=a.spectrum(m,2);assert r['schur_residual']<1e-12 and max(r['sampled_gains'])>1 and not r['certified'];assert a.stability(m)['strictly_stable']
    A=np.array(m.a,float);B=np.array(m.b,float);w=a.gramians(m)['reach'];ref=np.zeros((2,2))
    if domain=='discrete':
        for k in range(100):
            x=np.linalg.matrix_power(A,k)@B;ref+=x@x.T
    else:
        for i,j in itertools.product(range(2),repeat=2):ref[i,j]=quad(lambda t: ((expm(A*t)@B)@(expm(A*t)@B).T)[i,j],0,40,epsabs=1e-10)[0]
    np.testing.assert_allclose(np.array(w,float),ref,atol=1e-9)


@pytest.mark.parametrize('domain',['continuous','discrete'])
def test_riccati_scalar(domain):
    m=model(((1,),),((1,),),((1,),),domain=domain);r=a.riccati(m,((1,),),((1,),));expected=1+np.sqrt(2) if domain=='continuous' else (1+np.sqrt(5))/2
    assert abs(r['p'][0,0]-expected)<1e-11 and r['closed_loop_strictly_stable'] and not r['optimality_certified'];assert r['scaled_residual']<1e-11
    p=r['closed_loop_p'];A=r['closed_loop_a'][0][0];assert p[0][0]>0 and (p[0][0]*(1-A*A) if domain=='discrete' else -2*A*p[0][0])==1


def test_riccati_coupled():
    m=model(((1,1),(0,1)),((0,),(1,)),((1,0),));r=a.riccati(m,((1,0),(0,1)),((1,),));A=np.array(m.a,float);B=np.array(m.b,float);x=np.zeros((2,2));R=np.eye(1)
    for _ in range(200):x=np.eye(2)+A.T@x@A-A.T@x@B@np.linalg.solve(R+B.T@x@B,B.T@x@A)
    np.testing.assert_allclose(r['p'],x,atol=1e-10)


def test_contraction_and_box():
    m=model(((Q(1,2),0),(0,Q(-1,2))),((1,),(2,)),((1,0),));r=a.contraction(m,s.eye(2),Q(1,2));assert r['slack']==((0,0),(0,0));boxes=a.reach_box(m,(-1,-2),(1,2),(((-1,),(1,)),)*3)['boxes']
    for x,u in itertools.product(itertools.product((-1,1),(-2,2)),itertools.product((-1,1),repeat=3)):
        x=tuple(Q(v) for v in x)
        for k,v in enumerate(u):
            x=s.va(s.mv(m.a,x),s.mv(m.b,(Q(v),)));lo,hi=boxes[k+1];assert all(l<=z<=h for l,z,h in zip(lo,x,hi))
    with pytest.raises(ValueError):a.contraction(m,s.eye(2),Q(1,4))
    m=model(((-2,0),(0,-1)),((1,),(1,)),((1,0),),domain='continuous');assert a.contraction(m,s.eye(2),1)['pivots']==(2,0)


def test_refusals():
    m=model(((2,),),((0,),),((0,),));calls=[lambda:a.gramians(m),lambda:a.reachability(m,(0,),(0,),0),lambda:a.reachability(m,(0,),(0,),True),lambda:a.riccati(m,((1,),),((1,),)),lambda:a.riccati(m,((-1,),),((1,),)),lambda:a.riccati(m,((1,),),((0,),)),lambda:a.lyapunov_certificate(m,((0,),)),lambda:a.lyapunov_certificate(m,((True,),)),lambda:a.lyapunov_certificate(m,((Q(1<<4096),),)),lambda:a.pbh(m,1.,0),lambda:a.reach_box(m,(1,),(0,),(((0,),(1,)),)),lambda:a.reconstruct(m,(),()),lambda:a.spectrum(m,65)]
    for call in calls:
        with pytest.raises(ValueError):call()


@pytest.mark.parametrize('n',[3,5,8])
def test_high_dimension_exact(n):
    A=tuple(tuple(Q(1,2) if i==j else Q(1) if j==i+1 else Q(0) for j in range(n)) for i in range(n));B=tuple((int(i==n-1),) for i in range(n));C=(tuple(int(j==0) for j in range(n)),);m=model(A,B,C)
    assert a.ranks(m)['reach_rank']==a.ranks(m)['observe_rank']==n
    p=a.stability(m)['p'];assert a.replay_lyapunov(m,p,a.lyapunov_certificate(m,p));assert a.gramians(m,n)['reach'][0][0]==1
    x=(Q(0),)*n;us=tuple((i%3-1,) for i in range(n));end,y,_=s.scan(m,s.state(m,x),us);assert a.reachability(m,x,end.x,n)['inputs']==us
    assert a.reconstruct(m,us,y)['initial']==x


@pytest.mark.parametrize('domain',['continuous','discrete'])
def test_noncoordinate_quotient(domain):
    v=-1 if domain=='continuous' else Q(1,2);m=model(((v,0),(0,2)),((1,),(0,)),((1,0),),domain=domain);new,_=a.f.similarity(m,((1,1),(1,2)),('z','z'));assert a.ranks(new)['reach_rank']==a.ranks(new)['observe_rank']==1
    z=a.stabilizability(new);assert not z['stabilizable'] and not z['detectable'] and z['unreachable_quotient']==z['dual_unobservable_quotient']==((2,),)


def test_continuous_mimo_riccati():
    from scipy.integrate import solve_ivp
    m=model(((0,1),(-1,0)),((1,0),(0,1)),((1,0),(0,1)),domain='continuous');cost=((2,1),(1,2));R=((2,0),(0,1));r=a.riccati(m,cost,R);A=np.array(m.a,float);B=np.array(m.b,float);q=np.array(cost,float);rr=np.array(R,float)
    def rhs(t,p):
        p=p.reshape(2,2);return (A.T@p+p@A-p@B@np.linalg.solve(rr,B.T@p)+q).ravel()
    ref=solve_ivp(rhs,(0,30),np.zeros(4),rtol=1e-11,atol=1e-12,method='DOP853').y[:,-1].reshape(2,2);np.testing.assert_allclose(r['p'],ref,atol=2e-10)
