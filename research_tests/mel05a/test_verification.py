"""Independent numerical enclosure and adversarial certificate controls."""
from dataclasses import replace, FrozenInstanceError
from decimal import Decimal, localcontext, ROUND_UP
from fractions import Fraction
import hashlib
import math
import struct
import pytest
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.mel import admission as a, native as n, engines as e, engines_pb2 as ep
from cognitum.mel import verification as v, verification_pb2 as p
from cognitum.mel.engine_limits import HdcLimits, KanLimits

S=a.Scope('verify-session','workspace','subject','turn')

def call(name='mel_vfa_evaluate',points=((0.,),(.5,),(1.,)),centers=((0.,),),widths=((1.,),),weights=(1.,),constant=0.,axes=(('x','m'),),domain=((-3.,3.),),rid='v'):
    f=n.gaussian(centers,widths,weights,constant=constant,axes=axes,domain=domain,output_unit='K')
    return n.make_call(name,f,n.points(f,points),rid,S.turn)

def honest_fixture(c,values):
    # Synthetic receipt deliberately able to carry WRONG numerical values.
    # Structural lineage alone does not attest mathematical correctness.
    r=n.result_object(c.operation,c.function,c.points,list(values));raw=n.serialize(n.pb.VfaResult(schema_version=1,operation=n.OP[c.operation],descriptor_sha256=bytes.fromhex(c.descriptor_sha256),request_id=c.request_id,correlation_id=c.correlation_id,result=r.message()))
    return a.Receipt(S,c.request_id,c.operation,c.descriptor_sha256,hashlib.sha256(c.wire()).hexdigest(),'completed',raw,hashlib.sha256(raw).hexdigest())

@pytest.fixture(scope='module')
def actual():
    r=Registry();r.install(n.NativeVFAPlugin,enabled=True);r.install(e.EnginePlugin,enabled=True)
    for op in n.OP:r.nominate(op,n.NAME)
    for op in e.OPERATIONS:r.nominate(op,e.NAME)
    h=a.Admission(Runtime(r),S.session,enable_engines=True)
    def execute(c,limits):
        route=next(x for x in a.routes(include_engines=True) if x.operation==c.operation);t=h.issue(S,route,limits,ttl_ms=60000)
        wire=c.wire() if type(c) is n.NativeCall else c.wire;rid=c.request_id if type(c) is n.NativeCall else c.message.request_id
        rec=h.execute(S,t,rid,wire,timeout_ms=10000);assert rec.status=='completed';return rec
    c=call(rid='value');g=call('mel_vfa_gradient',rid='gradient')
    b=e.make_call('hdc.bind',ep.BindInput(left=ep.BinaryVector(dimension=5,bits=b'\x15'),right=ep.BinaryVector(dimension=5,bits=b'\x03')),'bind',S.turn)
    q=e.make_call('hdc.query',ep.QueryInput(probe=ep.BinaryVector(dimension=5,bits=b'\x15'),candidates=[ep.BinaryVector(dimension=5,bits=z) for z in (b'\x03',b'\x15',b'\x15')]),'query',S.turn)
    k=e.make_call('kan.evaluate',ep.KanInput(layers=[ep.KanLayer(inputs=1,outputs=1,knots=3,basis=ep.RBF,grid=[-1.,0.,1.],coefficients=[0.,1.,0.],mask=[1.])],rows=1,coordinates=[0.]),'kan',S.turn)
    out=[(c,execute(c,a.Limits(timeout_ms=10000))),(g,execute(g,a.Limits(timeout_ms=10000))),(b,execute(b,HdcLimits(timeout_ms=10000))),(q,execute(q,HdcLimits(timeout_ms=10000))),(k,execute(k,KanLimits(timeout_ms=10000)))];h.close();return out


def rational_exp_bounds(q):
    # Independent exact alternating Taylor bound for 0 <= q <= 1.
    term=Fraction(1);total=term
    for i in range(1,141):
        term=-term*q/i;total+=term
        if i==139:lower=total
    return lower,total

@pytest.mark.parametrize('q',[Fraction(0),Fraction(1,1024),Fraction(1,8),Fraction(1,2),Fraction(1)])
def test_exp_encloses_independent_rational_oracle(q):
    lo,hi=v._Arithmetic().exp_negative(q);rlo,rhi=rational_exp_bounds(q)
    assert Fraction(lo)<=rlo<=rhi<=Fraction(hi)

