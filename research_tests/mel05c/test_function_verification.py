from fractions import Fraction as F
import math
import numpy as np
import pytest
from cognitum.mel import function_verification as c, native as n, admission as a, model_engines as m, engines as e, engines_pb2 as ep
from cognitum.research.vfa_multivariate import Mixture
from cognitum.research.kan_portable import PortableKAN

S=a.Scope('s','workspace','subject','turn')
BOX=((-1.,1.),)
TOL=(1e-12,1e-12)

def gaussian(centers=((-1.,),(0.,),(1.,)),widths=((2**-.5,),)*3,weights=(.5,1.,-.25),constant=.125,axes=(('x','1'),),domain=BOX):
    return n.gaussian(centers,widths,weights,constant=constant,axes=axes,domain=domain,output_unit='1')

def kan(f=None,review='review',axis='x'):
    return c.KanFunction(m.Approval(c.propose_kan(f or gaussian()),review),axis)

def check_range(obj,seed):
    b=obj.message().body;d=len(b.axes);t=b.shape[0];f=b.function
    box=tuple((z.lower,z.upper) for z in b.domain)
    cert=c.enclose(S,obj,box); assert cert.message().verdict=='enclosed'
    kernel=Mixture(np.array(f.centers).reshape(t,d),np.array(f.weights),np.array(f.widths).reshape(t,d),f.constant)
    rng=np.random.default_rng(seed);xs=rng.uniform([v[0] for v in box],[v[1] for v in box],size=(200,d));yy=np.column_stack((kernel.evaluate(xs),kernel.gradient(xs),kernel.hessian(xs).reshape(-1,d*d)))
    for j,r in enumerate(cert.bounds):
        # This is a floating diagnostic, not the independent proof oracle.
        assert min(yy[:,j])>=float(r.lo)-1e-9 and max(yy[:,j])<=float(r.hi)+1e-9
    assert c.replay(S,obj,cert,box)=='enclosed'

@pytest.mark.parametrize('d',[1,2,3,4])
@pytest.mark.parametrize('seed',[1,5,12])
def test_box_range_against_kernel(d,seed):
    r=np.random.default_rng(seed);f=gaussian(tuple(map(tuple,r.uniform(-1,1,(4,d)).tolist())),tuple(map(tuple,r.uniform(.2,2,(4,d)).tolist())),tuple(r.uniform(-2,2,4).tolist()),axes=tuple((f'x{i}','1') for i in range(d)),domain=BOX*d)
    check_range(f,seed)

@pytest.mark.parametrize('const',[0.,1.,-4.5])
def test_constant_exact(const):
    f=gaussian((),(),(),const);r=c.enclose(S,f,BOX)
    assert r.bounds==(c.P(const),c.P(0),c.P(0))
    assert c.certify(S,f,f,BOX,(0.,0.)).message().verdict=='within'

@pytest.mark.parametrize('direction',['vfa-kan','kan-vfa'])
def test_cross_engine_whole_box(direction):
    f=gaussian();k=kan(f);g=c.propose_vfa(k);s,t=(f,k) if direction=='vfa-kan' else (k,g)
    cert=c.certify(S,s,t,BOX,TOL);assert cert.message().verdict=='within' and cert.message().cells==1
    assert float(cert.bounds[0].hi)<5e-15 and float(cert.bounds[1].hi)<3e-15
    tr=c.verified_target(S,s,t,cert,BOX,TOL)
    assert tr.candidate is t and tr.certificate==cert and tr.covers(S,BOX)
    with pytest.raises(ValueError):tr.covers(S,((-2.,1.),))
    assert c.replay(S,s,cert,BOX,target=t,absolute_tolerance=TOL)=='within'

@pytest.mark.parametrize('offset',[.001,.01,.5])
def test_changed_bias_disproved(offset):
    f=gaussian();g=gaussian(constant=.125+offset);r=c.certify(S,f,g,BOX,(offset/2,1e-12));assert r.message().verdict=='outside'
    with pytest.raises(ValueError):c.verified_target(S,f,g,r,BOX,(offset/2,1e-12))


def test_exact_cancel_and_order():
    f=gaussian(((-1.,),(-1.,),(0.,)),((1.,),(1.,),(2.,)),(1.,-1.,.5),0.)
    g=gaussian(((0.,),),((2.,),),(.5,),0.)
    assert c.certify(S,f,g,BOX,(0.,0.)).message().verdict=='within'


