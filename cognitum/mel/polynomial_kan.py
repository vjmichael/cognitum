"""COG-04B bounded binary64 polynomial KAN profile in the existing MEL runtime.

Trusted typed calls only, no model schema or default registry enablement.
Exact represented-input witness checked again by the shared Admission host.
"""
from dataclasses import dataclass
import hashlib
import math
from fractions import Fraction
import numpy as np
from cognitum.contracts import Manifest, Operation, Shape, Response, CONTRACT_VERSION
from cognitum.registry import Registry
from cognitum.research.kan_trainable import Layer, Network
from . import polynomial_kan_pb2 as pb, polynomial_witness as w
from .native import parse, serialize, encode_carrier, decode_carrier, ID, need
from .discovery import sha

NAME='mel_polynomial_kan_reference';VERSION='1.0.0';OP='kan.polynomial.evaluate'
MAX_REQUEST=32768;MAX_RESULT=8192;MAX_CHECKPOINT=16384;MAX_ROWS=4;MAX_WIDTH=4
INPUT=Shape((('frame',43692),));OUTPUT=Shape((('frame',10924),))
MAX_WORK=2000000;MAX_COMPONENTS=200
TRAINABLE_BLOB='238f1ea9969aab6ecd87be0dcefb9966ae6a6d59'
WITNESS_BLOB='c269dc30b926e3ffc4649e5ece79a78416d88209'
KINDS={pb.CLAMPED_SPLINE:'spline_clamped',pb.CHEBYSHEV:'chebyshev'}


def digest(raw):return hashlib.sha256(raw).digest()


def model_from_message(m):
    need(m.schema_version==1 and 1<=len(m.layers)<=2,'checkpoint profile')
    ls=[]
    for v in m.layers:
        i,o,k,p=v.inputs,v.outputs,v.knots,v.degree
        need(1<=i<=MAX_WIDTH and 1<=o<=MAX_WIDTH and v.basis in KINDS,'layer shape/basis')
        kind=KINDS[v.basis]
        need((k==2 and p<=8) if kind=='chebyshev' else (1<=p<=3 and 2*(p+1)<=k<=12),'basis profile')
        n=p+1 if kind=='chebyshev' else k-p-1
        need(len(v.grid)==i*k and len(v.coefficients)==o*i*n and len(v.mask)==o*i and len(v.bias)==o,'checkpoint arrays')
        # Reject very tiny nonzero values to bound exact-rational operand sizes.
        need(all(math.isfinite(x) and (x==0 or 2**-128<=abs(x)<=1000) for x in (*v.grid,*v.coefficients,*v.bias)),'parameter bounds')
        ls.append(Layer(kind,p,np.array(v.grid).reshape(i,k),np.array(v.coefficients).reshape(o,i,n),np.array(v.mask,dtype=float).reshape(o,i),np.array(v.bias)))
    return Network(tuple(ls))


@dataclass(frozen=True,slots=True)
class Checkpoint:
    wire:bytes
    def __post_init__(self):self.model()
    def message(self):return parse(self.wire,pb.Checkpoint,MAX_CHECKPOINT)
    def model(self):return model_from_message(self.message())
    @property
    def identity(self):return digest(self.wire).hex()


def export_checkpoint(model):
    need(type(model) is Network,'typed trained network')
    m=pb.Checkpoint(schema_version=1)
    for layer in model.layers:
        need(layer.kind in KINDS.values(),'unsupported basis; no implicit legacy conversion')
        m.layers.add(basis=next(k for k,v in KINDS.items() if v==layer.kind),degree=layer.degree,
                     inputs=layer.inputs,outputs=layer.outputs,knots=layer.grid.shape[1],grid=layer.grid.ravel(),
                     coefficients=layer.coefficients.ravel(),mask=layer.mask.ravel().astype(bool).tolist(),bias=layer.bias)
    return Checkpoint(serialize(m))


@dataclass(frozen=True,slots=True)
class Approval:
    checkpoint:Checkpoint
    review_id:str
    def __post_init__(self):need(type(self.checkpoint) is Checkpoint and type(self.review_id) is str and ID.fullmatch(self.review_id),'invalid checkpoint review')


