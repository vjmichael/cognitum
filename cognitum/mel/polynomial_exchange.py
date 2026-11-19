"""Typed, exact-sample transfer to existing VFA calls (no grant or worker).

The trusted host must supply the scope, original Call and Receipt. The
canonical source witness is replayed. This bridge intentionally refuses
rounding a mathematical value into a different coordinate, and requires
explicit dimensionless axis labels. This is not graph-node integration.
"""
from dataclasses import dataclass
import hashlib
from cognitum.contracts import Response
from . import admission as a, native as n, polynomial_kan as p
from .native import need

@dataclass(frozen=True,slots=True)
class Transfer:
    scope:a.Scope
    source_request_sha256:str
    source_result_sha256:str
    checkpoint_sha256:str
    target:n.NativeCall

    @property
    def identity(self):
        # Scope and all source/target identities included, no authority.
        from .discovery import sha
        return sha(dict(scope=[self.scope.session,self.scope.workspace,self.scope.subject,self.scope.turn],
                        source_request_sha256=self.source_request_sha256,source_result_sha256=self.source_result_sha256,
                        checkpoint_sha256=self.checkpoint_sha256,target_request_sha256=hashlib.sha256(self.target.wire()).hexdigest()))


def prepare_vfa(scope,call,receipt,function,axes,request_id,public_name='mel_vfa_evaluate'):
    need(type(scope) is a.Scope and type(call) is p.Call and type(receipt) is a.Receipt and type(function) is n.NativeObject,'typed transfer inputs')
    m=call.message;raw=receipt.result_frame
    need(type(raw) is bytes and receipt.scope==scope and receipt.status=='completed' and m.correlation_id==scope.turn and
         (receipt.operation,receipt.request_id,receipt.descriptor_sha256,receipt.request_sha256,receipt.result_sha256)==
         (p.OP,m.request_id,m.descriptor_sha256.hex(),p.digest(call.wire).hex(),p.digest(raw).hex()),'source receipt identity')
    response=Response(m.request_id,scope.turn,p.OP,'completed',module={'name':p.NAME,'version':p.VERSION},assurance='numerical',result={'frame':n.encode_carrier(raw,p.MAX_RESULT)})
    r=p.pb.Result.FromString(p.checked_result(call,response));b=function.message().body
    need(b.WhichOneof('representation')=='function' and type(axes) is tuple and len(axes)==r.outputs and tuple((v.name,v.unit) for v in b.axes)==tuple((v,'1') for v in axes),'explicit dimensionless axes')
    values=r.components[:r.rows*r.outputs]
    need(all(v.lower==v.upper==v.observed and v.absolute_error_upper==0 for v in values),'nonexact sample transfer refused')
    rows=[[v.observed for v in values[i*r.outputs:(i+1)*r.outputs]] for i in range(r.rows)]
    target=n.make_call(public_name,function,n.points(function,rows),request_id,scope.turn)
    return Transfer(scope,receipt.request_sha256,receipt.result_sha256,r.checkpoint_sha256.hex(),target)


def replay(transfer,scope,call,receipt,function,axes):
    need(type(transfer) is Transfer,'typed transfer')
    expected=prepare_vfa(scope,call,receipt,function,axes,transfer.target.request_id,transfer.target.public_name)
    need(expected==transfer,'transfer mismatch')
    return True
