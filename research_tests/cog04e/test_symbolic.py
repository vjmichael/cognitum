from dataclasses import replace
from fractions import Fraction as Q
import hashlib,json
import numpy as np
import pytest
from scipy.interpolate import BSpline
from cognitum.research.kan_trainable import Layer,Network
from cognitum.mel import kan_symbolic as s, polynomial_kan as p, admission as a, model_reference as r, polynomial_model as pm


def cheb(coeff,lo=-1.,hi=1.,bias=0.,mask=1.):
    return Layer('chebyshev',len(coeff)-1,[[lo,hi]],[[coeff]],[[mask]],[bias])


def cp(*layers):return p.export_checkpoint(Network(tuple(layers)))


def f(coeff,lo=-1,hi=1):return s.function(lo,hi,coeff)

@pytest.mark.parametrize('coeff',[ [1.], [0.,1.], [.5,0.,.5], [0.,.75,0.,.25], [0.,0.,0.,0.,0.,0.,0.,0.,1.] ])
def test_cheb_exact(coeff):
    c=cp(cheb(coeff));e=s.extract(c);assert s.replay(c,e)==e.function
    xs=np.linspace(-1,1,101);exact=np.array([float(e.function.evaluate(float(x))) for x in xs])
    np.testing.assert_allclose(exact,np.polynomial.chebyshev.chebval(xs,coeff),atol=2e-14,rtol=0)

@pytest.mark.parametrize('degree',[1,2,3])
def test_clamped_exact(degree):
    knots=[-1.]*(degree+1)+[-.5,.25]+[1.]*(degree+1);co=[(-1)**i*i/8 for i in range(len(knots)-degree-1)]
    layer=Layer('spline_clamped',degree,[knots],[[co]],[[1.]],[.125]);c=cp(layer);e=s.extract(c)
    assert s.verify_layer(layer,e.function);xs=np.linspace(-1,1,147)
    np.testing.assert_allclose([float(e.function.evaluate(float(x))) for x in xs],BSpline(knots,co,degree)(xs)+.125,atol=5e-14,rtol=0)
    for x in [-1,-.5,.25,1]:assert e.function.evaluate(x)==s.exact_layer_value(layer,Q(x))


def test_mask_bias():assert s.extract(cp(cheb([7.,9.],bias=.25,mask=0.))).function==f([Q(1,4)])


def test_scaled_domain():assert s.extract(cp(cheb([0.,1.],0.,4.))).function==f([-1,Q(1,2)],0,4)


def test_two_layer_exact():
    c=cp(cheb([.5,0.,.5]),cheb([.5,0.,.5]));g=s.extract(c).function
    assert g==f([0,0,0,0,1]);assert g.evaluate(Q(3,5))==Q(81,625)


def test_two_layer_range_subdivide():assert s.extract(cp(cheb([.5,0,.5]),cheb([0.,1.],0.,1.))).function==f([-1,0,2])


def test_outside_domain():
    with pytest.raises(ValueError,match='range'):s.extract(cp(cheb([0.,2.]),cheb([0.,1.])))


def test_non_scalar():
    layer=Layer('chebyshev',1,[[-1,1],[-1,1]],[[[0,1],[0,1]]],[[1,1]],[0])
    with pytest.raises(ValueError,match='scalar'):s.extract(cp(layer))


def test_forged_extract():
    c=cp(cheb([0.,1.]));e=s.extract(c)
    with pytest.raises(ValueError,match='witness'):s.replay(c,replace(e,function=f([1.])))
    with pytest.raises(ValueError,match='witness'):s.replay(cp(cheb([-.5,1.])),e)
    with pytest.raises(ValueError,match='coefficient'):s.verify_layer(c.model().layers[0],f([0.,2.]))

@pytest.mark.parametrize('op,expect',[('add',[1,1,1]),('subtract',[-1,-1,1]),('multiply',[0,0,1,1])])
def test_arithmetic(op,expect):
    x=f([0,0,1]);y=f([1,1]);cert=s.arithmetic(op,x,y);assert cert.result==f(expect);assert s.replay_arithmetic(cert,x,y)==cert.result
    with pytest.raises(ValueError,match='witness'):s.replay_arithmetic(replace(cert,result=f([0])),x,y)


def test_exact_quotient():
    q=f([2,1]);x=f([0,1,1]);p=s.combine(x,q,'multiply');assert s.arithmetic('divide',p,q).result==x