@pytest.mark.parametrize('q',[Fraction(256),Fraction(257),Fraction(10**21)])
def test_tail_bound(q):
    lo,hi=v._Arithmetic().exp_negative(q)
    assert lo==0 and Fraction(hi)>=Fraction(1,2**256)
    assert Fraction(hi)<Fraction(1,2**255)

@pytest.mark.parametrize('index',[0,1])
def test_real_vfa_worker(actual,index):
    c,r=actual[index];cert=v.certify_vfa(S,c,r,(1e-12,));b=cert.message()
    assert b.verdict==p.WITHIN_TOLERANCE and b.represented_inputs_only
    assert b.shape==([3] if index==0 else [3,1]) and b.units[0].denominator==('1' if index==0 else 'm')
    assert v.replay(S,c,r,cert,absolute_tolerance=(1e-12,))==p.WITHIN_TOLERANCE
    for i,comp in enumerate(b.components):
        q=Fraction(i,2)**2/2;rlo,rhi=rational_exp_bounds(q)
        if index:rlo,rhi=-Fraction(i,2)*rhi,-Fraction(i,2)*rlo
        assert Fraction(Decimal(comp.lower))<=rlo<=rhi<=Fraction(Decimal(comp.upper))
        y=Fraction(comp.observed);err_hi=max(abs(y-rlo),abs(y-rhi))
        assert Fraction(Decimal(comp.absolute_error_upper))>=err_hi

@pytest.mark.parametrize('index',[2,3])
def test_real_hdc_worker(actual,index):
    c,r=actual[index];cert=v.certify_hdc(S,c,r)
    assert cert.message().verdict==p.EXACT_SUBMITTED_BITS and v.replay(S,c,r,cert)==p.EXACT_SUBMITTED_BITS
    assert cert.message().shape==([5] if index==2 else [3])


def test_kan_not_certified(actual):
    c,r=actual[4]
    with pytest.raises(ValueError):v.certify_hdc(S,c,r)
    with pytest.raises(ValueError):v.certify_vfa(S,c,r,(1e-12,))


def test_valid_lineage_does_not_certify_bad_value():
    c=call(points=((0.,),));r=honest_fixture(c,(2.,));cert=v.certify_vfa(S,c,r,(.01,));b=cert.message()
    assert b.verdict==p.OUTSIDE_TOLERANCE
    assert Decimal(b.components[0].absolute_error_lower)==1
    assert v.replay(S,c,r,cert,absolute_tolerance=(.01,))==p.OUTSIDE_TOLERANCE


def test_exact_absolute_tolerance_boundary():
    c=call(points=((0.,),),centers=(),widths=(),weights=(),constant=1.)
    r=honest_fixture(c,(1.25,));assert v.certify_vfa(S,c,r,(.25,)).message().verdict==p.WITHIN_TOLERANCE
    assert v.certify_vfa(S,c,r,(math.nextafter(.25,0.),)).message().verdict==p.OUTSIDE_TOLERANCE


def test_tail_inconclusive_not_exact():
    c=call(points=((1000.,),),constant=1.,domain=((-2000.,2000.),));r=honest_fixture(c,(1.,))
    cert=v.certify_vfa(S,c,r,(0.,));assert cert.message().verdict==p.INCONCLUSIVE
    assert v.certify_vfa(S,c,r,(1e-70,)).message().verdict==p.WITHIN_TOLERANCE


def test_signed_zero_constant_gradient():
    c=call('mel_vfa_gradient',points=((-0.,),),centers=(),widths=(),weights=(),constant=-0.)
    r=honest_fixture(c,(-0.,));cert=v.certify_vfa(S,c,r,(0.,));b=cert.message();assert b.verdict==p.WITHIN_TOLERANCE
    assert struct.pack('<d',b.components[0].observed)==struct.pack('<d',-0.)
    assert b.components[0].HasField('observed')


def test_multidimensional_negative_weight_gradient_units():
    c=call('mel_vfa_gradient',points=((.5,1.),),centers=((0.,0.),),widths=((1.,2.),),weights=(-2.,),axes=(('x','m'),('t','s')),domain=((-2.,2.),(-2.,2.)))
    y=math.exp(-.25);r=honest_fixture(c,(y,.5*y));b=v.certify_vfa(S,c,r,(1e-12,1e-13)).message()
    assert b.verdict==p.WITHIN_TOLERANCE and [(w.numerator,w.denominator) for w in b.units]==[('K','m'),('K','s')]
    rlo,rhi=rational_exp_bounds(Fraction(1,4));assert Fraction(Decimal(b.components[0].lower))<=rlo<=rhi<=Fraction(Decimal(b.components[0].upper))
    assert Fraction(Decimal(b.components[1].lower))<=rlo/2<=rhi/2<=Fraction(Decimal(b.components[1].upper))


