"""Independent functional, training, and existing MEL interoperability controls."""
import hashlib
import json
import numpy as np
import pytest
from scipy.interpolate import BSpline
from scipy.integrate import quad
from cognitum.research.kan_trainable import Layer, Network, load_candidate, load_snapshot
from cognitum.research.kan_portable import PortableKAN


def layer(kind='rbf',degree=0,i=1,o=1,seed=3,scale=.1):
    knots = (np.r_[np.repeat(-1.,degree+1),[-.5,0.,.5],np.repeat(1.,degree+1)] if kind=='spline_clamped'
             else np.linspace(-1,1,2 if kind=='chebyshev' else 9))
    grid=np.tile(knots,(i,1))
    k=degree+1 if kind=='chebyshev' else 9 if kind=='rbf' else len(knots)-degree-1
    rng=np.random.default_rng(seed)
    return Layer(kind,degree,grid,rng.normal(0,scale,(o,i,k)),np.ones((o,i)),np.zeros(o))


@pytest.mark.parametrize('degree',range(4))
@pytest.mark.parametrize('order',range(3))
def test_spline_against_independent_scipy(degree,order):
    l=layer('spline',degree);g=l.grid[0];xs=np.linspace(-.983,.973,117)
    b=l.basis(xs[:,None],order)[order][:,0,:]
    for j in range(b.shape[1]):
        q=BSpline.basis_element(g[j:j+degree+2],extrapolate=False)
        outside=(xs<g[j])|(xs>g[j+degree+1]);oracle=np.zeros(len(xs))
        if order<=degree:oracle[~outside]=q(xs[~outside],nu=order)
        assert np.allclose(b[:,j],oracle,atol=1e-11,rtol=1e-11)


@pytest.mark.parametrize('kind,degree',[('rbf',0),('chebyshev',4),('spline',3),('spline_clamped',3)])
def test_multilayer_jacobian_hessian(kind,degree):
    model=Network((layer(kind,degree,2,3),layer(kind,degree,3,2,4)))
    x=np.array([[.23,-.17],[.31,.12]])
    y,j,h=model.evaluate(x,2);eps=1e-5
    for q in range(2):
        step=np.eye(2)[q]*eps
        yp,jp=model.evaluate(x+step,1);ym,jm=model.evaluate(x-step,1)
        assert np.allclose(j[:,:,q],(yp-ym)/(2*eps),atol=2e-7)
        assert np.allclose(h[:,:,:,q],(jp-jm)/(2*eps),atol=3e-6)
    assert np.allclose(h,h.swapaxes(-1,-2))


@pytest.mark.parametrize('kind,degree',[('rbf',0),('chebyshev',8),('spline',0),('spline',1),('spline',3),('spline_clamped',3)])
def test_integral_against_quad(kind,degree):
    l=layer(kind,degree,2,2);lo=np.array([-.83,-.92]);hi=np.array([.78,.61]);out=l.edge_integrals(lo,hi)
    for o in range(2):
        for i in range(2):
            def f(t):
                x=np.zeros((1,2));x[0,i]=t
                return float(l.basis(x)[0][0,i]@l.coefficients[o,i])
            want=quad(f,lo[i],hi[i],points=[x for x in l.grid[i] if lo[i]<x<hi[i]],epsabs=1e-11)[0]
            assert abs(want-out[o,i])<1e-10


