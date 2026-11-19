"""MEL-03C3 closed model JSON codecs and typed, pinned checkpoint objects.

Host approval is an explicit trusted process-local decision, not a model claim.
The checkpoint wire profile uses the existing KanInput protobuf with layers only:
rows=0, no coordinates. It is distinct from a runnable EngineRequest.
"""
from dataclasses import dataclass
import hashlib
import re
from . import engines as e, engines_pb2 as pb
from .native import parse, serialize, need, ID
from .discovery import strict_json, fields, sequence, obj, arr, num, const, sha
from .objects import number

MAX_MODEL_DIM=1024
MAX_MODEL_CANDIDATES=8
MAX_CHECKPOINT_BYTES=16384
MAX_CHECKPOINTS=16
DIGEST=re.compile(r'[0-9a-f]{64}\Z',re.ASCII)
BITSTR=re.compile(r'[01]+\Z',re.ASCII)
LIMITATIONS=('submitted_vectors_only','exact_binary_hamming_not_semantic_probability')
KAN_LIMITATIONS=('approved_parameters_only','binary32_numerical_not_certified','no_training_or_calibration')
STATUSES=('resource_denied','invalid_input','replay_denied','revoked','cancelled','timed_out','unavailable','denied','error')


def checkpoint_wire(layers):
    return serialize(pb.KanInput(layers=layers))


@dataclass(frozen=True, slots=True)
class Checkpoint:
    wire: bytes
    def __post_init__(self):self.message()
    def message(self):
        m=parse(self.wire,pb.KanInput,MAX_CHECKPOINT_BYTES)
        need(m.rows==0 and not m.coordinates and 1<=len(m.layers)<=2,'checkpoint layers-only profile')
        first=m.layers[0];need(1<=first.inputs<=8 and 3<=first.knots<=12 and len(first.grid)==first.inputs*first.knots,'checkpoint grid')
        # Validate all parameters and shapes, without running the model.
        probe=pb.KanInput(layers=m.layers,rows=1,coordinates=[first.grid[i*first.knots] for i in range(first.inputs)])
        e.layers_and_input(probe)
        return m
    @property
    def identity(self):return hashlib.sha256(self.wire).hexdigest()


@dataclass(frozen=True, slots=True)
class Approval:
    checkpoint: Checkpoint
    review_id: str
    def __post_init__(self):
        need(type(self.checkpoint) is Checkpoint and type(self.review_id) is str and ID.fullmatch(self.review_id),'invalid checkpoint review')


def public_name(operation):
    need(operation in e.OPERATIONS,'unknown operation')
    return 'mel_'+operation.replace('.','_')


def schema(operation):
    bit={'type':'string','pattern':'^[01]+$','minLength':1,'maxLength':MAX_MODEL_DIM}
    if operation=='hdc.bind':return obj({'left':bit,'right':bit})
    if operation=='hdc.query':return obj({'probe':bit,'candidates':arr(bit,1,MAX_MODEL_CANDIDATES)})
    need(operation=='kan.evaluate','unknown operation')
    return obj({'points':arr(arr(num(-1000,1000),1,8),1,e.MAX_ROWS)})


def output_schema(operation):
    digest={'type':'string','pattern':'^[0-9a-f]{64}$','minLength':64,'maxLength':64}
    base={'tool':const(public_name(operation)),'codec_sha256':digest,'descriptor_sha256':digest,'request_sha256':digest}
    if operation=='hdc.bind':data={'bits':{'type':'string','pattern':'^[01]+$','minLength':1,'maxLength':MAX_MODEL_DIM}}
    elif operation=='hdc.query':data={'hamming_distance':arr({'type':'integer','minimum':0,'maximum':MAX_MODEL_DIM},1,MAX_MODEL_CANDIDATES),'best_index':arr({'type':'integer','minimum':0,'maximum':MAX_MODEL_CANDIDATES-1},1,MAX_MODEL_CANDIDATES)}
    else:data={'values':arr(arr(num(-1e6,1e6),1,8),1,e.MAX_ROWS),'checkpoint_sha256':digest}
    result=obj(dict(data,assurance=const(e.descriptor(operation)[1]['assurance']),limitations=const(list(KAN_LIMITATIONS if operation=='kan.evaluate' else LIMITATIONS)),kernel_git_blob=const(e.kernel(operation))))
    return {'oneOf':[obj(dict(base,ok=const(True),result_sha256=digest,result=result)),obj(dict(base,ok=const(False),error=obj({'code':{'enum':list(STATUSES)},'retryable':const(False)})))]}


def descriptor(operation):
    h,b=e.descriptor(operation);name=public_name(operation)
    descriptions={'hdc.bind':'XOR two equal-length binary hypervectors. Bit strings use index order, 0 or 1 only.',
        'hdc.query':'Compare a binary probe with equal-length candidates. Return exact Hamming distances and all nearest indices (zero based); not semantic probabilities.',
        'kan.evaluate':'Evaluate the host-selected approved KAN checkpoint at ordered in-domain coordinate rows. Submit points only, no weights or paths. Numerical approximation, not certified.'}
    d={'schema':'cognitum.mel.engine_model_codec.v1','public_name':name,'operation':operation,
       'engine_descriptor_sha256':h,'arguments_schema':schema(operation),'result_schema':output_schema(operation),
       'description':descriptions[operation],'checkpoint_profile':'layers_only_KanInput_v1' if operation=='kan.evaluate' else None,
       'native_proto_type_urls':b['native_proto_type_urls'],'execution_authorized':False,'lu_registered':False}
    return sha(d),d


