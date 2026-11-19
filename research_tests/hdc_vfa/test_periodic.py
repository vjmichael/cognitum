import numpy as np
import pytest
from scipy.integrate import quad
from cognitum.research.vfa_periodic import Periodic, MAX_MODE

X = np.linspace(-5, 7, 137)
F = Periodic([2,.6-.2j, -.3j])
G = Periodic([3,.2+.4j])

@pytest.mark.parametrize('op', ['add','sub','mul','conv','shift','derivative','integral','primitive','parseval','truncate','negative_winding','positive_winding','zero_winding'])
def test_oracles(op):
    f=lambda x: 2+1.2*np.cos(x)+.4*np.sin(x)+.6*np.sin(2*x)
    g=lambda x: 3+.4*np.cos(x)-.8*np.sin(x)
    if op=='add': actual, expected=(F+G).evaluate(X), f(X)+g(X)
    elif op=='sub': actual, expected=(F-G).evaluate(X), f(X)-g(X)
    elif op=='mul': actual, expected=F.multiply(G).evaluate(X), f(X)*g(X)
    elif op=='conv': actual, expected=F.convolve(G).evaluate(X), [quad(lambda y:f(x-y)*g(y),0,2*np.pi)[0]/(2*np.pi) for x in X]
    elif op=='shift': actual, expected=F.shift(.7).evaluate(X), f(X-.7)
    elif op=='derivative': actual, expected=F.derivative().evaluate(X), -1.2*np.sin(X)+.4*np.cos(X)+1.2*np.cos(2*X)
    elif op=='integral': actual, expected=F.integral(-2,4), quad(f,-2,4)[0]
    elif op=='primitive': actual, expected=(F-Periodic.constant(2)).antiderivative().derivative().evaluate(X), f(X)-2
    elif op=='parseval': actual, expected=F.parseval_energy(), quad(lambda y:f(y)**2,0,2*np.pi)[0]/(2*np.pi)
    elif op=='truncate':
        short, bound=F.truncate(1); assert np.max(np.abs(short.evaluate(X)-f(X)))<=bound+1e-12
        actual, expected=bound,.6
    elif op=='negative_winding': actual, expected=F.compose_affine(-3,.2).evaluate(X), f(-3*X+.2)
    elif op=='positive_winding': actual, expected=F.compose_affine(2,-.3).evaluate(X), f(2*X-.3)
    else: actual, expected=F.compose_affine(0,.2).evaluate(X), f(.2)*np.ones_like(X)
    np.testing.assert_allclose(actual,expected,atol=2e-12,rtol=2e-12)

@pytest.mark.parametrize('order',[1,4,12,24])
def test_quotient(order):
    q=F.divide(G,order=order,grid=256,max_error=2)
    error=np.max(np.abs(q.function.evaluate(X)-F.evaluate(X)/G.evaluate(X)))
    assert error<=q.error_bound_estimate+1e-13
    assert q.denominator_lower_bound>0
    if order==24: assert q.error_bound_estimate<1e-12

@pytest.mark.parametrize('bad',[Periodic([0,.5]),Periodic([1,.5]),Periodic([1e-320])])
def test_division_refuses(bad):
    with pytest.raises(ValueError): F.divide(bad,order=8,grid=64,max_error=.01)

def test_nonclosure_and_alias():
    cos=Periodic([0,0,.5]); result=cos.multiply(cos)
    assert result.order==4
    np.testing.assert_allclose(result.evaluate(X),np.cos(2*X)**2,atol=1e-14)
    assert not np.allclose(result.evaluate(X),cos.convolve(cos).evaluate(X))
    with pytest.raises(ValueError): Periodic([0]*(MAX_MODE+1)).multiply(cos)
    with pytest.raises(ValueError): Periodic.from_grid(np.zeros(4),2)

def test_invariants():
    rng=np.random.default_rng(17)
    for _ in range(20):
        c=rng.normal(size=5)+1j*rng.normal(size=5); c[0]=c[0].real
        h=Periodic(c)
        np.testing.assert_allclose(F.multiply(G+h).evaluate(X),(F.multiply(G)+F.multiply(h)).evaluate(X),atol=3e-13)
        np.testing.assert_allclose(F.multiply(G).derivative().evaluate(X),(F.derivative().multiply(G)+F.multiply(G.derivative())).evaluate(X),atol=3e-13)
        np.testing.assert_allclose(F.convolve(h).positive,h.convolve(F).positive,atol=1e-14)
        np.testing.assert_allclose(h.shift(.2).shift(-.2).positive,h.positive,atol=1e-14)

def test_fft_exact_supported_polynomial():
    x=2*np.pi*np.arange(51)/51
    p=Periodic.from_grid(F.evaluate(x), F.order)
    np.testing.assert_allclose(p.positive,F.positive,atol=1e-14)

def test_refusals():
    for fn in [lambda: F.antiderivative(),lambda: F.divide(G,order=1,grid=64,max_error=1e-10),lambda: F.divide(G,order=3,grid=5,max_error=1),lambda:F.compose_affine(.5),lambda: F.evaluate(np.inf),lambda: Periodic([1j]),lambda: Periodic([0,np.nan]),lambda: F.derivative(-1),lambda:F.scale(np.inf),lambda:F.evaluate(1j),lambda:F.evaluate(np.zeros(65537))]:
        with pytest.raises(ValueError): fn()

def test_snapshots():
    p=np.array([1,.5]); f=Periodic(p);p[:]=3
    assert f.positive[1]==.5
    with pytest.raises(ValueError): f.positive.setflags(write=True)
    a=f.full;a[:]=0
    assert f.positive[1]==.5
