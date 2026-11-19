"""Native Protobuf objects and VFA frames; computation remains the VFA-03 kernel.

Closed v1 canonical wire profile, not generic Protobuf canonicalization.
Legacy string-only Runtime carries base64 protobuf bytes, never JSON math objects.
No host authority or automatic registration.
"""
import base64
from dataclasses import dataclass
import hashlib
import math
import re

from google.protobuf.message import DecodeError
import numpy as np

from cognitum.contracts import Manifest, Operation, Shape, CONTRACT_VERSION, Response
from cognitum.registry import Registry
from cognitum.research.vfa_multivariate import Mixture
from . import mel_pb2 as pb
from .objects import need, number, token, matrix, KERNEL, MAX_DIM, MAX_TERMS, MAX_POINTS
from .discovery import (PUBLIC, MAX_MODEL_TERMS, MAX_MODEL_POINTS, strict_json, fields,
                        sequence, catalog as legacy_catalog, sha, LIMITATIONS, FAILURES, ID)

MAX_OBJECT = 40960
MAX_REQUEST = 49152
MAX_RESULT = 6144
NAME = 'mel_vfa_protobuf'
VERSION = '2.0.0'
PRODUCER = 'cognitum.mel.vfa.protobuf/2.0.0'
WIRE_VERSION = 1
OP = {'vfa.evaluate': pb.VFA_EVALUATE, 'vfa.gradient': pb.VFA_GRADIENT}
INPUT = Shape((('frame',65536),))
OUTPUT = Shape((('frame',8192),))
DOMAIN = b'cognitum.mel.v1.MathBody\x00'


def serialize(m):
    return m.SerializeToString(deterministic=True)


def parse(raw, cls, limit):
    need(type(raw) is bytes and 1 <= len(raw) <= limit, 'frame byte budget')
    try:
        m=cls.FromString(raw)
    except (DecodeError, ValueError, RecursionError) as exc:
        raise ValueError('invalid protobuf') from exc
    # Strict profile rejects unknown fields, nonminimal varints, duplicate
    # singular/oneof fields, unpacked alternatives and noncanonical ordering.
    m.DiscardUnknownFields()
    need(serialize(m)==raw,'noncanonical or unknown protobuf fields')
    return m


def _digest(body):
    return hashlib.sha256(DOMAIN+serialize(body)).digest()


def _finite(values, limit):
    need(all(math.isfinite(v) and abs(v)<=limit for v in values),'numeric range')