def descriptor():
    m=PolynomialPlugin().manifest().describe();body=dict(schema='cognitum.mel.polynomial_kan.descriptor.v1',operation=OP,
        plugin_name=NAME,plugin_version=VERSION,operation_schema_version=VERSION,contract_version=CONTRACT_VERSION,
        runtime_manifest_sha256=sha(m),operation_sha256=sha(m['operations'][0]),
        native_proto_type_urls=['type.googleapis.com/'+x.DESCRIPTOR.full_name for x in (pb.Request,pb.Result)],
        protobuf_descriptor_sha256=digest(pb.DESCRIPTOR.serialized_pb).hex(),
        kernel_git_blobs=[TRAINABLE_BLOB,WITNESS_BLOB],max_components=MAX_COMPONENTS,assurance='numerical',witness='exact_rational_piecewise_polynomial_v1',profile='binary64_polynomial_layers_v1',
        max_rows=MAX_ROWS,max_width=MAX_WIDTH,max_layers=2,max_order=2,max_request_bytes=MAX_REQUEST,
        max_result_bytes=MAX_RESULT,track='research',effects=[],model_advertised=False,lu_registered=False,execution_authorized=False)
    return sha(body),body


def discover(registry,selection):
    h,b=descriptor();need(type(registry) is Registry and selection==((OP,h),),'explicit exact selection')
    resolved=registry.resolve(OP,allow_research=True);need(resolved is not None,'unavailable operation')
    entry,operation=resolved
    need(entry.factory is PolynomialPlugin and sha(entry.manifest.describe())==b['runtime_manifest_sha256'] and sha(operation.describe())==b['operation_sha256'] and not operation.effects,'runtime mismatch')
    return ((h,b),)


@dataclass(frozen=True,slots=True)
class Limits:
    request_bytes:int=MAX_REQUEST
    result_bytes:int=MAX_RESULT
    timeout_ms:int=5000
    calls:int=1
    work:int=MAX_WORK
    def __post_init__(self):need(all(type(x) is int and 1<=x<=hi for x,hi in ((self.request_bytes,MAX_REQUEST),(self.result_bytes,MAX_RESULT),(self.timeout_ms,10000),(self.calls,16),(self.work,16*MAX_WORK))),'polynomial grant limits')


def validated(raw):
    m=parse(raw,pb.Request,MAX_REQUEST)
    need(m.schema_version==1 and m.descriptor_sha256==bytes.fromhex(descriptor()[0]) and ID.fullmatch(m.request_id) and ID.fullmatch(m.correlation_id),'request identity')
    c=Checkpoint(serialize(m.checkpoint));model=c.model()
    need(m.checkpoint_sha256==bytes.fromhex(c.identity) and 1<=m.rows<=MAX_ROWS and len(m.coordinates)==m.rows*model.layers[0].inputs and m.order<=2,'request profile')
    width=model.layers[0].inputs
    need(m.rows*model.layers[-1].outputs*(1+(width if m.order else 0)+(width*width if m.order==2 else 0))<=MAX_COMPONENTS,'component budget')
    need(m.HasField('absolute_tolerance') and 0<=m.absolute_tolerance<=1e-6,'absolute tolerance')
    need(all(math.isfinite(x) and (x==0 or 2**-128<=abs(x)<=1000) for x in m.coordinates),'coordinate bounds')
    x=np.array(m.coordinates).reshape(m.rows,model.layers[0].inputs);g=model.layers[0].grid
    need(np.all(x>=g[:,0]) and np.all(x<=g[:,-1]),'input outside domain')
    return m,model,x


@dataclass(frozen=True,slots=True)
class Call:
    operation:str
    wire:bytes
    def __post_init__(self):need(self.operation==OP,'wrong operation');validated(self.wire)
    @property
    def message(self):return validated(self.wire)[0]
    def payload(self):return {'frame':encode_carrier(self.wire,MAX_REQUEST)}


def make_call(checkpoint,rows,order,absolute_tolerance,request_id,correlation_id):
    need(type(checkpoint) is Checkpoint and type(order) is int and 0<=order<=2 and type(absolute_tolerance) in (int,float),'typed call')
    x=np.asarray(rows);need(x.dtype.kind in 'fiu' and x.ndim==2 and 1<=len(x)<=MAX_ROWS and x.shape[1]<=MAX_WIDTH,'point array')
    m=pb.Request(schema_version=1,descriptor_sha256=bytes.fromhex(descriptor()[0]),request_id=request_id,correlation_id=correlation_id,
                 checkpoint=checkpoint.message(),checkpoint_sha256=bytes.fromhex(checkpoint.identity),rows=len(x),coordinates=x.astype(float).ravel(),order=order,absolute_tolerance=absolute_tolerance)
    return Call(OP,serialize(m))


def matches(c,approval):return type(approval) is Approval and serialize(c.message.checkpoint)==approval.checkpoint.wire


