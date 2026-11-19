from dataclasses import replace
from fractions import Fraction as Q
import hashlib,json
import numpy as np
import pytest
from scipy.interpolate import BSpline
from cognitum.mel import kan_multivariate as m, polynomial_kan as pk, model_reference as r, polynomial_model as pm, admission as a
from cognitum.research.kan_trainable import Layer, Network

BOX=((-1,1),(-1,1))
x,y=m.variable(2,0),m.variable(2,1)
def fn(p,box=BOX):return m.Function(box,(p,))
def cp(*layers):return pk.export_checkpoint(Network(layers))
def quadratic():
    return fn(x.multiply(x).add(y.multiply(y).scale(2)).add(x.multiply(y).scale(3)).add(x.scale(Q(1,2))).add(m.constant(2,Q(1,4))))

def test_sparse_canonical():
    p=m.make(2,[((1,1),1),((0,0),2),((1,1),-1),((2,0),3)]);assert p.terms==(((0,0),Q(2)),((2,0),Q(3)))
    assert p.evaluate([Q(1,2),Q(2,3)])==Q(11,4)

@pytest.mark.parametrize('wrong',[True,0,4])
def test_dimension(wrong):
    with pytest.raises(ValueError):m.constant(wrong,0)

@pytest.mark.parametrize('terms',[(((1,0),0),),(((1,0),1),((1,0),2)),(((0,13),1),),(((True,0),1),)])
def test_invalid_terms(terms):
    with pytest.raises(ValueError):m.Polynomial(2,terms)

def test_multiply_degree():
    with pytest.raises(ValueError,match='degree'):m.make(2,[((12,0),1)]).multiply(x)

def test_rational_budget():
    with pytest.raises(ValueError,match='budget'):m.constant(2,2**4096)

def test_bounds():
    assert m.bounds(x.multiply(x),BOX)==(0,1);assert m.bounds(x.multiply(y),BOX)==(-1,1)

def test_scaled_box():
    f=fn(x.add(y),((0,2),(3,4)));assert f.evaluate([2,3])==(5,)
    with pytest.raises(ValueError,match='outside'):f.evaluate([2,5])

def test_additive_extract():
    l=Layer('chebyshev',2,[[-1,1],[-1,1]],[[[.5,0,.5],[1,0,1]]],[[1,1]],[.25]);c=cp(l);e=m.extract(c)
    assert e.function==fn(x.multiply(x).add(y.multiply(y).scale(2)).add(m.constant(2,Q(1,4))))
    assert m.replay(c,e)==e.function

def test_vector_three_dimensions():
    l=Layer('chebyshev',1,[[-1,1]]*3,[[[0,1],[0,2],[0,3]],[[0,4],[0,5],[0,6]]],[[1,1,1],[1,0,1]],[.25,-.5]);e=m.extract(cp(l));assert e.function.evaluate([Q(1,2),Q(1,4),Q(1,8)])==(Q(13,8),Q(9,4))

@pytest.mark.parametrize('degree',[1,2,3])
def test_clamped_subbox(degree):
    g=[-1.]*(degree+1)+[0.]+[1.]*(degree+1);co=[i/8 for i in range(len(g)-degree-1)];l=Layer('spline_clamped',degree,[g,g],[[co,co]],[[1,1]],[.25]);c=cp(l);f=m.extract(c,((-1,0),(0,1))).function
    bs=BSpline(g,co,degree);pt=[-.25,.75];assert abs(float(f.evaluate(pt)[0])-(bs(pt[0])+bs(pt[1])+.25))<1e-14
    with pytest.raises(ValueError,match='crossing'):m.extract(c)


def test_quadratic_polarization():
    f=quadratic();c=m.export_quadratic(f);assert len(c.model().layers)==2;assert m.extract(c).function==f
    for u,v in [(0,0),(1,1),(-1,1),(Q(1,2),Q(-1,4))]:assert f.evaluate([u,v])==(u*u+2*v*v+3*u*v+u/2+Q(1,4),)


