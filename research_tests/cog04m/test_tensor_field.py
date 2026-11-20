import copy
from fractions import Fraction as Q
from itertools import product
import json
from pathlib import Path
import math
import pytest
import numpy as np
from scipy.interpolate import BSpline
from cognitum.mel import tensor_field as f, tensor_field_pb2 as pb
from cognitum.research import kan_elliptic_certificate as j,kan_transient_certificate as k,kan_spacetime_certificate as l

# Exact manufactured represented fields: J=9*x(1-x)*y(1-y); K=x(1-x);
# L=x(1-x)*y(1-y) (nonzero initial lifts). All homogeneous spatial faces.
def examples():
    c=tuple(int(0<i<3 and 0<a<3) for i,a in product(range(4),repeat=2))
    jp=j.Problem(1,1,0,((0,1,18),(0,2,-18),(1,0,18),(2,0,-18)))
    kp=k.Problem(1,0,((0,0,2),),(0,1,-1))
    lp=l.Problem(1,1,0,((0,1,0,2),(0,2,0,-2),(1,0,0,2),(2,0,0,-2)),((1,1,1),(1,2,-1),(2,1,-1),(2,2,1)))
    return [(j,jp,j.Model((),(),c)),(k,kp,k.Model(j.Model((),(),(0,)*16))),(l,lp,l.Model(((),(),()),(0,)*64))]

@pytest.fixture(params=examples(),ids=['xy','xt','xyt'])
def field(request):
    mod,p,m=request.param;c=mod.assess(p,m);assert c.solution_error_upper==0
    return mod,p,m,c,f.export(p,m,c)

def test_checkpoint_identity(field):
    mod,p,m,c,w=field;assert f.restore(w)==(mod,p,m,c)
    assert f.export(p,m,c)==w
    assert f.uncarrier(f.carrier(w))==w
    assert pb.Checkpoint.FromString(w).model_json==m.checkpoint()

def test_exact_values_and_derivatives(field):
    mod,p,m,c,w=field;rank=3 if mod is l else 2
    value={j:Q(9,16),k:Q(1,4),l:Q(1,16)}[mod]
    for derivative,expected in [((0,)*rank,value),((1,)+(0,)*(rank-1),0),((2,)+(0,)*(rank-1),{j:Q(-9,2),k:Q(-2),l:Q(-1,2)}[mod])]:
        req=f.make_request(w,pb.POINT,(.5,)*rank,derivative=derivative)
        raw=f.execute(w,req);r=pb.Result.FromString(raw)
        assert Q(r.exact_value)==expected and f.replay(w,req,raw)
        assert r.pde_target_error_upper==('0' if not any(derivative) else '')
        assert r.assurance=='represented-function-exact'

def test_full_and_partial_integrals(field):
    mod,p,m,c,w=field;rank=3 if mod is l else 2
    full={j:Q(1,4),k:Q(1,6),l:Q(1,36)}[mod]
    for high,expected in [((1,)*rank,full),((.5,)*rank,full/2**rank)]:
        req=f.make_request(w,pb.BOX_INTEGRAL,(0,)*rank,upper=high)
        result=f.execute(w,req);r=pb.Result.FromString(result)
        assert Q(r.exact_value)==expected and r.pde_target_error_upper=='0' and f.replay(w,req,result)

def test_scope_and_result_rebinding(field):
    mod,_,_,_,w=field;rank=3 if mod is l else 2
    req=f.make_request(w,pb.POINT,(.25,)*rank,derivative=(0,)*rank,request_id='field-a',correlation_id='turn-b')
    raw=f.execute(w,req);r=pb.Result.FromString(raw);assert r.request_id=='field-a' and r.correlation_id=='turn-b'
    other=f.make_request(w,pb.POINT,(.25,)*rank,derivative=(0,)*rank,correlation_id='turn-c')
    with pytest.raises(ValueError):f.replay(w,other,raw)
    r.exact_value='123';
    with pytest.raises(ValueError):f.replay(w,req,f.wire(r))

