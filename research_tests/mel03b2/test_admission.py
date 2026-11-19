from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace, FrozenInstanceError
import hashlib
import json
from threading import Event
from time import monotonic, sleep
import pytest

from cognitum.contracts import Response
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.mel import native as n
from cognitum.mel import mel_pb2 as pb
from cognitum.mel import admission as a

S=a.Scope('session','workspace','subject','turn')
E='mel_vfa_evaluate';G='mel_vfa_gradient'


def route(name=E):return next(r for r in a.routes() if r.public_name==name)


def make(name=E, request_id='request', turn=S.turn, terms=1, d=1, count=2):
    f=n.gaussian([[0]*d]*terms,[[1]*d]*terms,[2.]*terms,constant=1.,axes=[(f'x{i}','1') for i in range(d)],domain=[(-2.,2.)]*d,output_unit='K')
    return n.make_call(name,f,n.points(f,[[0.]*d]*count),request_id,turn)


def setup():
    r=Registry();r.install(n.NativeVFAPlugin,enabled=True)
    for op in n.OP:r.nominate(op,n.NAME)
    return r,Runtime(r)


@pytest.fixture(scope='module')
def engine():return setup()


@pytest.fixture
def host(engine):return a.Admission(engine[1],S.session)


def submit(h,t,c=None,scope=S,**kw):
    c=c or make();return h.execute(scope,t,c.request_id,c.wire(),timeout_ms=kw.get('timeout_ms',3000))


def wait_active(h,scope,request_id):
    end=monotonic()+3
    while monotonic()<end:
        with h._lock:
            if (scope,request_id) in h._active:return
        sleep(.005)
    raise AssertionError('call never reserved')


@pytest.mark.parametrize('name',[E,G])
def test_real_worker_owned_receipt(host,name):
    t=host.issue(S,route(name));c=make(name);r=submit(host,t,c)
    assert r.scope==S and r.request_id==c.request_id and r.operation==c.operation and r.status=='completed'
    assert r.descriptor_sha256==c.descriptor_sha256 and r.request_sha256==hashlib.sha256(c.wire()).hexdigest()
    assert hashlib.sha256(r.result_frame).hexdigest()==r.result_sha256
    m=pb.VfaResult.FromString(r.result_frame);assert m.correlation_id==S.turn and m.request_id==c.request_id
    assert m.result.body.parent_sha256==[bytes.fromhex(c.function.identity),bytes.fromhex(c.points.identity)]
    assert list(m.result.body.values.values if name==E else m.result.body.gradient.values)==([3.,3.] if name==E else [0.,0.])
    assert m.result.body.uncertainty==pb.NOT_CERTIFIED
    with pytest.raises(FrozenInstanceError):r.status='forged'


def test_only_exact_compute_route(host):
    x=route();assert x.effect is a.Effect.COMPUTE_ONLY and x.input_type_url=='type.googleapis.com/cognitum.mel.v1.VfaRequest'
    t=host.issue(S,x);schema=host.discover(S,t);assert schema['function']['name']==E and schema['function']['parameters']['additionalProperties'] is False
    assert 'grant' not in json.dumps(schema) and t.hex() not in json.dumps(schema)
    schema['function']['name']='mutated';assert host.discover(S,t)['function']['name']==E
    for bad in (replace(x,effect='compute_only'),replace(x,descriptor_sha256='0'*64),replace(x,input_type_url='wrong'),replace(x,operation='hdc.bind'),replace(x,operation_version='1.0.0')):
        with pytest.raises(ValueError):host.issue(S,bad)


@pytest.mark.parametrize('field',['session','workspace','subject','turn'])
def test_scope_isolation(host,field):
    t=host.issue(S,route());other=replace(S,**{field:'other'})
    with pytest.raises(ValueError):submit(host,t,scope=other)
    with pytest.raises(ValueError):host.discover(other,t)
    if field=='session':
        with pytest.raises(ValueError):host.revoke(other,t)
    else:assert not host.revoke(other,t)
    assert submit(host,t).status=='completed'


@pytest.mark.parametrize('token',[None,'fake',b'',b'x'*32])
def test_no_ambient_grant(host,token):
    with pytest.raises(ValueError):submit(host,token)


@pytest.mark.parametrize('change',['operation','request','turn','unknown','descriptor','broken'])
def test_mismatched_frame_refused(host,change):
    t=host.issue(S,route());c=make(G if change=='operation' else E,turn='other' if change=='turn' else S.turn)
    raw=c.wire();m=pb.VfaRequest.FromString(raw)
    if change=='descriptor':m.descriptor_sha256=b'\0'*32;raw=n.serialize(m)
    if change=='unknown':raw+=b'\x98\x06\x01'
    if change=='broken':raw=raw[:-1]
    r=host.execute(S,t,'other' if change=='request' else c.request_id,raw,timeout_ms=3000)
    assert r.status=='invalid_input' and r.result_frame is None
    assert submit(host,t).status=='completed'


