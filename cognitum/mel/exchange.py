"""MEL-04A bounded, typed sample and bit exchange. Trusted host reference only.

Hashes establish content identity, not receipt authenticity or execution authority.
No engine is called here; prepared frames require their own Admission grant.
Numeric sample transfer is not a function conversion or error certificate.
"""
from dataclasses import dataclass
import hashlib
import math
import struct
from cognitum.contracts import Response
from . import admission as a, native as n, engines as e, engines_pb2 as ep
from . import model_engines as m, exchange_pb2 as p
from .objects import token, number, need
from . import polynomial_kan as pk

MAX_OBJECT=8192
MAX_TRANSFER=65536
MAX_ROWS=32
MAX_COLS=8
MAX_BITS=e.MAX_DIM
DOMAIN=b'cognitum.mel.exchange.v1.Body\x00'
TRANSFER_DOMAIN=b'cognitum.mel.exchange.v1.Transfer\x00'
SOURCES={p.VFA_POINTS,p.VFA_VALUES,p.KAN_VALUES,p.HDC_BOUND,p.POLYNOMIAL_VALUES}
NUMERIC={p.VFA_POINTS,p.VFA_VALUES,p.KAN_VALUES,p.BIT_LIFT,p.POLYNOMIAL_VALUES}
PRECISION={p.VFA_POINTS:p.BINARY64,p.VFA_VALUES:p.BINARY64,p.KAN_VALUES:p.BINARY32_WIDENED,p.POLYNOMIAL_VALUES:p.BINARY64,p.HDC_BOUND:p.PACKED_BITS,p.THRESHOLD:p.PACKED_BITS,p.BIT_LIFT:p.EXACT_ZERO_ONE_BINARY64}


def digest(raw):return hashlib.sha256(raw).digest()

def scope_message(s):
    need(type(s) is a.Scope,'trusted scope')
    return p.Scope(session=s.session,workspace=s.workspace,subject=s.subject,turn=s.turn)


def scope_value(s):return a.Scope(s.session,s.workspace,s.subject,s.turn)


def same_scope(b,s):need(b.scope==scope_message(s),'exchange scope mismatch')


def _axes(v):return [(x.name,x.unit) for x in v]


def _matrix(rows,columns,values,axes,domain=()):
    s=p.Samples(rows=rows,columns=columns,values=values)
    for name,unit in axes:s.axes.add(name=name,unit=unit)
    for lo,hi in domain:s.domain.add(lower=lo,upper=hi)
    return s


def _binary(b):
    v=ep.BinaryVector(dimension=b.dimension,bits=b.packed_bits)
    e.vector(v);return v