@pytest.mark.parametrize('den',[ [0],[0,1],[0,0,1],[1,1] ])
def test_zero_denominator(den):
    q=f(den)
    with pytest.raises(ValueError,match='denominator'):s.combine(s.combine(q,f([2]),'multiply'),q,'divide')


def test_nonpolynomial_quotient():
    with pytest.raises(ValueError,match='not polynomial'):s.combine(f([1]),f([2,1]),'divide')


def test_piecewise_arithmetic():
    g=s.canonical([s.Piece(-1,0,[0,-1]),s.Piece(0,1,[0,1])]);h=s.arithmetic('multiply',g,g).result;assert h==f([0,0,1]);j=s.arithmetic('add',g,f([1])).result;assert len(j.pieces)==2 and j.evaluate(Q(-1,4))==Q(5,4)


def test_domain_mismatch():
    with pytest.raises(ValueError,match='domain'):s.combine(f([1]),f([2],0,1),'add')


def test_calculus():
    x=f([0,0,0,0,1]);d=s.Operator(('D',));i=s.Operator(('I',));assert d.after(i).apply(x)==x
    assert i.after(d).apply(x)==f([-1,0,0,0,1]);assert d.after(d).apply(x)==f([0,0,12]);assert s.integrate(x).evaluate(1)==Q(2,5)


def test_piecewise_integral_and_nonsmooth():
    g=s.canonical([s.Piece(-1,0,[0,-1]),s.Piece(0,1,[0,1])]);i=s.integrate(g);assert i.evaluate(0)==Q(1,2) and i.evaluate(1)==1;assert s.differentiate(i)==g
    with pytest.raises(ValueError,match='discontinuous'):s.differentiate(g)


def test_operator_order():
    with pytest.raises(ValueError):s.Operator(('eval',))
    with pytest.raises(ValueError):s.Operator(('D',)*9)
    assert s.compose(f([0,0,1]),f([0,Q(1,2)]))==f([0,0,Q(1,4)])


def test_affine_spline_preimage():
    g=s.canonical([s.Piece(-1,0,[0,-1]),s.Piece(0,1,[0,1])]);h=s.compose(g,f([Q(1,3),Q(1,2)]));assert h.pieces[0].hi==Q(-2,3);assert h.evaluate(Q(-2,3))==0


def test_non_affine_unresolved_crossing():
    g=s.canonical([s.Piece(-1,0,[0,-1]),s.Piece(0,1,[0,1])]);inner=f([-Q(1,3),0,1]);
    with pytest.raises(ValueError,match='range'):s.compose(g,inner)


def test_refuse_bounds():
    with pytest.raises(ValueError):s.Piece(0,0,[1])
    with pytest.raises(ValueError):s.Piece(0,1,[True])
    with pytest.raises(ValueError):s.Piece(0,1,[float('nan')])
    with pytest.raises(ValueError):s.Piece(0,1,[2**4096])
    with pytest.raises(ValueError):s.Piece(0,1,[1]*66)
    with pytest.raises(ValueError):s.Function((s.Piece(-1,0,[1]),s.Piece(Q(1,2),1,[1])))
    with pytest.raises(ValueError):f([0,1]).evaluate(2)
    with pytest.raises(ValueError):s.enclosure((Q(1),),Q(-1),Q(1),9)
    with pytest.raises(ValueError):s.combine(f([0]*33+[1]),f([0]*33+[1]),'multiply')


def test_bernstein_bounds():
    g=f([0,0,1]);assert g.range()==(-1,1);assert g.range(1)==(0,1)


def test_export_refusal():
    with pytest.raises(ValueError,match='lossy'):s.export_candidate(f([Q(1,3)]))
    with pytest.raises(ValueError,match='degree'):s.export_candidate(f([0]*9+[1]))
    with pytest.raises(ValueError,match='single'):s.export_candidate(s.canonical([s.Piece(-1,0,[0,-1]),s.Piece(0,1,[0,1])]))


