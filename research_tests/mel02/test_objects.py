import base64
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import math
import struct

import numpy as np
import pytest

from cognitum.contracts import HostContext, Request
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.mel.objects import MathObject, gaussian, points, canonical, MAX_WIRE, MAX_POINTS, MAX_TERMS, result_object
from cognitum.mel.vfa import VFAPlugin, NAME, OPERATIONS, request_payload, checked_response


def fixture():
    return gaussian([[-.7,.3],[.4,-.2]],[[.6,1.1],[.9,.4]],[.8,-.3],constant=.2,axes=[('x','m'),('t','s')],domain=[(-2,2),(-3,3)],output_unit='K')


def mutated(obj, action):
    e=json.loads(obj.wire);action(e['body']);e['id']=hashlib.sha256(canonical(e['body']).encode('ascii')).hexdigest();return canonical(e)


def call(rt,op,f,p,**kw):
    return rt.call(Request('request','correlation',op,request_payload(f,p),timeout_ms=10000,**kw),HostContext('local','local-user',allow_research=True))


def checked(r,op,f,p):
    return checked_response(r,op,f,p,request_id='request',correlation_id='correlation')


def oracle(x,y):
    return .2+.8*math.exp(-.5*(((x+.7)/.6)**2+((y-.3)/1.1)**2))-.3*math.exp(-.5*(((x-.4)/.9)**2+((y+.2)/.4)**2))


@pytest.fixture(scope='module')
def runtime():
    registry=Registry();registry.install(VFAPlugin)
    for op in OPERATIONS:registry.nominate(op,NAME)
    registry.enable(NAME);return Runtime(registry)


def test_immutable_snapshot():
    c=[[0.]];w=[[1.]];a=[2.];f=gaussian(c,w,a,constant=1,axes=[('x','1')],domain=[(-1,1)],output_unit='1');wire=f.wire
    c[0][0]=9;w[0][0]=3;a[0]=0
    metadata=f.metadata;metadata['axes'][0][0]='bad'
    assert f.wire==wire and f.values==(1.,0.,1.,2.) and f.metadata['axes']==[['x','1']]
    with pytest.raises(FrozenInstanceError):f.wire='other'


def test_exact_wire_and_identity():
    f=fixture();assert MathObject(f.wire)==f
    e=json.loads(f.wire);assert f.identity==hashlib.sha256(canonical(e['body']).encode('ascii')).hexdigest()
    assert struct.unpack('<d',base64.b64decode(e['body']['payload'])[:8])==(.2,)
    assert points(f,[[-0.,0.]]).identity!=points(f,[[0.,0.]]).identity


@pytest.mark.parametrize('bad',[lambda f:f.wire+' ',lambda f:f.wire.replace('"id":','"id":"bad","id":'),lambda f:f.wire.replace('diagonal_gaussian_mixture','unknown_representation'),lambda f:'['*10000+']'*10000,lambda f:' '* (MAX_WIRE+1),lambda f:mutated(f,lambda b:b.update(schema='v2')),lambda f:mutated(f,lambda b:b.update(shape=[True,2])),lambda f:mutated(f,lambda b:b.update(unknown='extra')),lambda f:mutated(f,lambda b:b.update(assurance='exact')),lambda f:mutated(f,lambda b:b.update(parents=['0'*64])),lambda f:mutated(f,lambda b:b.update(payload='AAAA')),lambda f:mutated(f,lambda b:b.update(payload=base64.b64encode(struct.pack('<d',float('nan'))+base64.b64decode(b['payload'])[8:]).decode())),lambda f:mutated(f,lambda b:b.update(box=[['0x0.0p+0','0x0.0p+0'],b['box'][1]])),lambda f:mutated(f,lambda b:b.update(axes=[['x','m'],['x','s']])),lambda f:mutated(f,lambda b:b.update(units=[['K','m']])),lambda f:mutated(f,lambda b:b.update(producer='trusted_host'))])
def test_invalid_wire(bad):
    with pytest.raises(ValueError):MathObject(bad(fixture()))


@pytest.mark.parametrize('rows',[[[True,0]],[[0,float('inf')]],[[0,3.1]],[[0]],[],[[0,0]]*(MAX_POINTS+1),[['0',0]]])
def test_invalid_points(rows):
    with pytest.raises(ValueError):points(fixture(),rows)


@pytest.mark.parametrize('width',[0,1e-4,1001,float('nan')])
def test_invalid_width(width):
    with pytest.raises(ValueError):gaussian([[0]],[[width]],[1],constant=0,axes=[('x','1')],domain=[(-1,1)],output_unit='1')


def test_domain_axis_compatibility():
    f=fixture();p=points(f,[[0,0]])
    for key,value in [('axes',[['y','m'],['t','s']]),('box',[[(-1.).hex(),(1.).hex()],p.metadata['box'][1]])]:
        other=MathObject(mutated(p,lambda b:b.update({key:value})))
        with pytest.raises(ValueError):request_payload(f,other)


