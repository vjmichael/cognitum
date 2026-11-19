"""Independent witnessed exchange checks. No general function equivalence claims."""
from dataclasses import replace, FrozenInstanceError
import math
import struct
import pytest
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.mel import admission as a, native as n, engines as e, engines_pb2 as ep, model_engines as m
from cognitum.mel import exchange as x, exchange_pb2 as p
from cognitum.mel.engine_limits import HdcLimits, KanLimits

S=a.Scope('session','workspace','subject','turn')

def route(op):return next(r for r in a.routes(include_engines=True) if r.operation==op)
def function(axis='x',unit='1',output='1',domain=(-3.,3.)):
    return n.gaussian([[0.]],[[1.]],[1.],constant=0.,axes=[(axis,unit)],domain=[domain],output_unit=output)
def samples(values=(0.,.5,1.),axis='x',unit='1'):
    return x.from_vfa_points(S,n.points(function(axis,unit),[[v] for v in values]))
def approval(weight=2.):
    layer=ep.KanLayer(inputs=1,outputs=1,knots=3,basis=ep.RBF,grid=[-1.,0.,1.],coefficients=[0.,weight,0.],mask=[1.])
    return m.Approval(m.Checkpoint(m.checkpoint_wire([layer])),'review')
def rehash(obj,fn):
    b=obj.message().body;fn(b);return n.serialize(p.Object(body=b,content_sha256=x.digest(x.DOMAIN+n.serialize(b))))

def test_point_wire_immutable():
    v=samples((-0.,.5,1.));b=v.message().body
    assert b.samples.rows==3 and b.samples.columns==1 and b.assurance==p.SUBMITTED
    assert x._axes(b.samples.axes)==[('x','1')] and b.samples.domain[0].lower==-3
    assert struct.pack('<d',b.samples.values[0])==struct.pack('<d',-0.)
    assert v.identity!=samples((0.,.5,1.)).identity
    b.samples.values[0]=99
    assert v.message().body.samples.values[0]==0
    with pytest.raises(FrozenInstanceError):v.wire=b'bad'

@pytest.mark.parametrize('case',['empty','unknown','truncated','duplicate','hash','oversized','nonminimal'])
def test_bad_wire(case):
    o=samples();r=o.wire;b=o.message();b.content_sha256=b'0'*32
    bad={'empty':b'','unknown':r+b'\x98\x06\x01','truncated':r[:-1],'duplicate':r+b'\x12\x20'+o.message().content_sha256,'hash':n.serialize(b),'oversized':b'x'*(x.MAX_OBJECT+1),'nonminimal':b'\x8a\x00'+r[1:]}[case]
    with pytest.raises(ValueError):x.Object(bad)

@pytest.mark.parametrize('case',['scope','version','origin','assurance','precision','parent','shape','unit','nonfinite','domain','outside','lossy','kernel','checkpoint','transfer','threshold'])
def test_rehashed_invalid_source(case):
    def edit(b):
        if case=='scope':b.scope.turn='bad turn'
        elif case=='version':b.schema_version=2
        elif case=='origin':b.origin=p.HDC_BOUND
        elif case=='assurance':b.assurance=p.EXACT_SUBMITTED_BITS
        elif case=='precision':b.precision=p.PACKED_BITS
        elif case=='transfer':b.transfer_sha256=b'0'*32
        elif case=='parent':b.parents_sha256[0]=b'bad'
        elif case=='shape':b.samples.columns=2
        elif case=='unit':b.samples.axes[0].unit='m/s'
        elif case=='nonfinite':b.samples.values[0]=float('nan')
        elif case=='domain':b.samples.domain[0].ClearField('lower')
        elif case=='outside':b.samples.values[0]=4
        elif case=='lossy':b.lossy_history=True
        elif case=='kernel':b.kernel_git_blob=b'0'*20
        elif case=='checkpoint':b.checkpoint_sha256=b'0'*32
        else:b.threshold.at_least=0
    with pytest.raises(ValueError):x.Object(rehash(samples(),edit))

@pytest.mark.parametrize('field',['session','workspace','subject','turn'])
def test_scope_refusal(field):
    other=replace(S,**{field:'other'})
    with pytest.raises(ValueError):x.threshold(other,samples(),0,'1')
    with pytest.raises(ValueError):x.prepare_vfa(other,samples(),function(),'mel_vfa_evaluate','r')


