"""MEL-03C first typed HDC/KAN research adapters. No grant or model advertising.

Reuse existing trusted Runtime and bounded base64 carrier, HDC algebra and
PortableKAN. The VFA-only Admission does not admit these routes yet.
"""
from dataclasses import dataclass
import hashlib
import numpy as np
from cognitum.contracts import Manifest, Operation, Shape, CONTRACT_VERSION, Response
from cognitum.registry import Registry
from cognitum.research.hdc_algebra import Spec
from cognitum.research.kan_portable import PortableKAN
from . import engines_pb2 as pb
from .native import parse, serialize, encode_carrier, decode_carrier, ID, need
from .discovery import sha

NAME = 'mel_hdc_kan_reference'
VERSION = '1.0.0'
MAX_DIM = 4096
MAX_CANDIDATES = 16
MAX_ROWS = 16
MAX_REQUEST = 32768
MAX_RESULT = 6144
INPUT = Shape((('frame', 43692),))
OUTPUT = Shape((('frame', 8192),))
OPERATIONS = {'hdc.bind': ('bind', 'bound', 'exact_arithmetic'),
              'hdc.query': ('query', 'query', 'exact_arithmetic'),
              'kan.evaluate': ('kan', 'kan', 'numerical')}
HDC_BLOB = '1b64d122fd0a34e5de3e747c4076ffaa80216284'
KAN_BLOB = 'f56b9b937a166531ca8130f89e50964ea02e66d8'
TYPE_URLS = ('type.googleapis.com/'+pb.EngineRequest.DESCRIPTOR.full_name,
             'type.googleapis.com/'+pb.EngineResult.DESCRIPTOR.full_name)


def kernel(operation):
    return KAN_BLOB if operation == 'kan.evaluate' else HDC_BLOB


def catalog():
    manifest = EnginePlugin().manifest().describe()
    rows = []
    for operation, (input_kind, output_kind, assurance) in sorted(OPERATIONS.items()):
        op = next(o for o in manifest['operations'] if o['name'] == operation)
        body = dict(schema='cognitum.mel.engines.descriptor.v1', operation=operation,
                    input_kind=input_kind, output_kind=output_kind, assurance=assurance,
                    native_proto_type_urls=list(TYPE_URLS), plugin_name=NAME,
                    plugin_version=VERSION, operation_schema_version=VERSION,
                    contract_version=CONTRACT_VERSION,
                    runtime_manifest_sha256=sha(manifest), operation_sha256=sha(op),
                    protobuf_descriptor_sha256=hashlib.sha256(pb.DESCRIPTOR.serialized_pb).hexdigest(),
                    kernel_git_blob=kernel(operation), max_request_bytes=MAX_REQUEST,
                    max_result_bytes=MAX_RESULT, max_hdc_dimension=MAX_DIM,
                    max_candidates=MAX_CANDIDATES, max_kan_rows=MAX_ROWS,
                    max_layers=2, max_width=8, max_knots=12,
                    track='research', effects=[], model_advertised=False,
                    lu_registered=False, execution_authorized=False,
                    limitations=['submitted_objects_only','no_intent_validation',
                        'bounded_binary_hdc_or_portable_kan_subset','no_training',
                        'no_semantic_probability_or_certified_numerical_bound'])
        rows.append((sha(body), body))
    return tuple(rows)


def descriptor(operation):
    need(type(operation) is str and operation in OPERATIONS, 'unsupported operation')
    return next((h,b) for h,b in catalog() if b['operation']==operation)


def discover(registry, selection):
    """Trusted reference discovery only, exact nominated factory, no grant."""
    need(type(registry) is Registry and type(selection) is tuple and len(selection)<=len(OPERATIONS), 'explicit selection')
    offers=[]; seen=set()
    for item in selection:
        need(type(item) is tuple and len(item)==2 and all(type(v) is str for v in item), 'selection entry')
        op,h=item; expected,b=descriptor(op)
        need(h==expected and op not in seen, 'stale or duplicate descriptor')
        seen.add(op); resolved=registry.resolve(op,allow_research=True)
        need(resolved is not None, 'unavailable operation'); entry,operation=resolved
        need(entry.factory is EnginePlugin and sha(entry.manifest.describe())==b['runtime_manifest_sha256']
             and sha(operation.describe())==b['operation_sha256'] and not operation.effects, 'runtime mismatch')
        offers.append((h,b))
    return tuple(sorted(offers,key=lambda item:item[1]['operation']))