def validate(obj):
    need(obj.HasField('body') and len(obj.content_sha256)==32,'object envelope')
    b=obj.body
    need(b.schema_version==WIRE_VERSION and b.precision==pb.IEEE754_BINARY64,'object schema or precision')
    need(_digest(b)==obj.content_sha256,'object digest mismatch')
    d=len(b.axes);shape=list(b.shape);kind=b.WhichOneof('representation')
    need(1<=d<=MAX_DIM and len(b.domain)==d and all(token(a.name) and token(a.unit) for a in b.axes) and len({a.name for a in b.axes})==d,'axes')
    for a in b.domain:
        need(a.HasField('lower') and a.HasField('upper') and -1e6<=a.lower<a.upper<=1e6,'domain')
    units=[(u.numerator,u.denominator) for u in b.units]
    need(all(token(x) and token(y) for x,y in units),'unit labels')
    if kind=='function':
        need(len(shape)==2 and shape[1]==d and 0<=shape[0]<=MAX_TERMS,'function shape')
        t=shape[0];f=b.function
        need(f.HasField('constant') and len(f.centers)==len(f.widths)==t*d and len(f.weights)==t,'function payload')
        _finite((f.constant,),1e6);_finite(f.centers,1e6);_finite(f.weights,1e6)
        need(all(1e-3<=v<=1e3 for v in f.widths),'width range')
        need(len(units)==1 and units[0][1]=='1','function unit')
    elif kind in ('points','values','gradient'):
        need(len(shape)==(1 if kind=='values' else 2) and 1<=shape[0]<=MAX_POINTS,'batch shape')
        n=shape[0]
        if kind!='values':need(shape[1]==d,'coordinate dimension')
        v=b.points.coordinates if kind=='points' else getattr(b,kind).values
        need(len(v)==n*(1 if kind=='values' else d),'batch payload')
        _finite(v,1e6 if kind=='points' else 1e12)
        if kind=='points':
            need(units==[(a.unit,'1') for a in b.axes] and all(b.domain[i%d].lower<=x<=b.domain[i%d].upper for i,x in enumerate(v)),'coordinate units or domain')
        elif kind=='values':need(len(units)==1 and units[0][1]=='1','value unit')
        else:need(len(units)==d and len({u[0] for u in units})==1 and all(u[1]==a.unit for u,a in zip(units,b.axes)),'gradient units')
    else:raise ValueError('missing representation')
    if kind in ('function','points'):
        need(not b.parent_sha256 and b.producer=='submitted' and not b.kernel_git_blob and b.assurance==pb.UNVERIFIED_INPUT and b.uncertainty==pb.UNKNOWN,'input provenance')
    else:
        need(len(b.parent_sha256)==2 and all(len(p)==32 for p in b.parent_sha256) and b.producer==PRODUCER and b.kernel_git_blob==bytes.fromhex(KERNEL) and b.assurance==pb.NUMERICAL and b.uncertainty==pb.NOT_CERTIFIED,'result provenance')
    return obj


@dataclass(frozen=True,slots=True)
class NativeObject:
    """Immutable canonical bytes. Message access returns a disposable copy."""
    wire: bytes

    def __post_init__(self):self.message()

    def message(self):return validate(parse(self.wire,pb.MathObject,MAX_OBJECT))

    @property
    def identity(self):return self.message().content_sha256.hex()


def freeze(b):
    return NativeObject(serialize(pb.MathObject(body=b,content_sha256=_digest(b))))


def _body(shape,axes,domain,units):
    b=pb.MathBody(schema_version=WIRE_VERSION,precision=pb.IEEE754_BINARY64,shape=shape,
                  producer='submitted',assurance=pb.UNVERIFIED_INPUT,uncertainty=pb.UNKNOWN)
    for n,u in axes:b.axes.add(name=n,unit=u)
    for lo,hi in domain:b.domain.add(lower=lo,upper=hi)
    for n,d in units:b.units.add(numerator=n,denominator=d)
    return b


def gaussian(centers,widths,weights,*,constant,axes,domain,output_unit):
    need(type(axes) in (list,tuple) and 1<=len(axes)<=MAX_DIM,'axis count');d=len(axes)
    need(all(type(a) in (list,tuple) and len(a)==2 and all(token(x) for x in a) for a in axes) and token(output_unit),'axis or output unit')
    need(type(domain) in (list,tuple) and len(domain)==d and all(type(a) in (list,tuple) and len(a)==2 for a in domain),'domain shape')
    need(type(weights) in (list,tuple) and len(weights)<=MAX_TERMS,'term count');t=len(weights)
    b=_body([t,d],axes,[(number(a),number(z)) for a,z in domain],[(output_unit,'1')])
    f=b.function;f.constant=number(constant);f.centers.extend(matrix(centers,t,d));f.widths.extend(matrix(widths,t,d));f.weights.extend(number(w) for w in weights)
    return freeze(b)


def points(function,rows):
    need(type(function) is NativeObject,'typed function');f=function.message().body
    need(f.WhichOneof('representation')=='function' and type(rows) in (list,tuple) and 1<=len(rows)<=MAX_POINTS,'point budget or kind')
    d=len(f.axes);n=len(rows);b=_body([n,d],[(a.name,a.unit) for a in f.axes],[(a.lower,a.upper) for a in f.domain],[(a.unit,'1') for a in f.axes]);b.points.coordinates.extend(matrix(rows,n,d))
    return freeze(b)


