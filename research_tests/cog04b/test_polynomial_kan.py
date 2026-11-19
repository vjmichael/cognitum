from dataclasses import replace
from fractions import Fraction
import hashlib
import math
import numpy as np
import pytest
from scipy.interpolate import BSpline
from cognitum.research.kan_trainable import Layer, Network
from cognitum.mel import polynomial_kan as p, polynomial_witness as w, polynomial_kan_pb2 as pb
from cognitum.mel import admission as a, engines as e, engines_pb2 as ep, native as n
from cognitum.mel.engine_limits import HdcLimits
from cognitum.runtime import Runtime
from cognitum.registry import Registry
from cognitum.contracts import Response
S=a.Scope('polynomial','workspace','owner','turn')
def layer(kind,degree,i=1,o=1,seed=22):
    grid=np.tile(np.r_[[-1.]*(degree+1),[-.5,0,.5],[1.]*(degree+1)] if kind=='spline_clamped' else [-1.,1.],(i,1))
    k=degree+1 if kind=='chebyshev' else grid.shape[1]-degree-1
    weights=np.random.default_rng(seed).integers(-8,9,(o,i,k))/128
    return Layer(kind,degree,grid,weights,np.ones((o,i)),np.zeros(o))
@pytest.mark.parametrize('kind,degree',[('spline_clamped',1),('spline_clamped',2),('spline_clamped',3),('chebyshev',0),('chebyshev',1),('chebyshev',4),('chebyshev',8)])
@pytest.mark.parametrize('depth',[1,2])
def test_roundtrip_points(kind,degree,depth):
    m=Network(tuple(layer(kind,degree,2,2,j) for j in range(depth)))
    c=p.export_checkpoint(m);assert c.model().research_snapshot()==m.research_snapshot();assert p.export_checkpoint(c.model())==c
    x=np.array([[.183,-.283],[.31,.12]])
    call=p.make_call(c,x,2,1e-8,'evaluate',S.turn);r=pb.Result.FromString(p.compute(call))
    assert [v.observed for v in r.components]==np.concatenate([v.ravel() for v in m.evaluate(x,2)]).tolist()
    for b,v in zip(p.exact_components(m,x,2),r.components):
        assert Fraction(v.lower)<=b[0]==b[1]<=Fraction(v.upper)
        assert abs(Fraction(v.observed)-b[0])<=Fraction(v.absolute_error_upper)<=Fraction(1e-8)
@pytest.mark.parametrize('degree',[1,2,3])
def test_spline_witness_independent_scipy(degree):
    l=layer('spline_clamped',degree);q=BSpline(l.grid[0],l.coefficients[0,0],degree)
    for x in (-.93,-.44,.11,.71,.99):
        b=w.edge(l,0,0,(Fraction(x),Fraction(x)),2)
        for i,(lo,hi) in enumerate(b):
            assert lo==hi and abs(float(lo)-(q(x,nu=i) if i<=degree else 0))<1e-10
@pytest.mark.parametrize('kind,degree',[('spline_clamped',3),('chebyshev',4)])
def test_continuous_box_multilayer(kind,degree):
    m=Network((layer(kind,degree,2,2),layer(kind,degree,2,1,25)));c=p.export_checkpoint(m);box=[(.20,.22),(-.35,-.33)];b=p.continuous_enclosure(c,box,2)
    for x in np.random.default_rng(8).uniform([.20,-.35],[.22,-.33],size=(15,2)):
        for (lo,hi),v in zip(b,p.exact_components(m,x[None,:],2)):assert Fraction(lo)<=v[0]<=v[1]<=Fraction(hi)
def test_known_chain_rule_and_box():
    l=Layer('chebyshev',2,[[-1,1]],[[[.5,0,.5]]],[[1]],[0]);c=p.export_checkpoint(Network((l,l)))
    r=pb.Result.FromString(p.compute(p.make_call(c,[[.5]],2,0,'known',S.turn)))
    assert [v.observed for v in r.components]==[.0625,.5,3.]
    assert all(v.lower==v.upper==v.observed and v.absolute_error_upper==0 for v in r.components)
    bounds=p.continuous_enclosure(c,[(.49,.51)],2)
    for x in (.49,.5,.51):
        for (lo,hi),v in zip(bounds,(x**4,4*x**3,12*x*x)):assert lo<=v<=hi
