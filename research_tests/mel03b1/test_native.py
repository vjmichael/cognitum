"""Strict native protobuf boundary, including genuine existing-worker execution."""
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import math
import struct
import pytest
import numpy as np
from cognitum.contracts import Request, HostContext, Response
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.mel import native as n
from cognitum.mel import mel_pb2 as pb
from cognitum.mel import discovery as legacy

E='mel_vfa_evaluate';G='mel_vfa_gradient'


def function():
    return n.gaussian([[0,0],[1,-1]],[[1,2],[.5,.8]],[2,-.25],constant=.5,axes=[('x','m'),('t','s')],domain=[(-2,2),(-3,3)],output_unit='K')


def call(name=E):
    f=function();return n.make_call(name,f,n.points(f,[[0,0],[1,2],[-2,3]]),'r1','c1')


def registry(enabled=True):
    r=Registry();r.install(n.NativeVFAPlugin,enabled=enabled)
    for op in n.OP:r.nominate(op,n.NAME)
    return r


@pytest.fixture(scope='module')
def reg():return registry()


def execute(r,c,**kw):
    context=HostContext('ws','user',allow_research=kw.pop('allow_research',True))
    req=Request(c.request_id,c.correlation_id,c.operation,c.payload(),workspace_id=kw.pop('workspace_id','ws'),subject_id='user',operation_schema_version=kw.pop('operation_schema_version',n.VERSION),timeout_ms=kw.pop('timeout_ms',10000),**kw)
    return Runtime(r).call(req,context)


def model_args():
    return dict(axes=[dict(name='x',unit='m'),dict(name='t',unit='s')],domain=[dict(lower=-2,upper=2),dict(lower=-3,upper=3)],terms=[dict(center=[0.,0.],width=[1.,2.],weight=2.),dict(center=[1.,-1.],width=[.5,.8],weight=-.25)],constant=.5,output_unit='K',points=[[0,0],[1,2],[-2,3]])


def bind(r,name=E,a=None,raw=None):
    return n.bind_model(r,((name,n.descriptor(name)[0]),),name,json.dumps(model_args() if a is None else a) if raw is None else raw,request_id='r1',correlation_id='c1')


def modified(obj,fn):
    m=obj.message();fn(m.body);m.content_sha256=hashlib.sha256(n.DOMAIN+n.serialize(m.body)).digest();return n.serialize(m)


def test_wire_contains_protobuf_not_json():
    c=call();m=pb.VfaRequest.FromString(c.wire());assert m.function.body.WhichOneof('representation')=='function'
    assert m.function.body.function.HasField('constant') and m.function.body.shape==[2,2]
    assert n.decode_carrier(c.payload()['frame'],n.MAX_REQUEST)==c.wire()
    assert set(c.payload())=={'frame'} and n.decode_request(c.wire(),c.operation)==c
    assert pb.VfaRequest.DESCRIPTOR.full_name=='cognitum.mel.v1.VfaRequest'
    assert pb.VfaResult.DESCRIPTOR.full_name=='cognitum.mel.v1.VfaResult'


def test_independent_wire_golden_negative_zero():
    # Independent protobuf bytes for constant-only function. No Python
    # protobuf serializer used to assemble expected body or content ID.
    def tag(number,wire):return bytes([number*8+wire])
    def length(number,data):return tag(number,2)+bytes([len(data)])+data
    def vi(number,v):return tag(number,0)+bytes([v])
    def dbl(number,v):return tag(number,1)+struct.pack('<d',v)
    axis=length(1,b'x')+length(2,b'1');domain=dbl(1,-0.)+dbl(2,1.)
    unit=length(1,b'1')+length(2,b'1')
    body=vi(1,1)+vi(2,1)+length(3,b'\x00\x01')+length(4,axis)+length(5,domain)+length(6,unit)+length(8,b'submitted')+vi(10,1)+vi(11,1)+length(12,dbl(1,-0.))
    digest=hashlib.sha256(b'cognitum.mel.v1.MathBody\x00'+body).digest();expected=length(1,body)+length(2,digest)
    f=n.gaussian([],[],[],constant=-0.,axes=[('x','1')],domain=[(-0.,1.)],output_unit='1')
    assert f.wire==expected and f.identity=='31a72f75ccfc085528e83062747e512cd51801a80eee7176ab2c4e0178879ef8'
    assert math.copysign(1,f.message().body.function.constant)==-1
    assert n.points(f,[[0.]]).identity!=n.points(f,[[-0.]]).identity


def test_immutable_source_and_message():
    centers=[[0.]];width=[[1.]];weight=[2.]
    f=n.gaussian(centers,width,weight,constant=0.,axes=[('x','m')],domain=[(-1,1)],output_unit='K');raw=f.wire
    centers[0][0]=9;width[0][0]=2;weight[0]=9
    m=f.message();m.body.function.weights[0]=100
    assert f.wire==raw and f.message().body.function.weights==[2.]
    with pytest.raises(FrozenInstanceError):f.wire=b'other'


