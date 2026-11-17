"""Descriptor-backed bounded cooperative messages, compared to compiled source."""
from google.protobuf import descriptor_pb2 as d, descriptor_pool, message_factory
f=d.FileDescriptorProto(name="cognitum/cooperative/v1/composition.proto",package="cognitum.cooperative.v1",syntax="proto3")
T=d.FieldDescriptorProto
FIELDS={"IntRow":[["values","sint64",1]],"SolutionSet":[["schema_version","uint32"],["request_sha256","string"],["cases_checked","uint32"],["solutions","IntRow",1],["status","string"]],"Scenario":[["name","string"],["physical_request","bytes"]],"MixtureRequest":[["schema_version","uint32"],["scenarios","Scenario",1],["weights","double",1]],"ScenarioResult":[["name","string"],["weight","double"],["physical_result","bytes"]],"MixtureResult":[["schema_version","uint32"],["request_sha256","string"],["scenarios","ScenarioResult",1],["mean_position_m","double"],["variance_position_m2","double"],["status","string"]]}
for name,fields in FIELDS.items():
    msg=f.message_type.add(name=name)
    for index,spec in enumerate(fields,1):
        key,kind=spec[:2]
        field=msg.field.add(name=key,number=index)
        field.label=T.LABEL_REPEATED if len(spec)==3 else T.LABEL_OPTIONAL
        if kind in FIELDS:
            field.type=T.TYPE_MESSAGE
            field.type_name="."+f.package+"."+kind
        else:field.type=getattr(T,"TYPE_"+kind.upper())
pool=descriptor_pool.DescriptorPool()
DESCRIPTOR=pool.Add(f)
for name in FIELDS:
    globals()[name]=message_factory.GetMessageClass(pool.FindMessageTypeByName(f.package+"."+name))
