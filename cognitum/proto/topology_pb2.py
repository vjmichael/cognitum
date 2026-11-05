"""C19 descriptor-backed Protobuf schema, compared to external protoc in CI."""
from google.protobuf import descriptor_pb2 as d,descriptor_pool,message_factory
f=d.FileDescriptorProto()
f.name="cognitum/topology/v1/topology.proto"
f.package="cognitum.topology.v1"
f.syntax="proto3"
T=d.FieldDescriptorProto
def field(n,t,rep=False,ref=None):return (n,t,rep,ref)
def msg(name,fields):
    m=f.message_type.add();m.name=name
    for i,(n,t,many,ref) in enumerate(fields,1):
        v=m.field.add();v.name=n;v.number=i
        v.type=getattr(T,"TYPE_"+t.upper())
        v.label=T.LABEL_REPEATED if many else T.LABEL_OPTIONAL
        if ref:v.type_name="."+f.package+"."+ref
msg("Vector",[field("values","double",True)])
msg("Query",[
 field("schema_version","uint32"),field("source_id","string"),
 field("snapshot_sha256","string"),field("coordinate_unit","string"),
 field("metric","string"),field("filtration","string"),
 field("maximum_scale","double"),field("maximum_homology_dimension","uint32"),
 field("points","message",True,"Vector"),field("max_points","uint32")])
msg("Interval",[
 field("dimension","uint32"),field("birth","double"),
 field("has_finite_death","bool"),field("death","double")])
msg("Result",[
 field("schema_version","uint32"),field("status","string"),
 field("source_id","string"),field("snapshot_sha256","string"),
 field("metric","string"),field("coordinate_unit","string"),
 field("filtration","string"),field("maximum_scale","double"),
 field("intervals","message",True,"Interval"),
 field("connected_components_at_scale","uint32"),
 field("persistent_h1_count","uint32"),
 field("longest_finite_h1","double"),field("has_h0_mst_check","bool"),
 field("h0_mst_max_deviation","double"),field("input_points","uint32"),
 field("unique_points","uint32"),field("resource_pair_bound","uint32"),
 field("limitations","string",True),field("request_sha256","string")])
pool=descriptor_pool.DescriptorPool()
DESCRIPTOR=pool.Add(f)
for name in ("Vector","Query","Interval","Result"):
    globals()[name]=message_factory.GetMessageClass(pool.FindMessageTypeByName(f.package+"."+name))