def pair(f,p):
    need(type(f) is NativeObject and type(p) is NativeObject,'typed pair')
    fm,pm=f.message(),p.message();a,b=fm.body,pm.body
    need(a.WhichOneof('representation')=='function' and b.WhichOneof('representation')=='points' and a.axes==b.axes and [serialize(q) for q in a.domain]==[serialize(q) for q in b.domain],'incompatible object domain or axes')
    return fm,pm


def result_object(operation,f,p,values):
    fm,pm=pair(f,p);a,b=fm.body,pm.body;n,d=b.shape;u=a.units[0].numerator
    need(operation in OP,'unsupported operation');grad=operation=='vfa.gradient'
    need(type(values) in (list,tuple) and len(values)==n*(d if grad else 1),'result count')
    o=_body([n,d] if grad else [n],[(q.name,q.unit) for q in a.axes],[(q.lower,q.upper) for q in a.domain],[(u,q.unit) for q in a.axes] if grad else [(u,'1')])
    o.parent_sha256.extend((fm.content_sha256,pm.content_sha256));o.producer=PRODUCER;o.kernel_git_blob=bytes.fromhex(KERNEL);o.assurance=pb.NUMERICAL;o.uncertainty=pb.NOT_CERTIFIED
    getattr(o,'gradient' if grad else 'values').values.extend(number(v,1e12) for v in values)
    return freeze(o)


def encode_carrier(raw,limit):
    need(type(raw) is bytes and 1<=len(raw)<=limit,'carrier budget')
    return base64.b64encode(raw).decode('ascii')