@pytest.mark.parametrize('degree',[1,2,3])
def test_clamped_endpoint_convention(degree):
    l=layer('spline_clamped',degree);c=p.export_checkpoint(Network((l,)))
    for x,i in [(-1,0),(1,-1)]:
        r=pb.Result.FromString(p.compute(p.make_call(c,[[x]],0,0,'endpoint',S.turn)));assert r.components[0].observed==l.coefficients[0,0,i]
        with pytest.raises(ValueError):p.compute(p.make_call(c,[[x]],1,1e-6,'endpoint',S.turn))
@pytest.mark.parametrize('degree',[1,2])
def test_nonsmooth_derivative_refused(degree):
    c=p.export_checkpoint(Network((layer('spline_clamped',degree),)))
    with pytest.raises(ValueError):p.compute(p.make_call(c,[[0]],degree,1e-6,'knot',S.turn))
    with pytest.raises(ValueError):p.continuous_enclosure(c,[(-.01,.01)],degree)
def test_exact_intermediate_domain_failure():
    l=Layer('chebyshev',0,[[-1,1]],[[[2.]]],[[1]],[0]);c=p.export_checkpoint(Network((l,layer('chebyshev',2))))
    with pytest.raises(ValueError):p.compute(p.make_call(c,[[.1]],0,1e-6,'ood',S.turn))
    with pytest.raises(ValueError):p.continuous_enclosure(c,[(-.1,.1)])
@pytest.mark.parametrize('kind',['rbf','spline'])
def test_no_legacy_relabel(kind):
    l=Layer(kind,0,[[-1,0,1]],[[[0]*(3 if kind=='rbf' else 2)]],[[1]],[0]);m=Network((l,))
    with pytest.raises(ValueError):p.export_checkpoint(m)
    with pytest.raises(ValueError):p.Checkpoint(m.checkpoint_candidate()[0])
@pytest.mark.parametrize('mutation',['grid','mask','shape','basis','nan','version','unknown','duplicate','tiny'])
def test_checkpoint_rejections(mutation):
    c=p.export_checkpoint(Network((layer('spline_clamped',3),)));m=c.message();l=m.layers[0]
    if mutation=='grid':l.grid[1]=-.9
    elif mutation=='mask':del l.mask[:]
    elif mutation=='shape':l.inputs=5
    elif mutation=='basis':l.basis=0
    elif mutation=='nan':l.bias[0]=math.nan
    elif mutation=='version':m.schema_version=2
    elif mutation=='unknown':
        with pytest.raises(ValueError):p.Checkpoint(c.wire+b'\xf8\x07\x01')
        return
    elif mutation=='duplicate':
        with pytest.raises(ValueError):p.Checkpoint(c.wire+b'\x08\x01')
        return
    else:l.bias[0]=2**-300
    with pytest.raises(ValueError):p.Checkpoint(p.serialize(m))
def setup(*,enabled=True,limits=None):
    r=Registry();r.install(p.PolynomialPlugin,enabled=True);r.nominate(p.OP,p.NAME)
    h=a.Admission(Runtime(r),S.session,enable_engines=True,enable_model_codecs=True,enable_polynomial_kan=enabled)
    c=p.export_checkpoint(Network((layer('chebyshev',3),)));route=next(v for v in a.routes(include_engines=True,include_polynomial_kan=True) if v.operation==p.OP)
    if not enabled:return h,c,route
    h.approve_polynomial_checkpoint(S,c.wire,expected_sha256=c.identity,review_id='review');token=h.issue(S,route,limits or p.Limits(timeout_ms=5000,calls=4),checkpoint_sha256=c.identity,ttl_ms=60000)
    return h,c,token
def test_shared_native_scope_and_replay():
    h,c,t=setup();assert not h.discover(S,t)['model_advertised'];call=p.make_call(c,[[.25]],2,1e-8,'worker',S.turn);r=h.execute(S,t,'worker',call.wire,timeout_ms=5000)
    assert r.status=='completed' and r.result_frame and r.result_sha256==hashlib.sha256(r.result_frame).hexdigest()
    assert h.execute(S,t,'worker',call.wire,timeout_ms=5000).status=='replay_denied' and h._grants[t].calls_left==3