def _validate(b):
    need(b.schema_version==1 and b.HasField('scope'),'exchange version or scope');scope_value(b.scope)
    o=b.origin;kind=b.WhichOneof('representation')
    need(o in SOURCES|{p.THRESHOLD,p.BIT_LIFT} and kind==('samples' if o in NUMERIC else 'bits'),'exchange origin or representation')
    need(b.assurance in (p.SUBMITTED,p.NUMERICAL_NOT_CERTIFIED,p.EXACT_SUBMITTED_BITS) and b.precision==PRECISION[o],'exchange assurance or precision')
    need((not b.transfer_sha256) or (o in (p.VFA_VALUES,p.KAN_VALUES,p.POLYNOMIAL_VALUES) and len(b.transfer_sha256)==32),'transfer lineage')
    need(len(b.parents_sha256)==(2 if o in (p.VFA_VALUES,p.KAN_VALUES,p.HDC_BOUND,p.POLYNOMIAL_VALUES) else 1) and all(len(h)==32 for h in b.parents_sha256),'source lineage')
    if o in (p.VFA_VALUES,p.KAN_VALUES,p.HDC_BOUND):
        op={p.VFA_VALUES:'vfa.evaluate',p.KAN_VALUES:'kan.evaluate',p.HDC_BOUND:'hdc.bind'}[o]
        h=n.descriptor('mel_vfa_evaluate')[0] if o==p.VFA_VALUES else e.descriptor(op)[0]
        k=n.KERNEL if o==p.VFA_VALUES else e.kernel(op)
        need(b.descriptor_sha256==bytes.fromhex(h) and b.kernel_git_blob==bytes.fromhex(k),'source descriptor or kernel')
    elif o==p.POLYNOMIAL_VALUES:
        need(b.descriptor_sha256==bytes.fromhex(pk.descriptor()[0]) and b.kernel_git_blob==bytes.fromhex(pk.TRAINABLE_BLOB),'polynomial producer identity')
    else:need(not b.descriptor_sha256 and not b.kernel_git_blob,'unexpected producer')
    need(len(b.checkpoint_sha256)==(32 if o in (p.KAN_VALUES,p.POLYNOMIAL_VALUES) else 0),'checkpoint lineage')
    if o in SOURCES:
        expected=p.SUBMITTED if o==p.VFA_POINTS else p.EXACT_SUBMITTED_BITS if o==p.HDC_BOUND else p.NUMERICAL_NOT_CERTIFIED
        need(b.assurance==expected and (not b.lossy_history or bool(b.transfer_sha256)),'source assurance')
    if kind=='bits':_binary(b.bits)
    else:
        s=b.samples;d=s.columns
        need(1<=s.rows<=MAX_ROWS and 1<=d<=MAX_COLS and len(s.values)==s.rows*d,'sample shape')
        need(len(s.axes)==d and all(token(x.name) and token(x.unit) for x in s.axes) and len({x.name for x in s.axes})==d,'sample axes')
        need(all(math.isfinite(x) and abs(x)<=1e12 for x in s.values),'sample range')
        need(len(s.domain)==(d if o==p.VFA_POINTS else 0),'domain metadata')
        for i,v in enumerate(s.domain):
            need(v.HasField('lower') and v.HasField('upper') and -1e6<=v.lower<v.upper<=1e6 and all(v.lower<=x<=v.upper for x in s.values[i::d]),'sample domain')
        if o==p.VFA_VALUES:need(d==1 and s.axes[0].name=='value','VFA scalar shape')
        if o==p.KAN_VALUES:
            need(s.rows<=e.MAX_ROWS and all(x.unit=='1' for x in s.axes) and all(abs(x)<=1e6 and _f32_equal(x) for x in s.values),'KAN binary32 dimensionless declared samples')
        if o==p.POLYNOMIAL_VALUES:need(s.rows<=pk.MAX_ROWS and d<=pk.MAX_WIDTH and all(x.unit=='1' for x in s.axes),'polynomial binary64 dimensionless samples')
        if o==p.BIT_LIFT:need(all(x in (0.,1.) for x in s.values) and _axes(s.axes)==[(f'bit{i}','1') for i in range(d)],'binary lift')
    need(b.HasField('threshold')==(o==p.THRESHOLD),'threshold metadata')
    if o==p.THRESHOLD:
        t=b.threshold
        need(b.lossy_history and 1<=t.rows<=MAX_ROWS and 1<=t.columns<=MAX_COLS and t.rows*t.columns==b.bits.dimension and t.HasField('at_least') and token(t.unit) and math.isfinite(t.at_least) and abs(t.at_least)<=1e12,'threshold bounds')
        need(len(t.axes)==t.columns and all(token(x.name) and x.unit==t.unit for x in t.axes) and len({x.name for x in t.axes})==t.columns,'threshold layout')
    return b


@dataclass(frozen=True,slots=True)
class Object:
    wire: bytes
    def __post_init__(self):self.message()
    def message(self):
        o=n.parse(self.wire,p.Object,MAX_OBJECT)
        need(o.HasField('body') and o.content_sha256==digest(DOMAIN+n.serialize(o.body)),'exchange identity')
        _validate(o.body);return o
    @property
    def identity(self):return self.message().content_sha256.hex()