def test_cancellation_and_subnormal_exact_inputs():
    tiny=math.ulp(0.);c=call(points=((tiny,),),centers=((0.,),(0.,)),widths=((1.,),(1.,)),weights=(1.,-1.),constant=tiny)
    r=honest_fixture(c,(tiny,));cert=v.certify_vfa(S,c,r,(1e-70,));b=cert.message();assert b.verdict==p.WITHIN_TOLERANCE
    assert Fraction(Decimal(b.components[0].lower))<=Fraction(tiny)<=Fraction(Decimal(b.components[0].upper))


@pytest.mark.parametrize('tol',[(),(True,),(-1.,),(float('nan'),),(float('inf'),),('1',),(1e13,),[1.],(1.,2.)],ids=['empty','bool','negative','nan','inf','string','large','list','width'])
def test_tolerance_validation(tol):
    c=call(points=((0.,),));r=honest_fixture(c,(1.,))
    with pytest.raises(ValueError):v.certify_vfa(S,c,r,tol)

@pytest.mark.parametrize('what',['terms','points'])
def test_verification_budget(what):
    kw={'centers':((0.,),)*33,'widths':((1.,),)*33,'weights':(1.,)*33} if what=='terms' else {'points':((0.,),)*17}
    c=call(**kw);r=honest_fixture(c,(0.,)*c.points.message().body.shape[0]);
    with pytest.raises(ValueError,match='budget'):v.certify_vfa(S,c,r,(1.,))

@pytest.mark.parametrize('field',['scope','request_id','operation','descriptor_sha256','request_sha256','result_sha256','status','result_frame'])
def test_unbound_receipt_refused(field):
    c=call(points=((0.,),));r=honest_fixture(c,(1.,));vals={'scope':replace(S,turn='different'),'request_id':'other','operation':'vfa.gradient','descriptor_sha256':'0'*64,'request_sha256':'0'*64,'result_sha256':'0'*64,'status':'cancelled','result_frame':b'bad'}
    with pytest.raises(ValueError):v.certify_vfa(S,c,replace(r,**{field:vals[field]}),(1.,))

@pytest.mark.parametrize('case',['version','method','precision','shape','units','tolerance','observation','nan','order','error','verdict','unsupported','represented'])
def test_structural_certificate_refusal(case):
    c=call(points=((0.,),));r=honest_fixture(c,(1.,));b=v.certify_vfa(S,c,r,(1e-12,)).message()
    if case=='version':b.schema_version=2
    elif case=='method':b.method='unreviewed'
    elif case=='precision':b.decimal_digits=1
    elif case=='shape':b.shape[0]=2
    elif case=='units':b.units[0].numerator='K/s'
    elif case=='tolerance':b.absolute_tolerance[0]=-1
    elif case=='observation':b.components[0].ClearField('observed')
    elif case=='nan':b.components[0].lower='NaN'
    elif case=='order':b.components[0].lower='2'
    elif case=='error':b.components[0].absolute_error_upper='1'
    elif case=='verdict':b.verdict=p.OUTSIDE_TOLERANCE
    elif case=='unsupported':b.operation='kan.evaluate'
    else:b.represented_inputs_only=False
    with pytest.raises(ValueError):v.Certificate(n.serialize(b))

@pytest.mark.parametrize('case',['empty','unknown','duplicate','truncated','oversized'])
def test_wire_refusal(case):
    c=call(points=((0.,),));r=honest_fixture(c,(1.,));raw=v.certify_vfa(S,c,r,(1e-12,)).wire
    bad={'empty':b'','unknown':raw+b'\x98\x06\x01','duplicate':raw+b'\x08\x01','truncated':raw[:-1],'oversized':b'x'*(v.MAX_CERTIFICATE+1)}[case]
    with pytest.raises(ValueError):v.Certificate(bad)


