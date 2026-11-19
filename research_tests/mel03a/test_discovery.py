from dataclasses import replace
import json
import math
import pytest

from cognitum.contracts import HostContext, Request, Response
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.mel.objects import MathObject, canonical
from cognitum.mel.vfa import NAME, OPERATIONS, VFAPlugin
from cognitum.mel.discovery import (MAX_ARGS_BYTES, MAX_MODEL_TERMS, MAX_MODEL_POINTS,
    BoundCall, catalog, selection_for, discover, bind_call, decode_result, strict_json,
    LIMITATIONS, sha, PUBLIC)

E='mel_vfa_evaluate'; G='mel_vfa_gradient'


def args():
    return {'axes':[{'name':'x','unit':'m'}, {'name':'t','unit':'s'}],
            'domain':[{'lower':-3,'upper':3},{'lower':-2,'upper':2}],
            'terms':[{'center':[0.,0.],'width':[1.,2.],'weight':2.}],
            'constant':1.5,'output_unit':'K','points':[[0.,0.],[1.,1.],[-3.,2.]]}


def registry(enabled=True):
    r=Registry();r.install(VFAPlugin)
    for op in OPERATIONS:r.nominate(op, NAME)
    if enabled:r.enable(NAME)
    return r


@pytest.fixture(scope='module')
def reg():return registry()


def bind(reg, name=E, a=None, raw=None, sel=None, **ids):
    return bind_call(reg, selection_for((name,)) if sel is None else sel,name,
        json.dumps(args() if a is None else a) if raw is None else raw,
        request_id=ids.get('request_id','call-1'),correlation_id=ids.get('correlation_id','turn-1'))


def execute(reg,call,**kw):
    ctx=HostContext('ws','subject',allow_research=kw.pop('allow_research',True))
    return Runtime(reg).call(Request(call.request_id,call.correlation_id,call.operation,call.payload(),
        workspace_id=kw.pop('workspace_id','ws'),subject_id='subject',timeout_ms=10000,**kw),ctx)


def test_descriptors_stable_and_closed():
    ds=catalog(); assert ds==catalog() and len(ds)==2 and ds[0].identity!=ds[1].identity
    for d in ds:
        b=d.body; assert b['schema']=='cognitum.mel.descriptor.v1' and b['execution_authorized'] is False
        assert b['model_advertised'] is False and b['lu_registered'] is False and b['native_proto_type_urls'] is None
        assert b['arguments_schema_sha256']==sha(b['arguments_schema']) and b['result_schema_sha256']==sha(b['result_schema'])
        assert d.identity==sha(b) and d.tool()['function']['parameters']['additionalProperties'] is False
        assert b['track']=='research' and b['effects']==[]
        b['arguments_schema']['properties'].clear(); assert d.body['arguments_schema']['properties']


def test_empty_selection(reg):assert discover(reg,())==()


def test_explicit_selection_only(reg):
    names=selection_for((G,)); offers=discover(reg,names);assert len(offers)==1
    assert offers[0]['tool_schema']['function']['name']==G and not offers[0]['execution_authorized']
    assert offers[0]['status']=='reference_candidate_not_advertised'
    assert all('grant' not in x for x in offers)
    with pytest.raises(ValueError):bind(reg, E,sel=names)


@pytest.mark.parametrize('bad',[('unknown',), (E,E), [E], (True,), ([],)])
def test_bad_public_names(bad):
    with pytest.raises(ValueError):selection_for(bad)


@pytest.mark.parametrize('sel',[((E,'0'*64),), ((E,'0'*64),(E,'0'*64)), ((E,),), (('unknown','0'*64),), [], None])
def test_bad_selection(reg,sel):
    with pytest.raises(ValueError):discover(reg,sel)


def test_unavailable_and_disabled():
    sel=selection_for((E,G))
    for r in (Registry(),registry(False)):
        with pytest.raises(ValueError):discover(r,sel)
    r=registry(); offer=discover(r,sel);assert len(offer)==2
    r.enable(NAME,False)
    with pytest.raises(ValueError):discover(r,sel)
    with pytest.raises(ValueError):bind(r)


def test_no_nomination():
    r=Registry();r.install(VFAPlugin,enabled=True)
    with pytest.raises(ValueError):discover(r,selection_for((E,)))