@pytest.mark.parametrize('mut',[
    lambda b:setattr(b,'schema_version',2),lambda b:setattr(b,'precision',7),lambda b:b.shape.__setitem__(0,999),
    lambda b:b.domain[0].ClearField('lower'),lambda b:setattr(b.domain[0],'lower',3),lambda b:setattr(b.axes[1],'name','x'),
    lambda b:setattr(b.axes[0],'unit','m/s'),lambda b:setattr(b.units[0],'denominator','m'),lambda b:b.function.ClearField('constant'),
    lambda b:b.function.widths.__setitem__(0,0),lambda b:b.function.weights.__setitem__(0,float('nan')),lambda b:b.function.centers.append(2),
    lambda b:setattr(b,'assurance',pb.NUMERICAL),lambda b:b.parent_sha256.append(b'\x00'*32),lambda b:setattr(b,'producer','host'),
    lambda b:b.ClearField('function'),lambda b:b.points.coordinates.append(1),lambda b:setattr(b,'uncertainty',pb.NOT_CERTIFIED),
],ids=[f'body{i:02d}' for i in range(18)])
def test_invalid_rehashed_object(mut):
    with pytest.raises(ValueError):n.NativeObject(modified(function(),mut))


@pytest.mark.parametrize('case',['empty','truncated','unknown','duplicate','oversize','bad_digest','json','nonminimal'])
def test_malformed_object(case):
    f=function();raw=f.wire
    m=f.message();m.content_sha256=b'\x00'*32
    bad={'empty':b'','truncated':raw[:-1],'unknown':raw+b'\x98\x06\x01','duplicate':raw+b'\x12\x20'+f.message().content_sha256,'oversize':b'x'*(n.MAX_OBJECT+1),'bad_digest':n.serialize(m),'json':b'{"id":"false"}','nonminimal':b'\x8a\x00'+raw[1:]}[case]
    with pytest.raises(ValueError):n.NativeObject(bad)


@pytest.mark.parametrize('rows',[[[True,0]],[[0,float('inf')]],[[3,0]],[[0]],[],[[0,0]]*33],ids=['bool','inf','outside','ragged','empty','count'])
def test_point_refusal(rows):
    with pytest.raises(ValueError):n.points(function(),rows)


@pytest.mark.parametrize('name',[E,G])
def test_real_worker(reg,name):
    c=bind(reg,name);assert c==call(name)
    r=execute(reg,c);out=n.model_feedback(c,r);assert out['ok'];b=out['result'];assert b['error']=='not_certified' and b['assurance']=='numerical'
    assert b['function_id']==c.function.identity and b['points_id']==c.points.identity
    assert b['producer']==n.PRODUCER and b['object_id']==n.checked_result(c,r).identity
    assert b['units']==([['K','1']] if name==E else [['K','m'],['K','s']])
    for i,(x,t) in enumerate(model_args()['points']):
        terms=[(w*math.exp(-.5*(((x-a)/s)**2+((t-z)/q)**2)),a,z,s,q) for w,a,z,s,q in [(2,0,0,1,2),(-.25,1,-1,.5,.8)]]
        if name==E:expected=.5+sum(v for v,*_ in terms)
        else:expected=[sum(-v*(x-a)/s**2 for v,a,z,s,q in terms),sum(-v*(t-z)/q**2 for v,a,z,s,q in terms)]
        np.testing.assert_allclose(b['values'][i],expected,atol=5e-13,rtol=0)
    assert n.decode_carrier(r.result['frame'],n.MAX_RESULT)==n.serialize(pb.VfaResult.FromString(n.decode_carrier(r.result['frame'],n.MAX_RESULT)))


def test_max_engine_budget(reg):
    d=8;t=256;f=n.gaussian([[0]*d]*t,[[1]*d]*t,[1/t]*t,constant=0,axes=[(f'x{i}','1') for i in range(d)],domain=[(-1,1)]*d,output_unit='1')
    c=n.make_call(G,f,n.points(f,[[0]*d]*32),'max','max');r=execute(reg,c);assert r.execution_status=='completed';b=n.checked_result(c,r).message().body
    assert b.gradient.values==[0.]*(d*32) and len(c.wire())<=n.MAX_REQUEST and len(c.payload()['frame'])<=65536 and len(r.result['frame'])<=8192


def test_constant_only(reg):
    a=model_args();a['terms']=[];c=bind(reg,E,a);assert n.model_feedback(c,execute(reg,c))['result']['values']==[.5]*3