def test_derivative_separate_target():
    f=gaussian(((0.,),),((.01,),),(1.,),0.)
    g=gaussian(((0.,),),((.01,),),(.99,),0.)
    r=c.certify(S,f,g,BOX,(.02,.01),max_cells=128)
    assert r.message().verdict=='outside' # derivative differs away from center


def test_no_sampling_only_success_narrow_peak():
    f=gaussian(((.127,),),((.001,),),(1.,),0.);g=gaussian((),(),(),0.)
    r=c.certify(S,f,g,BOX,(.1,1e12),max_cells=1)
    assert r.message().verdict=='inconclusive' and r.bounds[0].hi>=1
    r=c.certify(S,f,g,BOX,(.1,1e12),max_cells=128)
    assert r.message().verdict=='outside'


def test_subdivision_improves_and_passes():
    f=gaussian(((0.,),),((.6,),),(1.,),0.);g=gaussian(((.01,),),((.6,),),(1.,),0.)
    r=c.certify(S,f,g,BOX,(.04,.1),max_cells=1);assert r.message().verdict=='inconclusive'
    q=c.certify(S,f,g,BOX,(.04,.1),max_cells=128);assert q.message().verdict=='within' and q.message().cells>1

@pytest.mark.parametrize('kind',['source','target','scope','unit','axis','box','tol','budget','review','wire'])
def test_replay_binds_everything(kind):
    f=gaussian();g=kan(f);r=c.certify(S,f,g,BOX,TOL);s=S;b=BOX;t=TOL;k=32
    if kind=='source':f=gaussian(constant=.5)
    elif kind=='target':g=kan(gaussian(constant=.5))
    elif kind=='scope':s=a.Scope('other','workspace','subject','turn')
    elif kind=='unit':f=n.gaussian([[0]],[[1]],[1],constant=0,axes=[('x','m')],domain=[(-1,1)],output_unit='1')
    elif kind=='axis':g=kan(f,axis='other')
    elif kind=='box':b=((-0.5,0.5),)
    elif kind=='tol':t=(1e-11,1e-11)
    elif kind=='budget':k=31
    elif kind=='review':g=kan(f,review='different')
    elif kind=='wire':
        z=r.message();z.bounds[0].upper.numerator='0';z.bounds[0].lower.numerator='0';z.bounds[0].upper.denominator='1';z.bounds[0].lower.denominator='1';r=c.Certificate(n.serialize(z))
    with pytest.raises(ValueError):c.replay(s,f,r,b,target=g,absolute_tolerance=t,max_cells=k)

@pytest.mark.parametrize('box',[((0.,0.),),((-2.,1.),),((float('nan'),1.),),((0,1),),((-.1,.1),(-.1,.1))])
def test_invalid_domains(box):
    with pytest.raises(ValueError):c.enclose(S,gaussian(),box)

@pytest.mark.parametrize('tol',[(-1.,0.),(0.,float('nan')),(0.,),(0.,0.,0.),(True,0.)])
def test_invalid_tolerance(tol):
    with pytest.raises(ValueError):c.certify(S,gaussian(),gaussian(),BOX,tol)

@pytest.mark.parametrize('budget',[0,129,True,1.0])
def test_invalid_budget(budget):
    with pytest.raises(ValueError):c.certify(S,gaussian(),gaussian(),BOX,TOL,max_cells=budget)

@pytest.mark.parametrize('kind',['spline','base','multilayer','multiout','nodomain'])
def test_unsupported_kan(kind):
    l=ep.KanLayer(inputs=1,outputs=1,knots=3,basis=ep.RBF,grid=[-1,0,1],coefficients=[0,1,0],mask=[1])
    layers=[l]
    if kind=='spline':l.basis=ep.BSPLINE;l.degree=0;l.coefficients.pop()
    elif kind=='base':l.base.append(1.)
    elif kind=='multilayer':layers.append(l)
    elif kind=='multiout':l.outputs=2;l.coefficients.extend([0,1,0]);l.mask.append(1)
    elif kind=='nodomain':l.grid[:]=[0.,.5,1.]
    app=m.Approval(m.Checkpoint(m.checkpoint_wire(layers)),'review')
    with pytest.raises(ValueError):
        x=c.KanFunction(app,'x');c.certify(S,gaussian(),x,BOX,TOL)


