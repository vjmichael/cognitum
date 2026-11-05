"""C19 strictly canonical inert topology query and verifiable diagram wire.

Verification recomputes the same mature Ripser engine and separately checks
H0 with SciPy MST. This is tamper detection, not independent H1 certification;
optional GUDHI verification provides a separate engine check.
"""
from hashlib import sha256
from math import isfinite
from google.protobuf.message import DecodeError
from .proto import topology_pb2 as pb
from .topology_rips import TopologyQuery,validate,compute

MAX_REQUEST=20000
MAX_RESULT=40000

def _read(data,cls,maxsize):
    if type(data) is not bytes or not 0<len(data)<=maxsize:
        raise ValueError("invalid topology wire frame")
    obj=cls()
    try:obj.ParseFromString(data)
    except DecodeError as exc:raise ValueError("malformed topology wire") from exc
    clean=cls();clean.CopyFrom(obj);clean.DiscardUnknownFields()
    if clean!=obj or obj.SerializeToString(deterministic=True)!=data:
        raise ValueError("unknown or noncanonical Protobuf fields")
    return obj

def _query(w):
    if w.schema_version!=1:raise ValueError("topology schema unsupported")
    query=TopologyQuery(w.source_id,w.snapshot_sha256,w.coordinate_unit,
        w.metric,w.filtration,w.maximum_scale,w.maximum_homology_dimension,
        tuple(tuple(row.values) for row in w.points),w.max_points)
    return validate(query)

def execute(request:bytes)->bytes:
    req=_read(request,pb.Query,MAX_REQUEST)
    q=_query(req)
    outcome=compute(q)
    out=pb.Result(schema_version=1,status=outcome.status,
        source_id=q.source_id,snapshot_sha256=q.snapshot_sha256,
        metric=q.metric,coordinate_unit=q.coordinate_unit,
        filtration=q.filtration,maximum_scale=q.maximum_scale,
        connected_components_at_scale=outcome.connected_components_at_scale,
        persistent_h1_count=outcome.persistent_h1_count,
        longest_finite_h1=outcome.longest_finite_h1,
        has_h0_mst_check=outcome.h0_mst_max_deviation is not None,
        h0_mst_max_deviation=outcome.h0_mst_max_deviation or 0.,
        input_points=outcome.input_points,unique_points=outcome.unique_points,
        resource_pair_bound=outcome.resource_pair_bound,
        limitations=outcome.limitations,
        request_sha256=sha256(request).hexdigest())
    for x in outcome.intervals:
        out.intervals.add(dimension=x.dimension,birth=x.birth,
           has_finite_death=x.death is not None,
           death=x.death if x.death is not None else 0.)
    frame=out.SerializeToString(deterministic=True)
    if len(frame)>MAX_RESULT:raise ValueError("oversized topology result")
    return frame

def verify(request:bytes,response:bytes):
    result=_read(response,pb.Result,MAX_RESULT)
    actual=_read(execute(request),pb.Result,MAX_RESULT)
    if result!=actual or result.schema_version!=1:
        raise ValueError("persistence diagram fails replay verification")
    return result