def test_bad_export():
    with pytest.raises(ValueError,match='nonseparable'):m.export_additive(quadratic())
    with pytest.raises(ValueError,match='lossy'):m.export_additive(fn(m.constant(2,Q(1,3))))
    with pytest.raises(ValueError,match='profile'):m.export_quadratic(fn(x.multiply(x).multiply(x)))


def test_additive_export():
    f=fn(x.multiply(x).add(y.scale(Q(1,2))).add(m.constant(2,Q(1,4))));assert m.extract(m.export_additive(f)).function==f

@pytest.mark.parametrize('op',['add','subtract','multiply'])
def test_arithmetic(op):
    a=fn(x.add(y));b=fn(x.add(y.scale(-1)));cert=m.manipulate(op,a,b);f=m.replay_operation(cert,a,b)
    expected={'add':x.scale(2),'subtract':y.scale(2),'multiply':x.multiply(x).add(y.multiply(y).scale(-1))}[op];assert f==fn(expected)
    with pytest.raises(ValueError,match='witness'):m.replay_operation(replace(cert,result=fn(m.constant(2,7))),a,b)


def test_mixed_derivative():
    f=quadratic();d=m.Operator((('D',0),('D',1)));e=m.manipulate(d,f);assert m.replay_operation(e,f)==fn(m.constant(2,3));assert m.Operator((('D',1),('D',0))).apply(f)==e.result


def test_gradient_and_hessian():
    f=quadratic();p=f.outputs[0];assert [v.evaluate([Q(1,2),Q(-1,4)]) for v in (p.partial(0),p.partial(1))]==[Q(3,4),Q(1,2)]
    assert [[p.partial(i).partial(j).evaluate([0,0]) for j in range(2)] for i in range(2)]==[[2,3],[3,4]]


def test_anchored_integration():
    f=fn(x.multiply(y));i=m.Operator((('I',0),));d=m.Operator((('D',0),));g=i.apply(f);assert g.evaluate([-1,Q(1,2)])==(0,);assert d.after(i).apply(f)==f
    assert i.after(d).apply(f)==fn(x.multiply(y).add(y))


def test_operator_bad():
    for steps in [(),(('eval',0),),(('D',True),),(('D',0),)*9]:
        with pytest.raises(ValueError):m.Operator(steps)
    with pytest.raises(ValueError,match='axis'):m.Operator((('D',2),)).apply(fn(x))


def test_compose_vector():
    a=quadratic();b=m.Function(BOX,(x.scale(Q(1,2)),y.scale(Q(1,2))));e=m.manipulate('compose',a,b);f=m.replay_operation(e,a,b);assert f.evaluate([1,1])==a.evaluate([Q(1,2),Q(1,2)])


def test_compose_cross_dimension():
    u=m.variable(1,0);b=m.Function(((-1,1),),(u,u.scale(-1)));f=m.compose(quadratic(),b);assert f.evaluate([Q(1,2)])==quadratic().evaluate([Q(1,2),Q(-1,2)])


def test_domain_refusal():
    with pytest.raises(ValueError,match='domain'):m.compose(quadratic(),m.Function(BOX,(x.scale(2),y)))
    l=Layer('chebyshev',1,[[-1,1],[-1,1]],[[[0,2],[0,0]]],[[1,1]],[0]);out=Layer('chebyshev',1,[[-1,1]],[[[0,1]]],[[1]],[0]);
    with pytest.raises(ValueError,match='domain'):m.extract(cp(l,out))


def test_tampered_extract():
    c=m.export_quadratic(quadratic());e=m.extract(c)
    with pytest.raises(ValueError,match='witness'):m.replay(c,replace(e,function=fn(x)))


