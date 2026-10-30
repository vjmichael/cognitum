"""C15 T3 P2W: bounded state-delta merge over *verified* P2V snapshots.

This adapter does not incrementally evaluate P2V, attest sensor inputs, mutate
canonical scene state, or supply navigation authority. Checkpoint SHA-256 is an
integrity checksum, NOT a signature. Consumers must anchor checkpoint digests
in a separately authenticated host journal before relying on continuity.
"""
from __future__ import annotations

import hashlib
import re
from cognitum.proto import spatial_map_lifecycle_pb2 as pb
from cognitum.proto import spatial_dynamic_scene_robustness_pb2 as vp
from cognitum.proto import spatial_volume_pb2 as volume_pb
from cognitum.spatial_dynamic_scene_robustness import verify as p2v_verify, RobustnessRejected
from cognitum.spatial_volume import classify, VolumeRejected

_SCOPE = re.compile(r'^[a-zA-Z0-9_.:-]{1,128}$')
MAX_REQUEST_BYTES = 15_000_000
MAX_STATE_BYTES = 3_000_000
MAX_CELLS = 4096
MAX_OBJECTS = 128

class LifecycleRejected(ValueError):
    pass

def _check(ok: bool, why: str) -> None:
    if not ok:
        raise LifecycleRejected(why)

def _digest(message):
    return hashlib.sha256(message.SerializeToString(deterministic=True)).digest()

def _known(message):
    clean = type(message)()
    clean.CopyFrom(message)
    clean.DiscardUnknownFields()
    return clean.SerializeToString(deterministic=True) == message.SerializeToString(deterministic=True)

def checkpoint_digest(state: pb.P2WCheckpoint) -> bytes:
    tmp = pb.P2WCheckpoint()
    tmp.CopyFrom(state)
    tmp.checkpoint_sha256 = b''
    return _digest(tmp)

def _check_checkpoint(state):
    _check(state.schema_version == 1 and state.research_only and not state.grants_authority
           and _known(state) and state.ByteSize() <= MAX_STATE_BYTES
           and bool(_SCOPE.fullmatch(state.conversation_id))
           and bool(_SCOPE.fullmatch(state.volume_id)), 'INVALID_PREVIOUS_CHECKPOINT')
    _check(state.sequence >= 1 and state.last_evaluation_tick >= state.max_capture_tick > 0
           and len(state.source_result_sha256) == 32
           and (len(state.prior_checkpoint_sha256) == 32 if state.sequence > 1
                else len(state.prior_checkpoint_sha256) == 0)
           and len(state.checkpoint_sha256) == 32
           and checkpoint_digest(state) == state.checkpoint_sha256,
           'CHECKPOINT_INTEGRITY_FAILURE')
    _check(len(state.cells) <= MAX_CELLS and len(state.objects) <= MAX_OBJECTS,
           'PREVIOUS_RESOURCE_LIMIT')
    coords = [(x.x,x.y,x.z) for x in state.cells]
    objects = [x.object_id for x in state.objects]
    _check(coords == sorted(set(coords)) and objects == sorted(set(objects)),
           'NONCANONICAL_CHECKPOINT')
    _check(all(x.last_support_tick <= state.last_evaluation_tick and x.last_support_tick > 0
               for x in state.cells) and
           all(x.last_observed_tick <= state.last_evaluation_tick and x.last_observed_tick > 0
               and not x.authenticated and bool(_SCOPE.fullmatch(x.object_id)) for x in state.objects),
           'INVALID_CHECKPOINT_RECORD')
    static = {(e.x,e.y,e.z) for e in state.current_stationary_hypothetical_volume.evidence}
    active = {(x.x,x.y,x.z) for x in state.cells if x.retained_now}
    _check(static == active and len(static)==len(state.current_stationary_hypothetical_volume.evidence),
           'CHECKPOINT_STATIC_MISMATCH')
    _validate_volume(state.current_stationary_hypothetical_volume)

def _validate_volume(grid):
    _check(grid.research_only and not grid.grants_authority and _known(grid)
           and all(e.kind in (volume_pb.VOLUME_PREDICTED_OCCUPIED,volume_pb.VOLUME_PREDICTED_FREE)
                   for e in grid.evidence), 'UNAUTHORIZED_MAP_EVIDENCE')
    try:
        audited = classify(grid)
    except VolumeRejected as exc:
        raise LifecycleRejected('INVALID_VOLUME:' + str(exc)) from exc
    _check(all(c.state == volume_pb.CELL_UNKNOWN for c in audited.cells),
           'MAP_MEASUREMENT_PROMOTION')