@pytest.mark.parametrize('limits,c',[(a.Limits(dimensions=1),make(d=2)),(a.Limits(terms=0),make()),(a.Limits(points=1),make()),(a.Limits(request_bytes=1),make()),(a.Limits(work=1),make())],ids=['dimension','terms','points','request-size','work'])
def test_resource_limits(host,limits,c):
    t=host.issue(S,route(),limits);r=submit(host,t,c);assert r.status=='resource_denied' and r.result_frame is None
    assert not host._seen


def test_timeout_budget_before_dispatch(host):
    t=host.issue(S,route(),a.Limits(timeout_ms=100));assert submit(host,t,timeout_ms=101).status=='resource_denied'


def test_result_budget_charged(host):
    t=host.issue(S,route(),a.Limits(result_bytes=1));r=submit(host,t)
    assert r.status=='resource_denied' and r.result_sha256 is None
    assert submit(host,t).status=='replay_denied'
    assert submit(host,t,make(request_id='new')).status=='resource_denied'


def test_replay_different_grants_and_cumulative_budget(host):
    t=host.issue(S,route(),a.Limits(calls=3,work=8));c=make()
    assert submit(host,t,c).status=='completed'
    t2=host.issue(S,route());assert submit(host,t2,c).status=='replay_denied'
    assert submit(host,t,make(request_id='r2')).status=='completed'
    assert submit(host,t,make(request_id='r3')).status=='resource_denied'


def test_revoke_before_admission(host):
    t=host.issue(S,route());assert host.revoke(S,t);assert not host.revoke(S,t)
    with pytest.raises(ValueError):submit(host,t)
    with pytest.raises(ValueError):host.discover(S,t)


def test_expired_and_closed(host):
    t=host.issue(S,route(),ttl_ms=1);sleep(.003)
    with pytest.raises(ValueError):submit(host,t)
    t=host.issue(S,route());host.close()
    with pytest.raises(ValueError):submit(host,t)
    with pytest.raises(ValueError):host.issue(S,route())


def test_live_entry_change_refused():
    registry,rt=setup();h=a.Admission(rt,S.session);t=h.issue(S,route());registry.enable(n.NAME,False)
    with pytest.raises(ValueError):h.discover(S,t)
    registry.enable(n.NAME,True);assert submit(h,t).status=='unavailable'  # even equivalent reenable creates new entry
    assert submit(h,h.issue(S,route()),make(request_id='fresh')).status=='completed'


def test_registry_entry_race_and_queue_cancel(monkeypatch):
    registry,rt=setup();h=a.Admission(rt,S.session);t=h.issue(S,route());calls=[]
    orig=Runtime.call
    def dispatch(*x,**kw):calls.append(1);return orig(*x,**kw)
    monkeypatch.setattr(Runtime,'call',dispatch)
    with ThreadPoolExecutor(1) as pool:
        with registry.lock:
            f=pool.submit(submit,h,t);wait_active(h,S,'request');assert h.cancel(S,'request');assert not h.cancel(S,'request')
            assert f.result(timeout=3).status=='cancelled'
    assert not calls and not h._active


@pytest.mark.parametrize('action',['cancel','revoke','close'])
def test_inflight_suppression_actual_worker(monkeypatch,action):
    registry,rt=setup();h=a.Admission(rt,S.session);t=h.issue(S,route(),ttl_ms=10000)
    ready=Event();release=Event();orig=Runtime.call
    def dispatch(*x,**kw):
        result=orig(*x,**kw);assert result.execution_status=='completed';ready.set();assert release.wait(3);return result
    monkeypatch.setattr(Runtime,'call',dispatch)
    with ThreadPoolExecutor(1) as pool:
        f=pool.submit(submit,h,t)
        try:
            assert ready.wait(5)
            if action=='cancel':assert h.cancel(S,'request')
            elif action=='revoke':assert h.revoke(S,t)
            else:h.close()
        finally:release.set()
        r=f.result(timeout=5)
    assert r.status==('cancelled' if action=='cancel' else 'revoked') and r.result_frame is None and not h._active


def test_real_worker_timeout(host):
    t=host.issue(S,route(),a.Limits(timeout_ms=10));r=submit(host,t,timeout_ms=10)
    assert r.status=='timed_out' and r.result_frame is None


def test_queue_deadline(monkeypatch):
    registry,rt=setup();h=a.Admission(rt,S.session);t=h.issue(S,route());calls=[]
    monkeypatch.setattr(Runtime,'call',lambda *x,**kw:calls.append(1))
    with ThreadPoolExecutor(1) as pool:
        with registry.lock:
            f=pool.submit(submit,h,t,timeout_ms=150);assert f.result(timeout=3).status=='timed_out'
    assert not calls


