from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
from threading import Event
from time import monotonic, sleep
import math
import pytest

from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.mel import admission as a, native as n, engines as e, engines_pb2 as pb
from cognitum.mel.engine_limits import HdcLimits, KanLimits, account, MAX_HDC_WORK, MAX_KAN_PARAMETERS, MAX_KAN_WORK
from cognitum.mel.native import serialize, encode_carrier

S=a.Scope('session','ws','user','turn')
B='hdc.bind';Q='hdc.query';K='kan.evaluate'


def v(value=5,dim=5):return pb.BinaryVector(dimension=dim,bits=value.to_bytes((dim+7)//8,'little'))


def layer(*,width=1,knots=3,spline=False,full=False):
    k=knots;w=width;b=k-2 if spline else k
    return pb.KanLayer(inputs=w,outputs=w,knots=k,basis=pb.BSPLINE if spline else pb.RBF,degree=1 if spline else 0,
        grid=[float(x) for x in range(k)]*w,coefficients=[.125]*(w*w*b),mask=[0. if full else 1.]*(w*w),
        base=[.1]*(w*w) if full else [],bias=[.1]*w if full else [])


def make(op,request='request',turn='turn',**kw):
    if op==B:inp=pb.BindInput(left=v(5,kw.get('dim',5)),right=v(3,kw.get('dim',5)))
    elif op==Q:inp=pb.QueryInput(probe=v(5,kw.get('dim',5)),candidates=[v(4,kw.get('dim',5))]*kw.get('count',3))
    else:
        w=kw.get('width',1);r=kw.get('rows',2);l=kw.get('layers',1)
        inp=pb.KanInput(layers=[layer(width=w,knots=kw.get('knots',3),spline=kw.get('spline',False),full=kw.get('full',False))]*l,rows=r,coordinates=[0.]*r*w)
    return e.make_call(op,inp,request,turn)


def route(op):return next(x for x in a.routes(include_engines=True) if x.operation==op)


def limits(op,**kw):return (KanLimits if op==K else HdcLimits)(timeout_ms=8000,**kw)


def setup(enabled=True):
    r=Registry();r.install(e.EnginePlugin,enabled=enabled)
    for op in e.OPERATIONS:r.nominate(op,e.NAME)
    r.install(n.NativeVFAPlugin,enabled=True)
    for op in n.OP:r.nominate(op,n.NAME)
    return r,a.Admission(Runtime(r),'session',enable_engines=True)


@pytest.fixture(scope='module')
def registry():return setup()[0]


@pytest.fixture
def host(registry):return a.Admission(Runtime(registry),'session',enable_engines=True)


def grant(h,op,lim=None):return h.issue(S,route(op),lim or limits(op),ttl_ms=20000)


def submit(h,t,c,scope=S,timeout=8000):return h.execute(scope,t,c.message.request_id,c.wire,timeout_ms=timeout)


@pytest.mark.parametrize('op',[B,Q,K])
def test_real_scoped_worker(host,op):
    c=make(op);t=grant(host,op);offer=host.discover(S,t)
    assert offer['model_advertised'] is False and 'tool_schema' not in offer and 'grant' not in offer
    assert offer['descriptor']['execution_authorized'] is False and offer['descriptor_sha256']==route(op).descriptor_sha256
    r=submit(host,t,c);assert r.status=='completed' and r.scope==S and r.operation==op
    assert r.request_sha256==hashlib.sha256(c.wire).hexdigest() and r.result_sha256==hashlib.sha256(r.result_frame).hexdigest()
    m=pb.EngineResult.FromString(r.result_frame);assert m.request_sha256==bytes.fromhex(r.request_sha256)
    if op==B:assert m.bound.bits==b'\x06' and m.assurance=='exact_arithmetic'
    elif op==Q:assert list(m.query.hamming_distance)==[1]*3 and list(m.query.best_index)==[0,1,2]
    else:assert list(m.kan.values)==pytest.approx([.125*(1+math.exp(-1)+math.exp(-4))]*2,abs=1e-6) and m.assurance=='numerical'
    assert submit(host,t,c).status=='replay_denied'


def test_default_off_and_distinct_profiles(registry):
    h=a.Admission(Runtime(registry),'session')
    assert len(a.routes())==2 and len(a.routes(include_engines=True))==5
    with pytest.raises(ValueError):h.issue(S,route(B),limits(B))
    with pytest.raises(ValueError):a.Admission(Runtime(registry),'session',enable_engines=1)
    h=a.Admission(Runtime(registry),'session',enable_engines=True)
    for op,bad in [(B,a.Limits()),(Q,KanLimits()),(K,HdcLimits()),('vfa.evaluate',HdcLimits())]:
        with pytest.raises(ValueError):h.issue(S,route(op),bad)


@pytest.mark.parametrize('field',['effect','descriptor_sha256','input_type_url','output_type_url','operation_version','public_name'])
def test_forged_route(host,field):
    with pytest.raises(ValueError):host.issue(S,replace(route(B),**{field:'forged'}),limits(B))


@pytest.mark.parametrize('op',[B,Q,K])
def test_scope_and_cross_operation_refusal(host,op):
    t=grant(host,op);c=make(op)
    for field in ('session','workspace','subject','turn'):
        with pytest.raises(ValueError):submit(host,t,c,replace(S,**{field:'alien'}))
    for other in {B,Q,K}-{op}:assert submit(host,t,make(other)).status=='invalid_input'
    assert submit(host,t,make(op,turn='alien')).status=='invalid_input'
    assert host.execute(S,t,'other',c.wire,timeout_ms=8000).status=='invalid_input'
    assert not host._seen


@pytest.mark.parametrize('op,kw,lim',[(B,{'dim':8},HdcLimits(dimensions=7)),(Q,{'count':3},HdcLimits(candidates=2)),(K,{'rows':2},KanLimits(rows=1)),(K,{'layers':2},KanLimits(layers=1)),(K,{'width':2},KanLimits(width=1)),(K,{'knots':4},KanLimits(knots=3)),(K,{'full':True},KanLimits(parameters=7))],ids=['dimension','candidates','rows','layers','width','knots','parameters'])
def test_resource_denial_before_reserve(host,monkeypatch,op,kw,lim):
    c=make(op,**kw);t=grant(host,op,replace(lim,timeout_ms=8000));calls=[]
    monkeypatch.setattr(Runtime,'call',lambda *args,**kw:calls.append(1))
    r=submit(host,t,c);assert r.status=='resource_denied' and r.result_frame is None
    assert not calls and not host._seen and host._grants[t].work_left==lim.work


@pytest.mark.parametrize('op,expected',[(B,20),(Q,63),(K,84)])
def test_exact_work_and_cumulative(host,op,expected):
    c=make(op);assert account(c,limits(op))==expected
    t=grant(host,op,limits(op,calls=3,work=2*expected))
    assert submit(host,t,c).status=='completed'
    assert submit(host,t,make(op,request='second')).status=='completed'
    assert submit(host,t,make(op,request='third')).status=='resource_denied'
    assert host._grants[t].calls_left==1 and host._grants[t].work_left==0


@pytest.mark.parametrize('op',[B,Q,K])
def test_byte_time_and_work_boundaries(host,op):
    c=make(op);w=account(c,limits(op))
    for lim in (limits(op,request_bytes=len(c.wire)-1),limits(op,work=w-1)):
        assert submit(host,grant(host,op,lim),c).status=='resource_denied'
    t=grant(host,op,replace(limits(op),timeout_ms=100))
    assert submit(host,t,c,timeout=101).status=='resource_denied'
    assert not host._seen
    t=grant(host,op,limits(op,result_bytes=1,work=w));r=submit(host,t,c)
    assert r.status=='resource_denied' and r.result_frame is None and r.result_sha256 is None
    assert host._grants[t].work_left==0 and submit(host,t,c).status=='replay_denied'


def test_masked_and_multilayer_work():
    c=make(K,rows=16,width=8,knots=12,layers=2,full=True)
    assert account(c,KanLimits(parameters=MAX_KAN_PARAMETERS-1)) is None
    assert account(c,KanLimits())==4*(MAX_KAN_PARAMETERS+16*2*(8*12+8*12*8+8*8+8))<=MAX_KAN_WORK
    b=make(K,rows=4,width=2,knots=6,layers=2,spline=True)
    # Per layer: 12 grid + 16 coeff + 4 mask; row work 24+16+2.
    assert account(b,KanLimits())==4*(64+4*84)
    q=make(Q,dim=4096,count=16);assert account(q,HdcLimits())==MAX_HDC_WORK


@pytest.mark.parametrize('op',[B,Q,K])
def test_invalid_and_replaced_registry(op):
    registry,h=setup(False)
    with pytest.raises(ValueError):grant(h,op)
    registry.enable(e.NAME);t=grant(h,op);registry.enable(e.NAME,False);registry.enable(e.NAME,True)
    with pytest.raises(ValueError):h.discover(S,t)
    assert submit(h,t,make(op)).status=='unavailable'
    fresh=grant(h,op);assert submit(h,fresh,make(op,request='fresh')).status=='completed'


def test_global_replay_across_all_engines(host):
    t=grant(host,B);assert submit(host,t,make(B)).status=='completed'
    assert submit(host,grant(host,Q),make(Q)).status=='replay_denied'
    vroute=route('vfa.evaluate');u=host.issue(S,vroute,a.Limits(timeout_ms=8000),ttl_ms=20000)
    f=n.gaussian([],[],[],constant=3.,axes=[('x','1')],domain=[(-1.,1.)],output_unit='1')
    c=n.make_call(vroute.public_name,f,n.points(f,[[0.]]),'request','turn')
    assert host.execute(S,u,'request',c.wire(),timeout_ms=8000).status=='replay_denied'


def wait_active(host,request):
    until=monotonic()+4
    while monotonic()<until:
        with host._lock:
            if (S,request) in host._active:return
        sleep(.005)
    raise AssertionError('admission not reserved')


@pytest.mark.parametrize('op',[B,Q,K])
def test_queue_cancel_and_deadline(op,monkeypatch):
    registry,h=setup();t=grant(h,op,limits(op,calls=2,work=2*account(make(op),limits(op))))
    calls=[];monkeypatch.setattr(Runtime,'call',lambda *args,**kw:calls.append(1))
    with ThreadPoolExecutor(1) as pool:
        with registry.lock:
            f=pool.submit(submit,h,t,make(op));wait_active(h,'request')
            assert not h.cancel(replace(S,subject='alien'),'request') and h.cancel(S,'request')
            r=f.result(timeout=4);assert r.status=='cancelled' and r.result_frame is None
            f=pool.submit(submit,h,t,make(op,request='late'),S,150)
            assert f.result(timeout=4).status=='timed_out'
    assert not calls and not h._active and h._grants[t].calls_left==0 and h._grants[t].work_left==0


@pytest.mark.parametrize('op,action',[(B,'revoke'),(Q,'cancel'),(K,'close')])
def test_inflight_result_suppression(op,action,monkeypatch):
    registry,h=setup();t=grant(h,op);ready=Event();release=Event();orig=Runtime.call
    def delayed(*args,**kw):
        r=orig(*args,**kw);assert r.execution_status=='completed';ready.set();assert release.wait(5);return r
    monkeypatch.setattr(Runtime,'call',delayed)
    with ThreadPoolExecutor(1) as pool:
        f=pool.submit(submit,h,t,make(op))
        try:
            assert ready.wait(10)
            if action=='revoke':assert h.revoke(S,t)
            elif action=='cancel':assert h.cancel(S,'request')
            else:h.close()
        finally:release.set()
        r=f.result(timeout=8)
    assert r.status==('cancelled' if action=='cancel' else 'revoked') and r.result_frame is None and not h._active
    assert h._grants[t].calls_left==0


@pytest.mark.parametrize('op',[B,Q,K])
def test_corrupted_result_rejected(host,op,monkeypatch):
    t=grant(host,op);orig=Runtime.call
    def altered(*args,**kw):
        r=orig(*args,**kw);assert r.execution_status=='completed';m=pb.EngineResult.FromString(e.decode_carrier(r.result['frame'],e.MAX_RESULT))
        if op==B:m.bound.bits=b'\x00'
        elif op==Q:m.query.best_index[:]=[0]
        else:m.request_sha256=b'\0'*32
        return replace(r,result={'frame':encode_carrier(serialize(m),e.MAX_RESULT)})
    monkeypatch.setattr(Runtime,'call',altered)
    r=submit(host,t,make(op));assert r.status=='error' and r.result_frame is None and r.result_sha256 is None


@pytest.mark.parametrize('cls,kw',[(HdcLimits,{'dimensions':True}),(HdcLimits,{'candidates':17}),(HdcLimits,{'work':0}),(KanLimits,{'parameters':0}),(KanLimits,{'layers':3}),(KanLimits,{'rows':17}),(KanLimits,{'knots':2}),(KanLimits,{'width':True}),(KanLimits,{'calls':17}),(KanLimits,{'request_bytes':e.MAX_REQUEST+1})],ids=[f'limit{i}' for i in range(10)])
def test_invalid_limits(cls,kw):
    with pytest.raises(ValueError):cls(**kw)
