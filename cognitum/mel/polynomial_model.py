"""Reviewed model codec for the approved polynomial profile, no authority.

Model supplies points and derivative order only. Host owns checkpoint, tolerance,
request identity and scope. Feedback replays the independent rational witness.
"""
from . import polynomial_kan as p, discovery as d, exchange as x
from .native import need
from .objects import number
import json

PUBLIC='mel_kan_polynomial_evaluate'
LIMITATIONS=('represented_parameters_and_inputs_only','no_learned_target_or_semantic_probability','bounds_not_unknown_input_uncertainty')

def descriptor():
    h,b=p.descriptor()
    schema=d.obj({'points':d.arr(d.arr(d.num(-1000,1000),1,p.MAX_WIDTH),1,p.MAX_ROWS),'order':{'type':'integer','minimum':0,'maximum':2}})
    digest={'type':'string','pattern':'^[0-9a-f]{64}$','minLength':64,'maxLength':64}
    numeric=d.num(-1e12,1e12);interval=d.obj({'lower':numeric,'upper':numeric})
    result_schema=d.obj(dict(values=d.arr(numeric,1,p.MAX_COMPONENTS),intervals=d.arr(interval,1,p.MAX_COMPONENTS),absolute_error_upper=d.arr(d.num(0,1e-6),1,p.MAX_COMPONENTS),component_shapes=d.arr(d.arr({'type':'integer','minimum':1,'maximum':4},2,4),1,3),order={'type':'integer','minimum':0,'maximum':2},checkpoint_sha256=digest,assurance=d.const('represented_input_enclosure'),limitations=d.const(list(LIMITATIONS)),request_sha256=digest,result_sha256=digest))
    result_schema={'oneOf':[d.obj({'ok':d.const(True),'tool':d.const(PUBLIC),'result':result_schema}),d.obj({'ok':d.const(False),'error':{'type':'string'},'result':{'type':'null'}})]}
    body=dict(schema='cognitum.mel.polynomial_model_codec.v1',public_name=PUBLIC,operation=p.OP,engine_descriptor_sha256=h,
              arguments_schema=schema,result_schema=result_schema,description='Evaluate the host-approved polynomial KAN at coordinate rows. Order 0 returns values, 1 also Jacobians, 2 also Hessians. No weights, paths or tolerance arguments. Certified represented-input intervals, not training accuracy.',
              checkpoint_profile='binary64_polynomial_layers_v1',native_proto_type_urls=b['native_proto_type_urls'],
              result_layout='values then row-major Jacobians then row-major Hessians; all interval endpoints outward',execution_authorized=False,lu_registered=False)
    return d.sha(body),body

def offer(approval,tolerance):
    need(type(approval) is p.Approval,'approved polynomial checkpoint')
    need(type(tolerance) is float and 0<=tolerance<=1e-6,'host tolerance')
    h,b=descriptor();ck=approval.checkpoint.message()
    return dict(codec_sha256=h,descriptor_sha256=b['engine_descriptor_sha256'],tool_schema={'type':'function','function':{'name':PUBLIC,'description':b['description'],'parameters':b['arguments_schema']}},checkpoint_sha256=approval.checkpoint.identity,checkpoint_shape=[ck.layers[0].inputs,ck.layers[-1].outputs],host_absolute_tolerance=tolerance,model_advertised=False,execution_authorized=False)

def bind(approval,tolerance,raw,request_id,turn):
    need(type(approval) is p.Approval and type(tolerance) is float and 0<=tolerance<=1e-6,'typed approved polynomial policy')
    args=d.strict_json(raw);d.fields(args,('points','order'));order=args['order'];need(type(order) is int and 0<=order<=2,'derivative order')
    width=approval.checkpoint.message().layers[0].inputs
    rows=[[number(v,1000) for v in d.sequence(row,width,width)] for row in d.sequence(args['points'],1,p.MAX_ROWS)]
    return p.make_call(approval.checkpoint,rows,order,tolerance,request_id,turn)

def matches(call,approval,tolerance):
    return type(call) is p.Call and p.matches(call,approval) and call.message.absolute_tolerance.hex()==tolerance.hex()

def feedback(scope,call,receipt,approval,tolerance):
    need(matches(call,approval,tolerance),'polynomial approval or tolerance drift')
    if receipt.status!='completed':return {'ok':False,'error':receipt.status,'result':None},None
    raw,_,_=x._checked_receipt(scope,call,receipt);msg=p.pb.Result.FromString(raw)
    rows,i,o=msg.rows,msg.inputs,msg.outputs
    shapes=[[rows,o]]+([[rows,o,i]] if msg.order else [])+([[rows,o,i,i]] if msg.order==2 else [])
    result=dict(values=[v.observed for v in msg.components],intervals=[dict(lower=v.lower,upper=v.upper) for v in msg.components],absolute_error_upper=[v.absolute_error_upper for v in msg.components],component_shapes=shapes,order=msg.order,checkpoint_sha256=approval.checkpoint.identity,
                assurance='represented_input_enclosure',limitations=list(LIMITATIONS),request_sha256=receipt.request_sha256,result_sha256=receipt.result_sha256)
    out={'ok':True,'tool':PUBLIC,'result':result}
    audit=dict(scope=dict(session=scope.session,workspace=scope.workspace,subject=scope.subject,turn=scope.turn),operation=p.OP,request_sha256=receipt.request_sha256,result_sha256=receipt.result_sha256,descriptor_sha256=receipt.descriptor_sha256,codec_sha256=descriptor()[0],request_hex=call.wire.hex(),result_hex=raw.hex(),tolerance=tolerance,verdict='within_represented_input_tolerance')
    need(len(json.dumps(out,sort_keys=True,separators=(',',':'),allow_nan=False))<=65536,'feedback budget')
    return out,audit
