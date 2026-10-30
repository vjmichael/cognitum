"""C15 T3 P2Q: validated pinhole depth -> temporal sparse occupancy -> T2 hypotheses.

No actual calibration, depth measurements, source ownership, or physical safety
are authenticated here. No undistortion, learned monocular-depth prediction,
canonical scene mutation, 3D pose inference from a 2D appearance descriptor,
or host permission are implied. All results are research-only Protobuf.
"""
from __future__ import annotations

import hashlib
import math

from cognitum.proto import spatial_calibrated_depth_pb2 as pb
from cognitum.proto import temporal_occupancy_pb2 as tp
from cognitum.proto import spatial_volume_pb2 as vp
from cognitum.spatial_temporal_occupancy import integrate, _rotate, TemporalOccupancyRejected
from cognitum.spatial_volume import classify as classify_volume, VolumeRejected

MAX_SAMPLES = 256
MAX_BYTES = 100_000
MAX_DIMENSION = 8192


class CalibratedDepthRejected(ValueError):
    pass


def _require(ok, why):
    if not ok:
        raise CalibratedDepthRejected(why)


def _id(x):
    return isinstance(x, str) and 0 < len(x) <= 128 and all(
        v.isascii() and (v.isalnum() or v in '-_:.') for v in x)


def _digest(message):
    return hashlib.sha256(message.SerializeToString(deterministic=True)).digest()


def _known(message):
    clone = type(message)()
    clone.CopyFrom(message)
    clone.DiscardUnknownFields()
    return _digest(message) == _digest(clone)


def _coords(p):
    return p.x, p.y, p.z


def _point(p, coords):
    p.x, p.y, p.z = coords


def _validate(req):
    _require(isinstance(req, pb.P2QDepthRequest) and req.schema_version == 1 and
             req.research_only and not req.grants_authority and _known(req) and
             req.ByteSize() <= MAX_BYTES and req.HasField('camera'), 'INVALID_RESEARCH_REQUEST')
    _require(_id(req.conversation_id) and _id(req.volume_id) and _id(req.capture_id) and
             math.isfinite(req.voxel_size_m) and .001 <= req.voxel_size_m <= 1000 and
             1 <= req.max_axis <= 128 and req.evaluation_tick > 0 and
             math.isfinite(req.half_life_ticks) and 0 < req.half_life_ticks <= 1e9,
             'INVALID_GRID_OR_SCOPE')
    _require(1 <= len(req.pixels) <= MAX_SAMPLES and
             math.isfinite(req.hit_probability) and .5 < req.hit_probability < .999 and
             math.isfinite(req.free_probability) and .001 < req.free_probability < .5,
             'INVALID_CAPACITY_OR_SENSOR_MODEL')
    c = req.camera
    q = (c.qw, c.qx, c.qy, c.qz)
    tr = _coords(c.translation)
    _require(_id(c.frame_id) and _id(c.calibration_source_ref) and
             c.HasField('translation') and c.rectified_pinhole and
             1 <= c.width <= MAX_DIMENSION and 1 <= c.height <= MAX_DIMENSION and
             all(math.isfinite(v) for v in (c.fx, c.fy, c.cx, c.cy, c.max_axial_depth_m) + q + tr) and
             0 < c.fx <= 1e7 and 0 < c.fy <= 1e7 and
             0 <= c.cx <= c.width and 0 <= c.cy <= c.height and
             .001 <= c.max_axial_depth_m <= 1000 and
             abs(sum(z*z for z in q) - 1) < 1e-5,
             'INVALID_OR_UNRECTIFIED_CAMERA')
    _require(len(req.camera_sha256) == 32 and req.camera_sha256 == _digest(c),
             'CAMERA_DIGEST_MISMATCH')
    seen = set()
    frame_digests = {}
    for pixel in req.pixels:
        key = (pixel.source_ref, pixel.tick, pixel.u, pixel.v)
        _require(key not in seen and _id(pixel.source_ref) and
                 pixel.tick > 0 and pixel.tick <= req.evaluation_tick and
                 0 <= pixel.u < c.width and 0 <= pixel.v < c.height and
                 len(pixel.depth_frame_sha256) == 32 and
                 math.isfinite(pixel.axial_depth_m) and
                 .001 <= pixel.axial_depth_m <= c.max_axial_depth_m,
                 'INVALID_DEPTH_SAMPLE_OR_PROVENANCE')
        # A no-return beam is a free-space observation to the declared axial
        # limit, NOT evidence of an occupied endpoint at a missing depth.
        _require(pixel.endpoint_hit or
                 abs(pixel.axial_depth_m - c.max_axial_depth_m) <= 1e-9,
                 'MISS_MUST_REACH_DECLARED_MAX_DEPTH')
        frame_key = (pixel.source_ref, pixel.tick)
        previous_digest = frame_digests.setdefault(frame_key, pixel.depth_frame_sha256)
        _require(previous_digest == pixel.depth_frame_sha256,
                 'INCONSISTENT_SOURCE_TICK_DEPTH_FRAME_HASH')
        seen.add(key)
    return c, q, tr


