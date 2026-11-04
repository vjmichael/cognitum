"""C15 descriptor-backed spatial core Protobuf bindings; checked against protoc."""
from google.protobuf import descriptor_pb2 as d, descriptor_pool, message_factory
f=d.FileDescriptorProto();f.name="cognitum/spatial_core/v1/spatial_core.proto";f.package="cognitum.spatial_core.v1";f.syntax="proto3"
T=d.FieldDescriptorProto
def fld(name,typ,rep=False,ref=None):return name,typ,rep,ref
def msg(name,fields):
 m=f.message_type.add();m.name=name
 for i,(name,typ,rep,ref) in enumerate(fields,1):
  x=m.field.add();x.name=name;x.number=i;x.type=getattr(T,"TYPE_"+typ.upper())
  x.label=T.LABEL_REPEATED if rep else T.LABEL_OPTIONAL
  if ref:x.type_name="."+f.package+"."+ref
msg("Frame",[fld("name","string"),fld("parent","string"),fld("translation_m","double",True),fld("quaternion_xyzw","double",True)])
msg("SceneObject",[fld("stable_id","string"),fld("frame","string"),fld("position_m","double",True),fld("dimensions_m","double",True),fld("visible","bool"),fld("observation_source","string"),fld("timestamp_ms","uint64"),fld("version","uint32")])
msg("SceneQuery",[fld("schema_version","uint32"),fld("frames","message",True,"Frame"),fld("objects","message",True,"SceneObject"),fld("epoch","uint64"),fld("object_id","string"),fld("reference_id","string")])
msg("SceneResult",[fld("schema_version","uint32"),fld("status","string"),fld("world_position_m","double",True),fld("distance_m","double"),fld("first_left_of_second","bool"),fld("limitations","string",True),fld("request_sha256","string")])
msg("Detection",[fld("detection_id","string"),fld("x","double"),fld("y","double"),fld("width","double"),fld("height","double"),fld("source","string")])
msg("Track",[fld("stable_id","string"),fld("x","double"),fld("y","double"),fld("width","double"),fld("height","double"),fld("missed","uint32"),fld("last_source","string")])
msg("Match",[fld("stable_id","string"),fld("detection_id","string")])
msg("TrackRequest",[fld("schema_version","uint32"),fld("tracks","message",True,"Track"),fld("detections","message",True,"Detection"),fld("min_iou","double"),fld("max_distance","double"),fld("max_missed","uint32")])
msg("TrackResult",[fld("schema_version","uint32"),fld("status","string"),fld("tracks","message",True,"Track"),fld("matches","message",True,"Match"),fld("unmatched_detections","string",True),fld("retired_ids","string",True),fld("limitations","string",True),fld("request_sha256","string")])
p=descriptor_pool.DescriptorPool();DESCRIPTOR=p.Add(f)
for name in ("Frame","SceneObject","SceneQuery","SceneResult","Detection","Track","Match","TrackRequest","TrackResult"):
 globals()[name]=message_factory.GetMessageClass(p.FindMessageTypeByName(f.package+"."+name))