def test_propose_does_not_approve():
    f=gaussian();q=c.propose_kan(f);assert type(q) is m.Checkpoint
    with pytest.raises(ValueError):c.certify(S,f,q,BOX,TOL)


def test_actual_portable_kernel_and_separate_rounding():
    f=gaussian();k=kan(f);g=c.propose_vfa(k)
    l=k.approval.checkpoint.message().layers; x=np.linspace(-1,1,129,dtype=np.float32).reshape(-1,1)
    inp=ep.KanInput(layers=l,rows=1,coordinates=[0]);layers,_=e.layers_and_input(inp);actual=PortableKAN(layers)(x).ravel()
    b=g.message().body;v=b.function;kernel=Mixture(np.array(v.centers).reshape(3,1),np.array(v.weights),np.array(v.widths).reshape(3,1),v.constant)
    mismatch=float(np.max(np.abs(actual-kernel.evaluate(x))));assert mismatch<3e-7
    # Worker float32 error is separate from the mathematical transform bound.
    assert mismatch>float(c.certify(S,k,g,BOX,TOL).bounds[0].hi)


def test_cancel_during_subdivision():
    n_calls=0
    def stop():
        nonlocal n_calls;n_calls+=1
        if n_calls>=5:raise TimeoutError('cancel')
    with pytest.raises(TimeoutError):c.certify(S,gaussian(((0.,),),((.6,),),(1.,),0.),gaussian(((.01,),),((.6,),),(1.,),0.),BOX,(.04,.1),max_cells=128,check=stop)


def test_noncanonical_and_malformed_certificate():
    r=c.enclose(S,gaussian(),BOX)
    with pytest.raises(ValueError):c.Certificate(r.wire+b'\xa0\x06\x01')
    m=r.message();m.bounds[0].lower.denominator='0'
    with pytest.raises(ValueError):c.Certificate(n.serialize(m))
    m=r.message();m.bounds[0].lower.numerator='0'*200
    with pytest.raises(ValueError):c.Certificate(n.serialize(m))


def test_exact_rational_midpoint_oracle():
    # Independent alternating series at x=1/2, width=1, q=1/8.
    f=gaussian(((0.,),),((1.,),),(2.,),.25)
    q=F(1,8);term=F(1);total=term
    for i in range(1,141):
        term=-term*q/i;total+=term
        if i==139:lo=total
    hi=total
    # Interior point enclosure of value, gradient, Hessian (real formula).
    r=c.enclose(S,f,((.49,.51),)).bounds
    for b,l,h in zip(r,(F(1,4)+2*lo,-hi,-F(3,2)*hi),(F(1,4)+2*hi,-lo,-F(3,2)*lo)):
        assert b.lo<=l<=h<=b.hi


def test_native_worker_use_after_verified_transfer():
    from cognitum.mel import cooperation as g, verified_graph as vg, uncertainty_pb2 as ip
    from research_tests.mel04b.test_cooperation import S as scope, setup
    f=gaussian();k=kan(f);cert=c.certify(scope,f,k,BOX,TOL)
    tr=c.verified_target(scope,f,k,cert,BOX,TOL);assert tr.covers(scope,BOX)
    # Deliberately separate trusted host approval and per-worker grant creation.
    p=g.Plan('function-transfer',scope,(g.Seed('seed',n.points(f,[[-1.],[-.5],[0.],[.5],[1.]])),g.Kan('kan','seed',tr.candidate.approval,('x',),('x',)),g.Vfa('vfa','seed',f)),g.Budget(step_ms=5000))
    h,t=setup(p)
    try:
        assert not h._seen
        bad=gaussian(constant=9.0);badcert=c.certify(scope,bad,k,BOX,TOL)
        with pytest.raises(ValueError):c.verified_target(scope,bad,k,badcert,BOX,TOL)
        assert not h._seen
        outcome=vg.execute_verified(h,p,t,(('kan',(1e-6,)),('vfa',(1e-12,))))
        assert outcome.status=='verified' and outcome.reserved_calls==2
        w=ip.GraphWitness.FromString(outcome.witness);nodes={v.node_id:v for v in w.nodes}
        for v,z in zip(nodes['vfa'].samples,nodes['kan'].samples):
            assert abs(F(v.observed)-F(z.observed))<=cert.bounds[0].hi+F(1e-6)+F(1e-12)
        assert vg.replay(p,outcome.outcome,(('kan',(1e-6,)),('vfa',(1e-12,))),outcome.witness)
    finally:h.close()