def project(req: pb.P2QDepthRequest) -> pb.P2QDepthResult:
    c, q, translation = _validate(req)
    out = pb.P2QDepthResult(
        schema_version=1, conversation_id=req.conversation_id,
        volume_id=req.volume_id, capture_id=req.capture_id,
        request_sha256=_digest(req), camera_sha256=req.camera_sha256,
        research_only=True, grants_authority=False)
    temporal = tp.TemporalOccupancyRequest(
        schema_version=1, conversation_id=req.conversation_id,
        volume_id=req.volume_id, voxel_size_m=req.voxel_size_m,
        max_axis=req.max_axis, evaluation_tick=req.evaluation_tick,
        half_life_ticks=req.half_life_ticks,
        research_only=True, grants_authority=False)
    frame = temporal.frames.add(frame_id=c.frame_id, qw=c.qw, qx=c.qx, qy=c.qy, qz=c.qz)
    _point(frame.translation, translation)
    world_max = req.voxel_size_m * req.max_axis
    for px in sorted(req.pixels, key=lambda x: (x.tick, x.source_ref, x.u, x.v)):
        # Axial-depth convention Z=d; pixel coordinates refer to pixel CENTERS.
        endpoint = (((px.u + .5 - c.cx) / c.fx) * px.axial_depth_m,
                    ((px.v + .5 - c.cy) / c.fy) * px.axial_depth_m,
                    px.axial_depth_m)
        world = tuple(a + b for a, b in zip(_rotate(q, endpoint), translation))
        _require(all(math.isfinite(z) and 0 <= z < world_max for z in translation + world) and
                 math.dist(translation, world) > 1e-12,
                 'PROJECTED_RAY_OUTSIDE_GRID')
        voxel = tuple(math.floor(z / req.voxel_size_m) for z in world)
        derived_ref = 'ray.' + hashlib.sha256(
            ('%s|%s|%s|%s|%s|%s' % (req.capture_id, px.source_ref, px.tick,
                                       px.u, px.v, px.depth_frame_sha256.hex())).encode('utf-8')
        ).hexdigest()[:32]
        r = temporal.rays.add(source_ref=derived_ref, tick=px.tick,
            frame_id=c.frame_id, endpoint_hit=px.endpoint_hit,
            hit_probability=req.hit_probability, free_probability=req.free_probability)
        _point(r.start, (0., 0., 0.))
        _point(r.end, endpoint)
        mapping = out.projections.add(u=px.u, v=px.v, tick=px.tick,
            source_ref=px.source_ref, depth_frame_sha256=px.depth_frame_sha256,
            endpoint_hit=px.endpoint_hit, derived_ray_source_ref=derived_ref, voxel_x=voxel[0],
            voxel_y=voxel[1], voxel_z=voxel[2])
        _point(mapping.camera_endpoint_m, endpoint)
        _point(mapping.world_endpoint_m, world)
    try:
        occupancy = integrate(temporal)
    except TemporalOccupancyRejected as exc:
        raise CalibratedDepthRejected('TEMPORAL_OCCUPANCY_REJECTED:' + str(exc)) from exc
    # Projected occupancy is a hypothesis, not a measured T2 truth. A
    # conflicted or near-0.5 cell is left unknown, never silently resolved.
    hypothetical = vp.VolumeGrid(schema_version=1, conversation_id=req.conversation_id,
        volume_id=req.volume_id, voxel_size_m=req.voxel_size_m,
        max_axis=req.max_axis, research_only=True, grants_authority=False)
    source_id = 'p2q.' + out.request_sha256.hex()[:32]
    for cell in occupancy.cells:
        if cell.conflicted or .35 < cell.probability < .65:
            continue
        occupied = cell.probability >= .65
        reliability = max(.5, min(.999, cell.probability if occupied else 1 - cell.probability))
        hypothetical.evidence.add(x=cell.x, y=cell.y, z=cell.z,
            kind=vp.VOLUME_PREDICTED_OCCUPIED if occupied else vp.VOLUME_PREDICTED_FREE,
            source_id=source_id, tick=req.evaluation_tick, reliability=reliability)
    _require(len(hypothetical.evidence) <= 8192, 'HYPOTHETICAL_VOLUME_CAPACITY')
    try:
        predicted = classify_volume(hypothetical)
    except VolumeRejected as exc:
        raise CalibratedDepthRejected('VOLUME_HANDOFF_REJECTED:' + str(exc)) from exc
    _require(all(c.state == vp.CELL_UNKNOWN for c in predicted.cells),
             'ILLEGAL_PROMOTION_OF_HYPOTHETICAL_GEOMETRY')
    out.temporal_request.CopyFrom(temporal)
    out.temporal_result.CopyFrom(occupancy)
    out.hypothetical_volume.CopyFrom(hypothetical)
    out.warnings.extend([
        'DEPTH_AND_CAMERA_CALIBRATION_ARE_CALLER_ASSERTED_NOT_AUTHENTICATED',
        'IMAGE_SHA256_CLAIM_HAS_NOT_BEEN_VERIFIED_AGAINST_IMAGE_BYTES',
        'PINHOLE_RECTIFIED_INPUT_REQUIRED_NO_DISTORTION_CORRECTION',
        'DEPTH_Z_IS_AXIAL_NOT_EUCLIDEAN_RAY_LENGTH',
        'SPARSE_LOG_ODDS_ASSUME_INDEPENDENCE_NOT_REAL_WORLD_CALIBRATION',
        'SAME_FRAME_RAYS_ARE_CORRELATED_DESPITE_DISTINCT_DERIVED_EVENT_REFS',
        'T2_VOLUME_HANDOFF_IS_PREDICTED_ONLY_NEVER_MEASURED',
        'T2_HYPOTHETICAL_STRUCTURE_IS_NOT_PHYSICAL_GEOMETRY',
        'NO_CANONICAL_SCENE_VOXEL_OR_ACTION_AUTHORITY',
    ])
    return out


def verify(req: pb.P2QDepthRequest, response: pb.P2QDepthResult) -> bool:
    _require(isinstance(response, pb.P2QDepthResult) and _known(response),
             'INVALID_RESPONSE')
    # Research reference determinism and exact provenance binding, not a
    # cryptographic signature, host source verification, or sensor attestation.
    expected = project(req)
    _require(response.SerializeToString(deterministic=True) ==
             expected.SerializeToString(deterministic=True), 'PROJECTED_HANDOFF_MISMATCH')
    return True