def test_threshold_and_lift_witness():
    src=samples((-1.,0.,.5,1.,-.5,0.,0.,1.,.5));o=x.threshold(S,src,.5,'1');b=o.message().body
    assert b.bits.packed_bits==bytes([0b10001100,1]) and b.bits.dimension==9
    assert b.lossy_history and b.assurance==p.SUBMITTED and b.parents_sha256==[src.message().content_sha256]
    assert b.threshold.rows==9 and b.threshold.columns==1
    q=x.lift(S,o,3,3);bb=q.message().body
    assert bb.samples.values==[0.,0.,1.,1.,0.,0.,0.,1.,1.]
    assert bb.lossy_history and bb.assurance==p.SUBMITTED
    assert x.verify_derivation(S,src,o) and x.verify_derivation(S,o,q)
    assert q.identity!=src.identity
    with pytest.raises(ValueError):x.verify_derivation(S,samples((0.,)*9),o)

@pytest.mark.parametrize('bad',[True,float('nan'),float('inf'),1e13,'0'],ids=['bool','nan','inf','range','string'])
def test_threshold_invalid_value(bad):
    with pytest.raises(ValueError):x.threshold(S,samples(),bad,'1')


def test_wrong_units_and_shape():
    with pytest.raises(ValueError):x.threshold(S,samples(unit='m'),0,'1')
    o=x.threshold(S,samples(),0,'1')
    for row,col in ((1,2),(True,3),(33,1),(3,0)):
        with pytest.raises(ValueError):x.lift(S,o,row,col)
    with pytest.raises(ValueError):x.threshold(S,o,0,'1')


def test_encoding_profiles():
    o=x.threshold(S,samples(),.5,'1')
    for bad in (x.threshold(S,samples(),0,'1'),x.threshold(S,samples(unit='m'),.5,'m'),x.threshold(S,samples(axis='y'),.5,'1'),x.threshold(S,samples((0.,.5)),.5,'1')):
        with pytest.raises(ValueError):x.prepare_query(S,o,(bad,),'query')
    q=x.prepare_query(S,o,(o,o),'query'); assert x.verify_transfer(S,q,(o,o,o)) and q.message().lossy_history
    assert e.Call('hdc.query',q.message().request_frame).message.query.probe.bits==b'\x06'


def test_exact_width_and_rounding():
    src=samples();app=approval();t=x.prepare_kan(S,src,app,('x',),'k')
    assert t.message().target_checkpoint_sha256.hex()==app.checkpoint.identity
    assert x.verify_transfer(S,t,(src,),approval=app,dimensionless_axes=('x',))
    with pytest.raises(ValueError):x.verify_transfer(S,t,(src,),approval=approval(3.),dimensionless_axes=('x',))
    for bad,names in ((samples((.1,)),('x',)),(samples((1.5,)),('x',)),(samples(unit='m'),('x',)),(src,('other',)),(samples((0.,)*17),('x',)),(samples((1.+2**-30,)),('x',))):
        with pytest.raises(ValueError):x.prepare_kan(S,bad,app,names,'k')


def test_vfa_transfer_compatibility():
    o=samples();f=function();t=x.prepare_vfa(S,o,f,'mel_vfa_gradient','g')
    assert t.message().operation=='vfa.gradient' and x.verify_transfer(S,t,(o,),function=f)
    for bad in (function('y'),function(unit='m'),function(domain=(-.25,.25))):
        with pytest.raises(ValueError):x.prepare_vfa(S,o,bad,'mel_vfa_evaluate','r')


@pytest.mark.parametrize('case',['source','loss','scope','request','descriptor','checkpoint','operation'])
def test_transfer_tamper(case):
    o=samples();f=function();t=x.prepare_vfa(S,o,f,'mel_vfa_evaluate','r');b=t.message()
    if case=='source':b.source_sha256[0]=b'0'*32
    elif case=='loss':b.lossy_history=True
    elif case=='scope':b.scope.workspace='other'
    elif case=='request':b.request_frame=b'bad'
    elif case=='descriptor':b.descriptor_sha256=b'0'*32
    elif case=='checkpoint':b.target_checkpoint_sha256=b'0'*32
    else:b.operation='kan.evaluate'
    with pytest.raises(ValueError):x.verify_transfer(S,x.Transfer(n.serialize(b)),(o,),function=f)