def test_late_result_and_foreign_response(monkeypatch):
    registry,rt=setup();h=a.Admission(rt,S.session);t=h.issue(S,route());orig=Runtime.call
    def wrong(*x,**kw):return replace(orig(*x,**kw),correlation_id='other')
    monkeypatch.setattr(Runtime,'call',wrong)
    r=submit(h,t);assert r.status=='error' and r.result_frame is None
    assert not h._active


def test_global_inflight_cap_and_concurrent_replay():
    registry,rt=setup();h=a.Admission(rt,S.session);t=h.issue(S,route(),a.Limits(calls=8,work=100))
    ids=[f'r{i}' for i in range(a.MAX_INFLIGHT)]
    with ThreadPoolExecutor(5) as pool:
        with registry.lock:
            futures=[pool.submit(submit,h,t,make(request_id=i)) for i in ids]
            for i in ids:wait_active(h,S,i)
            assert submit(h,t,make(request_id=ids[0])).status=='replay_denied'
            assert submit(h,t,make(request_id='overflow')).status=='resource_denied'
            for i in ids:assert h.cancel(S,i)
            assert all(f.result(timeout=3).status=='cancelled' for f in futures)
    assert not h._active and len(h._seen)==a.MAX_INFLIGHT


def test_grant_capacity(host,monkeypatch):
    monkeypatch.setattr(a,'MAX_GRANTS',2)
    x=host.issue(S,route());host.revoke(S,x);host.issue(S,route())
    with pytest.raises(ValueError):host.issue(S,route())


@pytest.mark.parametrize('kw',[{'calls':True},{'terms':257},{'timeout_ms':10001},{'work':0},{'result_bytes':0}])
def test_invalid_limits(kw):
    with pytest.raises(ValueError):a.Limits(**kw)


def test_late_result_discard(monkeypatch):
    registry,rt=setup();h=a.Admission(rt,S.session);t=h.issue(S,route(),ttl_ms=10000)
    orig=Runtime.call;observed=[]
    def delayed(*args,**kwargs):
        response=orig(*args,**kwargs);observed.append(response.execution_status)
        sleep(.9);return response
    monkeypatch.setattr(Runtime,'call',delayed)
    r=submit(h,t,timeout_ms=800)
    assert r.status=='timed_out' and r.result_frame is None
    assert observed and observed[0] in ('completed','timed_out')


def test_queued_registry_replacement(monkeypatch):
    registry,rt=setup();h=a.Admission(rt,S.session);t=h.issue(S,route());calls=[]
    monkeypatch.setattr(Runtime,'call',lambda *x,**kw:calls.append(1))
    with ThreadPoolExecutor(1) as pool:
        with registry.lock:
            future=pool.submit(submit,h,t);wait_active(h,S,'request')
            registry.enable(n.NAME,False);registry.enable(n.NAME,True)
        assert future.result(timeout=4).status=='unavailable'
    assert not calls


def test_bounded_replay_history(host,monkeypatch):
    monkeypatch.setattr(a,'MAX_REQUESTS',1)
    t=host.issue(S,route(),a.Limits(calls=4,work=20))
    assert submit(host,t).status=='completed'
    assert submit(host,t,make(request_id='new')).status=='resource_denied'
    assert submit(host,t).status=='replay_denied'
    assert len(host._seen)==1


def test_cross_turn_same_request_id(host):
    other=replace(S,turn='new-turn')
    t=host.issue(S,route());u=host.issue(other,route())
    assert submit(host,t).status=='completed'
    assert submit(host,u,make(turn=other.turn),scope=other).status=='completed'


def test_wrong_owner_cannot_cancel():
    registry,rt=setup();h=a.Admission(rt,S.session);t=h.issue(S,route())
    with ThreadPoolExecutor(1) as pool:
        with registry.lock:
            f=pool.submit(submit,h,t);wait_active(h,S,'request')
            assert not h.cancel(replace(S,subject='other'),'request')
            assert not h.cancel(replace(S,turn='other'),'request')
            assert h.cancel(S,'request')
        assert f.result(timeout=3).status=='cancelled'


@pytest.mark.parametrize('raw',[None,{},b'',b'x'*(n.MAX_REQUEST+1)],ids=['none','map','empty','oversized'])
def test_raw_byte_boundary(host,raw):
    t=host.issue(S,route());r=host.execute(S,t,'id',raw,timeout_ms=3000)
    assert r.status=='resource_denied' and r.request_sha256==('' if type(raw) is not bytes or len(raw)>n.MAX_REQUEST else hashlib.sha256(raw).hexdigest()) and r.result_frame is None


def test_wrong_result_frame_refused(monkeypatch):
    registry,rt=setup();h=a.Admission(rt,S.session);t=h.issue(S,route());orig=Runtime.call
    def altered(*x,**kw):
        response=orig(*x,**kw)
        assert response.execution_status=='completed'
        return replace(response,result={'frame':n.encode_carrier(b'\x98\x06\x01',n.MAX_RESULT)})
    monkeypatch.setattr(Runtime,'call',altered)
    r=submit(h,t);assert r.status=='error' and r.result_frame is None