@pytest.mark.parametrize('kind,degree',[('rbf',0),('chebyshev',3),('spline',3),('spline_clamped',3)])
def test_training_gradient(kind,degree):
    l=layer(kind,degree,2,2);m=Network((l,layer(kind,degree,2,1,4)));x=np.array([[.21,-.17],[-.37,.12]]);y=np.array([[.2],[-.1]])
    loss,gradient=m.loss_gradient(x,y,.001)
    for i,old in enumerate(m.layers):
        for coord in [(0,0,0),(0,0,1)]:
            delta=np.zeros_like(old.coefficients);delta[coord]=1e-6
            a=list(m.layers);b=list(m.layers);a[i]=old.updated(old.coefficients+delta,old.bias);b[i]=old.updated(old.coefficients-delta,old.bias)
            diff=(Network(tuple(a)).loss_gradient(x,y,.001)[0]-Network(tuple(b)).loss_gradient(x,y,.001)[0])/2e-6
            assert np.isclose(gradient[i][0][coord],diff,atol=1e-8,rtol=1e-6)
        dx=np.zeros_like(old.bias);dx[0]=1e-6;a=list(m.layers);b=list(m.layers);a[i]=old.updated(old.coefficients,old.bias+dx);b[i]=old.updated(old.coefficients,old.bias-dx)
        assert np.isclose(gradient[i][1][0],(Network(tuple(a)).loss_gradient(x,y,.001)[0]-Network(tuple(b)).loss_gradient(x,y,.001)[0])/2e-6,atol=1e-8)


@pytest.mark.parametrize('kind,degree',[('rbf',0),('chebyshev',5),('spline_clamped',3)])
def test_fit_disjoint_holdout(kind,degree):
    m=Network((layer(kind,degree),));x=np.linspace(-.73,.73,81)[:,None];h=(x[:-1]+x[1:])/2
    f=lambda t: .4*np.sin(2*t)+.1*t*t
    fitted=m.fit_linear(x,f(x),ridge=1e-8)
    assert np.sqrt(np.mean((fitted.evaluate(h)[0]-f(h))**2))<.006
    assert set(x[:,0]).isdisjoint(h[:,0])


@pytest.mark.parametrize('kind,degree',[('rbf',0),('chebyshev',3),('spline',3),('spline_clamped',3)])
def test_nonlinear_training_really_updates_both_layers(kind,degree):
    m=Network((layer(kind,degree,1,2),layer(kind,degree,2,1,4)));x=np.linspace(-.7,.7,61)[:,None];h=(x[:-1]+x[1:])/2;f=lambda q:.2*q+.1*q*q
    fitted,history=m.fit(x,f(x),steps=300,rate=.35,ridge=1e-5)
    assert history[-1]<history[0]*.2 and np.all(np.diff(history)<0)
    assert np.sqrt(np.mean((fitted.evaluate(h)[0]-f(h))**2))<.05
    assert all(not np.array_equal(a.coefficients,b.coefficients) for a,b in zip(m.layers,fitted.layers))


@pytest.mark.parametrize('kind,degree',[('rbf',0),('spline',3),('spline',0)])
@pytest.mark.parametrize('depth',[1,2])
def test_checkpoint_portable_parity(kind,degree,depth):
    m=Network(tuple(layer(kind,degree,1,1,j) for j in range(depth)));raw,d=m.checkpoint_candidate();loaded=load_candidate(raw,d)
    # Compare represented binary32 params, not unquantized parameters.
    ls=[dict(kind=z.kind,degree=z.degree,grid=z.grid.astype('f'),spline=z.coefficients.astype('f'),mask=z.mask.astype('f'),bias=z.bias.astype('f'),base=None) for z in loaded.layers]
    x=np.linspace(-.95,.95,31,dtype=np.float32)[:,None]
    assert np.max(np.abs(loaded.evaluate(x)[0]-PortableKAN(ls)(x)))<2e-6
    assert loaded.checkpoint_candidate()==(raw,d)
    with pytest.raises(ValueError):load_candidate(raw+b'\x00',d)


@pytest.mark.parametrize('kind,degree',[('rbf',0),('spline',3),('chebyshev',8),('spline_clamped',3)])
def test_research_snapshot(kind,degree):
    m=Network((layer(kind,degree),));raw,d=m.research_snapshot();loaded=load_snapshot(raw,d)
    assert loaded.research_snapshot()==(raw,d)
    assert np.array_equal(loaded.evaluate([[.4]])[0],m.evaluate([[.4]])[0])
    with pytest.raises(ValueError):load_snapshot(raw+b' ',hashlib.sha256(raw+b' ').hexdigest())
    with pytest.raises(ValueError):load_snapshot(raw,'0'*64)
    if kind in ('chebyshev','spline_clamped'):
        with pytest.raises(ValueError):m.checkpoint_candidate()


