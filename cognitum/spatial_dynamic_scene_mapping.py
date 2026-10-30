"""C15 T3 P2U: bounded, replayable dynamic/static research map.

Recomputes P2T outcomes from supplied windows and carries motion-candidate
provenance across independent captures. All IDs/frames remain caller assertions;
no real sensor attestation, authority, canonical writes or safe navigation map.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import math
import re

from cognitum.proto import spatial_dynamic_scene_mapping_pb2 as pb
from cognitum.proto import spatial_object_aware_volume_pb2 as tpb
from cognitum.proto import spatial_volume_pb2 as vpb
from cognitum.spatial_object_aware_volume import analyze as p2t_analyze, ObjectAwareVolumeRejected
from cognitum.spatial_temporal_consistency import reconcile as temporal_reconcile, TemporalConsistencyRejected
from cognitum.spatial_volume import classify as classify_volume, VolumeRejected

_ID = re.compile(r'^[A-Za-z0-9_.:-]{1,128}$')
MAX_WINDOWS = 8
MAX_REQUEST_BYTES = 7_000_000
MAX_CELLS = 4096
MAX_OBJECTS = 128

class DynamicSceneRejected(ValueError):
    pass

def require(ok: bool, reason: str) -> None:
    if not ok:
        raise DynamicSceneRejected(reason)

def _sha(msg):
    return hashlib.sha256(msg.SerializeToString(deterministic=True)).digest()

def _known(msg):
    cleaned = type(msg)()
    cleaned.CopyFrom(msg)
    cleaned.DiscardUnknownFields()
    return cleaned.SerializeToString(deterministic=True) == msg.SerializeToString(deterministic=True)

def _coord(cell):
    return (cell.x, cell.y, cell.z)

def _map_scene(req: pb.P2UDynamicSceneRequest, *, _evaluate_window=p2t_analyze,
               _reconcile_temporal=temporal_reconcile) -> pb.P2UDynamicSceneResult:
    require(isinstance(req, pb.P2UDynamicSceneRequest) and req.schema_version == 1
            and req.research_only and not req.grants_authority and _known(req)
            and req.ByteSize() <= MAX_REQUEST_BYTES, 'INVALID_P2U_CONTRACT')
    require(_ID.fullmatch(req.conversation_id) and _ID.fullmatch(req.volume_id), 'INVALID_SCOPE')
    require(2 <= len(req.windows) <= MAX_WINDOWS and
            2 <= req.min_motion_windows <= MAX_WINDOWS and
            2 <= req.min_stationary_windows <= MAX_WINDOWS and
            1 <= req.dynamic_hold_ticks <= 1_000_000 and
            1 <= req.max_object_gap_ticks <= 1_000_000,
            'INVALID_P2U_POLICY')
    require(req.min_motion_windows <= len(req.windows) and
            req.min_stationary_windows <= len(req.windows), 'IMPOSSIBLE_P2U_POLICY')

    scene_id = None
    grid_spec = None
    last_eval = 0
    seen_capture = {}  # id -> immutable capture content and tick
    seen_frame = {}  # (source,digest) -> capture id to prevent re-labeling/replay
    used_motion_links = set()
    object_motion_windows = defaultdict(set)
    object_links = defaultdict(list)
    object_seen = {}
    last_dynamic = {}
    streak = {}
    last_cells = {}
    last_output = None
    result_hashes = []
    cells_union = set()
    last_fresh_dynamic = set()

    for wi, window in enumerate(req.windows):
        require(window.conversation_id == req.conversation_id and
                window.volume_id == req.volume_id and
                window.research_only and not window.grants_authority,
                'CROSS_SCOPE_P2T_WINDOW')
        temporal = window.temporal_request
        evaluation = temporal.evaluation_tick
        require(evaluation > last_eval, 'NONMONOTONIC_WINDOW_TICK')
        last_eval = evaluation
        require(scene_id is None or window.scene.scene_id == scene_id, 'SCENE_ID_CHANGED')
        scene_id = window.scene.scene_id
        require(bool(temporal.captures), 'EMPTY_TEMPORAL_WINDOW')
        first = temporal.captures[0].depth
        spec = (first.voxel_size_m, first.max_axis)
        require(grid_spec is None or spec == grid_spec, 'VOXEL_GRID_CHANGED')
        grid_spec = spec
        new_captures = 0
        new_capture_ids = set()
        for capture in temporal.captures:
            depth = capture.depth
            ident = (depth.capture_id, _sha(capture))
            frame = depth.pixels[0]
            frame_id = (frame.source_ref, bytes(frame.depth_frame_sha256))
            record = (frame.tick, ident[1], frame_id)
            if depth.capture_id in seen_capture:
                require(seen_capture[depth.capture_id] == record, 'CAPTURE_REDEFINED')
            else:
                require(frame_id not in seen_frame, 'FRAME_RELABELED_OR_REPLAYED')
                seen_capture[depth.capture_id] = record
                seen_frame[frame_id] = depth.capture_id
                new_captures += 1
                new_capture_ids.add(depth.capture_id)
        require(new_captures > 0, 'WINDOW_WITH_NO_NEW_CAPTURE')
        try:
            output = _evaluate_window(window)
        except ObjectAwareVolumeRejected as exc:
            raise DynamicSceneRejected('INVALID_P2T_WINDOW:' + str(exc)) from exc
        # P2T deliberately does not expose the P2S provenance fields.
        # Re-evaluate that bounded request for per-cell freshness instead of
        # treating overlapping-window observations as independent support.
        try:
            per_capture = _reconcile_temporal(temporal)
        except TemporalConsistencyRejected as exc:
            raise DynamicSceneRejected('INVALID_CELL_PROVENANCE:' + str(exc)) from exc
        fresh_cells = {(_coord(c)) for c in per_capture.cells if any(
            e.capture_id in new_capture_ids for e in c.provenance)}
        result_hashes.append(_sha(output))
        current = {_coord(c): c for c in output.cells}
        require(len(current) == len(output.cells), 'DUPLICATE_P2T_CELL')
        cells_union.update(current)
        require(len(cells_union) <= MAX_CELLS, 'P2U_CELL_RESOURCE_LIMIT')
        last_cells = current
        last_output = output
        # A recent link in a repeated sliding window is NOT fresh evidence.
        fresh_dynamic = set()
        for link in output.motion_candidates:
            key = (link.object_id,link.origin_capture_id,link.destination_capture_id,
                   link.origin_tick,link.destination_tick,link.origin_x,link.origin_y,
                   link.origin_z,link.destination_x,link.destination_y,link.destination_z)
            if key in used_motion_links or link.destination_capture_id not in new_capture_ids:
                continue
            used_motion_links.add(key)
            object_motion_windows[link.object_id].add(wi)
            object_links[link.object_id].append(link)
            for cell in ((link.origin_x,link.origin_y,link.origin_z),
                         (link.destination_x,link.destination_y,link.destination_z)):
                last_dynamic[cell] = max(last_dynamic.get(cell,0), link.destination_tick)
                fresh_dynamic.add(cell)
        last_fresh_dynamic = fresh_dynamic
        # Snapshot ID visibility is not a motion confirmation. Track last bound
        # sample tick only, as a claimant-provided freshness hint.
        for tr in window.tracks:
            require(tr.object_id not in object_seen or
                    tr.samples[-1].tick >= object_seen[tr.object_id],
                    'OBJECT_ID_REWOUND')
            object_seen[tr.object_id] = tr.samples[-1].tick
        require(len(object_seen) <= MAX_OBJECTS, 'P2U_OBJECT_RESOURCE_LIMIT')
        next_streak = {}
        for coord, cell in current.items():
            if cell.static_handoff_allowed and coord not in fresh_dynamic and coord in fresh_cells:
                next_streak[coord] = streak.get(coord,0) + 1
        streak = next_streak
    assert last_output is not None
    output = pb.P2UDynamicSceneResult(schema_version=1, conversation_id=req.conversation_id,
           volume_id=req.volume_id, request_sha256=_sha(req), research_only=True,
           grants_authority=False, unique_capture_count=len(seen_capture))
    output.p2t_result_sha256.extend(result_hashes)
    for obj in sorted(object_seen):
        links = object_links.get(obj, [])
        nwin = len(object_motion_windows[obj])
        last_seen = object_seen[obj]
        age = last_eval - last_seen
        require(age >= 0, 'OBJECT_SAMPLE_IN_FUTURE')
        if age > 2 * req.max_object_gap_ticks:
            state = pb.P2U_RETIRED
        elif age > req.max_object_gap_ticks:
            state = pb.P2U_DORMANT
        elif nwin >= req.min_motion_windows:
            state = pb.P2U_PERSISTENT
        else:
            state = pb.P2U_TENTATIVE
        ts = [x.destination_tick for x in links]
        r = output.objects.add(object_id=obj, state=state, distinct_motion_windows=nwin,
                   distinct_motion_links=len(links), last_seen_tick=last_seen,
                   first_motion_tick=min(ts) if ts else 0,
                   last_motion_tick=max(ts) if ts else 0)
        r.destination_capture_ids.extend(sorted({x.destination_capture_id for x in links}))
    stationary = vpb.VolumeGrid()
    stationary.CopyFrom(last_output.stationary_hypothetical_volume)
    allowed = set()
    for coord in sorted(cells_union):
        cell = last_cells.get(coord)
        latest_state = cell.explanation if cell is not None else tpb.P2T_UNRESOLVED
        last_motion = last_dynamic.get(coord,0)
        hold = bool(last_motion and last_eval - last_motion <= req.dynamic_hold_ticks)
        contested = latest_state == tpb.P2T_MULTIPLE_OBJECTS
        if contested:
            state = pb.P2U_CONTESTED
        elif coord in last_fresh_dynamic:
            state = pb.P2U_DYNAMIC_HYPOTHESIS
        elif hold:
            state = pb.P2U_RECENTLY_DYNAMIC
        elif cell is not None and cell.static_handoff_allowed and streak.get(coord,0) >= req.min_stationary_windows:
            state = pb.P2U_STATIC_HYPOTHESIS
            allowed.add(coord)
        else:
            state = pb.P2U_UNKNOWN
        owners = sorted({link.object_id for links in object_links.values() for link in links
                         if coord in ((link.origin_x,link.origin_y,link.origin_z),
                                      (link.destination_x,link.destination_y,link.destination_z))})
        record = output.cells.add(x=coord[0],y=coord[1],z=coord[2],state=state,
                       consecutive_static_windows=streak.get(coord,0),
                       last_dynamic_tick=last_motion,
                       static_handoff_allowed=coord in allowed)
        record.candidate_object_ids.extend(owners)
    kept = [e for e in stationary.evidence if _coord(e) in allowed]
    stationary.ClearField('evidence')
    stationary.evidence.extend(kept)
    require(all(e.kind in (vpb.VOLUME_PREDICTED_FREE,vpb.VOLUME_PREDICTED_OCCUPIED)
                for e in stationary.evidence), 'NONPREDICTIVE_STATIONARY_EVIDENCE')
    try:
        classified = classify_volume(stationary)
    except VolumeRejected as exc:
        raise DynamicSceneRejected('INVALID_STATIC_VOLUME:' + str(exc)) from exc
    require(all(c.state == vpb.CELL_UNKNOWN for c in classified.cells), 'ILLEGAL_MEASUREMENT_PROMOTION')
    output.stationary_hypothetical_volume.CopyFrom(stationary)
    output.warnings.extend([
       'CALLER_SUPPLIED_OBJECT_IDS_ARE_NOT_AUTHENTICATED',
       'CAPTURE_HASHES_DETECT_REPLAY_TAMPERING_NOT_SENSOR_ATTESTATION',
       'PERSISTENT_MEANS_REPEATED_MOTION_CANDIDATES_NOT_PROVEN_IDENTITY',
       'DYNAMIC_STATIC_LABELS_ARE_RESEARCH_HYPOTHESES_NOT_PHYSICAL_FACTS',
       'STATIC_PREDICTIONS_ARE_NOT_SAFE_SPACE_OR_NAVIGATION_AUTHORITY',
       'NO_CANONICAL_MAP_SCENE_OR_HOST_STATE_MUTATION'])
    return output

def verify(req: pb.P2UDynamicSceneRequest, result: pb.P2UDynamicSceneResult) -> bool:
    require(isinstance(result,pb.P2UDynamicSceneResult) and _known(result) and
            result.SerializeToString(deterministic=True) ==
            map_scene(req).SerializeToString(deterministic=True), 'P2U_REPLAY_MISMATCH')
    return True


def map_scene(req: pb.P2UDynamicSceneRequest) -> pb.P2UDynamicSceneResult:
    """Original independent, full-replay public evaluator."""
    return _map_scene(req)