def vector(m):
    d=m.dimension
    need(1<=d<=MAX_DIM and len(m.bits)==(d+7)//8, 'binary vector shape')
    need(d%8==0 or m.bits[-1]>>(d%8)==0, 'nonzero padding')
    return np.unpackbits(np.frombuffer(m.bits,dtype=np.uint8),bitorder='little')[:d].astype(np.bool_)


def pack(a):
    return pb.BinaryVector(dimension=len(a),bits=np.packbits(a,bitorder='little').tobytes())


def _floats(values, shape, max_abs=1000.):
    count=int(np.prod(shape))
    need(count>0 and len(values)==count, 'array shape')
    a=np.asarray(values,dtype=np.float32).reshape(shape)
    need(np.isfinite(a).all() and (np.abs(a)<=max_abs).all(), 'array range')
    return a


def layers_and_input(m):
    need(1<=len(m.layers)<=2 and 1<=m.rows<=MAX_ROWS, 'KAN layer or row bound')
    layers=[]; prev=None
    for layer in m.layers:
        i,o,k,degree=layer.inputs,layer.outputs,layer.knots,layer.degree
        need(1<=i<=8 and 1<=o<=8 and 3<=k<=12 and (prev is None or prev==i), 'KAN layer shape')
        need(layer.basis in (pb.BSPLINE,pb.RBF) and (0<=degree<=3 and k-degree-1>0 if layer.basis==pb.BSPLINE else degree==0), 'KAN basis')
        basis=k if layer.basis==pb.RBF else k-degree-1
        grid=_floats(layer.grid,(i,k))
        need((np.diff(grid,axis=1)>=1e-4).all(), 'KAN separated knots')
        weights=_floats(layer.coefficients,(o,i,basis));mask=_floats(layer.mask,(o,i))
        need(((mask==0)|(mask==1)).all(), 'KAN binary mask')
        base=_floats(layer.base,(o,i)) if layer.base else None
        bias=_floats(layer.bias,(o,)) if layer.bias else None
        layers.append(dict(grid=grid,spline=weights,mask=mask,base=base,bias=bias,
                           degree=degree,kind='rbf' if layer.basis==pb.RBF else 'spline'))
        prev=o
    x=_floats(m.coordinates,(m.rows,m.layers[0].inputs))
    _domain(x,layers[0]['grid'])
    return layers,x


def _domain(x,grid):
    need(np.isfinite(x).all() and (x>=grid[:,0]).all() and (x<=grid[:,-1]).all(), 'KAN input outside knot domain')


def validate_request(raw,operation):
    m=parse(raw,pb.EngineRequest,MAX_REQUEST);h,b=descriptor(operation)
    need(m.schema_version==1 and m.descriptor_sha256==bytes.fromhex(h) and ID.fullmatch(m.request_id)
         and ID.fullmatch(m.correlation_id) and m.WhichOneof('input')==b['input_kind'], 'request identity or operation mismatch')
    if operation=='hdc.bind':
        need(m.bind.HasField('left') and m.bind.HasField('right'), 'missing vectors')
        a,z=vector(m.bind.left),vector(m.bind.right);need(len(a)==len(z), 'dimension mismatch')
    elif operation=='hdc.query':
        need(m.query.HasField('probe') and 1<=len(m.query.candidates)<=MAX_CANDIDATES, 'query size')
        a=vector(m.query.probe)
        for c in m.query.candidates:need(len(vector(c))==len(a), 'dimension mismatch')
    else:layers_and_input(m.kan)
    return m


@dataclass(frozen=True,slots=True)
class Call:
    operation: str
    wire: bytes
    def __post_init__(self):validate_request(self.wire,self.operation)
    @property
    def message(self):return validate_request(self.wire,self.operation)
    def payload(self):return {'frame':encode_carrier(self.wire,MAX_REQUEST)}


def make_call(operation,input_message,request_id,correlation_id):
    h,b=descriptor(operation)
    m=pb.EngineRequest(schema_version=1,descriptor_sha256=bytes.fromhex(h),request_id=request_id,correlation_id=correlation_id)
    getattr(m,b['input_kind']).CopyFrom(input_message)
    return Call(operation,serialize(m))


def compute(call):
    m=call.message;op=call.operation;h,b=descriptor(op)
    out=pb.EngineResult(schema_version=1,descriptor_sha256=bytes.fromhex(h),request_id=m.request_id,
                        correlation_id=m.correlation_id,request_sha256=hashlib.sha256(call.wire).digest(),
                        assurance=b['assurance'],kernel_git_blob=bytes.fromhex(kernel(op)))
    if op=='hdc.bind':
        a,z=vector(m.bind.left),vector(m.bind.right)
        out.bound.CopyFrom(pack(Spec('BSC',len(a)).bind(a,z)))
    elif op=='hdc.query':
        a=vector(m.query.probe);spec=Spec('BSC',len(a));dist=[]
        for c in m.query.candidates:
            z=vector(c);d=int(np.count_nonzero(a!=z))
            # Cross-check the existing algebra's normalized Hamming similarity.
            need(abs(spec.similarity(a,z)-(1-2*d/len(a)))<1e-12,'similarity mismatch')
            dist.append(d)
        out.query.hamming_distance.extend(dist)
        out.query.best_index.extend(i for i,d in enumerate(dist) if d==min(dist))
    else:
        layers,x=layers_and_input(m.kan)
        for layer in layers:
            _domain(x,layer['grid'])
            x=PortableKAN([layer])(x)
            need(np.isfinite(x).all() and (np.abs(x)<=1e6).all(),'KAN result range')
        out.kan.rows,out.kan.columns=x.shape
        out.kan.values.extend(x.ravel().tolist())
    raw=serialize(out);need(len(raw)<=MAX_RESULT,'result budget');return raw


class EnginePlugin:
    def manifest(self):
        return Manifest(NAME,VERSION,tuple(Operation(op,op,INPUT,OUTPUT,assurance=details[2],schema_version=VERSION)
                                         for op,details in OPERATIONS.items()),track='research')
    def health(self):return True
    def self_test(self):
        c=make_call('hdc.bind',pb.BindInput(left=pb.BinaryVector(dimension=3,bits=b'\x01'),right=pb.BinaryVector(dimension=3,bits=b'\x03')),'self','self')
        return pb.EngineResult.FromString(compute(c)).bound.bits==b'\x02'
    def handle(self,operation,request):
        INPUT.validate(request)
        c=Call(operation,decode_carrier(request['frame'],MAX_REQUEST))
        return {'frame':encode_carrier(compute(c),MAX_RESULT)}


def checked_result(call,response):
    need(type(call) is Call and type(response) is Response,'typed result')
    m=call.message; h,b=descriptor(call.operation)
    need(response.contract_version==CONTRACT_VERSION and (response.request_id,response.correlation_id,response.operation)==(m.request_id,m.correlation_id,call.operation)
         and response.execution_status=='completed' and response.module=={'name':NAME,'version':VERSION} and response.assurance==b['assurance'],'response identity or status')
    OUTPUT.validate(response.result);raw=decode_carrier(response.result['frame'],MAX_RESULT)
    r=parse(raw,pb.EngineResult,MAX_RESULT)
    need(r.schema_version==1 and (r.request_id,r.correlation_id)==(m.request_id,m.correlation_id) and r.descriptor_sha256==bytes.fromhex(h)
         and r.request_sha256==hashlib.sha256(call.wire).digest() and r.kernel_git_blob==bytes.fromhex(kernel(call.operation))
         and r.WhichOneof('output')==b['output_kind'] and r.assurance==b['assurance'],'result binding')
    if call.operation=='hdc.bind':
        # Independent packed byte XOR witness, including exact padding/dimension.
        vector(r.bound)
        need(r.bound.dimension==m.bind.left.dimension and r.bound.bits==bytes(a^b for a,b in zip(m.bind.left.bits,m.bind.right.bits)),'wrong binding witness')
    elif call.operation=='hdc.query':
        dist=[sum((a^b).bit_count() for a,b in zip(m.query.probe.bits,c.bits)) for c in m.query.candidates]
        need(list(r.query.hamming_distance)==dist and list(r.query.best_index)==[i for i,d in enumerate(dist) if d==min(dist)],'wrong query witness')
    else:
        need(r.kan.rows==m.kan.rows and r.kan.columns==m.kan.layers[-1].outputs,'KAN result shape')
        _floats(r.kan.values,(r.kan.rows,r.kan.columns),1e6)
        # Shape/lineage only: no independent per-request KAN value certificate.
    return raw
