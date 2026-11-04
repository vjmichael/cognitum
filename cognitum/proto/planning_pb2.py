"""Descriptor-backed C12 schema; source: proto/cognitum/planning/v1/planning.proto."""
from google.protobuf import descriptor_pb2 as d, descriptor_pool, message_factory
f=d.FileDescriptorProto()
f.name="cognitum/planning/v1/planning.proto"
f.package="cognitum.planning.v1"
f.syntax="proto3"
T=d.FieldDescriptorProto
def msg(name,fields):
    node=f.message_type.add()
    node.name=name
    for number,(name,kind,rep,ref) in enumerate(fields,1):
        a=node.field.add();a.name=name;a.number=number
        a.type=getattr(T,"TYPE_"+kind.upper())
        a.label=T.LABEL_REPEATED if rep else T.LABEL_OPTIONAL
        if ref:a.type_name="."+f.package+"."+ref
def field(name,kind,rep=False,ref=None):
    return name,kind,rep,ref
msg("PlanAction",[
    field("name","string"),field("requires","string",True),
    field("forbids","string",True),field("add","string",True),
    field("delete","string",True),field("cost","uint32"),field("risk","uint32")])
msg("PlanRequest",[
    field("schema_version","uint32"),field("facts","string",True),
    field("initial","string",True),field("goal","string",True),
    field("goal_forbids","string",True),field("actions","message",True,"PlanAction"),
    field("horizon","uint32"),field("risk_budget","uint32"),field("algorithm","string")])
msg("PlanResult",[
    field("schema_version","uint32"),field("status","string"),
    field("actions","string",True),field("final_state","string",True),
    field("has_result","bool"),field("total_cost","uint32"),field("total_risk","uint32"),
    field("expanded_states","uint32"),field("backend","string"),
    field("limitations","string",True),field("request_sha256","string")])
p=descriptor_pool.DescriptorPool()
DESCRIPTOR=p.Add(f)
for name in ("PlanAction","PlanRequest","PlanResult"):
    globals()[name]=message_factory.GetMessageClass(
        p.FindMessageTypeByName(f.package+"."+name))