def _freeze(b):return Object(n.serialize(p.Object(body=b,content_sha256=digest(DOMAIN+n.serialize(b)))))


def _body(scope,origin,assurance,parents,**kw):
    return p.Body(schema_version=1,scope=scope_message(scope),origin=origin,assurance=assurance,precision=PRECISION[origin],parents_sha256=parents,**kw)


def _read(obj,scope):
    need(type(obj) is Object,'typed exchange object');o=obj.message();same_scope(o.body,scope);return o


def from_vfa_points(scope,points):
    need(type(points) is n.NativeObject,'typed native object');o=points.message();b=o.body
    need(b.WhichOneof('representation')=='points','VFA coordinate object required')
    s=_matrix(*b.shape,list(b.points.coordinates),_axes(b.axes),[(v.lower,v.upper) for v in b.domain])
    return _freeze(_body(scope,p.VFA_POINTS,p.SUBMITTED,[o.content_sha256],samples=s))


def _checked_receipt(scope,call,receipt):
    """Recheck trusted in-process receipt, not authenticate arbitrary imported bytes."""
    need(type(receipt) is a.Receipt and receipt.scope==scope and receipt.status=='completed' and type(receipt.result_frame) is bytes,'completed trusted scoped receipt')
    if type(call) is n.NativeCall:
        backend=n;raw=call.wire();rid=call.request_id;turn=call.correlation_id;h=call.descriptor_sha256;assurance='numerical'
    elif type(call) is pk.Call:
        backend=pk;raw=call.wire;c=call.message;rid=c.request_id;turn=c.correlation_id;h=pk.descriptor()[0];assurance='numerical'
    else:
        need(type(call) is e.Call,'typed call');backend=e;raw=call.wire;c=call.message;rid=c.request_id;turn=c.correlation_id;h=e.descriptor(call.operation)[0];assurance=e.descriptor(call.operation)[1]['assurance']
    op=call.operation
    need((receipt.request_id,receipt.operation,receipt.descriptor_sha256,receipt.request_sha256,receipt.result_sha256)==(rid,op,h,digest(raw).hex(),digest(receipt.result_frame).hex()) and turn==scope.turn,'receipt identity')
    response=Response(rid,turn,op,'completed',module={'name':backend.NAME,'version':backend.VERSION},result={'frame':n.encode_carrier(receipt.result_frame,backend.MAX_RESULT)},assurance=assurance)
    result=backend.checked_result(call,response)
    return result,[digest(raw),digest(receipt.result_frame)],bytes.fromhex(h)