@pytest.mark.parametrize('case',['disabled','no_checkpoint','wrong_scope','wrong_checkpoint','revoked','model_codec','resource','wrong_profile'])
def test_shared_controls(case):
    h,c,t=setup(enabled=case!='disabled',limits=p.Limits(work=1) if case=='resource' else None);route=next(v for v in a.routes(include_engines=True,include_polynomial_kan=True) if v.operation==p.OP)
    if case=='disabled':
        with pytest.raises(ValueError):h.approve_polynomial_checkpoint(S,c.wire,expected_sha256=c.identity,review_id='review')
        return
    if case in ('no_checkpoint','model_codec','wrong_profile'):
        opts={} if case=='no_checkpoint' else {'model_codec':True,'checkpoint_sha256':c.identity} if case=='model_codec' else {'checkpoint_sha256':c.identity}
        with pytest.raises(ValueError):h.issue(S,route,a.Limits() if case=='wrong_profile' else p.Limits(),**opts)
    elif case=='wrong_scope':
        with pytest.raises(ValueError):h.execute(replace(S,subject='other'),t,'bad',p.make_call(c,[[.3]],0,1e-8,'bad',S.turn).wire,timeout_ms=5000)
    elif case=='revoked':
        assert h.revoke_checkpoint(S,c.identity)
        with pytest.raises(ValueError):h.discover(S,t)
    else:
        other=p.export_checkpoint(Network((layer('chebyshev',3,seed=11),))) if case=='wrong_checkpoint' else c;x=p.make_call(other,[[.3]],0,1e-8,'bad',S.turn)
        assert h.execute(S,t,'bad',x.wire,timeout_ms=5000).status==('invalid_input' if case=='wrong_checkpoint' else 'resource_denied')
    assert not h._seen
@pytest.mark.parametrize('mutation',['forged_bound','forged_observation','checkpoint','request','count','error'])
def test_host_independent_result_rejection(mutation):
    c=p.export_checkpoint(Network((layer('chebyshev',4),)));call=p.make_call(c,[[.25]],2,1e-8,'forgery',S.turn);m=pb.Result.FromString(p.compute(call))
    if mutation=='forged_bound':m.components[0].lower+=.1
    elif mutation=='forged_observation':m.components[0].observed+=.1
    elif mutation=='checkpoint':m.checkpoint_sha256=b'0'*32
    elif mutation=='request':m.request_sha256=b'0'*32
    elif mutation=='count':del m.components[-1]
    else:m.components[0].absolute_error_upper+=.1
    response=Response('forgery',S.turn,p.OP,'completed',module={'name':p.NAME,'version':p.VERSION},assurance='numerical',result={'frame':n.encode_carrier(p.serialize(m),p.MAX_RESULT)})
    with pytest.raises(ValueError):p.checked_result(call,response)

def test_trained_checkpoint_roundtrip():
    for kind,degree in [('spline_clamped',3),('chebyshev',5)]:
        m=Network((layer(kind,degree),));x=np.linspace(-.8,.8,81)[:,None];y=.1*x+.2*x*x
        trained=m.fit_linear(x,y,ridge=1e-8);c=p.export_checkpoint(trained)
        assert c.model().research_snapshot()==trained.research_snapshot()
        assert np.max(np.abs(c.model().evaluate(np.array([[.37],[-.23]]))[0]-(.1*np.array([[.37],[-.23]])+.2*np.array([[.37],[-.23]])**2)))<1e-6
        h,_,_=setup();h.approve_polynomial_checkpoint(S,c.wire,expected_sha256=c.identity,review_id='fit-review')
        route=next(v for v in a.routes(include_engines=True,include_polynomial_kan=True) if v.operation==p.OP)
        token=h.issue(S,route,p.Limits(timeout_ms=5000),checkpoint_sha256=c.identity,ttl_ms=60000)
        call=p.make_call(c,[[.37],[-.23]],2,1e-8,'fit',S.turn);receipt=h.execute(S,token,'fit',call.wire,timeout_ms=5000)
        assert receipt.status=='completed';r=pb.Result.FromString(receipt.result_frame)
        assert max(v.absolute_error_upper for v in r.components)<1e-8