def offer(operation,approval):
    h,d=descriptor(operation)
    need((type(approval) is Approval) if operation=='kan.evaluate' else approval is None,'checkpoint selection')
    return {'codec_sha256':h,'descriptor_sha256':d['engine_descriptor_sha256'],
            'tool_schema':{'type':'function','function':{'name':d['public_name'],'description':d['description'],'parameters':d['arguments_schema']}},
            'checkpoint_sha256':approval.checkpoint.identity if approval else None,
            'checkpoint_shape':([approval.checkpoint.message().layers[0].inputs,approval.checkpoint.message().layers[-1].outputs] if approval else None),
            'model_advertised':False,'execution_authorized':False}


def _bits(value):
    need(type(value) is str and 1<=len(value)<=MAX_MODEL_DIM and BITSTR.fullmatch(value),'binary vector')
    raw=bytearray((len(value)+7)//8)
    for i,v in enumerate(value):
        if v=='1':raw[i//8]|=1<<(i%8)
    return pb.BinaryVector(dimension=len(value),bits=bytes(raw))


def _unpack(m):return ''.join('1' if m.bits[i//8]&(1<<(i%8)) else '0' for i in range(m.dimension))


def bind(operation,approval,raw,request_id,turn):
    a=strict_json(raw)
    if operation=='hdc.bind':
        fields(a,('left','right'));m=pb.BindInput(left=_bits(a['left']),right=_bits(a['right']))
    elif operation=='hdc.query':
        fields(a,('probe','candidates'));m=pb.QueryInput(probe=_bits(a['probe']),candidates=[_bits(v) for v in sequence(a['candidates'],1,MAX_MODEL_CANDIDATES)])
    else:
        need(operation=='kan.evaluate' and type(approval) is Approval,'approved checkpoint required')
        fields(a,('points',));checkpoint=approval.checkpoint.message();d=checkpoint.layers[0].inputs
        rows=sequence(a['points'],1,e.MAX_ROWS)
        coordinates=[number(x,1000) for r in rows for x in sequence(r,d,d)]
        first=checkpoint.layers[0];k=first.knots
        # Reject out-of-domain source values before binary32 rounding.
        need(all(first.grid[(i%d)*k]<=x<=first.grid[(i%d+1)*k-1] for i,x in enumerate(coordinates)),'KAN point outside approved knot domain')
        m=pb.KanInput(layers=checkpoint.layers,rows=len(rows),coordinates=coordinates)
    c=e.make_call(operation,m,request_id,turn);need(matches(c,approval),'model subset or checkpoint mismatch');return c


def matches(c,approval):
    m=c.message
    if c.operation=='hdc.bind':return approval is None and m.bind.left.dimension<=MAX_MODEL_DIM
    if c.operation=='hdc.query':return approval is None and m.query.probe.dimension<=MAX_MODEL_DIM and len(m.query.candidates)<=MAX_MODEL_CANDIDATES
    return type(approval) is Approval and checkpoint_wire(m.kan.layers)==approval.checkpoint.wire


def feedback(c,approval,receipt):
    """Only after trusted Admission.execute; never accepts a model-supplied receipt."""
    op=c.operation;m=c.message;ch,_=descriptor(op);h=e.descriptor(op)[0]
    request_hash=hashlib.sha256(c.wire).hexdigest()
    need(receipt.operation==op and receipt.descriptor_sha256==h and receipt.request_id==m.request_id and receipt.scope.turn==m.correlation_id and receipt.request_sha256==request_hash,'receipt binding')
    out=dict(tool=public_name(op),codec_sha256=ch,descriptor_sha256=h,request_sha256=request_hash)
    if receipt.status!='completed':
        need(receipt.status in STATUSES and receipt.result_frame is None and receipt.result_sha256 is None,'invalid refusal')
        return dict(out,ok=False,error=dict(code=receipt.status,retryable=False))
    raw=receipt.result_frame;need(type(raw) is bytes and hashlib.sha256(raw).hexdigest()==receipt.result_sha256,'receipt result hash')
    r=parse(raw,pb.EngineResult,e.MAX_RESULT)
    need(r.schema_version==1 and r.descriptor_sha256==bytes.fromhex(h) and r.request_sha256==bytes.fromhex(request_hash) and r.request_id==m.request_id and r.correlation_id==m.correlation_id and r.kernel_git_blob==bytes.fromhex(e.kernel(op)) and r.assurance==e.descriptor(op)[1]['assurance'] and r.WhichOneof('output')==e.descriptor(op)[1]['output_kind'],'result identity')
    if op=='hdc.bind':data=dict(bits=_unpack(r.bound))
    elif op=='hdc.query':data=dict(hamming_distance=list(r.query.hamming_distance),best_index=list(r.query.best_index))
    else:
        need(matches(c,approval),'checkpoint mismatch');v=list(r.kan.values);d=r.kan.columns
        data=dict(values=[v[i*d:(i+1)*d] for i in range(r.kan.rows)],checkpoint_sha256=approval.checkpoint.identity)
    return dict(out,ok=True,result_sha256=receipt.result_sha256,result=dict(data,assurance=r.assurance,limitations=list(KAN_LIMITATIONS if op=='kan.evaluate' else LIMITATIONS),kernel_git_blob=e.kernel(op)))