@pytest.fixture(scope='module')
def chain():
    reg=Registry();reg.install(n.NativeVFAPlugin,enabled=True);reg.install(e.EnginePlugin,enabled=True)
    for op in n.OP:reg.nominate(op,n.NAME)
    for op in e.OPERATIONS:reg.nominate(op,e.NAME)
    host=a.Admission(Runtime(reg),S.session,enable_engines=True,enable_model_codecs=True)
    app=approval();pin=host.approve_checkpoint(S,app.checkpoint.wire,expected_sha256=app.checkpoint.identity,review_id=app.review_id)
    source=samples();k=x.prepare_kan(S,source,app,('x',),'k');kt=host.issue(S,route('kan.evaluate'),KanLimits(timeout_ms=10000),ttl_ms=60000,model_codec=True,checkpoint_sha256=pin)
    kr=host.execute(S,kt,'k',k.message().request_frame,timeout_ms=10000);kc=e.Call('kan.evaluate',k.message().request_frame)
    assert kr.status=='completed';kv=x.from_transfer_result(S,k,(source,),kr,approval=app,dimensionless_axes=('x',),output_axes=('x',))
    f=function();v=x.prepare_vfa(S,kv,f,'mel_vfa_evaluate','v');vt=host.issue(S,route('vfa.evaluate'),a.Limits(timeout_ms=10000),ttl_ms=60000)
    vr=host.execute(S,vt,'v',v.message().request_frame,timeout_ms=10000);vc=n.decode_request(v.message().request_frame,'vfa.evaluate');assert vr.status=='completed'
    vv=x.from_transfer_result(S,v,(kv,),vr,function=f);probe=x.threshold(S,vv,.5,'1')
    # A second real VFA result on submitted coordinates, same threshold profile.
    alt=x.prepare_vfa(S,source,f,'mel_vfa_evaluate','alt');at=host.issue(S,route('vfa.evaluate'),a.Limits(timeout_ms=10000),ttl_ms=60000)
    ar=host.execute(S,at,'alt',alt.message().request_frame,timeout_ms=10000);assert ar.status=='completed'
    av=x.from_transfer_result(S,alt,(source,),ar,function=f);candidate=x.threshold(S,av,.5,'1')
    q=x.prepare_query(S,probe,(candidate,probe,probe),'q');qt=host.issue(S,route('hdc.query'),HdcLimits(timeout_ms=10000),ttl_ms=60000)
    qr=host.execute(S,qt,'q',q.message().request_frame,timeout_ms=10000);assert qr.status=='completed'
    bind=m.bind('hdc.bind',None,'{"left":"101","right":"110"}','b',S.turn);bt=host.issue(S,route('hdc.bind'),HdcLimits(timeout_ms=10000),ttl_ms=60000)
    br=host.execute(S,bt,'b',bind.wire,timeout_ms=10000);assert br.status=='completed';bv=x.from_result(S,bind,br)
    # A second numerical call on lossy bit-lift samples must retain the loss flag.
    lifted=x.lift(S,probe,3,1);lf=function('bit0');lt=x.prepare_vfa(S,lifted,lf,'mel_vfa_evaluate','loss');lg=host.issue(S,route('vfa.evaluate'),a.Limits(timeout_ms=10000),ttl_ms=60000)
    lr=host.execute(S,lg,'loss',lt.message().request_frame,timeout_ms=10000);assert lr.status=='completed';lv=x.from_transfer_result(S,lt,(lifted,),lr,function=lf)
    host.close()
    return dict(source=source,k=k,kr=kr,kc=kc,kv=kv,app=app,v=v,vc=vc,vr=vr,vv=vv,probe=probe,candidate=candidate,q=q,qr=qr,bind=bind,br=br,bv=bv,lv=lv,lt=lt,lifted=lifted,lr=lr)


def test_actual_three_engine_chain(chain):
    c=chain;kv=c['kv'].message().body;vv=c['vv'].message().body
    expect=[2*math.exp(-z*z) for z in (0.,.5,1.)]
    assert list(kv.samples.values)==pytest.approx(expect,abs=3e-7)
    assert list(vv.samples.values)==pytest.approx([math.exp(-.5*v*v) for v in kv.samples.values],abs=5e-13)
    assert kv.assurance==vv.assurance==p.NUMERICAL_NOT_CERTIFIED
    assert kv.precision==p.BINARY32_WIDENED and vv.precision==p.BINARY64
    assert kv.transfer_sha256==x.digest(b'cognitum.mel.exchange.v1.Transfer\x00'+c['k'].wire)
    assert kv.checkpoint_sha256.hex()==c['app'].checkpoint.identity
    assert c['probe'].message().body.assurance==p.NUMERICAL_NOT_CERTIFIED
    assert c['probe'].message().body.bits.packed_bits==b'\x04' and c['candidate'].message().body.bits.packed_bits==b'\x07'
    q=ep.EngineResult.FromString(c['qr'].result_frame).query
    assert q.hamming_distance==[2,0,0] and q.best_index==[1,2]
    assert x.verify_transfer(S,c['q'],(c['probe'],c['candidate'],c['probe'],c['probe']))
    assert x.verify_transfer(S,c['v'],(c['kv'],),function=function())