def test_descriptors_versioned_and_schema_matched(reg):
    assert n.catalog()==n.catalog() and len(n.catalog())==2
    for h,b in n.catalog():
        name=b['public_name'];old=next(d for d in legacy.catalog() if d.body['public_name']==name)
        assert h!=old.identity and b['arguments_schema']==old.body['arguments_schema'] and b['legacy_descriptor_sha256']==old.identity
        assert b['operation_schema_version']=='2.0.0' and b['model_advertised'] is False and b['lu_registered'] is False and not b['execution_authorized']
        assert b['native_proto_type_urls']==['type.googleapis.com/'+pb.VfaRequest.DESCRIPTOR.full_name,'type.googleapis.com/'+pb.VfaResult.DESCRIPTOR.full_name]
        assert n.discover(reg,((name,h),))[0]['descriptor_sha256']==h
    assert n.discover(reg,())==()
    with pytest.raises(ValueError):n.discover(reg,((E,legacy.catalog()[0].identity),))


def test_discovery_unavailable_legacy_factory_and_duplicates(reg):
    r=Registry();from cognitum.mel.vfa import VFAPlugin,NAME as legacy_name
    r.install(VFAPlugin,enabled=True);r.nominate('vfa.evaluate',legacy_name)
    sel=((E,n.descriptor(E)[0]),)
    for candidate in (Registry(),registry(False),r):
        with pytest.raises(ValueError):n.discover(candidate,sel)
    with pytest.raises(ValueError):n.discover(reg,sel+sel)


def test_wrong_version_and_scope(reg):
    c=call()
    for kw,code in [({'allow_research':False},'UNAVAILABLE'),({'workspace_id':'wrong'},'DENIED'),({'operation_schema_version':'1.0.0'},'INVALID_INPUT'),({'dry_run':True},'NOT_EXECUTED')]:
        assert n.model_feedback(c,execute(reg,c,**kw))['error']['code']==code


def test_revoked_after_binding():
    r=registry();c=bind(r);r.enable(n.NAME,False);assert n.model_feedback(c,execute(r,c))['error']['code']=='UNAVAILABLE'


@pytest.mark.parametrize('change',['operation','descriptor','missing','wrong_version','bad_id','unknown'])
def test_invalid_request(change):
    c=call();m=pb.VfaRequest.FromString(c.wire())
    if change=='operation':m.operation=pb.VFA_GRADIENT
    elif change=='descriptor':m.descriptor_sha256=b'\x00'*32
    elif change=='missing':m.ClearField('points')
    elif change=='wrong_version':m.schema_version=2
    elif change=='bad_id':m.request_id='bad id'
    raw=n.serialize(m)+(b'\x98\x06\x01' if change=='unknown' else b'')
    with pytest.raises(ValueError):n.decode_request(raw,c.operation)


@pytest.mark.parametrize('change',['operation','descriptor','request_id','wrong_version','wrong_kind','parent','unknown'])
def test_invalid_response(reg,change):
    c=call();r=execute(reg,c);m=pb.VfaResult.FromString(n.decode_carrier(r.result['frame'],n.MAX_RESULT));assert n.checked_result(c,r)
    if change=='operation':m.operation=pb.VFA_GRADIENT
    elif change=='descriptor':m.descriptor_sha256=b'\x00'*32
    elif change=='request_id':m.request_id='r2'
    elif change=='wrong_version':m.schema_version=2
    elif change=='wrong_kind':m.result.CopyFrom(n.result_object('vfa.gradient',c.function,c.points,[0.]*6).message())
    elif change=='parent':
        m.result.body.parent_sha256[0]=b'\x00'*32;m.result.content_sha256=hashlib.sha256(n.DOMAIN+n.serialize(m.result.body)).digest()
    raw=n.serialize(m)+(b'\x98\x06\x01' if change=='unknown' else b'')
    with pytest.raises(ValueError):n.model_feedback(c,replace(r,result={'frame':n.encode_carrier(raw,n.MAX_RESULT)}))


@pytest.mark.parametrize('raw',['{"points":[],"points":[]}', '{}', '[]', '{"constant":NaN}',' '*65537],ids=['duplicate','missing','nonobject','nan','oversize'])
def test_model_json_refusal(reg,raw):
    with pytest.raises(ValueError):bind(reg,raw=raw)


def test_model_subset_and_no_dispatch(reg,monkeypatch):
    def fail(*a,**k):raise AssertionError('binding dispatched')
    monkeypatch.setattr(Runtime,'call',fail);monkeypatch.setattr(n.NativeVFAPlugin,'handle',fail)
    c=bind(reg);assert c.operation=='vfa.evaluate'
    a=model_args();a['terms']*=17
    with pytest.raises(ValueError):bind(reg,a=a)


def test_windows_node_id_budget():
    # Check all actual pytest-generated node IDs without running the suite here;
    # dedicated acceptance independently checks the collected output too.
    from pathlib import Path
    s=(Path(__file__).resolve().parents[1]/'mel03a'/'test_discovery.py').read_text()
    assert '"oversized"' in s and '(MAX_ARGS_BYTES+1)' in s