def test_same_session_three_engines(tmp_path):
    from cognitum.mel import polynomial_exchange as pe, exchange as x, verification as v
    reg=Registry();reg.install(p.PolynomialPlugin,enabled=True);reg.install(n.NativeVFAPlugin,enabled=True);reg.install(e.EnginePlugin,enabled=True)
    reg.nominate(p.OP,p.NAME)
    for op in n.OP:reg.nominate(op,n.NAME)
    for op in e.OPERATIONS:reg.nominate(op,e.NAME)
    h=a.Admission(Runtime(reg),S.session,enable_engines=True,enable_polynomial_kan=True)
    routes={r.operation:r for r in a.routes(include_engines=True,include_polynomial_kan=True)}
    l=Layer('chebyshev',2,[[-1,1]],[[[.5,0,.5]]],[[1]],[0]);c=p.export_checkpoint(Network((l,l)))
    h.approve_polynomial_checkpoint(S,c.wire,expected_sha256=c.identity,review_id='review')
    t=h.issue(S,routes[p.OP],p.Limits(timeout_ms=5000),checkpoint_sha256=c.identity,ttl_ms=60000)
    call=p.make_call(c,[[0.],[.5],[1.]],2,0,'kan',S.turn);receipt=h.execute(S,t,'kan',call.wire,timeout_ms=5000)
    assert receipt.status=='completed';r=pb.Result.FromString(receipt.result_frame);assert [v.observed for v in r.components[:3]]==[0.,.0625,1.]
    f=n.gaussian([[0]],[[1]],[1],constant=0,axes=[('x','1')],domain=[(-2,2)],output_unit='1')
    trans=pe.prepare_vfa(S,call,receipt,f,('x',),'vfa');assert pe.replay(trans,S,call,receipt,f,('x',))
    with pytest.raises(ValueError):pe.prepare_vfa(S,call,receipt,f,('wrong',),'vfa')
    with pytest.raises(ValueError):pe.prepare_vfa(S,call,replace(receipt,result_sha256='0'*64),f,('x',),'vfa')
    t2=h.issue(S,routes[trans.target.operation],a.Limits(timeout_ms=5000),ttl_ms=60000)
    rr=h.execute(S,t2,'vfa',trans.target.wire(),timeout_ms=5000);assert rr.status=='completed'
    # Verify ideal represented samples before crossing the lossy threshold;
    # no downstream dispatch if any enclosure straddles the threshold.
    from cognitum.mel import verification_pb2 as vp
    from decimal import Decimal
    cert=v.certify_vfa(S,trans.target,rr,(1e-10,));assert v.replay(S,trans.target,rr,cert,absolute_tolerance=(1e-10,))==vp.WITHIN_TOLERANCE
    for component,bit in zip(cert.message().components,(1,1,0)):
        assert (Decimal(component.lower)>=Decimal.from_float(.8) if bit else Decimal(component.upper)<Decimal.from_float(.8))
    obj=x.from_result(S,trans.target,rr);bits=x.threshold(S,obj,.8,'1').message().body.bits;assert bits.packed_bits==b'\x03'
    probe=ep.BinaryVector(dimension=bits.dimension,bits=bits.packed_bits)
    query=e.make_call('hdc.query',ep.QueryInput(probe=probe,candidates=[ep.BinaryVector(dimension=3,bits=b'\x00'),probe,probe]),'hdc',S.turn)
    t3=h.issue(S,routes['hdc.query'],HdcLimits(timeout_ms=5000),ttl_ms=60000)
    qr=h.execute(S,t3,'hdc',query.wire,timeout_ms=5000);assert qr.status=='completed'
    z=ep.EngineResult.FromString(qr.result_frame).query;assert list(z.hamming_distance)==[2,0,0] and list(z.best_index)==[1,2]
    cert2=v.certify_hdc(S,query,qr);assert v.replay(S,query,qr,cert2)==vp.EXACT_SUBMITTED_BITS
    assert len(h._seen)==3
    # Retained exact request/result bytes and independent witness records.
    import json
    frames={'kan.checkpoint.pb':c.wire,'kan.request.pb':call.wire,'kan.result.pb':receipt.result_frame,
            'vfa.request.pb':trans.target.wire(),'vfa.result.pb':rr.result_frame,'vfa.certificate.pb':cert.wire,
            'hdc.request.pb':query.wire,'hdc.result.pb':qr.result_frame,'hdc.certificate.pb':cert2.wire}
    for name,raw in frames.items():(tmp_path/name).write_bytes(raw)
    (tmp_path/'summary.json').write_text(json.dumps(dict(scope=[S.session,S.workspace,S.subject,S.turn],
        calls=3,checkpoint=c.identity,transfer=trans.identity,distances=list(z.hamming_distance),tied_indices=list(z.best_index),
        verified_vfa=True,verified_hdc=True,exact_kan_sample_transfer=True,production_enabled=False,
        sha256={name:hashlib.sha256(raw).hexdigest() for name,raw in frames.items()}),indent=2)+'\n',encoding='utf8')