def test_exact_hdc_lift_and_no_mixed_profiles(chain):
    b=chain['bv'];assert b.message().body.bits.packed_bits==b'\x06'
    lift=x.lift(S,b,3,1);bb=lift.message().body
    assert bb.samples.values==[0.,1.,1.] and bb.assurance==p.EXACT_SUBMITTED_BITS and not bb.lossy_history
    t=x.prepare_vfa(S,lift,function('bit0'),'mel_vfa_evaluate','bits-to-vfa');assert x.verify_transfer(S,t,(lift,),function=function('bit0'))
    with pytest.raises(ValueError):x.prepare_query(S,b,(chain['probe'],),'bad')


@pytest.mark.parametrize('case',['scope','status','request','descriptor','request_hash','result_hash','result_frame'])
def test_receipt_tamper(chain,case):
    r=chain['vr'];c=chain['vc']
    change={'scope':{'scope':replace(S,subject='other')},'status':{'status':'cancelled'},'request':{'request_id':'other'},'descriptor':{'descriptor_sha256':'0'*64},'request_hash':{'request_sha256':'0'*64},'result_hash':{'result_sha256':'0'*64},'result_frame':{'result_frame':b'bad','result_sha256':x.digest(b'bad').hex()}}[case]
    with pytest.raises(ValueError):x.from_result(S,c,replace(r,**change))


def test_kan_mapping_refusals(chain):
    c=chain
    for app,axes in ((None,('x',)),(approval(3.),('x',)),(c['app'],None),(c['app'],('x','y')),(c['app'],('m/s',))):
        with pytest.raises(ValueError):x.from_result(S,c['kc'],c['kr'],approval=app,dimensionless_axes=axes)


def test_preparation_never_dispatches(monkeypatch):
    def fail(*args,**kw):raise AssertionError('execution during exchange')
    monkeypatch.setattr(Runtime,'call',fail);monkeypatch.setattr(a.Admission,'execute',fail)
    o=samples();x.prepare_vfa(S,o,function(),'mel_vfa_evaluate','v');x.prepare_kan(S,o,approval(),('x',),'k')
    b=x.threshold(S,o,.5,'1');x.prepare_query(S,b,(b,),'q')


def test_loss_survives_downstream_execution(chain):
    c=chain;b=c['lv'].message().body
    assert b.lossy_history and b.assurance==p.NUMERICAL_NOT_CERTIFIED and b.precision==p.BINARY64
    assert b.transfer_sha256==x.digest(b'cognitum.mel.exchange.v1.Transfer\x00'+c['lt'].wire)
    assert x.threshold(S,c['lv'],.7,'1').message().body.lossy_history
    assert list(b.samples.values)==pytest.approx([1.,1.,math.exp(-.5)],abs=5e-13)
    with pytest.raises(ValueError):x.from_transfer_result(S,c['lt'],(x.lift(S,c['candidate'],3,1),),c['lr'],function=function('bit0'))


def test_hdc_lift_kan_input(chain):
    obj=x.lift(S,chain['bv'],3,1);app=chain['app'];t=x.prepare_kan(S,obj,app,('bit0',),'bits-to-kan')
    assert t.message().target_checkpoint_sha256.hex()==app.checkpoint.identity and not t.message().lossy_history
    assert e.Call('kan.evaluate',t.message().request_frame).message.kan.coordinates==[0.,1.,1.]
    assert x.verify_transfer(S,t,(obj,),approval=app,dimensionless_axes=('bit0',))


def test_transfer_is_not_grant():
    r=Registry();r.install(n.NativeVFAPlugin,enabled=True);r.nominate('vfa.evaluate',n.NAME)
    h=a.Admission(Runtime(r),S.session);t=x.prepare_vfa(S,samples(),function(),'mel_vfa_evaluate','r')
    with pytest.raises(ValueError):h.execute(S,bytes.fromhex(t.identity),'r',t.message().request_frame,timeout_ms=1000)
    h.close()


def test_fabricated_exact_hdc_witness_refused(chain):
    c=chain['bind'];r=chain['br'];b=ep.EngineResult.FromString(r.result_frame);b.bound.bits=b'\x01';raw=n.serialize(b)
    with pytest.raises(ValueError):x.from_result(S,c,replace(r,result_frame=raw,result_sha256=x.digest(raw).hex()))


def test_rehashed_threshold_padding_refused():
    b=x.threshold(S,samples(),0,'1')
    with pytest.raises(ValueError):x.Object(rehash(b,lambda m:setattr(m.bits,'packed_bits',b'\xff')))


def test_source_order_is_bound(chain):
    c=chain
    with pytest.raises(ValueError):x.verify_transfer(S,c['q'],(c['probe'],c['probe'],c['candidate'],c['probe']))
