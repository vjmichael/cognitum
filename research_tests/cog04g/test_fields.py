from dataclasses import replace
from fractions import Fraction as Q
import hashlib
import json
import pytest
from scipy.integrate import dblquad
from cognitum.mel import kan_fields as s, kan_multivariate as m, polynomial_kan as pk
from cognitum.mel import admission as a, model_reference as r, polynomial_model as pm
from cognitum.research.kan_trainable import Layer,Network

BOX=((-1,1),(-1,1))
x,y=(m.variable(2,i) for i in range(2))
u,v,w=(m.variable(3,i) for i in range(3))
def c(d,a):return m.constant(d,a)
def f(*p,box=BOX):return m.Function(box,p)
def calc(op,*fields):return s.replay(s.certify(op,*fields),*fields)
def quadratic():return f(x.multiply(x).add(y.multiply(y).scale(2)).add(x.multiply(y).scale(3)).add(x.scale(Q(1,2))).add(c(2,Q(1,4))))


def test_gradient():
    z=calc('gradient',quadratic());assert z.evaluate([Q(1,2),Q(-1,4)])==(Q(3,4),Q(1,2));assert z==f(x.scale(2).add(y.scale(3)).add(c(2,Q(1,2))),x.scale(3).add(y.scale(4)))

def test_jacobian():
    a=f(x.multiply(y),x.multiply(x));j=s.jacobian(a);assert j==(f(y,x),f(x.scale(2),c(2,0)))

def test_hessian():
    assert s.hessian(quadratic())==(f(c(2,2),c(2,3)),f(c(2,3),c(2,4)))

def test_rectangular_jacobian():
    j=s.jacobian(f(u,v,w,box=((-1,1),)*3));assert [p.evaluate([0,0,0]) for p in j]==[(1,0,0),(0,1,0),(0,0,1)]

def test_divergence():
    assert calc('divergence',f(x.multiply(x),y.multiply(y)))==f(x.scale(2).add(y.scale(2)))

def test_curl2():
    assert calc('curl',f(y.scale(-1),x))==f(c(2,2))

def test_curl3():
    b=((-1,1),)*3;a=f(v.scale(-1),u, w,box=b);assert calc('curl',a)==f(c(3,0),c(3,0),c(3,2),box=b)

def test_curl_gradient_zero():
    b=((-1,1),)*3;a=f(u.multiply(v).multiply(w),box=b);assert calc('curl',calc('gradient',a))==f(c(3,0),c(3,0),c(3,0),box=b)

def test_div_curl_zero():
    a=f(u.multiply(v),v.multiply(w),w.multiply(u),box=((-1,1),)*3);assert not calc('divergence',calc('curl',a)).outputs[0].terms

def test_laplacian():
    a=quadratic();assert calc('laplacian',a)==f(c(2,6))==calc('divergence',calc('gradient',a))

def test_vector_laplace():
    assert calc('laplacian',f(x.multiply(x),y.multiply(y).scale(2)))==f(c(2,2),c(2,4))

def test_advection():
    assert calc('advection',f(x.multiply(y)),f(x,y))==f(x.multiply(y).scale(2))

def test_vector_advection():
    assert calc('advection',f(x.multiply(y),y.multiply(y)),f(x,y))==f(x.multiply(y).scale(2),y.multiply(y).scale(2))

def test_diffusion():
    assert calc('diffusion',quadratic(),f(x.add(c(2,1))))==f(x.scale(8).add(y.scale(3)).add(c(2,Q(13,2))))

def test_diffusion_constant():
    assert calc('diffusion',quadratic(),f(c(2,2)))==f(c(2,12))

def test_diffusion_mixed():
    a=f(x.multiply(y));k=f(x.multiply(y));assert calc('diffusion',a,k)==f(x.multiply(x).add(y.multiply(y)))

def test_poisson_zero():
    a=calc('poisson_residual',quadratic(),f(c(2,6)));cert=s.residual_certificate(a);assert cert.identically_zero and cert.squared_l2==0 and cert.absolute_upper==(0,);assert s.replay_residual(cert,a)==cert

