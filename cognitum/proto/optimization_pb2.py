"""Descriptor-backed binding for proto/cognitum/optimization/v1/optimization.proto.

Typed inert component messages. Schema source and descriptor checked in CI.
"""
from google.protobuf import descriptor_pb2 as d, descriptor_pool, message_factory

f=d.FileDescriptorProto()
f.name="cognitum/optimization/v1/optimization.proto"
f.package="cognitum.optimization.v1"
f.syntax="proto3"
T=d.FieldDescriptorProto
def msg(name,fields):
    node=f.message_type.add()
    node.name=name
    for number,(field,kind,repeated,ref) in enumerate(fields,1):
        a=node.field.add()
        a.name=field;a.number=number
        a.type=getattr(T,"TYPE_"+kind.upper())
        a.label=T.LABEL_REPEATED if repeated else T.LABEL_OPTIONAL
        if ref:a.type_name="."+f.package+"."+ref
def field(name,typ,rep=False,ref=None):
    return name,typ,rep,ref
msg("ScheduleJob",[
 field("name","string"),field("duration","uint32"),
 field("release","uint32"),field("deadline","uint32"),
 field("eligible_resources","string",True),field("after","string",True)])
msg("ScheduleRequest",[
 field("schema_version","uint32"),field("horizon","uint32"),
 field("resources","string",True),field("jobs","message",True,"ScheduleJob"),
 field("unit","string"),field("timeout_ms","uint32")])
msg("ScheduledJob",[
 field("name","string"),field("resource","string"),field("start","uint32"),field("end","uint32")])
msg("ScheduleResult",[
 field("schema_version","uint32"),field("status","string"),
 field("assignments","message",True,"ScheduledJob"),
 field("has_objective","bool"),field("makespan","sint64"),
 field("solver_bound","string"),field("limitations","string",True),
 field("request_sha256","string")])
msg("AllocationQuantity",[
 field("name","string"),field("lower","sint64"),field("upper","sint64"),
 field("cost","sint64")])
msg("AllocationConstraint",[
 field("coefficients","sint64",True),field("relation","string"),field("rhs","sint64")])
msg("AllocationRequest",[
 field("schema_version","uint32"),field("quantities","message",True,"AllocationQuantity"),
 field("constraints","message",True,"AllocationConstraint"),
 field("unit","string"),field("timeout_ms","uint32")])
msg("AllocationResult",[
 field("schema_version","uint32"),field("status","string"),
 field("values","sint64",True),field("has_objective","bool"),
 field("objective","sint64"),field("solver_bound","string"),field("gap","string"),
 field("limitations","string",True),field("request_sha256","string")])
p=descriptor_pool.DescriptorPool()
DESCRIPTOR=p.Add(f)
for _name in ("ScheduleJob","ScheduleRequest","ScheduledJob","ScheduleResult",
              "AllocationQuantity","AllocationConstraint","AllocationRequest","AllocationResult"):
    globals()[_name]=message_factory.GetMessageClass(p.FindMessageTypeByName(f.package+"."+_name))