def test_mask_and_immutable_arrays():
    l=layer('rbf',0,2,1);l=Layer(l.kind,l.degree,l.grid,l.coefficients,[[0,1]],l.bias)
    assert not l.coefficients.flags.writeable
    with pytest.raises(ValueError):l.coefficients.setflags(write=True)
    m=Network((l,));y,j=m.evaluate([[.4,.2]],1);assert j[0,0,0]==0
    _,g=m.loss_gradient([[.4,.2]],[[1.]])
    assert np.all(g[0][0][0,0]==0)
    f=m.fit_linear([[.1,.2],[.3,.5]],[[0.],[1.]])
    assert np.all(f.layers[0].coefficients[0,0]==0)


@pytest.mark.parametrize('x',[[[2.]],[[float('nan')]],[[True]],[[.2,.3]],np.zeros((2049,1)),np.zeros((1,2048))])
def test_controls_input(x):
    with pytest.raises(ValueError):Network((layer(),)).evaluate(x)


def test_controls_nonsmooth_and_intermediate_domain():
    for d in (0,1,2):
        with pytest.raises(ValueError):Network((layer('spline',d),)).evaluate([[0.]],min(2,max(d,1)))
    l=layer();first=l.updated(np.zeros_like(l.coefficients),[2.])
    with pytest.raises(ValueError):Network((first,layer())).evaluate([[.2]])
    assert layer('spline',0).basis([[1.]])[0][0,0,-1]==1
    with pytest.raises(ValueError):Network((layer('spline',3),)).evaluate([[1.]],1)


def test_canonical_wire_negative_controls():
    from cognitum.mel import engines_pb2 as pb
    raw,d=Network((layer(),)).checkpoint_candidate()
    def bad(m):
        b=m.SerializeToString(deterministic=True)
        with pytest.raises(ValueError):load_candidate(b,hashlib.sha256(b).hexdigest())
    m=pb.KanInput.FromString(raw);m.rows=1;m.coordinates.append(.1);bad(m)
    m=pb.KanInput.FromString(raw);m.layers[0].base.append(0.);bad(m)
    m=pb.KanInput.FromString(raw);m.layers[0].mask[0]=.5;bad(m)
    b=raw+b'\x98\x06\x01'
    with pytest.raises(ValueError):load_candidate(b,hashlib.sha256(b).hexdigest())


@pytest.mark.parametrize('kind,degree',[('rbf',0),('spline',3)])
def test_trained_checkpoint_actual_verified_worker(kind,degree):
    from cognitum.mel import model_engines as me, model_reference as r, admission as a
    x=np.linspace(-.7,.7,81)[:,None];target=.1*x+.2*x*x
    trained=Network((layer(kind,degree),)).fit_linear(x,target,1e-6)
    raw,digest=trained.checkpoint_candidate();checkpoint=me.Checkpoint(raw)
    assert checkpoint.identity==digest
    scope=a.Scope('cog04a','bench','cpu','turn');app=me.Approval(checkpoint,'local-review')
    with r.ReferenceTurn(scope,r.Allowed(('kan.evaluate',),app)) as t:
        req=json.dumps({'tool':'mel_kan_evaluate','arguments':{'points':[[.125],[.432]]}})
        out=t.dispatch(req);assert out['ok'],out
        assert out['result']['checkpoint_sha256']==digest and len(t.host._seen)==1
        assert out['result']['assurance']=='represented_input_enclosure'
        assert np.max(np.abs(np.array(out['result']['values'])-load_candidate(raw,digest).evaluate(np.asarray([[.125],[.432]],dtype=np.float32))[0].ravel()))<1e-5
    with r.ReferenceTurn(scope,r.Allowed(())) as t:
        assert not t.dispatch(req)['ok'] and not t.host._seen


