"""Independent interval mathematics; no worker execution required."""
from dataclasses import replace, dataclass
from decimal import localcontext, ROUND_UP
from fractions import Fraction as F
from types import SimpleNamespace as NS
import math
import random
import struct
import pytest
from cognitum.mel import uncertainty as u, uncertainty_pb2 as pb

P=u.Interval.point
I=u.Interval


def series(q):
    term=total=F(1)
    for i in range(1,141):
        term=-term*q/i;total+=term
        if i==139: low=total
    return low,total


@pytest.mark.parametrize('q',[F(0),F(1,1024),F(1,8),F(1,2),F(1)])
def test_exp_oracle(q):
    b=u.exp_minus(q);lo,hi=series(q);assert b.lo<=lo<=hi<=b.hi


@pytest.mark.parametrize('q',[F(256),F(257),F(10**25)])
def test_tail_not_exact_zero(q):
    assert u.exp_minus(q)==I(F(0),F(1,2**256))


def test_context_isolation():
    expected=u.exp_minus(F(1,3))
    with localcontext() as c:
        c.prec=2;c.rounding=ROUND_UP
        assert u.exp_minus(F(1,3))==expected


@pytest.mark.parametrize('lo,hi,t,y,status,bit',[(1,1,1,1,'verified',1),(0,0,1,0,'verified',0),(0,1,1,1,'ambiguous',None),(1,2,1,0,'contradicted',None),(0,1,2,3,'contradicted',None),(-1,1,0,0,'ambiguous',None)])
def test_threshold(lo,hi,t,y,status,bit):
    assert u.threshold_bit(I(F(lo),F(hi)),t,y)==(status,bit)


@pytest.mark.parametrize('lo,hi,y,t,status',[(1,1,2,1,'within'),(1,1,2,.5,'outside'),(1,2,1,.5,'inconclusive'),(1,2,1,1,'within'),(1,2,4,1,'outside')])
def test_error(lo,hi,y,t,status):
    assert u.error_verdict(I(F(lo),F(hi)),y,t)==status


def layer(**kw):
    base=dict(inputs=1,outputs=1,knots=3,basis=2,degree=0,grid=[-1.,0.,1.],coefficients=[0.,1.,0.],mask=[1.],base=[],bias=[])
    return NS(**(base|kw))


@pytest.mark.parametrize('x',[0.,.125,.5,1.,-1.])
def test_kan_rbf_rational_oracle(x):
    b=u.kan_bounds([layer()],((P(x),),))[0][0];lo,hi=series(F(x)**2)
    assert b.lo<=lo<=hi<=b.hi


@pytest.mark.parametrize('x,expected',[(-1.,0.),(-.5,.5),(0.,1.),(.5,.5)])
def test_degree_one_spline_exact(x,expected):
    b=u.kan_bounds([layer(basis=1,degree=1,coefficients=[1.])],((P(x),),))[0][0]
    assert b==P(expected)


def test_endpoint_float32_predecessor():
    b=u.kan_bounds([layer(basis=1,degree=1,coefficients=[1.])],((P(1.),),))[0][0]
    assert b==P(F(1,2**24))


def test_discontinuous_degree_zero_crosses_knot():
    b=u.kan_bounds([layer(basis=1,degree=0,coefficients=[-2.,3.])],((I(F(-1,4),F(1,4)),),))[0][0]
    assert b==I(F(-2),F(3));assert u.threshold_bit(b,0,3)==('ambiguous',None)


def test_masks_bias_and_silu():
    m=layer(mask=[0.],base=[1000.],bias=[-2.])
    assert u.kan_bounds([m],((P(.5),),))[0][0]==P(-2)
    m=layer(coefficients=[0.,0.,0.],base=[2.],bias=[1.])
    b=u.kan_bounds([m],((P(.5),),))[0][0]
    lo,hi=series(F(1,2));assert b.lo<=1+1/(1+hi)<=1+1/(1+lo)<=b.hi


def test_two_layers_and_uncertain_domain():
    l1=layer(coefficients=[0.,.5,0.]); l2=layer()
    b=u.kan_bounds([l1,l2],((P(0),),))[0][0]
    lo,hi=series(F(1,4));assert b.lo<=lo<=hi<=b.hi
    with pytest.raises(ValueError,match='knot domain'):
        u.kan_bounds([layer(coefficients=[0.,2.,0.]),l2],((P(0),),))


def test_vfa_propagation_and_negative_weights():
    f=NS(shape=[1,1],function=NS(centers=[0.],widths=[1.],weights=[-2.],constant=1.),domain=[NS(lower=-2.,upper=2.)])
    b=u.vfa_bounds(f,((I(F(0),F(1)),),))[0][0]
    lo,hi=series(F(1,2));assert b.lo<=-1 and b.hi>=1-2*lo
    assert u.threshold_bit(b,-.5,-.75)==('ambiguous',None)
    with pytest.raises(ValueError):u.vfa_bounds(f,((I(F(0),F(3)),),))


def test_constant_vfa():
    f=NS(shape=[0,1],function=NS(centers=[],widths=[],weights=[],constant=1.),domain=[NS(lower=-2.,upper=2.)])
    assert u.vfa_bounds(f,((P(0),),))==((P(1),),)


@pytest.mark.parametrize('lo,hi',[(2,1),(float('nan'),1),(True,1)])
def test_bad_rational_bounds(lo,hi):
    with pytest.raises(ValueError):I(u.rational(lo),u.rational(hi))


@pytest.mark.parametrize('change',[{'grid':[0.,0.,1.]},{'coefficients':[0.,1.]},{'mask':[.5]},{'degree':1},{'grid':[-1.,0.,0.1]},{'inputs':9},{'bias':[float('inf')]}])
def test_bad_kan_parameters(change):
    with pytest.raises(ValueError):u.kan_bounds([layer(**change)],((P(0),),))


def test_fraction_budget():
    with pytest.raises(ValueError,match='budget'):P(F(1,2**9000))


def test_typed_witness_determinism():
    from cognitum.mel.verified_graph import _interval
    b=I(F(-1,3),F(2,7));m=pb.GraphWitness(schema_version=1,plan_sha256=b'x'*32,represented_inputs_only=True)
    m.nodes.add(node_id='test').samples.add(local=_interval(b),propagated=_interval(b),unit='1')
    raw=m.SerializeToString(deterministic=True);again=pb.GraphWitness.FromString(raw)
    assert again.nodes[0].samples[0].local.lower.numerator=='-1'
    assert again.SerializeToString(deterministic=True)==raw


def test_random_interval_spline_contains_sampled_exact_values():
    ran=random.Random(417); grid=tuple(map(F,(-3,-2,-1,0,1,2,3)))
    for degree in (0,1,2,3):
        for _ in range(15):
            lo,hi=sorted([F(ran.randint(-12,12),4) for _ in range(2)])
            bounds=u.spline(I(lo,hi),grid,degree)
            for j in range(5):
                sample=u.spline(P(lo+(hi-lo)*j/4),grid,degree)
                assert all(b.lo<=s.lo<=s.hi<=b.hi for b,s in zip(bounds,sample))
