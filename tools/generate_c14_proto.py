"""Build deterministic checked-in protobuf classes; requires only protobuf, not protoc."""
from google.protobuf import descriptor_pb2
from pathlib import Path
f=descriptor_pb2.FileDescriptorProto()
f.name='cognitum/causal/v1/causal.proto';f.package='cognitum.causal.v1';f.syntax='proto3'
TY=descriptor_pb2.FieldDescriptorProto
T={'double':TY.TYPE_DOUBLE,'string':TY.TYPE_STRING,'uint32':TY.TYPE_UINT32,'bool':TY.TYPE_BOOL,'message':TY.TYPE_MESSAGE}
def msg(name, fields):
 m=f.message_type.add();m.name=name
 for n,(field,typ,repeated,ref) in enumerate(fields,1):
  v=m.field.add();v.number=n;v.name=field;v.type=T[typ];v.label=TY.LABEL_REPEATED if repeated else TY.LABEL_OPTIONAL
  if ref:v.type_name='.'+f.package+'.'+ref
msg('NumericRow',[('values','double',True,None)])
msg('CausalEdge',[(x,t,False,None) for x,t in [('source','string'),('target','string'),('lag','uint32'),('orientation','string'),('statistic','double'),('p_value','double')]])
msg('CausalRequest',[
 ('schema_version','uint32',False,None),('operation','string',False,None),('columns','string',True,None),('rows','message',True,'NumericRow'),('treatment','string',False,None),('outcome','string',False,None),('adjustment','string',True,None),('effect_modifiers','string',True,None),('graph_edges','message',True,'CausalEdge'),('declared_assumptions','string',True,None),('alpha','double',False,None),('max_lag','uint32',False,None),('modifier_profile','double',True,None)])
msg('CausalReply',[
 ('schema_version','uint32',False,None),('status','string',False,None),('code','string',False,None),('backend','string',False,None),('estimand','string',False,None),('has_effect','bool',False,None),('effect','double',False,None),('has_interval','bool',False,None),('interval_lower','double',False,None),('interval_upper','double',False,None),('confidence_level','double',False,None),('uncertainty_kind','string',False,None),('discovered_edges','message',True,'CausalEdge'),('declared_assumptions','string',True,None),('limitations','string',True,None),('input_sha256','string',False,None)])
from google.protobuf import descriptor_pool, message_factory
p=descriptor_pool.DescriptorPool();p.Add(f)
source='''# Generated from proto/cognitum/causal/v1/causal.proto. DO NOT EDIT.\n# Dynamic builder, independent of protoc executable; deterministic schema descriptor.\nfrom google.protobuf import descriptor_pool as _pool, message_factory as _factory\nfrom google.protobuf import descriptor_pb2 as _descriptor_pb2\n_DESCR = _descriptor_pb2.FileDescriptorProto.FromString('''+repr(f.SerializeToString())+''')\n_POOL = _pool.DescriptorPool()\nDESCRIPTOR = _POOL.Add(_DESCR)\nNumericRow = _factory.GetMessageClass(_POOL.FindMessageTypeByName("cognitum.causal.v1.NumericRow"))\nCausalEdge = _factory.GetMessageClass(_POOL.FindMessageTypeByName("cognitum.causal.v1.CausalEdge"))\nCausalRequest = _factory.GetMessageClass(_POOL.FindMessageTypeByName("cognitum.causal.v1.CausalRequest"))\nCausalReply = _factory.GetMessageClass(_POOL.FindMessageTypeByName("cognitum.causal.v1.CausalReply"))\n'''
(Path(__file__).resolve().parents[1]/'cognitum/proto/causal_pb2.py').write_text(source)