def test_trained_rbf_to_vfa_continuous_certificate():
    from cognitum.mel import function_verification as c, model_engines as me, admission as a
    x=np.linspace(-.7,.7,81)[:,None];m=Network((layer(),)).fit_linear(x,.1*x*x,1e-6)
    raw,d=m.checkpoint_candidate();f=c.KanFunction(me.Approval(me.Checkpoint(raw),'local-review'),'x')
    target=c.propose_vfa(f);scope=a.Scope('cog04a','bench','cpu','turn');box=((-1.,1.),);tol=(1e-10,1e-10)
    cert=c.certify(scope,f,target,box,tol);assert cert.message().verdict=='within'
    assert c.replay(scope,f,cert,box,target=target,absolute_tolerance=tol)=='within'


@pytest.mark.parametrize('degree',[1,2,3])
def test_clamped_spline_partition_and_scipy(degree):
    l=layer('spline_clamped',degree);g=l.grid[0];n=l.coefficients.shape[2];x=np.linspace(-1,1,71)[:,None];b=l.basis(x)[0][:,0]
    oracle=BSpline(g,np.eye(n),degree,extrapolate=False)
    assert np.allclose(b,oracle(x[:,0]),atol=1e-12)
    assert np.allclose(b.sum(axis=1),1.,atol=1e-12)
    assert b[0,0]==1 and b[-1,-1]==1
    q=np.array([[-.81],[-.15],[.29],[.78]])
    for j in (1,2):
        if j<=degree:assert np.allclose(l.basis(q,j)[j][:,0],oracle(q[:,0],nu=j),atol=1e-10)


def test_preserve_strict_spline_boundary_failure():
    x=np.linspace(-.73,.73,81)[:,None];h=(x[:-1]+x[1:])/2;f=lambda t:.4*np.sin(2*t)+.1*t*t
    strict=Network((layer('spline',3),)).fit_linear(x,f(x),1e-8)
    clamped=Network((layer('spline_clamped',3),)).fit_linear(x,f(x),1e-8)
    a=np.sqrt(np.mean((strict.evaluate(h)[0]-f(h))**2));b=np.sqrt(np.mean((clamped.evaluate(h)[0]-f(h))**2))
    assert a>.05 and b<.006
    assert strict.layers[0].basis([[-1.]])[0].sum()==0
    assert clamped.layers[0].basis([[-1.]])[0].sum()==1


def test_bad_clamping():
    l=layer('spline_clamped',3);g=l.grid.copy();g[0,1]=-.99
    with pytest.raises(ValueError):Layer(l.kind,l.degree,g,l.coefficients,l.mask,l.bias)


def test_trained_checkpoint_verified_three_engine_exchange():
    from dataclasses import replace
    from cognitum.mel import cooperation as g, model_engines as me, verified_graph as vg, uncertainty_pb2 as pb
    from research_tests.mel04b.test_cooperation import fixture_plan, setup
    from research_tests.mel05b.test_graph_acceptance import TOL
    x=np.linspace(-1.,1.,81)[:,None];m=Network((layer(),)).fit_linear(x,.1*x*x,1e-6)
    raw,d=m.checkpoint_candidate();app=me.Approval(me.Checkpoint(raw),'cog04a-local-review')
    plan=fixture_plan('trained');nodes=tuple(replace(z,approval=app) if type(z) is g.Kan else
        replace(z,at_least=.95) if type(z) is g.Threshold and z.id=='probe' else
        replace(z,at_least=.95) if type(z) is g.Threshold and z.id=='candidate' else z for z in plan.nodes)
    p=replace(plan,nodes=nodes);h,t=setup(p)
    try:
        v=vg.execute_verified(h,p,t,TOL);assert v.status=='verified' and v.reserved_calls==4
        witness=pb.GraphWitness.FromString(v.witness);records={z.node_id:z for z in witness.nodes}
        assert list(records['query'].hamming_distance)==[2,0,0] and list(records['query'].best_index)==[1,2]
        assert vg.replay(p,v.outcome,TOL,v.witness)
        with pytest.raises(ValueError):vg.replay(p,v.outcome,TOL,v.witness+b'\0')
    finally:h.close()