@pytest.mark.parametrize('bad',['axis','shape','unit','knot','profile','version','basis','layout','arithmetic','model-digest','problem-digest','cert-digest','cert-rehashed','model-rehashed','problem-rehashed','unknown-field','duplicate-field','truncated'],ids=str)
def test_checkpoint_corruption(field,bad):
    _,_,_,_,w=field;c=pb.Checkpoint.FromString(w)
    if bad=='axis':c.axes[0].name='t'
    elif bad=='shape':c.axes[0].basis_count+=1
    elif bad=='unit':c.axes[0].unit='m'
    elif bad=='knot':c.axes[0].interior_knots.append(.5)
    elif bad=='profile':c.profile=0
    elif bad=='version':c.schema_version=2
    elif bad=='basis':c.basis='chebyshev'
    elif bad=='layout':c.layout='column-major'
    elif bad=='arithmetic':c.arithmetic='binary32'
    elif bad=='model-digest':c.model_sha256=b'x'*32
    elif bad=='problem-digest':c.problem_identity=b'x'*32
    elif bad=='cert-digest':c.certificate_sha256=b'x'*32
    elif bad=='cert-rehashed':c.certificate_json=b'{}';c.certificate_sha256=f.digest(c.certificate_json)
    elif bad=='model-rehashed':c.model_json+=b' ';c.model_sha256=f.digest(c.model_json)
    elif bad=='problem-rehashed':c.problem_json+=b' '
    raw=f.wire(c)
    if bad=='unknown-field':raw+=b'\xf8\x07\x01'
    if bad=='duplicate-field':raw+=b'\x08\x01'
    if bad=='truncated':raw=raw[:-1]
    with pytest.raises(ValueError):f.restore(raw)

@pytest.mark.parametrize('case',['bad-rank','nan','outside','derivative','box','wrong-digest','wrong-descriptor','wrong-operation','wrong-id','unknown'],ids=str)
def test_request_corruption(field,case):
    mod,_,_,_,w=field;rank=3 if mod is l else 2
    q=pb.Request.FromString(f.make_request(w,pb.POINT,(.25,)*rank,derivative=(0,)*rank))
    if case=='bad-rank':del q.lower[-1]
    elif case=='nan':q.lower[0]=math.nan
    elif case=='outside':q.lower[0]=2
    elif case=='derivative':q.derivative[0]=3
    elif case=='box':q.operation=pb.BOX_INTEGRAL;q.upper.extend([0]*rank);del q.derivative[:]
    elif case=='wrong-digest':q.checkpoint_sha256=b'x'*32
    elif case=='wrong-descriptor':q.descriptor_sha256=b'x'*32
    elif case=='wrong-operation':q.operation=0
    elif case=='wrong-id':q.request_id='../../foo'
    r=f.wire(q)
    if case=='unknown':r+=b'\xf8\x07\x01'
    with pytest.raises(ValueError):f.execute(w,r)

def test_budget_and_carrier():
    for raw in [b'',b'x'*(f.MAX_FRAME+1)]:
        with pytest.raises(ValueError):f.restore(raw)
    for s in ['?','YQ','YQ==\n','YQ===','']:
        with pytest.raises(ValueError):f.uncarrier(s)

def test_wrong_conditions_refused():
    p=j.Problem(1,1,0,());m=j.Model((),(),(1,)*16)
    c=j.assess(p,m);assert c.residual_upper==0 and c.solution_error_upper is None
    with pytest.raises(ValueError):f.export(p,m,c)

def test_scalar_profile_not_coerced():
    # Scalar protobuf envelope with schema version=1 cannot be interpreted as tensor.
    with pytest.raises(ValueError):f.restore(b'\x08\x01')
    assert f.descriptor()['execution_authorized'] is False and f.descriptor()['lu_registered'] is False