def test_wrong_factory():
    class Other(VFAPlugin):pass
    r=Registry();r.install(Other,enabled=True);r.nominate('vfa.evaluate',NAME)
    with pytest.raises(ValueError):discover(r,selection_for((E,)))


def test_no_runtime_dispatch(reg,monkeypatch):
    def fail(*a,**k):raise AssertionError('dispatch not allowed')
    monkeypatch.setattr(Runtime,'call',fail)
    monkeypatch.setattr(VFAPlugin,'handle',fail)
    c=bind(reg);assert c.operation=='vfa.evaluate' and c.payload()['function']==c.function.wire
    assert c.coordinates.metadata['shape']==[3,2]


@pytest.mark.parametrize('raw',[None, '', '[]','{} trailing','{}{}','{"x":1,"x":2}',
    '{"x":{"a":1,"a":2}}','{"x":NaN}','{"x":Infinity}','{"x":-Infinity}',
    '{"x":1234567890123456789}','{"x":0.'+'1'*65+'}', '{"x":'+'['*13+'0'+']'*13+'}',
    '{"x":"\u00e9"}', ' '* (MAX_ARGS_BYTES+1), '{"x": [}', '{"x":"unterminated}'], ids=["none", "empty", "nonobject", "trailing", "multiple", "duplicate", "nested_duplicate", "nan", "inf", "negative_inf", "integer_budget", "decimal_budget", "depth", "unicode", "oversized", "structure", "unterminated"])
def test_strict_parser(raw):
    with pytest.raises((ValueError,TypeError)):strict_json(raw)


@pytest.mark.parametrize('mutate',[
    lambda a:a.update(authorize=True),lambda a:a.pop('constant'),lambda a:a.update(constant=True),
    lambda a:a.update(constant='1'),lambda a:a.update(constant=1e300),lambda a:a.update(constant=math.nan),
    lambda a:a.update(axes=[]),lambda a:a['axes'][0].update(extra='x'),lambda a:a['axes'][1].update(name='x'),
    lambda a:a['axes'][0].update(unit='m/s'),lambda a:a['domain'][0].update(lower=3),
    lambda a:a['domain'].pop(),lambda a:a['domain'][0].update(extra=0),
    lambda a:a['terms'][0].update(width=[0.,2.]),lambda a:a['terms'][0].update(width=[1.]),
    lambda a:a['terms'][0].update(center=[1.,2.,3.]),lambda a:a['terms'][0].update(weight=False),
    lambda a:a.update(terms=a['terms']*(MAX_MODEL_TERMS+1)),lambda a:a['terms'][0].update(checkpoint='file'),
    lambda a:a.update(points=[]),lambda a:a.update(points=[[4.,0.]]),lambda a:a.update(points=[[1.,2.,3.]]),
    lambda a:a.update(points=[[1.,2.]]*(MAX_MODEL_POINTS+1)),lambda a:a.update(points=[[True,1]]),
    lambda a:a.update(output_unit=''),lambda a:a.update(points=[[1.,'1']]),
])
def test_nested_arguments_reject(reg,mutate):
    a=args();mutate(a)
    with pytest.raises(ValueError):bind(reg,a=a)


def test_json_duplicate_in_valid_args(reg):
    raw=json.dumps(args()).replace('"weight": 2.0','"weight": 0, "weight": 2.0')
    with pytest.raises(ValueError):bind(reg,raw=raw)


@pytest.mark.parametrize('raw',['{"a":1e999}', '{"a":-1e999}'])
def test_overflow_cannot_bind(reg,raw):
    data=json.dumps(args()).replace('1.5',raw.split(':')[1][:-1],1)
    with pytest.raises(ValueError):bind(reg,raw=data)


@pytest.mark.parametrize('bad',['','space id','x'*129,'é',None])
def test_invalid_host_call_identity(reg,bad):
    with pytest.raises(ValueError):bind(reg,request_id=bad)


