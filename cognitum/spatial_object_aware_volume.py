"""C15 T3 P2T: bounded T1-object / T3-volume research hypothesis audit.

Reuses P2S temporal fusion without modifying its probabilities. Requires
paired vacated/arrived voxels before proposing object-linked motion. Object
identity, depth hashes, and poses remain *caller assertions*, not attestation.
Never writes a canonical scene, static map, or Lu runtime state.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import math
import re

from cognitum.proto import spatial_object_aware_volume_pb2 as pb
from cognitum.proto import spatial_temporal_consistency_pb2 as p2s_pb
from cognitum.proto import spatial_volume_pb2 as volume_pb
from cognitum.proto import spatial_scene_pb2 as scene_pb
from cognitum.spatial_temporal_consistency import reconcile as temporal_reconcile, TemporalConsistencyRejected
from cognitum.spatial_scene_reference import _world_position, _quat, SceneRejected
from cognitum.spatial_volume import classify as classify_volume, VolumeRejected

MAX_BYTES = 1_100_000
MAX_TRACKS = 16
MAX_SAMPLES = 12
MAX_LINKS = 1024
_IDENT = re.compile(r'^[a-zA-Z0-9_.:-]{1,128}$')

class ObjectAwareVolumeRejected(ValueError):
    pass


def _check(ok: bool, reason: str):
    if not ok:
        raise ObjectAwareVolumeRejected(reason)


def _sha(m):
    return hashlib.sha256(m.SerializeToString(deterministic=True)).digest()


def _known(m):
    copy = type(m)()
    copy.CopyFrom(m)
    copy.DiscardUnknownFields()
    return copy.SerializeToString(deterministic=True) == m.SerializeToString(deterministic=True)


def _xyz(vec):
    xyz = (vec.x, vec.y, vec.z)
    _check(all(math.isfinite(v) and abs(v) <= 1_000_000 for v in xyz), 'NONFINITE_WORLD_POSITION')
    return xyz


def _center(cell, size):
    return tuple((c + .5) * size for c in cell)


def _distance_to_segment(xyz, a, b):
    direction = tuple(q - p for p, q in zip(a, b))
    denom = sum(x*x for x in direction)
    factor = max(0., min(1., sum((xyz[i]-a[i])*direction[i] for i in range(3)) / denom)) if denom else 0.
    return math.dist(xyz, tuple(a[i] + factor*direction[i] for i in range(3)))


def analyze(req: pb.P2TObjectAwareRequest) -> pb.P2TObjectAwareResult:
    _check(isinstance(req, pb.P2TObjectAwareRequest) and req.schema_version == 1 and
           req.research_only and not req.grants_authority and _known(req) and
           req.ByteSize() <= MAX_BYTES, 'INVALID_P2T_CONTRACT')
    _check(all(_IDENT.fullmatch(s) for s in (req.conversation_id, req.volume_id)), 'INVALID_SCOPE')
    _check(req.temporal_request.conversation_id == req.conversation_id and
           req.temporal_request.volume_id == req.volume_id and
           req.temporal_request.research_only and not req.temporal_request.grants_authority,
           'CROSS_SCOPE_TEMPORAL_INPUT')
    _check(req.scene.schema_version == 1 and req.scene.research_only and _known(req.scene) and
           req.scene.conversation_id == req.conversation_id and _IDENT.fullmatch(req.scene.scene_id) and
           bytes(req.scene_sha256) == _sha(req.scene), 'INVALID_OR_UNBOUND_T1_SCENE')
    _check(math.isfinite(req.min_displacement_m) and 0 < req.min_displacement_m <= 100 and
           math.isfinite(req.spatial_tolerance_m) and 0 < req.spatial_tolerance_m <= 10 and
           1 <= req.max_link_gap_ticks <= 100000 and 1 <= len(req.tracks) <= MAX_TRACKS,
           'INVALID_OBJECT_AWARE_POLICY')
    try:
        temporal = temporal_reconcile(req.temporal_request)
    except TemporalConsistencyRejected as exc:
        raise ObjectAwareVolumeRejected('INVALID_P2S_EVIDENCE:' + str(exc)) from exc
    grid_size = req.temporal_request.captures[0].depth.voxel_size_m
    _check(req.spatial_tolerance_m <= 4 * grid_size, 'SPATIAL_TOLERANCE_EXCEEDS_FOUR_VOXELS')
    frame_refs = {}
    for capture in req.temporal_request.captures:
        depth = capture.depth
        frame = depth.pixels[0]
        frame_refs[depth.capture_id] = (frame.tick, frame.source_ref, bytes(frame.depth_frame_sha256))
    _check(len(frame_refs) == len(req.temporal_request.captures), 'DUPLICATE_CAPTURE')
    frames = {f.frame_id:f for f in req.scene.frames}
    _check(len(frames) == len(req.scene.frames), 'DUPLICATE_SCENE_FRAME')
    objs = {o.object_id: o for o in req.scene.objects}
    _check(len(objs) == len(req.scene.objects), 'DUPLICATE_SCENE_OBJECT')
    tracks = {}
    occupied_paths = []
    for tr in req.tracks:
        _check(_IDENT.fullmatch(tr.object_id) and tr.object_id not in tracks and tr.object_id in objs and
               2 <= len(tr.samples) <= MAX_SAMPLES, 'INVALID_OBJECT_TRACK')
        obj = objs[tr.object_id]
        _check(obj.visibility != scene_pb.VISIBILITY_DELETED and obj.HasField('position_m') and
               obj.HasField('rotation_xyzw'), 'INVALID_T1_OBJECT_STATE')
        samples = []
        prev = 0
        seen_captures = set()
        for sample in tr.samples:
            _check(sample.HasField('center_world_m') and sample.capture_id in frame_refs and
                   sample.capture_id not in seen_captures and sample.tick > prev, 'INVALID_OBJECT_SAMPLE')
            prev = sample.tick
            seen_captures.add(sample.capture_id)
            _check((sample.tick, sample.source_ref, bytes(sample.depth_frame_sha256)) == frame_refs[sample.capture_id],
                   'UNBOUND_OBJECT_SAMPLE_FRAME')
            samples.append((sample.tick, sample.capture_id, _xyz(sample.center_world_m)))
        _check(samples[-1][0] == obj.last_observed_tick, 'T1_LATEST_TICK_MISMATCH')
        _check(obj.observation_source_id == frame_refs[samples[-1][1]][1],
               'T1_LATEST_SOURCE_MISMATCH')
        try:
            _quat(obj.rotation_xyzw)
            world = _world_position(obj.frame_id, _xyz(obj.position_m), frames)
        except (SceneRejected, ValueError) as exc:
            raise ObjectAwareVolumeRejected('INVALID_T1_COORDINATE_FRAME') from exc
        _check(math.dist(world, samples[-1][2]) <= 1e-6, 'T1_LATEST_POSE_MISMATCH')
        tracks[tr.object_id] = samples
        occupied_paths.extend([pos for _, _, pos in samples])

    cells = {(c.x, c.y, c.z):c for c in temporal.cells}
    frees = {coord:c for coord,c in cells.items() if c.state == p2s_pb.P2S_RECOVERED_FREE}
    hits = {coord:c for coord,c in cells.items() if c.state == p2s_pb.P2S_RECOVERED_OCCUPIED}
    links = []
    # Pair recovery evidence on both sides of a displacement. A vacated voxel
    # alone never establishes movement or makes a safe-free-space claim.
    for object_id, samples in sorted(tracks.items()):
        for before, after in zip(samples, samples[1:]):
            at, acap, a = before
            bt, bcap, b = after
            dist = math.dist(a, b)
            if dist < req.min_displacement_m or bt-at > req.max_link_gap_ticks:
                continue
            source_cells = [(key,c) for key,c in frees.items() if
                at < c.change_candidate_tick <= bt and
                math.dist(a, _center(key,grid_size)) <= req.spatial_tolerance_m]
            dest_cells = [(key,c) for key,c in hits.items() if
                at < c.change_candidate_tick <= bt and
                math.dist(b, _center(key,grid_size)) <= req.spatial_tolerance_m]
            for old, _ in sorted(source_cells):
                for new, _ in sorted(dest_cells):
                    if new == old: continue
                    _check(len(links) < MAX_LINKS, 'MOTION_LINK_RESOURCE_LIMIT')
                    links.append((object_id, acap, bcap, at, bt, old, new, dist))
    links = sorted(set(links))
    membership = defaultdict(set)
    for object_id, _, _, _, _, old, new, _ in links:
        membership[old].add(object_id)
        membership[new].add(object_id)

    output = pb.P2TObjectAwareResult(schema_version=1,conversation_id=req.conversation_id,
       volume_id=req.volume_id,request_sha256=_sha(req),
       temporal_request_sha256=temporal.request_sha256,scene_sha256=req.scene_sha256,
       research_only=True,grants_authority=False)
    for object_id, acap, bcap, at, bt, old, new, dist in links:
        output.motion_candidates.add(object_id=object_id,origin_capture_id=acap,
           destination_capture_id=bcap,origin_tick=at,destination_tick=bt,
           origin_x=old[0],origin_y=old[1],origin_z=old[2],
           destination_x=new[0],destination_y=new[1],destination_z=new[2],displacement_m=dist)

    output.stationary_hypothetical_volume.CopyFrom(temporal.hypothetical_volume)
    # Preserve the P2S volume as evidence, then filter into a *separate*
    # stationary-map hypothesis. Never mutate the P2S result or scene.
    allowed = set()
    for coord, cell in sorted(cells.items()):
        moving_ids = sorted(membership.get(coord, ()))
        center = _center(coord, grid_size)
        overlapping = any(math.dist(center, pos) <= req.spatial_tolerance_m for pos in occupied_paths)
        # Entire caller-asserted path is excluded, not just its endpoints.
        if not overlapping:
            for samples in tracks.values():
                if any(_distance_to_segment(center, a[2], b[2]) <= req.spatial_tolerance_m
                       for a,b in zip(samples, samples[1:])):
                    overlapping = True
                    break
        stable = cell.state in (p2s_pb.P2S_PREDICTED_FREE,p2s_pb.P2S_PREDICTED_OCCUPIED)
        static = stable and not overlapping and not moving_ids
        if moving_ids:
            explanation = (pb.P2T_MOTION_CANDIDATE if len(moving_ids) == 1 else pb.P2T_MULTIPLE_OBJECTS)
        elif cell.state in (p2s_pb.P2S_RECOVERED_FREE,p2s_pb.P2S_RECOVERED_OCCUPIED):
            explanation = pb.P2T_UNATTRIBUTED_CHANGE
        elif static:
            explanation = pb.P2T_STATIONARY_CANDIDATE
        else:
            explanation = pb.P2T_UNRESOLVED
        c = output.cells.add(x=coord[0],y=coord[1],z=coord[2],
            temporal_state=cell.state,explanation=explanation,static_handoff_allowed=static)
        c.candidate_object_ids.extend(moving_ids)
        if static: allowed.add(coord)
    stationary = output.stationary_hypothetical_volume
    original = [e for e in stationary.evidence if (e.x,e.y,e.z) in allowed]
    stationary.ClearField('evidence')
    stationary.evidence.extend(original)
    try:
        validated = classify_volume(stationary)
    except VolumeRejected as exc:
        raise ObjectAwareVolumeRejected('INVALID_T2_STATIONARY_HYPOTHESIS:' + str(exc)) from exc
    _check(all(c.state == volume_pb.CELL_UNKNOWN for c in validated.cells), 'ILLEGAL_T2_PROMOTION')
    output.warnings.extend([
        'OBJECT_IDS_AND_T1_SNAPSHOT_ARE_CALLER_SUPPLIED_NOT_AUTHENTICATED',
        'FRAME_SHA256_AND_WORLD_POSE_BINDING_DOES_NOT_ATTEST_SENSORS',
        'PAIRED_VOXEL_CHANGES_SUGGEST_MOTION_NOT_CAUSATION',
        'UNATTRIBUTED_CHANGES_ARE_NOT_PROOF_OF_STATIONARY_STRUCTURE',
        'STATIC_HANDOFF_IS_PREDICTED_ONLY_AND_NOT_A_SAFE_NAVIGATION_MAP',
        'NO_CANONICAL_SCENE_VOLUME_OR_IDENTITY_MUTATION',
    ])
    return output


def verify(req: pb.P2TObjectAwareRequest, got: pb.P2TObjectAwareResult) -> bool:
    _check(isinstance(got,pb.P2TObjectAwareResult) and _known(got) and
           got.SerializeToString(deterministic=True) == analyze(req).SerializeToString(deterministic=True),
           'P2T_REPLAY_MISMATCH')
    return True