def test_actual_worker_export(tmp_path):
    # Extract two reviewed checkpoints, multiply, differentiate, export the exact
    # expression to an existing approved binary64 KAN route, independently replay.
    c1=cp(cheb([.5,0.,.5]));c2=cp(cheb([.5,0.,.5]));x=s.extract(c1);y=s.extract(c2)
    cert=s.arithmetic('multiply',x.function,y.function);g=s.replay_arithmetic(cert,x.function,y.function);z=s.replay_operator(s.apply_verified(s.Operator(('D',)),g),g);c=s.export_candidate(z);assert s.extract(c).function==f([0,0,0,4])
    app=p.Approval(c,'symbolic-local-review');scope=a.Scope('cog04e','lab','owner','turn');pts=[[-.5],[.25]];order=2
    with r.ReferenceTurn(scope,r.Allowed((p.OP,),tolerance=1e-8,polynomial_approval=app)) as turn:
        out=turn.dispatch(r.canonical(dict(tool=pm.PUBLIC,arguments={'points':pts,'order':order})));assert out['ok'],out
        exact=[float(fn.evaluate(v[0])) for fn in (z,s.differentiate(z),s.differentiate(s.differentiate(z))) for v in pts]
        assert out['result']['values']==exact
        blobs={'source.checkpoint.pb':c1.wire,'symbolic.json':z.snapshot(),'derived.checkpoint.pb':c.wire,'request.pb':turn.last_call.wire,'result.pb':turn.last_receipt.result_frame}
        for k,v in blobs.items():(tmp_path/k).write_bytes(v)
        (tmp_path/'symbolic_evidence.json').write_text(json.dumps(dict(operation='D(f*f)',values=exact,checkpoint_sha256=c.identity,source_sha256=c1.identity,symbolic_sha256=z.identity,sha256={k:hashlib.sha256(v).hexdigest() for k,v in blobs.items()}),indent=2))


def test_snapshot_pin_and_canonical():
    g=f([Q(1,3),Q(-7,5)]);raw=g.snapshot();assert s.load_snapshot(raw,g.identity)==g
    with pytest.raises(ValueError,match='pin'):s.load_snapshot(raw,'0'*64)
    for bad in [raw+b' ',raw.replace(b'1/3',b'2/6'),raw.replace(b'1/3',b'1/0'),raw.replace(b'1/3',b'1e-999999999'),raw.replace(b'1/3',b'x'),raw.replace(b'"pieces":',b'"unknown":')]:
        with pytest.raises(ValueError):s.load_snapshot(bad,hashlib.sha256(bad).hexdigest())


def test_export_graph(tmp_path):
    from research_tests.cog04c.test_integration import graph,setup,TOLS
    from cognitum.mel import cooperation as g, verified_graph as vg, uncertainty_pb2 as wp
    source=cp(cheb([.5,0.,.5]));f1=s.extract(source).function;z=s.arithmetic('multiply',f1,f1).result
    derived=s.export_candidate(z);app=p.Approval(derived,'symbolic-graph-review');plan=graph(app);host,tokens=setup(plan)
    try:
        result=vg.execute_verified(host,plan,tokens,TOLS);assert result.status=='verified' and result.reserved_calls==4 and len(host._seen)==4
        record={n.node_id:n for n in result.outcome.nodes};values=list(record['poly'].output.message().body.samples.values);assert values==[0.,.0625,1.]
        nodes={n.node_id:n for n in wp.GraphWitness.FromString(result.witness).nodes};ties=list(nodes['query'].best_index);distances=list(nodes['query'].hamming_distance);assert ties==[1,2] and distances==[1,0,0]
        assert vg.replay(plan,result.outcome,TOLS,result.witness)
        blobs={'source.checkpoint.pb':source.wire,'derived.checkpoint.pb':derived.wire,'symbolic.json':z.snapshot(),'graph_witness.pb':result.witness,'plan.material':g._validate(plan)[1]}
        for node in result.outcome.nodes:
            if node.worker:blobs[node.node_id+'.result.pb']=node.worker.result_frame
        for k,v in blobs.items():(tmp_path/k).write_bytes(v)
        (tmp_path/'symbolic_graph.json').write_text(json.dumps(dict(operation='f*f',calls=len(host._seen),values=values,ties=ties,distances=distances,sha256={k:hashlib.sha256(v).hexdigest() for k,v in blobs.items()}),indent=2))
    finally:host.close()


def test_operator_witness_tamper():
    g=f([1,2,3]);op=s.Operator(('I','D','D'));w=s.apply_verified(op,g)
    assert s.replay_operator(w,g)==f([2,6]);assert w.input_sha256==g.identity
    with pytest.raises(ValueError,match='witness'):s.replay_operator(replace(w,result=f([0])),g)
    with pytest.raises(ValueError,match='witness'):s.replay_operator(w,f([1,2]))
    with pytest.raises(ValueError,match='identity'):s.verify_operator_step('D',g,f([0]))
    with pytest.raises(ValueError,match='anchor'):s.verify_operator_step('I',g,f([0,1,1,1]))