@pytest.mark.parametrize('op',OPERATIONS)
def test_worker_numerical(runtime,op):
    f=fixture();x=[[-2,-3],[-.9,.8],[0,0],[1.1,-.5],[2,3]];p=points(f,x)
    r=call(runtime,op,f,p);out=checked(r,op,f,p)
    assert out.metadata['parents']==[f.identity,p.identity] and out.metadata['error']=='not_certified'
    if op=='vfa.evaluate':
        expected=[oracle(*q) for q in x];assert out.metadata['units']==[['K','1']]
    else:
        h=1e-5;expected=[v for a,b in x for v in ((oracle(a+h,b)-oracle(a-h,b))/(2*h),(oracle(a,b+h)-oracle(a,b-h))/(2*h))];assert out.metadata['units']==[['K','m'],['K','s']]
    np.testing.assert_allclose(out.values,expected,rtol=2e-8,atol=2e-9)
    assert set(runtime.trace.events[-1])=={'trace_version','request_id','correlation_id','operation','module','execution_status','error','latency_ms'}


def test_constant_and_upper_budget(runtime):
    f=gaussian([],[],[],constant=-3,axes=[('x','1')],domain=[(-1,1)],output_unit='1');p=points(f,[[0],[-1],[1]])
    assert checked(call(runtime,'vfa.gradient',f,p),'vfa.gradient',f,p).values==(0.,0.,0.)
    d=8;t=MAX_TERMS;f=gaussian([[0]*d]*t,[[1]*d]*t,[1/t]*t,constant=0,axes=[(f'x{i}','1') for i in range(d)],domain=[(-1,1)]*d,output_unit='1');p=points(f,[[0]*d]*MAX_POINTS)
    r=call(runtime,'vfa.gradient',f,p);out=checked(r,'vfa.gradient',f,p)
    assert len(out.values)==d*MAX_POINTS and set(out.values)=={0.} and len(json.dumps(r.result))<16384 and len(f.wire)<MAX_WIRE


def test_default_disabled():
    f=fixture();p=points(f,[[0,0]]);reg=Registry();rt=Runtime(reg)
    assert call(rt,'vfa.evaluate',f,p).execution_status=='unavailable'
    reg.install(VFAPlugin);reg.nominate('vfa.evaluate',NAME)
    assert call(rt,'vfa.evaluate',f,p).execution_status=='unavailable'
    reg.enable(NAME);req=Request('request','correlation','vfa.evaluate',request_payload(f,p))
    assert rt.call(req,HostContext('local','local-user')).execution_status=='unavailable'
    assert call(rt,'vfa.gradient',f,p).execution_status=='unavailable'
    reg.enable(NAME,False);assert call(rt,'vfa.evaluate',f,p).execution_status=='unavailable'


def test_host_scope_and_dry_run(runtime):
    f=fixture();p=points(f,[[0,0]])
    r=call(runtime,'vfa.evaluate',f,p,workspace_id='other');assert r.execution_status=='denied' and r.result is None
    r=call(runtime,'vfa.evaluate',f,p,dry_run=True);assert r.execution_status=='validated' and r.result is None
    with pytest.raises(ValueError):checked(r,'vfa.evaluate',f,p)


def test_worker_malformed_and_wire_extra(runtime):
    f=fixture();p=points(f,[[0,0]]);ctx=HostContext('local','local-user',allow_research=True)
    payload=request_payload(f,p);payload['function']=f.wire+' '
    r=runtime.call(Request('request','correlation','vfa.evaluate',payload,timeout_ms=10000),ctx);assert r.execution_status=='invalid_input' and r.result is None
    payload=request_payload(f,p);payload['authority']='true'
    r=runtime.call(Request('request','correlation','vfa.evaluate',payload),ctx);assert r.execution_status=='invalid_input' and r.result is None


def test_result_lineage_and_response_mismatch(runtime):
    f=fixture();p=points(f,[[0,0]]);q=points(f,[[1,1]])
    r=call(runtime,'vfa.evaluate',f,p);obj=checked(r,'vfa.evaluate',f,p)
    with pytest.raises(ValueError):checked(r,'vfa.evaluate',f,q)
    with pytest.raises(ValueError):checked(r,'vfa.gradient',f,p)
    with pytest.raises(ValueError):checked(replace(r,request_id='different'),'vfa.evaluate',f,p)
    bogus=MathObject(mutated(obj,lambda b:b.update(units=[['m','1']])))
    with pytest.raises(ValueError):checked(replace(r,result={'object':bogus.wire}),'vfa.evaluate',f,p)


def test_timeout(runtime):
    f=fixture();p=points(f,[[0,0]])
    r=runtime.call(Request('request','correlation','vfa.evaluate',request_payload(f,p),timeout_ms=1),HostContext('local','local-user',allow_research=True))
    assert r.execution_status=='timed_out' and r.result is None