def account(c,limits):
    need(type(c) is Call and type(limits) is Limits,'resource profile')
    m=c.message
    # Conservative administrative charge, not a FLOP/runtime certificate.
    work=1000+100*m.rows*(m.order+1)*sum(v.inputs*v.outputs*v.knots*(v.degree+1)**2 for v in m.checkpoint.layers)
    return work if work<=MAX_WORK else None


def exact_components(model,x,order):
    # All values, all Jacobians, all Hessians; each row independently certified.
    rows=[w.enclose(model,[(v,v) for v in row],order) for row in x]
    return [b for k in range(order+1) for row in rows for b in w.flatten(row[k])]


def canonical_component(bounds,observed,tolerance):
    lo,hi=bounds;need(lo==hi,'point witness must be exact');need(math.isfinite(observed) and abs(observed)<=1e12,'observation bounds')
    error=abs(Fraction(observed)-lo);need(error<=Fraction(tolerance),'numerical observation outside absolute tolerance')
    return pb.Component(observed=observed,lower=w.outward(lo,False),upper=w.outward(hi,True),absolute_error_upper=w.outward(error,True))


def compute(c):
    m,model,x=validated(c.wire)
    observed=np.concatenate([v.ravel() for v in model.evaluate(x,m.order)])
    bounds=exact_components(model,x,m.order);need(len(observed)==len(bounds),'component count')
    r=pb.Result(schema_version=1,descriptor_sha256=m.descriptor_sha256,request_id=m.request_id,correlation_id=m.correlation_id,
        request_sha256=digest(c.wire),checkpoint_sha256=m.checkpoint_sha256,rows=m.rows,inputs=model.layers[0].inputs,outputs=model.layers[-1].outputs,order=m.order)
    for b,v in zip(bounds,observed):r.components.append(canonical_component(b,float(v),m.absolute_tolerance))
    raw=serialize(r);need(len(raw)<=MAX_RESULT,'result budget');return raw


class PolynomialPlugin:
    def manifest(self):return Manifest(NAME,VERSION,(Operation(OP,OP,INPUT,OUTPUT,assurance='numerical',schema_version=VERSION),),track='research')
    def health(self):return True
    def self_test(self):
        c=export_checkpoint(Network((Layer('chebyshev',1,[[-1.,1.]],[[[0.,.5]]],[[1.]],[0.]),)))
        r=pb.Result.FromString(compute(make_call(c,[[.5]],1,0.,'self','self')))
        return [v.observed for v in r.components]==[.25,.5]
    def handle(self,operation,request):
        INPUT.validate(request);return {'frame':encode_carrier(compute(Call(operation,decode_carrier(request['frame'],MAX_REQUEST))),MAX_RESULT)}


def checked_result(c,response):
    need(type(c) is Call and type(response) is Response,'typed result')
    m,model,x=validated(c.wire)
    need(response.contract_version==CONTRACT_VERSION and (response.request_id,response.correlation_id,response.operation)==(m.request_id,m.correlation_id,OP) and response.execution_status=='completed' and response.module=={'name':NAME,'version':VERSION} and response.assurance=='numerical','response identity')
    OUTPUT.validate(response.result);raw=decode_carrier(response.result['frame'],MAX_RESULT);r=parse(raw,pb.Result,MAX_RESULT)
    need((r.schema_version,r.descriptor_sha256,r.request_id,r.correlation_id,r.request_sha256,r.checkpoint_sha256,r.rows,r.inputs,r.outputs,r.order)==(1,m.descriptor_sha256,m.request_id,m.correlation_id,digest(c.wire),m.checkpoint_sha256,m.rows,model.layers[0].inputs,model.layers[-1].outputs,m.order),'result binding')
    bounds=exact_components(model,x,m.order);need(len(r.components)==len(bounds),'component count')
    for b,v in zip(bounds,r.components):need(serialize(v)==serialize(canonical_component(b,v.observed,m.absolute_tolerance)),'incorrect witness or observation')
    return raw


def continuous_enclosure(checkpoint,box,order=0):
    """Local exact rational continuous-box verifier; not a worker or authority."""
    need(type(checkpoint) is Checkpoint and type(order) is int and 0<=order<=2,'box profile')
    x=np.asarray(box);need(x.dtype.kind in 'fiu' and x.shape==(checkpoint.model().layers[0].inputs,2) and np.isfinite(x).all() and np.all((x==0)|(np.abs(x)>=2**-128)),'box shape/range')
    return tuple((w.outward(lo,False),w.outward(hi,True)) for lo,hi in w.flatten(w.enclose(checkpoint.model(),x,order)))