def from_result(scope,call,receipt,*,approval=None,dimensionless_axes=None):
    """Supported result imports; KAN units are explicitly host-declared dimensionless."""
    res,parents,h=_checked_receipt(scope,call,receipt)
    op=call.operation
    if op=='vfa.evaluate':
        need(approval is None and dimensionless_axes is None,'unexpected mapping');b=res.message().body
        s=_matrix(b.shape[0],1,list(b.values.values),[('value',b.units[0].numerator)])
        return _freeze(_body(scope,p.VFA_VALUES,p.NUMERICAL_NOT_CERTIFIED,parents,descriptor_sha256=h,kernel_git_blob=bytes.fromhex(n.KERNEL),samples=s))
    if op=='hdc.bind':
        need(approval is None and dimensionless_axes is None,'unexpected mapping');b=ep.EngineResult.FromString(res).bound
        return _freeze(_body(scope,p.HDC_BOUND,p.EXACT_SUBMITTED_BITS,parents,descriptor_sha256=h,kernel_git_blob=bytes.fromhex(e.HDC_BLOB),bits=p.Bits(dimension=b.dimension,packed_bits=b.bits)))
    if op==pk.OP:
        need(type(approval) is pk.Approval and pk.matches(call,approval),'approved polynomial checkpoint required')
        b=pk.pb.Result.FromString(res)
        need(b.order==0 and type(dimensionless_axes) is tuple and len(dimensionless_axes)==b.outputs and all(token(v) for v in dimensionless_axes),'polynomial graph value mapping')
        s=_matrix(b.rows,b.outputs,[v.observed for v in b.components],[(v,'1') for v in dimensionless_axes])
        return _freeze(_body(scope,p.POLYNOMIAL_VALUES,p.NUMERICAL_NOT_CERTIFIED,parents,descriptor_sha256=h,kernel_git_blob=bytes.fromhex(pk.TRAINABLE_BLOB),checkpoint_sha256=bytes.fromhex(approval.checkpoint.identity),samples=s))
    need(op=='kan.evaluate' and type(approval) is m.Approval and m.matches(call,approval),'approved checkpoint mapping required')
    b=ep.EngineResult.FromString(res).kan
    need(type(dimensionless_axes) is tuple and len(dimensionless_axes)==b.columns and all(token(v) for v in dimensionless_axes),'explicit dimensionless KAN output labels')
    s=_matrix(b.rows,b.columns,list(b.values),[(v,'1') for v in dimensionless_axes])
    return _freeze(_body(scope,p.KAN_VALUES,p.NUMERICAL_NOT_CERTIFIED,parents,descriptor_sha256=h,kernel_git_blob=bytes.fromhex(e.KAN_BLOB),checkpoint_sha256=bytes.fromhex(approval.checkpoint.identity),samples=s))