def decode_carrier(text,limit):
    need(type(text) is str and 1<=len(text)<=4*((limit+2)//3) and text.isascii(),'carrier budget')
    try:raw=base64.b64decode(text,validate=True)
    except (ValueError,TypeError) as exc:raise ValueError('invalid carrier') from exc
    need(encode_carrier(raw,limit)==text,'noncanonical carrier')
    return raw


class NativeVFAPlugin:
    def manifest(self):
        return Manifest(NAME,VERSION,tuple(Operation(op,op,INPUT,OUTPUT,schema_version=VERSION,assurance='numerical') for op in OP),track='research')

    def health(self):return True

    def self_test(self):
        f=gaussian([[0]],[[1]],[2],constant=1,axes=[('x','1')],domain=[(-2,2)],output_unit='1');p=points(f,[[0]])
        c=make_call('mel_vfa_evaluate',f,p,'self-test','self-test')
        m=parse(decode_carrier(self.handle(c.operation,c.payload())['frame'],MAX_RESULT),pb.VfaResult,MAX_RESULT)
        return list(m.result.body.values.values)==[3.]

    def handle(self,operation,request):
        need(operation in OP,'unsupported operation');INPUT.validate(request)
        c=decode_request(decode_carrier(request['frame'],MAX_REQUEST),operation)
        fm,pm=pair(c.function,c.points);b=fm.body;n,d=pm.body.shape;t=b.shape[0];f=b.function
        kernel=Mixture(np.array(f.centers).reshape(t,d),np.array(f.weights),np.array(f.widths).reshape(t,d),f.constant)
        x=np.array(pm.body.points.coordinates).reshape(n,d)
        v=kernel.evaluate(x) if operation=='vfa.evaluate' else kernel.gradient(x)
        r=result_object(operation,c.function,c.points,v.ravel().tolist())
        raw=serialize(pb.VfaResult(schema_version=WIRE_VERSION,operation=OP[operation],descriptor_sha256=bytes.fromhex(c.descriptor_sha256),request_id=c.request_id,correlation_id=c.correlation_id,result=r.message()))
        return {'frame':encode_carrier(raw,MAX_RESULT)}


def catalog():
    manifest=NativeVFAPlugin().manifest().describe();out=[]
    for d in legacy_catalog():
        b=d.body;op=next(o for o in manifest['operations'] if o['name']==b['operation'])
        # Model JSON input schema is unchanged; native result identity/producer is distinct.
        rs=b['result_schema'];rs['oneOf'][0]['properties']['result']['properties']['producer']={'const':PRODUCER}
        b.update(schema='cognitum.mel.descriptor.v2',codec='cognitum.mel.native_protobuf.v1',
                 plugin_name=NAME,plugin_version=VERSION,operation_schema_version=VERSION,
                 object_schema='cognitum.mel.v1.MathObject',runtime_manifest_sha256=sha(manifest),operation_sha256=sha(op),
                 result_schema_sha256=sha(rs),native_proto_type_urls=['type.googleapis.com/cognitum.mel.v1.VfaRequest','type.googleapis.com/cognitum.mel.v1.VfaResult'],
                 protobuf_descriptor_sha256=hashlib.sha256(pb.DESCRIPTOR.serialized_pb).hexdigest(),legacy_descriptor_sha256=d.identity)
        del b['object_codec_git_blob'];del b['runtime_adapter_git_blob']
        b['status']='reviewed_protobuf_reference_only'
        out.append((sha(b),b))
    return tuple(out)


def descriptor(name):
    known={b['public_name']:(h,b) for h,b in catalog()}
    need(type(name) is str and name in known,'unknown operation');return known[name]


def discover(registry,selection):
    need(type(registry) is Registry and type(selection) is tuple and len(selection)<=len(PUBLIC),'explicit trusted selection')
    out=[];seen=set()
    for item in selection:
        need(type(item) is tuple and len(item)==2 and all(type(v) is str for v in item),'selection entry');name,identity=item;h,b=descriptor(name)
        need(name not in seen and h==identity,'duplicate or stale descriptor');seen.add(name)
        r=registry.resolve(b['operation'],allow_research=True)
        need(r is not None,'operation unavailable');e,o=r
        need(e.factory is NativeVFAPlugin and sha(e.manifest.describe())==b['runtime_manifest_sha256'] and sha(o.describe())==b['operation_sha256'],'runtime descriptor mismatch')
        out.append({'descriptor_sha256':h,'descriptor':b,'tool_schema':{'type':'function','function':{'name':name,'description':b['description'],'parameters':b['arguments_schema']}},'execution_authorized':False})
    return tuple(sorted(out,key=lambda v:v['descriptor']['public_name']))


@dataclass(frozen=True,slots=True)
class NativeCall:
    public_name: str
    descriptor_sha256: str
    request_id: str
    correlation_id: str
    function: NativeObject
    points: NativeObject

    def __post_init__(self):
        need(descriptor(self.public_name)[0]==self.descriptor_sha256 and all(type(v) is str and ID.fullmatch(v) for v in (self.request_id,self.correlation_id)),'call identity')
        pair(self.function,self.points)

    @property
    def operation(self):return PUBLIC[self.public_name]

    def wire(self):
        return serialize(pb.VfaRequest(schema_version=WIRE_VERSION,operation=OP[self.operation],descriptor_sha256=bytes.fromhex(self.descriptor_sha256),request_id=self.request_id,correlation_id=self.correlation_id,function=self.function.message(),points=self.points.message()))

    def payload(self):return {'frame':encode_carrier(self.wire(),MAX_REQUEST)}


def make_call(name,f,p,request_id,correlation_id):return NativeCall(name,descriptor(name)[0],request_id,correlation_id,f,p)


def decode_request(raw,operation):
    m=parse(raw,pb.VfaRequest,MAX_REQUEST)
    need(operation in OP and m.schema_version==WIRE_VERSION and m.operation==OP[operation] and m.HasField('function') and m.HasField('points'),'request schema or operation')
    name=next(n for n,o in PUBLIC.items() if o==operation)
    return NativeCall(name,m.descriptor_sha256.hex(),m.request_id,m.correlation_id,NativeObject(serialize(m.function)),NativeObject(serialize(m.points)))


def bind_model(registry,selection,name,raw_arguments,*,request_id,correlation_id):
    offers=discover(registry,selection);need(type(name) is str and any(x['descriptor']['public_name']==name for x in offers),'operation not selected')
    a=strict_json(raw_arguments);fields(a,('axes','domain','terms','constant','output_unit','points'))
    axes=[];domain=[];centers=[];widths=[];weights=[]
    for v in sequence(a['axes'],1,MAX_DIM):fields(v,('name','unit'));axes.append((v['name'],v['unit']))
    for v in sequence(a['domain'],len(axes),len(axes)):fields(v,('lower','upper'));domain.append((v['lower'],v['upper']))
    for v in sequence(a['terms'],0,MAX_MODEL_TERMS):
        fields(v,('center','width','weight'));centers.append(sequence(v['center'],len(axes),len(axes)));widths.append(sequence(v['width'],len(axes),len(axes)));weights.append(v['weight'])
    f=gaussian(centers,widths,weights,constant=a['constant'],axes=axes,domain=domain,output_unit=a['output_unit'])
    p=points(f,[sequence(v,len(axes),len(axes)) for v in sequence(a['points'],1,MAX_MODEL_POINTS)])
    return make_call(name,f,p,request_id,correlation_id)


def checked_result(call,response):
    need(type(call) is NativeCall and type(response) is Response and response.contract_version==CONTRACT_VERSION and (response.request_id,response.correlation_id,response.operation)==(call.request_id,call.correlation_id,call.operation),'response identity')
    need(response.execution_status=='completed' and response.module=={'name':NAME,'version':VERSION} and response.assurance=='numerical','unsuccessful response')
    OUTPUT.validate(response.result);m=parse(decode_carrier(response.result['frame'],MAX_RESULT),pb.VfaResult,MAX_RESULT)
    need(m.schema_version==WIRE_VERSION and m.operation==OP[call.operation] and m.descriptor_sha256==bytes.fromhex(call.descriptor_sha256) and (m.request_id,m.correlation_id)==(call.request_id,call.correlation_id) and m.HasField('result'),'result frame mismatch')
    r=NativeObject(serialize(m.result));b=r.message().body;kind='gradient' if call.operation=='vfa.gradient' else 'values'
    need(b.WhichOneof('representation')==kind,'result kind')
    need(result_object(call.operation,call.function,call.points,list(getattr(b,kind).values)).wire==r.wire,'result type or lineage')
    return r


def model_feedback(call,response):
    need(type(call) is NativeCall and type(response) is Response and response.contract_version==CONTRACT_VERSION and (response.request_id,response.correlation_id,response.operation)==(call.request_id,call.correlation_id,call.operation),'response identity')
    out=dict(tool=call.public_name,descriptor_sha256=call.descriptor_sha256)
    if response.execution_status!='completed':
        need(response.execution_status in FAILURES and response.result is None,'unexpected failure response')
        return dict(out,ok=False,error=dict(code=FAILURES[response.execution_status],retryable=False))
    r=checked_result(call,response);b=r.message().body;k=b.WhichOneof('representation');v=list(getattr(b,k).values)
    if k=='gradient':d=b.shape[1];v=[v[i:i+d] for i in range(0,len(v),d)]
    return dict(out,ok=True,result=dict(object_id=r.identity,function_id=call.function.identity,points_id=call.points.identity,kind=k,axes=[[a.name,a.unit] for a in b.axes],shape=list(b.shape),domain=[dict(lower=a.lower,upper=a.upper) for a in b.domain],units=[[u.numerator,u.denominator] for u in b.units],values=v,assurance='numerical',error='not_certified',limitations=list(LIMITATIONS),producer=PRODUCER,kernel_git_blob=KERNEL))