def test_poisson_nonzero():
    a=calc('poisson_residual',quadratic(),f(c(2,5).add(x)));cert=s.residual_certificate(a);assert not cert.identically_zero and cert.absolute_upper==(2,) and cert.squared_l2==Q(16,3)
    assert abs(float(cert.squared_l2)-dblquad(lambda v,u:(1-u)**2,-1,1,lambda u:-1,lambda u:1)[0])<1e-12

def test_vector_residual_norm():
    cert=s.residual_certificate(f(x,y));assert cert.squared_l2==Q(8,3) and cert.absolute_upper==(1,1)

def test_residual_asymmetric_box():
    a=f(x,box=((1,2),(2,4)));assert s.residual_certificate(a).squared_l2==Q(14,3)

def test_commutator():
    D=s.derivative(2,(1,0));X=s.multiplier(x);I=s.multiplier(c(2,1));assert D.after(X).add(X.after(D).scale(-1))==I
    assert D.after(X).apply(f(x))==f(x.scale(2));assert X.after(D).apply(f(x))==f(x)

def test_mixed_leibniz():
    D=s.derivative(2,(1,1));X=s.multiplier(x.multiply(y));a=f(x.multiply(y));L=D.after(X);assert L.apply(a)==D.apply(X.apply(a))==f(x.multiply(y).scale(4))

def test_biharmonic():
    L=s.laplace_operator(2);p=f(x.multiply(x).multiply(y.multiply(y)));assert L.after(L).apply(p)==f(c(2,8))

def test_operator_linear_combination():
    D=s.derivative(2,(1,0));E=s.derivative(2,(0,1));a=quadratic();assert D.add(E.scale(2)).apply(a)==f(a.outputs[0].partial(0).add(a.outputs[0].partial(1).scale(2)))

def test_operator_cancellation():
    D=s.derivative(2,(1,1));zero=D.add(D.scale(-1));assert zero.terms==() and zero.apply(quadratic())==f(c(2,0)) and zero.identity==s.operator(2,()).identity

def test_operator_multiple_terms():
    D=s.derivative(2,(1,0));E=s.derivative(2,(0,1));X=s.multiplier(x);Y=s.multiplier(y);A=D.add(Y);B=E.add(X);z=quadratic();assert A.after(B).apply(z)==A.apply(B.apply(z))

def test_fourth_order_mixed():
    p=f(x.multiply(x).multiply(y.multiply(y)));assert s.derivative(2,(2,2)).apply(p)==f(c(2,4))

def test_operator_identity_stability():
    D=s.derivative(2,(1,0));X=s.multiplier(x);assert D.add(X).identity==X.add(D).identity!=D.identity

@pytest.mark.parametrize('alpha',[(5,0),(True,0),(-1,1),(0,),[0,1]])
def test_bad_alpha(alpha):
    with pytest.raises(ValueError):s.derivative(2,alpha)

def test_composition_order_refusal():
    with pytest.raises(ValueError,match='order'):s.derivative(2,(3,0)).after(s.derivative(2,(2,0)))

def test_dimension_refusal():
    with pytest.raises(ValueError,match='dimension'):s.derivative(3,(0,0,1)).apply(quadratic())
    with pytest.raises(ValueError,match='dimension'):s.derivative(2,(0,1)).after(s.derivative(3,(0,0,1)))

def test_noncanonical_operator():
    with pytest.raises(ValueError,match='noncanonical'):s.DifferentialOperator(2,(((1,0),x),((1,0),y)))

def test_zero_coefficient_refusal():
    with pytest.raises(ValueError,match='coefficient'):s.DifferentialOperator(2,(((1,0),c(2,0)),))

@pytest.mark.parametrize('op,args', [('gradient',(f(x,y),)),('divergence',(f(x),)),('curl',(f(x),)),('advection',(f(x),f(x))),('poisson_residual',(f(x,y),f(x))),('diffusion',(f(x),f(x,y))),('foo',(f(x),)),('gradient',(f(x),f(y)))])
def test_shape_refusal(op,args):
    with pytest.raises(ValueError):s.certify(op,*args)

def test_domain_refusal():
    with pytest.raises(ValueError,match='domain'):s.certify('diffusion',f(x),f(y,box=((0,1),(0,1))))