def threshold(scope,obj,at_least,unit):
    o=_read(obj,scope);b=o.body;v=number(at_least,1e12)
    need(b.HasField('samples') and token(unit) and all(x.unit==unit for x in b.samples.axes),'threshold unit mismatch')
    values=b.samples.values;packed=bytearray((len(values)+7)//8)
    for i,x in enumerate(values):
        if x>=v:packed[i//8]|=1<<(i%8)
    return _freeze(_body(scope,p.THRESHOLD,b.assurance,[o.content_sha256],lossy_history=True,bits=p.Bits(dimension=len(values),packed_bits=bytes(packed)),threshold=p.Threshold(at_least=v,unit=unit,rows=b.samples.rows,columns=b.samples.columns,axes=b.samples.axes)))


def lift(scope,obj,rows,columns):
    o=_read(obj,scope);b=o.body
    need(b.HasField('bits') and type(rows) is int and type(columns) is int and 1<=rows<=MAX_ROWS and 1<=columns<=MAX_COLS and rows*columns==b.bits.dimension,'explicit bit reshape')
    bits=b.bits.packed_bits;values=[float((bits[i//8]>>(i%8))&1) for i in range(rows*columns)]
    return _freeze(_body(scope,p.BIT_LIFT,b.assurance,[o.content_sha256],lossy_history=b.lossy_history,samples=_matrix(rows,columns,values,[(f'bit{i}','1') for i in range(columns)])))


def verify_derivation(scope,parent,child):
    b=_read(child,scope).body
    if b.origin==p.THRESHOLD:expected=threshold(scope,parent,b.threshold.at_least,b.threshold.unit)
    elif b.origin==p.BIT_LIFT:expected=lift(scope,parent,b.samples.rows,b.samples.columns)
    else:raise ValueError('not a derived object')
    need(expected.wire==child.wire,'derived object mismatch');return True


def _f32_equal(x):
    try:return struct.pack('<d',x)==struct.pack('<d',struct.unpack('<f',struct.pack('<f',x))[0])
    except (OverflowError,struct.error):return False


def _rows(s):return [list(s.values[i:i+s.columns]) for i in range(0,len(s.values),s.columns)]


@dataclass(frozen=True,slots=True)
class Transfer:
    wire: bytes
    def __post_init__(self):self.message()
    @property
    def identity(self):return digest(TRANSFER_DOMAIN+self.wire).hex()
    def message(self):
        t=n.parse(self.wire,p.Transfer,MAX_TRANSFER);scope=scope_value(t.scope)
        need(t.schema_version==1 and 1<=len(t.source_sha256)<=1+e.MAX_CANDIDATES and all(len(h)==32 for h in t.source_sha256) and t.request_sha256==digest(t.request_frame),'transfer identity')
        if t.operation in n.OP:
            c=n.decode_request(t.request_frame,t.operation);h=c.descriptor_sha256;turn=c.correlation_id
        elif t.operation==pk.OP:
            c=pk.Call(t.operation,t.request_frame);h=pk.descriptor()[0];turn=c.message.correlation_id
        else:
            need(t.operation in ('kan.evaluate','hdc.query'),'transfer operation');c=e.Call(t.operation,t.request_frame);h=e.descriptor(t.operation)[0];turn=c.message.correlation_id
        need(t.descriptor_sha256==bytes.fromhex(h) and turn==scope.turn,'transfer route or scope')
        if t.operation=='kan.evaluate':need(t.target_checkpoint_sha256==digest(m.checkpoint_wire(c.message.kan.layers)),'target checkpoint pin')
        elif t.operation==pk.OP:need(t.target_checkpoint_sha256==c.message.checkpoint_sha256,'target polynomial checkpoint pin')
        else:need(not t.target_checkpoint_sha256,'unexpected checkpoint')
        return t


def _transfer(scope,objects,call,pin=b''):
    body=[_read(o,scope) for o in objects]
    raw=call.wire() if type(call) is n.NativeCall else call.wire
    h=call.descriptor_sha256 if type(call) is n.NativeCall else pk.descriptor()[0] if type(call) is pk.Call else e.descriptor(call.operation)[0]
    return Transfer(n.serialize(p.Transfer(schema_version=1,scope=scope_message(scope),source_sha256=[o.content_sha256 for o in body],operation=call.operation,descriptor_sha256=bytes.fromhex(h),request_frame=raw,request_sha256=digest(raw),target_checkpoint_sha256=pin,lossy_history=any(o.body.lossy_history for o in body))))


def prepare_vfa(scope,obj,function,public_name,request_id):
    b=_read(obj,scope).body;need(b.HasField('samples') and type(function) is n.NativeObject,'sample/function mapping')
    f=function.message().body;s=b.samples
    need(f.WhichOneof('representation')=='function' and _axes(s.axes)==_axes(f.axes),'VFA axis mapping mismatch')
    c=n.make_call(public_name,function,n.points(function,_rows(s)),request_id,scope.turn)
    return _transfer(scope,[obj],c)


def prepare_kan(scope,obj,approval,dimensionless_axes,request_id):
    b=_read(obj,scope).body;need(b.HasField('samples') and type(approval) is m.Approval,'samples and host-selected checkpoint required')
    s=b.samples;ck=approval.checkpoint.message()
    need(type(dimensionless_axes) is tuple and _axes(s.axes)==[(v,'1') for v in dimensionless_axes] and s.columns==ck.layers[0].inputs and s.rows<=e.MAX_ROWS,'explicit KAN dimensionless input mapping')
    need(all(_f32_equal(x) for x in s.values),'lossy binary64-to-binary32 conversion refused')
    c=e.make_call('kan.evaluate',ep.KanInput(layers=ck.layers,rows=s.rows,coordinates=s.values),request_id,scope.turn)
    return _transfer(scope,[obj],c,bytes.fromhex(approval.checkpoint.identity))


def prepare_polynomial(scope,obj,approval,dimensionless_axes,request_id,absolute_tolerance):
    b=_read(obj,scope).body;need(b.HasField('samples') and type(approval) is pk.Approval,'samples and approved polynomial checkpoint')
    s=b.samples;ck=approval.checkpoint.message()
    need(type(dimensionless_axes) is tuple and _axes(s.axes)==[(v,'1') for v in dimensionless_axes] and s.columns==ck.layers[0].inputs and s.rows<=pk.MAX_ROWS,'explicit polynomial dimensionless input mapping')
    c=pk.make_call(approval.checkpoint,_rows(s),0,absolute_tolerance,request_id,scope.turn)
    return _transfer(scope,[obj],c,bytes.fromhex(approval.checkpoint.identity))


def prepare_query(scope,probe,candidates,request_id):
    need(type(candidates) is tuple and 1<=len(candidates)<=e.MAX_CANDIDATES,'query candidates')
    objects=(probe,)+candidates;bs=[_read(o,scope).body for o in objects]
    need(all(b.HasField('bits') for b in bs),'binary exchange objects required')
    # Only like encodings. A matching threshold/layout still does not establish
    # common semantics or codebook identity; host chooses the comparison.
    need(all(b.origin==bs[0].origin and (b.origin!=p.THRESHOLD or n.serialize(b.threshold)==n.serialize(bs[0].threshold)) for b in bs),'incompatible bit encoding profiles')
    c=e.make_call('hdc.query',ep.QueryInput(probe=_binary(bs[0].bits),candidates=[_binary(b.bits) for b in bs[1:]]),request_id,scope.turn)
    return _transfer(scope,objects,c)


def verify_transfer(scope,transfer,objects,*,function=None,approval=None,dimensionless_axes=None,absolute_tolerance=None):
    """Rebuild from trusted sources; never trust a transfer's self-asserted lineage."""
    need(type(transfer) is Transfer and type(objects) is tuple and bool(objects),'typed transfer and sources')
    t=transfer.message();same_scope(t,scope)
    need((absolute_tolerance is not None)==(t.operation==pk.OP),'explicit polynomial tolerance only')
    if t.operation==pk.OP:
        need(len(objects)==1 and function is None,'polynomial transfer mapping')
        c=pk.Call(t.operation,t.request_frame)
        expected=prepare_polynomial(scope,objects[0],approval,dimensionless_axes,c.message.request_id,absolute_tolerance)
    elif t.operation in n.OP:
        need(len(objects)==1 and approval is None and dimensionless_axes is None,'VFA transfer mapping')
        c=n.decode_request(t.request_frame,t.operation)
        expected=prepare_vfa(scope,objects[0],function,c.public_name,c.request_id)
    else:
        c=e.Call(t.operation,t.request_frame);rid=c.message.request_id
        if t.operation=='kan.evaluate':
            need(len(objects)==1 and function is None,'KAN transfer mapping')
            expected=prepare_kan(scope,objects[0],approval,dimensionless_axes,rid)
        else:
            need(function is None and approval is None and dimensionless_axes is None,'HDC transfer mapping')
            expected=prepare_query(scope,objects[0],objects[1:],rid)
    need(expected.wire==transfer.wire,'transfer source or derivation mismatch');return True


def from_transfer_result(scope,transfer,objects,receipt,*,function=None,approval=None,dimensionless_axes=None,output_axes=None,absolute_tolerance=None):
    """Import numerical results with the verified transfer edge and inherited loss.

    The host must supply the actual scope-owned receipt and original objects.
    Standalone imports are for standalone source calls, not graph history.
    """
    verify_transfer(scope,transfer,objects,function=function,approval=approval,dimensionless_axes=dimensionless_axes,absolute_tolerance=absolute_tolerance)
    t=transfer.message()
    need(t.operation in ('vfa.evaluate','kan.evaluate',pk.OP),'supported numerical exchange result only')
    if t.operation=='vfa.evaluate':
        need(output_axes is None,'unexpected output mapping');c=n.decode_request(t.request_frame,t.operation)
        result=from_result(scope,c,receipt)
    else:
        c=pk.Call(t.operation,t.request_frame) if t.operation==pk.OP else e.Call(t.operation,t.request_frame);result=from_result(scope,c,receipt,approval=approval,dimensionless_axes=output_axes)
    b=result.message().body;b.transfer_sha256=bytes.fromhex(transfer.identity);b.lossy_history=t.lossy_history
    return _freeze(b)