def _validate_request(req: pb.P2WUpdateRequest) -> None:
    _check(isinstance(req,pb.P2WUpdateRequest) and req.schema_version == 1
           and req.research_only and not req.grants_authority and _known(req)
           and req.ByteSize() <= MAX_REQUEST_BYTES, 'INVALID_P2W_CONTRACT')
    _check(1 <= req.max_resident_cells <= MAX_CELLS
           and 1 <= req.max_resident_objects <= MAX_OBJECTS
           and 1 <= req.max_idle_ticks <= 10_000_000 and req.sequence >= 1,
           'INVALID_P2W_BUDGET')

def advance(req: pb.P2WUpdateRequest) -> pb.P2WUpdateResult:
    """Verify entire upstream P2V snapshot, then incrementally merge its metadata.

    The expensive P2V evaluation still runs in full. Only this metadata merge
    has bounded O(previous + snapshot) work and a capped resident state.
    """
    _validate_request(req)
    try:
        p2v_verify(req.source_request, req.source_result)
    except RobustnessRejected as exc:
        raise LifecycleRejected('UNVERIFIED_UPSTREAM_P2V:' + str(exc)) from exc
    return _merge_preverified(req)

def _merge_preverified(req: pb.P2WUpdateRequest) -> pb.P2WUpdateResult:
    """Internal profiling primitive; caller MUST verify P2V beforehand.

    Not a host endpoint or authorization bypass. Public callers use advance().
    """
    source = req.source_result
    _check(source.research_only and not source.grants_authority
           and bool(_SCOPE.fullmatch(source.conversation_id))
           and bool(_SCOPE.fullmatch(source.volume_id)), 'INVALID_P2V_SCOPE')
    _validate_volume(source.conservative_static_hypothetical_volume)
    evaluated = req.source_request.dynamic_request.windows[-1].temporal_request.evaluation_tick
    _check(len(source.cameras) > 0 and len(source.cells) <= MAX_CELLS
           and len(source.identities) <= MAX_OBJECTS, 'UPSTREAM_RESOURCE_LIMIT')
    newest_capture = max(x.tick for x in source.cameras)
    _check(newest_capture <= evaluated, 'CAPTURE_AHEAD_OF_EVALUATION')
    previous = req.previous if req.HasField('previous') else None
    if previous is not None:
        _check_checkpoint(previous)
        _check(req.sequence == previous.sequence + 1
               and source.conversation_id == previous.conversation_id
               and source.volume_id == previous.volume_id,
               'SEQUENCE_OR_SCOPE_MISMATCH')
        _check(evaluated > previous.last_evaluation_tick
               and newest_capture > previous.max_capture_tick,
               'STALE_OR_REPLAYED_UPDATE')
    else:
        _check(req.sequence == 1, 'MISSING_PREDECESSOR')
    result = pb.P2WUpdateResult(schema_version=1,request_sha256=_digest(req),
                                 verified_p2v_sha256=_digest(source),
                                 upstream_replay_verified=True,research_only=True)
    state = result.checkpoint
    state.schema_version=1
    state.conversation_id=source.conversation_id
    state.volume_id=source.volume_id
    state.sequence=req.sequence
    state.last_evaluation_tick=evaluated
    state.max_capture_tick=newest_capture
    state.source_result_sha256=result.verified_p2v_sha256
    state.research_only=True
    if previous is not None:
        state.prior_checkpoint_sha256=previous.checkpoint_sha256
    # Merge unique voxel keys, but a prior static prediction is NEVER assumed
    # eligible in a later snapshot that omits or disputes the cell.
    prev_cells = {(c.x,c.y,c.z):c for c in previous.cells} if previous else {}
    current = {(c.x,c.y,c.z):c for c in source.cells}
    _check(len(current) == len(source.cells),'DUPLICATE_P2V_CELLS')
    evidence = {(e.x,e.y,e.z):e for e in source.conservative_static_hypothetical_volume.evidence}
    _check(len(evidence) == len(source.conservative_static_hypothetical_volume.evidence)
           and all(k in current and current[k].retained for k in evidence),
           'INVALID_STATIC_EVIDENCE_BINDING')
    result.input_cell_count=len(current)
    merged = {}
    for key in prev_cells.keys() | current.keys():
        old = prev_cells.get(key)
        cur = current.get(key)
        tick = max(old.last_support_tick if old else 0,cur.latest_support_tick if cur else 0)
        if not tick or tick > evaluated:
            continue
        if evaluated-tick > req.max_idle_ticks:
            result.evicted_cells.add(x=key[0],y=key[1],z=key[2],reason=pb.P2W_IDLE_EXPIRED)
            continue
        # A previously qualified voxel cannot stay qualified without an
        # identical, fresh, latest P2V retained evidence claim.
        eligible = bool(cur and cur.retained and key in evidence
                        and cur.latest_support_tick == tick)
        merged[key]=(tick,eligible)
    survivors = sorted(merged,key=lambda key:(not merged[key][1],-merged[key][0],key))
    keep = set(survivors[:req.max_resident_cells])
    for key in sorted(set(merged)-keep):
        result.evicted_cells.add(x=key[0],y=key[1],z=key[2],reason=pb.P2W_CAPACITY_LIMIT)
    for key in sorted(keep):
        tick,eligible=merged[key]
        state.cells.add(x=key[0],y=key[1],z=key[2],last_support_tick=tick,retained_now=eligible)
    vol = state.current_stationary_hypothetical_volume
    vol.CopyFrom(source.conservative_static_hypothetical_volume)
    retained_evidence=[e for e in vol.evidence if (e.x,e.y,e.z) in keep and merged[(e.x,e.y,e.z)][1]]
    vol.ClearField('evidence')
    vol.evidence.extend(retained_evidence)
    _validate_volume(vol)
    result.current_static_evidence_count=len(vol.evidence)
    # Object identity is caller-asserted; snapshot handles only bounded cache
    # lifetimes, never authenticates or extrapolates missing observations.
    prev_obj = {o.object_id:o for o in previous.objects} if previous else {}
    cur_obj = {o.object_id:o for o in source.identities}
    _check(len(cur_obj)==len(source.identities),'DUPLICATE_P2V_OBJECT')
    result.input_object_count=len(cur_obj)
    object_records={}
    for ident in prev_obj.keys() | cur_obj.keys():
        old=prev_obj.get(ident)
        cur=cur_obj.get(ident)
        tick=max(old.last_observed_tick if old else 0,cur.last_observed_tick if cur else 0)
        if tick == 0 or tick > evaluated:
            continue
        if evaluated-tick > req.max_idle_ticks:
            result.evicted_objects.add(object_id=ident,reason=pb.P2W_IDLE_EXPIRED)
            continue
        state_code = cur.state if cur and cur.last_observed_tick >= (old.last_observed_tick if old else 0) else old.last_state
        object_records[ident]=(tick,state_code)
    object_order=sorted(object_records,key=lambda ident:(-object_records[ident][0],ident))
    object_keep=set(object_order[:req.max_resident_objects])
    for ident in sorted(set(object_records)-object_keep):
        result.evicted_objects.add(object_id=ident,reason=pb.P2W_CAPACITY_LIMIT)
    for ident in sorted(object_keep):
        tick,code=object_records[ident]
        state.objects.add(object_id=ident,last_observed_tick=tick,last_state=code,authenticated=False)
    result.output_cell_count=len(state.cells)
    result.output_object_count=len(state.objects)
    state.checkpoint_sha256=checkpoint_digest(state)
    _check(state.ByteSize() <= MAX_STATE_BYTES, 'CHECKPOINT_BYTE_LIMIT')
    result.warnings.extend([
        'INCREMENTAL_ONLY_FOR_P2W_STATE_MERGE_P2V_REPLAY_IS_FULL',
        'CHECKPOINT_DIGEST_IS_NOT_AN_AUTHENTICATED_HOST_JOURNAL',
        'EVICTED_HISTORY_IS_NOT_AVAILABLE_FOR_FUTURE_INFERENCE',
        'STATIC_HYPOTHESES_NOT_MEASUREMENTS_OR_NAVIGATION_AUTHORITY',
        'NO_LU_OR_CANONICAL_SCENE_STATE_MUTATION'])
    return result

def verify(req: pb.P2WUpdateRequest, result: pb.P2WUpdateResult) -> bool:
    _check(isinstance(result,pb.P2WUpdateResult) and _known(result) and
           result.SerializeToString(deterministic=True) ==
           advance(req).SerializeToString(deterministic=True),'P2W_REPLAY_MISMATCH')
    return True