def test_atlas_refusal():
    g=[-1.,-1.,0.,1.,1.];cp=pk.export_checkpoint(Network((Layer('spline_clamped',1,[g,g],[[[0,1,0],[0,1,0]]],[[1,1]],[0]),)));atlas=m.replay_atlas(cp,m.extract_atlas(cp))
    with pytest.raises(ValueError,match='single polynomial'):s.certify('gradient',atlas)

def test_tampered_field_witness():
    a=quadratic();w=s.certify('gradient',a)
    with pytest.raises(ValueError,match='witness'):s.replay(replace(w,result=f(x,y)),a)
    with pytest.raises(ValueError,match='witness'):s.replay(w,f(x))

def test_tampered_residual():
    a=f(x);w=s.residual_certificate(a)
    with pytest.raises(ValueError,match='witness'):s.replay_residual(replace(w,squared_l2=Q(0)),a)

def test_independent_oracle_rejects_bad_operator(monkeypatch):
    monkeypatch.setattr(s,'multi_partial',lambda p,a:p)
    with pytest.raises(ValueError,match='identity'):s.derivative(2,(1,0)).apply(f(x.multiply(x)))

def test_independent_oracle_rejects_bad_field(monkeypatch):
    monkeypatch.setattr(s,'_d',lambda p,i:p)
    with pytest.raises(ValueError,match='identity'):s.certify('gradient',f(x.multiply(x)))

def test_independent_oracle_rejects_bad_composition(monkeypatch):
    # In the primary formula a derivative of a coefficient is corrupted.
    monkeypatch.setattr(s,'multi_partial',lambda p,a:p)
    with pytest.raises(ValueError,match='identity'):s.derivative(2,(1,0)).after(s.multiplier(x))

def test_degree_budget():
    p=m.make(2,[((12,0),1)]);op=s.multiplier(x)
    with pytest.raises(ValueError,match='degree'):op.apply(f(p))

def test_work_budget(monkeypatch):
    monkeypatch.setattr(s,'MAX_WORK',1)
    with pytest.raises(ValueError,match='work budget'):s.derivative(2,(1,0)).after(s.multiplier(x))
    with pytest.raises(ValueError,match='work budget'):s.multiplier(x.add(y)).apply(f(x.add(y)))

def test_poisson_residual_negative_control():
    assert not s.residual_certificate(calc('poisson_residual',quadratic(),f(c(2,5)))).identically_zero

def test_immutable_inputs():
    a=quadratic();before=a.snapshot();op=s.derivative(2,(2,0));identity=op.identity
    op.apply(a);op.after(s.multiplier(x));assert a.snapshot()==before and op.identity==identity
    with pytest.raises(AttributeError):op.dimension=3

def test_actual_field_workers(tmp_path):
    source=m.export_quadratic(quadratic());a0=m.replay(source,m.extract(source));k=f(x.add(c(2,1)))
    (tmp_path/'source.checkpoint.pb').write_bytes(source.wire);(tmp_path/'source.symbolic.json').write_bytes(a0.snapshot());(tmp_path/'conductivity.symbolic.json').write_bytes(k.snapshot())
    fields=[('gradient',calc('gradient',a0)),('laplacian',calc('laplacian',a0)),('diffusion',calc('diffusion',a0,k))];rows=[]
    pts=[[.5,-.25],[.25,.5]]
    for name,field in fields:
        cp=m.export_additive(field);assert m.replay(cp,m.extract(cp))==field
        scope=a.Scope('cog04g','lab','owner',name);app=pk.Approval(cp,'scientific-field-review')
        with r.ReferenceTurn(scope,r.Allowed((pk.OP,),tolerance=1e-8,polynomial_approval=app)) as turn:
            out=turn.dispatch(r.canonical(dict(tool=pm.PUBLIC,arguments={'points':pts,'order':0})));assert out['ok'],out
            expected=[float(v) for pt in pts for v in field.evaluate(pt)];assert out['result']['values']==expected
            blobs={name+'.checkpoint.pb':cp.wire,name+'.symbolic.json':field.snapshot(),name+'.request.pb':turn.last_call.wire,name+'.result.pb':turn.last_receipt.result_frame}
            for n,b in blobs.items():(tmp_path/n).write_bytes(b)
            rows.append(dict(name=name,values=expected,sha256={n:hashlib.sha256(b).hexdigest() for n,b in blobs.items()}))
    (tmp_path/'scientific_field_evidence.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