@pytest.mark.parametrize('dim',[2,3])
def test_nonuniform_basis_against_scipy(dim):
    cuts=((.25,),(.5,.75)) if dim==2 else ((.25,),(.5,),(.75,))
    shape=tuple(len(x)+4 for x in cuts);C=np.zeros(shape)
    # Spline correction with exactly zero spatial face coefficients and initial face.
    for idx in product(*(range(1,n-1) for n in shape)):
        C[idx]=(sum(idx)%5-2)/16
    coeff=tuple(map(float,C.ravel()))
    if dim==2:mod=j;p=j.Problem(1,1,0,());m=j.Model(*cuts,coeff)
    else:mod=l;p=l.Problem(1,1,0,(),());m=l.Model(cuts,coeff)
    cert=mod.assess(p,m);w=f.export(p,m,cert);assert cert.solution_error_upper>0
    splines=[BSpline([0]*4+list(c)+[1]*4,np.eye(n),3) for c,n in zip(cuts,shape)]
    for point in [(0.,)*dim,(.25,)*dim,(.5,)*dim,(.75,)*dim,(1.,)*dim,(.125,)*dim]:
        for d in [(0,)*dim,(1,)+(0,)*(dim-1),(1,1)+(0,)*(dim-2)]:
            q=f.make_request(w,pb.POINT,point,derivative=d);r=pb.Result.FromString(f.execute(w,q))
            wts=[s(x,nu=o) for s,x,o in zip(splines,point,d)]
            oracle=sum(C[idx]*math.prod(wts[a][i] for a,i in enumerate(idx)) for idx in product(*(range(n) for n in shape)))
            assert float(Q(r.exact_value))==pytest.approx(oracle,abs=1e-12)
            assert r.pde_target_error_upper==(str(cert.solution_error_upper) if not any(d) else '')
    low,high=(.125,)*dim,(.875,)*dim
    q=f.make_request(w,pb.BOX_INTEGRAL,low,upper=high);r=pb.Result.FromString(f.execute(w,q));wts=[s.integrate(a,b) for s,a,b in zip(splines,low,high)]
    oracle=sum(C[idx]*math.prod(wts[a][i] for a,i in enumerate(idx)) for idx in product(*(range(n) for n in shape)))
    assert float(Q(r.exact_value))==pytest.approx(oracle,abs=1e-12)
    assert Q(r.pde_target_error_upper)==cert.solution_error_upper*Q(3,4)**dim

def test_existing_scalar_protobuf_coexists():
    from cognitum.mel import polynomial_kan_pb2 as scalar
    original=scalar.Checkpoint(schema_version=1);original.layers.add(basis=scalar.CLAMPED_SPLINE,degree=3,inputs=1,outputs=1,knots=8,grid=[0]*4+[1]*4,coefficients=[0,1,1,0],mask=[True],bias=[0])
    raw=f.wire(original);assert scalar.Checkpoint.FromString(raw)==original
    with pytest.raises(ValueError):f.restore(raw)
    assert pb.DESCRIPTOR.package!=scalar.DESCRIPTOR.package

@pytest.mark.parametrize('mode',['good','invalid-envelope','result-binding','malformed-checkpoint'],ids=str)
def test_worker_roundtrip(field,mode):
    import subprocess,sys
    mod,_,_,_,cp=field;rank=3 if mod is l else 2
    req=f.make_request(cp,pb.POINT,(.25,)*rank,derivative=(0,)*rank)
    data=f.canonical(dict(checkpoint=f.carrier(cp),request=f.carrier(req)))
    if mode=='invalid-envelope':data+=b' '
    if mode=='malformed-checkpoint':data=f.canonical(dict(checkpoint=f.carrier(b'\x08\x01'),request=f.carrier(req)))
    proc=subprocess.run([sys.executable,'-m','tools.cog04m.worker'],input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
    if mode in ('invalid-envelope','malformed-checkpoint'):assert proc.returncode==2 and not proc.stdout
    else:
        assert proc.returncode==0 and f.replay(cp,req,proc.stdout)
        if mode=='result-binding':
            modified=pb.Result.FromString(proc.stdout);modified.pde_target_error_upper='123'
            with pytest.raises(ValueError):f.replay(cp,req,f.wire(modified))