def test_self_asserted_certificate_not_authority():
    c=call(points=((0.,),));r=honest_fixture(c,(2.,));b=v.certify_vfa(S,c,r,(0.,)).message();b.components[0].lower=b.components[0].upper='2';b.components[0].absolute_error_lower=b.components[0].absolute_error_upper='0';b.verdict=p.WITHIN_TOLERANCE
    # Internally consistent forgery passes structural parsing, but not replay.
    forged=v.Certificate(n.serialize(b));assert forged.message().verdict==p.WITHIN_TOLERANCE
    with pytest.raises(ValueError,match='replay mismatch'):v.replay(S,c,r,forged,absolute_tolerance=(0.,))


def test_replay_tolerance_independent_and_immutable():
    c=call(points=((0.,),));r=honest_fixture(c,(1.,));cert=v.certify_vfa(S,c,r,(0.,));msg=cert.message();msg.scope.turn='other'
    assert cert.message().scope.turn==S.turn
    with pytest.raises(FrozenInstanceError):cert.wire=b'bad'
    with pytest.raises(ValueError):v.replay(S,c,r,cert,absolute_tolerance=(1.,))
    assert cert.identity==v.certify_vfa(S,c,r,(0.,)).identity


def test_context_independence():
    c=call();r=honest_fixture(c,(1.,.8,.6));cert=v.certify_vfa(S,c,r,(.1,))
    with localcontext() as ctx:
        ctx.prec=2;ctx.rounding=ROUND_UP
        assert v.certify_vfa(S,c,r,(.1,)).wire==cert.wire

@pytest.mark.parametrize('index',[2,3])
def test_bad_hdc_mathematical_witness(actual,index):
    c,r=actual[index];b=ep.EngineResult.FromString(r.result_frame)
    if index==2:b.bound.bits=b'\x00'
    else:b.query.best_index[:]=[0]
    raw=n.serialize(b);f=replace(r,result_frame=raw,result_sha256=hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError):v.certify_hdc(S,c,f)


def test_maximum_supported_gradient_shape():
    # Full verifier profile, large/small widths and strongly decayed terms.
    d=8;t=32;rows=16
    c=call('mel_vfa_gradient',points=((.5,)*d,)*rows,centers=((0.,)*d,)*t,widths=((1.,.001,1000.,1.,.5,2.,1.,1.),)*t,weights=(1.,-1.)*16,axes=tuple((f'x{i}','m') for i in range(d)),domain=((-1.,1.),)*d)
    r=honest_fixture(c,(0.,)*(d*rows));cert=v.certify_vfa(S,c,r,(1e-65,)*d);b=cert.message()
    assert b.verdict==p.WITHIN_TOLERANCE and len(b.components)==128 and len(cert.wire)<=v.MAX_CERTIFICATE
    assert all(Decimal(comp.lower)<=0<=Decimal(comp.upper) for comp in b.components)


def test_multiple_terms_exact_independent_mixture_oracle():
    c=call(points=((.5,),),centers=((0.,),(1.,),(.5,)),widths=((1.,),(1.,),(2.,)),weights=(3.,-1.,-.5),constant=.25)
    r=honest_fixture(c,(2*math.exp(-.125)-.25,));comp=v.certify_vfa(S,c,r,(1e-13,)).message().components[0]
    lo,hi=rational_exp_bounds(Fraction(1,8));assert Fraction(Decimal(comp.lower))<=2*lo-Fraction(1,4)<=2*hi-Fraction(1,4)<=Fraction(Decimal(comp.upper))


def test_default_context_independence():
    from decimal import DefaultContext, Inexact
    c=call();r=honest_fixture(c,(1.,.8,.6));expected=v.certify_vfa(S,c,r,(.1,)).wire;old=DefaultContext.traps[Inexact];prec=DefaultContext.prec
    try:
        DefaultContext.traps[Inexact]=True;DefaultContext.prec=3
        assert v.certify_vfa(S,c,r,(.1,)).wire==expected
    finally:DefaultContext.traps[Inexact]=old;DefaultContext.prec=prec


def test_small_interval_scientific_wire():
    # A small but nonzero result must not exceed the fixed significant-digit
    # budget merely because fixed-point notation inserts leading zeroes.
    c=call(points=((0.,),),weights=(.001,),constant=-.0009999)
    r=honest_fixture(c,(1e-7,));cert=v.certify_vfa(S,c,r,(1e-15,))
    assert cert.message().verdict==p.WITHIN_TOLERANCE
    assert all('E' in getattr(cert.message().components[0],field) for field in ('lower','upper','absolute_error_lower','absolute_error_upper'))
    assert v.replay(S,c,r,cert,absolute_tolerance=(1e-15,))==p.WITHIN_TOLERANCE
