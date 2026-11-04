"""Descriptor-backed C10 typed wire classes. See proto/cognitum/formal/v1/formal.proto."""
from google.protobuf import descriptor_pb2 as d
from google.protobuf import descriptor_pool, message_factory

f=d.FileDescriptorProto()
f.name="cognitum/formal/v1/formal.proto"
f.package="cognitum.formal.v1"
f.syntax="proto3"
T=d.FieldDescriptorProto
def msg(name,fields):
    node=f.message_type.add()
    node.name=name
    for number,(field,typ,repeated,ref) in enumerate(fields,1):
        x=node.field.add()
        x.name=field;x.number=number
        x.type=getattr(T,"TYPE_"+typ.upper())
        x.label=T.LABEL_REPEATED if repeated else T.LABEL_OPTIONAL
        if ref:x.type_name="."+f.package+"."+ref
msg("IntVariable",[("name","string",False,None),("lower","sint64",False,None),("upper","sint64",False,None)])
msg("LinearTerm",[("name","string",False,None),("coefficient","sint64",False,None)])
msg("LinearConstraint",[("terms","message",True,"LinearTerm"),("relation","string",False,None),("rhs","sint64",False,None)])
msg("VerifyRequest",[("schema_version","uint32",False,None),("variables","message",True,"IntVariable"),
                     ("constraints","message",True,"LinearConstraint"),("backend","string",False,None),
                     ("timeout_ms","uint32",False,None),("proof_required","bool",False,None)])
msg("VerifyResult",[("schema_version","uint32",False,None),("status","string",False,None),
                    ("witness","sint64",True,None),("backend","string",False,None),
                    ("assurance","string",False,None),("limitation","string",False,None),
                    ("request_sha256","string",False,None)])
p=descriptor_pool.DescriptorPool()
DESCRIPTOR=p.Add(f)
for _name in ("IntVariable","LinearTerm","LinearConstraint","VerifyRequest","VerifyResult"):
    globals()[_name]=message_factory.GetMessageClass(p.FindMessageTypeByName("cognitum.formal.v1."+_name))