@pytest.mark.parametrize('name',[E,G])
def test_actual_worker_feedback(reg,name):
    c=bind(reg,name);r=execute(reg,c);assert r.execution_status=='completed'
    out=decode_result(c,r);assert out['ok'] and out['tool']==name
    data=out['result'];assert data['function_id']==c.function.identity and data['points_id']==c.coordinates.identity
    assert data['object_id']==MathObject(r.result['object']).identity
    assert data['limitations']==list(LIMITATIONS) and data['assurance']=='numerical' and data['error']=='not_certified'
    for i,(x,t) in enumerate(args()['points']):
        v=2*math.exp(-.5*(x*x+(t/2)**2))
        if name==E:assert data['values'][i]==pytest.approx(1.5+v,abs=1e-13)
        else:assert data['values'][i]==pytest.approx([-v*x,-v*t/4],abs=1e-13)
    assert data['units']==([['K','1']] if name==E else [['K','m'],['K','s']])
    assert data['shape']==([3] if name==E else [3,2]) and data['domain']==args()['domain']
    assert json.loads(canonical(out))==out


def test_max_model_subset(reg):
    a={'axes':[{'name':f'x{i}','unit':'1'} for i in range(8)],'domain':[{'lower':-1,'upper':1}]*8,
       'terms':[{'center':[0.]*8,'width':[1.]*8,'weight':1/MAX_MODEL_TERMS}]*MAX_MODEL_TERMS,
       'constant':0.,'output_unit':'1','points':[[0.]*8]*MAX_MODEL_POINTS}
    c=bind(reg,G,a);out=decode_result(c,execute(reg,c));assert out['result']['values']==[[0.]*8]*MAX_MODEL_POINTS


def test_constant_only(reg):
    a=args();a['terms']=[];c=bind(reg,a=a);out=decode_result(c,execute(reg,c))
    assert out['result']['values']==[1.5]*3


def test_host_policy_still_independent(reg):
    c=bind(reg);r=execute(reg,c,allow_research=False);assert decode_result(c,r)['error']['code']=='UNAVAILABLE'
    r=execute(reg,c,workspace_id='wrong');assert decode_result(c,r)['error']['code']=='DENIED'
    r=execute(reg,c,dry_run=True);assert decode_result(c,r)['error']['code']=='NOT_EXECUTED'


def test_revoked_after_binding():
    r=registry();c=bind(r);r.enable(NAME,False)
    assert decode_result(c,execute(r,c))['error']['code']=='UNAVAILABLE'


def test_failure_never_echoes_payload(reg):
    c=bind(reg);r=Response(c.request_id,c.correlation_id,c.operation,'error',error='private path and secret')
    assert decode_result(c,r)=={'tool':E,'descriptor_sha256':c.descriptor_sha256,'ok':False,'error':{'code':'EXECUTION_ERROR','retryable':False}}
    with pytest.raises(ValueError):decode_result(c,replace(r,result={'object':'bad'}))
    with pytest.raises(ValueError):decode_result(c,replace(r,execution_status='unknown'))


def test_wrong_response_rejected(reg):
    c=bind(reg);r=execute(reg,c);assert decode_result(c,r)['ok']
    for change in ({'request_id':'other'},{'correlation_id':'other'},{'contract_version':'2.0.0'},
                   {'operation':'vfa.gradient'},{'assurance':'exact_arithmetic'},{'module':{'name':'other','version':'1.0.0'}},
                   {'result':{'object':'invalid'}},{'result':dict(r.result,extra='bad')}):
        with pytest.raises(ValueError):decode_result(c,replace(r,**change))
    a=args();a['points']=[[.5,.2]];other=bind(reg,a=a)
    with pytest.raises(ValueError):decode_result(other,r)


def test_descriptor_bound_to_call(reg):
    c=bind(reg)
    with pytest.raises(ValueError):replace(c,descriptor_sha256='0'*64)
    with pytest.raises(ValueError):replace(c,public_name=G)
    snap=c.payload();snap['function']='bad';assert c.payload()['function']!=snap['function']


def test_mismatched_manifest(reg):
    r=registry()
    entry=r._entries[NAME]
    r._entries[NAME]=replace(entry,manifest=replace(entry.manifest,version='2.0.0'))
    with pytest.raises(ValueError):discover(r,selection_for((E,)))


def test_atomic_selection_failure():
    r=Registry();r.install(VFAPlugin,enabled=True);r.nominate('vfa.evaluate',NAME)
    assert len(discover(r,selection_for((E,))))==1
    with pytest.raises(ValueError):discover(r,selection_for((E,G)))
