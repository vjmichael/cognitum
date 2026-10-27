"""Protobuf descriptor-backed classes; source is math/v1/specialists.proto.

This is not an installer, Lu tool registration, or worker execution channel.
CI checks exact schema equivalence against grpc_tools.protoc.
"""
from google.protobuf import descriptor_pb2 as d
from google.protobuf import descriptor_pool as pool
from google.protobuf.internal import builder

fd = d.FileDescriptorProto()
fd.name = "cognitum/math/v1/specialists.proto"
fd.package = "cognitum.math.v1"
fd.syntax = "proto3"

S=d.FieldDescriptorProto.TYPE_STRING
N=d.FieldDescriptorProto.TYPE_UINT32
M=d.FieldDescriptorProto.TYPE_MESSAGE
def msg(name,fields):
    node=fd.message_type.add()
    node.name=name
    for idx,entry in enumerate(fields,1):
        name,typ,*options=entry
        field=node.field.add()
        field.name=name
        field.number=idx
        field.type=typ
        field.label=(d.FieldDescriptorProto.LABEL_REPEATED
                     if options and options[0]=="repeated"
                     else d.FieldDescriptorProto.LABEL_OPTIONAL)
        if typ==M:
            field.type_name=".cognitum.math.v1.RationalRow"
    return node

msg("SymbolicRequest",[("expression",S),("action",S)])
msg("SymbolicResult",[("polynomial",S),("assurance",S),("limitations",S,"repeated")])
msg("ScientificRequest",[("function",S),("argument",S),("digits",N)])
msg("ScientificResult",[("decimal",S),("digits",N),("method",S),
                        ("limitations",S,"repeated")])
msg("PrecisionRequest",[("action",S),("left",S),("right",S),("digits",N)])
msg("PrecisionResult",[("decimal",S),("digits",N),("method",S),
                       ("limitations",S,"repeated")])
msg("RationalRow",[("entries",S,"repeated")])
msg("LinearRequest",[("action",S),("a",M,"repeated"),("b",M,"repeated")])
msg("LinearResult",[("rows",M,"repeated"),("scalar",S),
                    ("limitations",S,"repeated")])
msg("RootRequest",[("polynomial",S),("lower",S),("upper",S),("iterations",N)])
msg("RootResult",[("lower",S),("upper",S),("midpoint",S),
                  ("limitations",S,"repeated")])
msg("SimulationRequest",[("position",S),("velocity",S),("omega_squared",S),
                         ("step",S),("steps",N)])
msg("SimulationResult",[("position",S),("velocity",S),
                        ("initial_energy",S),("final_energy",S),
                        ("limitations",S,"repeated")])

msg("SpecialistDescriptor",[
    ("operation",S),("input_type_url",S),("output_type_url",S),
    ("use_when",S),("avoid_when",S),("assurance",S),
    ("registered",d.FieldDescriptorProto.TYPE_BOOL),
    ("model_advertised",d.FieldDescriptorProto.TYPE_BOOL),
])
# Catalog contains repeated typed specialist definitions, not arbitrary JSON.
catalog=fd.message_type.add()
catalog.name="SpecialistCatalog"
for name,number,t,repeated in [
    ("schema_version",1,N,False),
    ("specialists",2,M,True),
    ("host_approved",3,d.FieldDescriptorProto.TYPE_BOOL,False),
]:
    field=catalog.field.add()
    field.name=name
    field.number=number
    field.type=t
    field.label=(d.FieldDescriptorProto.LABEL_REPEATED if repeated
                 else d.FieldDescriptorProto.LABEL_OPTIONAL)
    if t==M:
        field.type_name=".cognitum.math.v1.SpecialistDescriptor"

DESCRIPTOR = pool.Default().AddSerializedFile(fd.SerializeToString())
builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
builder.BuildTopDescriptorsAndMessages(
    DESCRIPTOR,"cognitum.proto.specialists_pb2",globals())