def test_snapshot():
    f=quadratic();raw=f.snapshot();assert m.load_snapshot(raw,f.identity)==f
    with pytest.raises(ValueError,match='pin'):m.load_snapshot(raw,'0'*64)
    for bad in [raw+b' ',raw.replace(b'1/4',b'2/8'),raw.replace(b'1/4',b'1/0'),raw.replace(b'"outputs"',b'"unknown"')]:
        with pytest.raises(ValueError):m.load_snapshot(bad,hashlib.sha256(bad).hexdigest())


def test_actual_multivariate_worker(tmp_path):
    # Learn/extract is separate; exact derived function is approved explicitly.
    source=m.export_quadratic(quadratic());f=m.replay(source,m.extract(source));d=m.Operator((('D',0),));derived=m.replay_operation(m.manipulate(d,f),f);c=m.export_additive(derived)
    evidence=[]
    for name,checkpoint,model in [('quadratic',source,f),('derivative',c,derived)]:
        app=pk.Approval(checkpoint,'multivariate-review');scope=a.Scope('cog04f','lab','owner',name);pts=[[.5,-.25],[.25,.5]]
        with r.ReferenceTurn(scope,r.Allowed((pk.OP,),tolerance=1e-8,polynomial_approval=app)) as turn:
            out=turn.dispatch(r.canonical(dict(tool=pm.PUBLIC,arguments={'points':pts,'order':2})));assert out['ok'],out
            p=model.outputs[0];exact=[float(p.evaluate(v)) for v in pts]+[float(p.partial(i).evaluate(v)) for v in pts for i in range(2)]+[float(p.partial(i).partial(j).evaluate(v)) for v in pts for i in range(2) for j in range(2)]
            assert out['result']['values']==exact
            blobs={name+'.checkpoint.pb':checkpoint.wire,name+'.symbolic.json':model.snapshot(),name+'.request.pb':turn.last_call.wire,name+'.result.pb':turn.last_receipt.result_frame}
            for k,v in blobs.items():(tmp_path/k).write_bytes(v)
            evidence.append(dict(name=name,values=exact,sha256={k:hashlib.sha256(v).hexdigest() for k,v in blobs.items()}))
    (tmp_path/'multivariate_evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf8')


def test_exact_division():
    a=fn(x.add(y));b=fn(m.constant(2,3).add(x));p=m.manipulate('multiply',a,b).result;cert=m.manipulate('divide',p,b);assert m.replay_operation(cert,p,b)==a
    with pytest.raises(ValueError,match='denominator'):m.manipulate('divide',fn(x.multiply(y)),fn(x))
    with pytest.raises(ValueError,match='not polynomial'):m.manipulate('divide',fn(x),b)


def test_atlas_complete_spline_partition():
    g=[-1.,-1.,0.,1.,1.];co=[0.,1.,0.];layer=Layer('spline_clamped',1,[g,g],[[co,co]],[[1,1]],[0.]);c=cp(layer);e=m.extract_atlas(c);f=m.replay_atlas(c,e);assert len(f.cells)==4
    for u,v in [(-1,-1),(0,0),(.5,-.25),(1,1),(-.25,0)]:assert f.evaluate([u,v])==(2-abs(u)-abs(v),)
    cells=list(f.cells);cells[0]=m.Function(cells[0].box,(m.constant(2,7),))
    with pytest.raises(ValueError,match='face'):m.Atlas(f.box,f.cuts,tuple(cells))


def test_atlas_cell_budget():
    g=[-1.,-1.,-.75,-.5,-.25,0.,.25,.5,.75,1.,1.];co=[0.]*(len(g)-2);c=cp(Layer('spline_clamped',1,[g,g,g],[[co,co,co]],[[1,1,1]],[0.]))
    with pytest.raises(ValueError,match='cell budget'):m.extract_atlas(c)


def test_3d_cross_mixed_derivative():
    u,v,w=(m.variable(3,i) for i in range(3));f=m.Function(((-1,1),)*3,(u.multiply(v).multiply(w),));op=m.Operator((('D',0),('D',1),('D',2)));assert m.replay_operation(m.manipulate(op,f),f).evaluate([0,0,0])==(1,)
