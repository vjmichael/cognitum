from fractions import Fraction as F
import math
import numpy as np
import pytest
from cognitum.research.vfa_periodic import Periodic
from cognitum.mel import admission as a, spectral_verification as s, native as n

S=a.Scope('spec','workspace','subject','turn')

@pytest.mark.parametrize('order',[0,1,2])
def test_truncation_exact_tail(order):
    p=Periodic([1.,.25+.125j,.125j]);q,estimate=p.truncate(order)
    r=s.certify(S,'truncation',p,q,(2.,2.))
    assert r.error_upper==tuple(2*sum((F(abs(z.real))+F(abs(z.imag)))*k**d for k,z in enumerate(p.positive) if k>order) for d in (0,1))
    assert s.replay(S,'truncation',p,q,r,(2.,2.))=='within'
    if order<2:assert s.certify(S,'truncation',p,q,(0.,0.)).message().verdict=='inconclusive'

@pytest.mark.parametrize('seed',[1,4,9,18])
def test_full_product_roundoff(seed):
    rng=np.random.default_rng(seed);p=Periodic([.5,*list(rng.normal(size=4)+1j*rng.normal(size=4))]);q=Periodic([.75,*list(rng.normal(size=4)+1j*rng.normal(size=4))]);z=p.multiply(q)
    r=s.certify(S,'product',p,z,(1e-12,1e-12),right=q)
    assert r.message().verdict=='within'
    # Deliberately dropping a nonzero generated mode cannot pass zero tolerance.
    bad,_=z.truncate(3);assert s.certify(S,'product',p,bad,(0.,0.),right=q).message().verdict=='inconclusive'

@pytest.mark.parametrize('den',[2.,-2.])
def test_exact_quotient(den):
    p=Periodic([1.,.125]);g=Periodic.constant(den);q=p.scale(1/den)
    r=s.certify(S,'quotient',p,q,(0.,0.),right=g,minimum_separation=1.)
    assert r.error_upper==(0,0) and r.message().verdict=='within'
    assert s.replay(S,'quotient',p,q,r,(0.,0.),right=g,minimum_separation=1.)=='within'


def test_actual_fft_quotient_global_value_and_derivative():
    f=Periodic([1.,.25]);g=Periodic([2.,.1+.05j]);q=f.divide(g,order=12,grid=1024,max_error=1e-10).function
    r=s.certify(S,'quotient',f,q,(1e-10,1e-9),right=g,minimum_separation=1.)
    assert r.message().verdict=='within'
    x=np.linspace(0,2*np.pi,503,endpoint=False);v=f.evaluate(x)/g.evaluate(x);d=(f.derivative().evaluate(x)*g.evaluate(x)-f.evaluate(x)*g.derivative().evaluate(x))/g.evaluate(x)**2
    assert np.max(np.abs(v-q.evaluate(x)))<=float(r.error_upper[0])+3e-15
    assert np.max(np.abs(d-q.derivative().evaluate(x)))<=float(r.error_upper[1])+3e-15

@pytest.mark.parametrize('g,sep',[(Periodic([0.,1.]),.1),(Periodic([1.,.5]),.1),(Periodic([1.,.49999999999999994]),1e-20),(Periodic.constant(2.),3.)],ids=['zero','crossing','ill-conditioned','policy'])
def test_denominator_refusal(g,sep):
    with pytest.raises(ValueError):s.certify(S,'quotient',Periodic.constant(1),Periodic.constant(1),(1.,1.),right=g,minimum_separation=sep)

@pytest.mark.parametrize('case',['forged','scope','left','right','target','tolerance','separation','unknown'])
def test_replay_binding(case):
    p=Periodic([1.,.25]);g=Periodic.constant(2.);q=p.scale(.5);t=(.01,.01);sc=S;sep=1.;r=s.certify(sc,'quotient',p,q,t,right=g,minimum_separation=sep)
    if case=='scope':sc=a.Scope('other','workspace','subject','turn')
    elif case=='left':p=Periodic([2.,.25])
    elif case=='right':g=Periodic.constant(3.)
    elif case=='target':q=Periodic.constant(.5)
    elif case=='tolerance':t=(.02,.01)
    elif case=='separation':sep=.5
    elif case=='forged':
        m=r.message();m.denominator_lower.numerator='5';r=s.Certificate(n.serialize(m))
    elif case=='unknown':
        with pytest.raises(ValueError):s.Certificate(r.wire+b'\xa0\x06\x01')
        return
    with pytest.raises(ValueError):s.replay(sc,'quotient',p,q,r,t,right=g,minimum_separation=sep)


def test_truncation_corrupted_prefix_refused():
    with pytest.raises(ValueError):s.certify(S,'truncation',Periodic([1.,.25]),Periodic.constant(2),(5.,5.))


def test_mode_budget_refuses():
    with pytest.raises(ValueError):s.certify(S,'truncation',Periodic([1.]+[.1]*33),Periodic.constant(1),(1.,1.))


def test_cancel_during_convolution():
    count=0
    def stop():
        nonlocal count;count+=1
        if count>=4:raise TimeoutError('cancel')
    p=Periodic([1.,.25,.5,.125])
    with pytest.raises(TimeoutError):s.certify(S,'product',p,p.multiply(p),(1.,1.),right=p,check=stop)
