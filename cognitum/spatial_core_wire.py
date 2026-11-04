"""C15 canonical Protobuf boundary for inert spatial scene/track operations."""
from hashlib import sha256
from google.protobuf.message import DecodeError
from .proto import spatial_core_pb2 as pb
from .spatial_geometry import Frame,SceneObject,Scene,world_position,world_pose,relation,validate as validate_scene
from .spatial_tracking import Track,Detection,update,validate as validate_track
from .spatial_scene_graph import graph_relations

MAX_INPUT=65536
MAX_OUTPUT=65536


def _read(frame,cls,limit):
    if type(frame) is not bytes or not 0<len(frame)<=limit:
        raise ValueError("invalid spatial wire size")
    obj=cls()
    try:obj.ParseFromString(frame)
    except DecodeError as exc:raise ValueError("malformed spatial wire") from exc
    copy=cls();copy.CopyFrom(obj);copy.DiscardUnknownFields()
    if copy!=obj or obj.SerializeToString(deterministic=True)!=frame:
        raise ValueError("noncanonical, unknown or duplicate spatial protobuf")
    return obj


def _write(obj):
    frame=obj.SerializeToString(deterministic=True)
    if len(frame)>MAX_OUTPUT:
        raise ValueError("oversized spatial result")
    return frame


def _scene(req):
    if req.schema_version!=1:
        raise ValueError("unknown spatial schema")
    return validate_scene(Scene(
        tuple(Frame(f.name,f.parent,tuple(f.translation_m),tuple(f.quaternion_xyzw))
              for f in req.frames),
        tuple(SceneObject(o.stable_id,o.frame,tuple(o.position_m),tuple(o.dimensions_m),
                          o.visible,o.observation_source,o.timestamp_ms,o.version,
                          tuple(o.orientation_xyzw) if o.orientation_xyzw else (0.,0.,0.,1.),
                          o.geometry_ref or "unresolved",o.confidence)
              for o in req.objects),
        req.epoch,
    ))


def _tracks(req):
    if req.schema_version!=1:
        raise ValueError("unknown track schema")
    tracks=tuple(Track(t.stable_id,t.x,t.y,t.width,t.height,t.missed,t.last_source)
                 for t in req.tracks)
    detections=tuple(Detection(d.detection_id,d.x,d.y,d.width,d.height,d.source)
                     for d in req.detections)
    validate_track(tracks,detections)
    return tracks,detections


def execute_scene(frame:bytes)->bytes:
    req=_read(frame,pb.SceneQuery,MAX_INPUT)
    scene=_scene(req)
    if not req.object_id or not req.reference_id:
        raise ValueError("explicit query and reference IDs required")
    position,orientation=world_pose(scene,req.object_id)
    info=relation(scene,req.object_id,req.reference_id)
    result=pb.SceneResult(schema_version=1,status="OK",
                          world_position_m=position,world_orientation_xyzw=orientation,
                          distance_m=info["distance_m"],
                          first_left_of_second=info["first_left_of_second"],
                          limitations=["caller_supplied_geometry_not_authenticated",
                                       "no_sensor_observations_acquired"],
                          request_sha256=sha256(frame).hexdigest())
    relevant={req.object_id,req.reference_id}
    for edge in graph_relations(scene):
        if edge.subject_id not in relevant or edge.object_id not in relevant:
            continue
        result.relations.add(
            subject_id=edge.subject_id,predicate=edge.predicate,
            object_id=edge.object_id,coordinate_frame=edge.coordinate_frame,
            value_m=edge.value_m,subject_version=edge.subject_version,
            object_version=edge.object_version,scene_epoch=edge.scene_epoch,
            evidence_sources=edge.evidence_sources,status=edge.status)
    return _write(result)


def execute_track(frame:bytes)->bytes:
    req=_read(frame,pb.TrackRequest,MAX_INPUT)
    tracks,detections=_tracks(req)
    result=update(tracks,detections,min_iou=req.min_iou,
                  max_distance=req.max_distance,max_missed=req.max_missed)
    wire=pb.TrackResult(schema_version=1,status=result.status,
                        unmatched_detections=result.unmatched_detections,
                        retired_ids=result.retired_ids,
                        limitations=result.limitations,
                        request_sha256=sha256(frame).hexdigest())
    for t in result.tracks:
        wire.tracks.add(stable_id=t.stable_id,x=t.x,y=t.y,width=t.width,
                        height=t.height,missed=t.missed,last_source=t.last_source)
    for a,b in result.assignments:
        wire.matches.add(stable_id=a,detection_id=b)
    return _write(wire)


def verify_scene(frame:bytes,reply:bytes):
    req=_read(frame,pb.SceneQuery,MAX_INPUT)
    result=_read(reply,pb.SceneResult,MAX_OUTPUT)
    if (result.schema_version!=1 or result.request_sha256!=sha256(frame).hexdigest()
            or result.status!="OK"):
        raise ValueError("scene result mismatch")
    expected=_read(execute_scene(frame),pb.SceneResult,MAX_OUTPUT)
    if result!=expected:
        raise ValueError("scene geometry fails independent recomputation")
    return result


def verify_track(frame:bytes,reply:bytes):
    req=_read(frame,pb.TrackRequest,MAX_INPUT)
    result=_read(reply,pb.TrackResult,MAX_OUTPUT)
    if (result.schema_version!=1 or result.request_sha256!=sha256(frame).hexdigest()
            or result.status not in ("ASSOCIATED","UNSUPPORTED")):
        raise ValueError("track result mismatch")
    expected=_read(execute_track(frame),pb.TrackResult,MAX_OUTPUT)
    if result!=expected:
        raise ValueError("track assignment differs from recomputed input")
    return result
