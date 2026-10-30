"""C15 P1 deterministic, in-memory, PROTOBUF-native scene-graph reference.

No camera ingest, perception, file writes, Lu authority, or autonomous action.
A caller-supplied admit callback is a TEST SEAM; it is NOT a trusted host by
itself. Frame conventions are right-handed, metres, child-to-parent SE(3).
"""
from __future__ import annotations
import hashlib
import math
import re
from google.protobuf.message import Message
from cognitum.proto import spatial_scene_pb2 as p

_ID = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,63}\Z")
MAX_COMMAND_BYTES = 65536
MAX_FRAMES = 64
MAX_OBJECTS = 96
MAX_MUTATIONS = 32
MAX_REQUEST_IDS = 2048
MAX_DERIVED_RELATIONS = 8192
NEAR_METRES = 1.0
POSITION_EPSILON = 0.000001

class SceneRejected(ValueError):
    pass


def require(cond: bool, code: str):
    if not cond:
        raise SceneRejected(code)


def sha(obj: Message) -> bytes:
    return hashlib.sha256(obj.SerializeToString(deterministic=True)).digest()


def _good_id(s: str) -> bool:
    return _ID.fullmatch(s) is not None


def _text(s: str) -> bool:
    return 0 < len(s) <= 120 and all(ord(c) >= 32 and ord(c) != 127 for c in s)


def _vector(v: p.Vector3):
    coords = (v.x, v.y, v.z)
    require(all(math.isfinite(v) and abs(v) <= 1e9 for v in coords), 'NONFINITE_OR_UNBOUNDED_POSITION')
    return coords


def _quat(q: p.UnitQuaternion):
    v = (q.x, q.y, q.z, q.w)
    require(all(math.isfinite(c) for c in v) and abs(sum(c*c for c in v)-1.0) <= 1e-6,
            'INVALID_OR_UNNORMALIZED_QUATERNION')
    return v


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _rotate(v, quat):
    x,y,z,w=quat
    uv = _cross((x,y,z),v)
    uuv = _cross((x,y,z),uv)
    return tuple(v[i]+2*w*uv[i]+2*uuv[i] for i in range(3))


def _qmul(a,b):
    ax,ay,az,aw=a;bx,by,bz,bw=b
    return (aw*bx+ax*bw+ay*bz-az*by,
            aw*by-ax*bz+ay*bw+az*bx,
            aw*bz+ax*by-ay*bx+az*bw,
            aw*bw-ax*bx-ay*by-az*bz)


def world_pose(obj, frames):
    """Return (position_m, quaternion_xyzw) in the canonical world frame."""
    position=_vector(obj.position_m)
    orientation=_quat(obj.rotation_xyzw)
    frame_id=obj.frame_id
    visited=set()
    while frame_id!='world':
        require(frame_id in frames and frame_id not in visited, 'UNREGISTERED_OR_CYCLIC_FRAME')
        visited.add(frame_id);f=frames[frame_id]
        offset=_vector(f.translation_m);q=_quat(f.rotation_xyzw)
        position=tuple(x+y for x,y in zip(_rotate(position,q),offset))
        orientation=_qmul(q,orientation)
        frame_id=f.parent_frame_id
    return position,orientation


def _world_position(frame_id, point, frames):
    visited=set()
    while frame_id != 'world':
        require(frame_id in frames and frame_id not in visited, 'UNREGISTERED_OR_CYCLIC_FRAME')
        visited.add(frame_id)
        f=frames[frame_id]
        offset=_vector(f.translation_m)
        point=tuple(x+y for x,y in zip(_rotate(point, _quat(f.rotation_xyzw)),offset))
        frame_id=f.parent_frame_id
    return point


def _validate_object(o, frames):
    require(_good_id(o.object_id) and _text(o.category) and _text(o.display_name), 'INVALID_OBJECT_ID_OR_LABEL')
    require(o.frame_id == 'world' or o.frame_id in frames, 'UNKNOWN_OBJECT_FRAME')
    require(o.HasField('position_m') and o.HasField('rotation_xyzw'), 'MISSING_POSE')
    _vector(o.position_m); _quat(o.rotation_xyzw)
    require(o.visibility==p.VISIBILITY_VISIBLE, 'OBSERVATION_NOT_VISIBLE')
    require(math.isfinite(o.confidence) and 0.0 <= o.confidence <= 1.0, 'INVALID_CONFIDENCE')
    require(o.version == 0 and o.last_observed_tick > 0, 'CALLER_SUPPLIED_VERSION_OR_MISSING_TICK')
    require(_good_id(o.observation_source_id), 'MISSING_OBSERVATION_PROVENANCE')
    require(len(o.geometry_ref) <= 256, 'GEOMETRY_REFERENCE_TOO_LONG')
    require(len(o.aliases) <= 16 and all(_text(a) for a in o.aliases), 'INVALID_ALIASES')
    require(len(set(o.aliases))==len(o.aliases), 'DUPLICATE_ALIASES')


def _check_command(before, command):
    require(isinstance(command,p.SceneCommand) and command.schema_version==1, 'INVALID_COMMAND_SCHEMA')
    require(all(_good_id(x) for x in (command.scene_id, command.conversation_id,
        command.trace_id,command.task_id,command.request_id)), 'INVALID_SCOPE')
    require(len(command.SerializeToString()) <= MAX_COMMAND_BYTES, 'COMMAND_TOO_LARGE')
    require(len(command.add_frames) <= 16 and len(command.mutations) <= MAX_MUTATIONS
            and (command.add_frames or command.mutations), 'INVALID_BATCH_SIZE')
    if before is None:
        require(command.expected_scene_revision==0, 'BAD_INITIAL_REVISION')
    else:
        require(isinstance(before,p.SceneSnapshot) and before.schema_version==1
                and before.research_only and before.scene_id==command.scene_id
                and before.conversation_id==command.conversation_id,'SCENE_SCOPE_MISMATCH')
        require(command.request_id not in before.processed_request_ids, 'REPLAYED_REQUEST_ID')
        require(command.expected_scene_revision == before.revision, 'STALE_SCENE_REVISION')
        require(len(before.processed_request_ids)<MAX_REQUEST_IDS, 'REPLAY_JOURNAL_LIMIT')


def _admit(admit, command, action, target):
    # Boundary is deliberately external; accepting a test callback doesn't certify a host.
    try:
        approved=admit(command.scene_id,command.conversation_id,command.task_id,action,target)
    except Exception as exc:
        raise SceneRejected('HOST_ADMISSION_FAILED') from exc
    require(approved is True, 'HOST_ADMISSION_DENIED')


def apply(before: p.SceneSnapshot | None, command: p.SceneCommand, *, admit=None):
    """Atomic pure transition; raises with no mutation of ``before`` on any error."""
    _check_command(before,command)
    require(callable(admit), 'HOST_ADMISSION_REQUIRED')
    if before is None:
        _admit(admit,command,'scene.create',command.scene_id)
        state=p.SceneSnapshot(schema_version=1,scene_id=command.scene_id,
            conversation_id=command.conversation_id,revision=0,research_only=True)
    else:
        state=p.SceneSnapshot();state.CopyFrom(before)
    frames={f.frame_id:f for f in state.frames}
    require(len(frames)==len(state.frames), 'DUPLICATE_STORED_FRAMES')
    objects={o.object_id:o for o in state.objects}
    require(len(objects)==len(state.objects),'DUPLICATE_STORED_OBJECTS')
    # Build in local tables; input state will never be modified even if any step fails.
    for f in command.add_frames:
        _admit(admit,command,'frame.add',f.frame_id)
        require(_good_id(f.frame_id) and f.frame_id!='world' and
                (f.parent_frame_id=='world' or _good_id(f.parent_frame_id)), 'INVALID_FRAME_NAME')
        require(f.frame_id not in frames and f.parent_frame_id!=f.frame_id,
                'REPLACED_OR_SELF_PARENT_FRAME')
        require(f.parent_frame_id=='world' or f.parent_frame_id in frames,
                'UNKNOWN_PARENT_FRAME')
        require(f.HasField('translation_m') and f.HasField('rotation_xyzw'), 'MISSING_FRAME_POSE')
        _vector(f.translation_m);_quat(f.rotation_xyzw)
        frames[f.frame_id]=f
    require(len(frames)<=MAX_FRAMES,'FRAME_LIMIT_EXCEEDED')
    for m in command.mutations:
        require(_good_id(m.object_id) and m.kind in
            (p.MUTATION_OBSERVE,p.MUTATION_OCCLUDE,p.MUTATION_OUT_OF_FRAME,
             p.MUTATION_RENAME,p.MUTATION_DELETE), 'INVALID_MUTATION')
        _admit(admit,command,'object.'+p.MutationKind.Name(m.kind).lower(),m.object_id)
        old=objects.get(m.object_id)
        require((old is not None and m.expected_object_version==old.version) or
                (old is None and m.kind==p.MUTATION_OBSERVE and m.expected_object_version==0),
                'UNKNOWN_ID_OR_STALE_OBJECT_VERSION')
        if m.kind==p.MUTATION_OBSERVE:
            require(m.HasField('observed') and not m.new_display_name,
                    'OBSERVATION_PAYLOAD_REQUIRED')
            o=p.SceneObject();o.CopyFrom(m.observed)
            require(o.object_id==m.object_id and o.last_observed_tick==m.tick,
                    'OBSERVATION_ID_OR_TICK_MISMATCH')
            _validate_object(o,frames)
            if old is not None:
                require(old.visibility != p.VISIBILITY_DELETED,'DELETED_ID_CANNOT_REAPPEAR')
                require(m.tick>old.last_observed_tick, 'NONMONOTONIC_OBSERVATION')
                require(o.category==old.category and
                        o.observation_source_id==old.observation_source_id,
                        'IDENTITY_SOURCE_OR_CATEGORY_SWITCH')
                o.version=old.version+1
                # Do not delete historical aliases on re-observation.
                o.aliases[:]=list(dict.fromkeys([*old.aliases,*o.aliases]))
                require(len(o.aliases)<=16,'ALIAS_LIMIT_EXCEEDED')
            else:
                o.version=1
            objects[m.object_id]=o
        else:
            require(old is not None and not m.HasField('observed'), 'UNEXPECTED_OBSERVATION_PAYLOAD')
            require(m.tick>=old.last_observed_tick,'EVENT_PRECEDES_LAST_OBSERVATION')
            require(old.visibility!=p.VISIBILITY_DELETED, 'DELETED_OBJECT_IMMUTABLE')
            o=p.SceneObject();o.CopyFrom(old)
            if m.kind==p.MUTATION_RENAME:
                require(_text(m.new_display_name),'INVALID_RENAME')
                if o.display_name!=m.new_display_name:
                    aliases=list(dict.fromkeys([*o.aliases,o.display_name]))
                    require(len(aliases)<=16,'ALIAS_LIMIT_EXCEEDED')
                    o.aliases[:]=aliases
                    o.display_name=m.new_display_name
            else:
                require(not m.new_display_name,'INAPPLICABLE_RENAME_FIELD')
                o.visibility={p.MUTATION_OCCLUDE:p.VISIBILITY_OCCLUDED,
                              p.MUTATION_OUT_OF_FRAME:p.VISIBILITY_OUT_OF_FRAME,
                              p.MUTATION_DELETE:p.VISIBILITY_DELETED}[m.kind]
            o.version+=1
            objects[m.object_id]=o
    require(len(objects)<=MAX_OBJECTS,'OBJECT_LIMIT_EXCEEDED')
    # Derived relations are only for currently visible objects. No inferred identity.
    world={o.object_id:_world_position(o.frame_id,_vector(o.position_m),frames)
           for o in objects.values() if o.visibility==p.VISIBILITY_VISIBLE}
    del state.frames[:];state.frames.extend(frames[k] for k in sorted(frames))
    del state.objects[:];state.objects.extend(objects[k] for k in sorted(objects))
    del state.relations[:]
    for source in sorted(world):
        for target in sorted(world):
            if source==target:continue
            v=tuple(world[target][i]-world[source][i] for i in range(3))
            distance=math.sqrt(sum(c*c for c in v))
            if distance<=NEAR_METRES:
                state.relations.add(source_id=source,target_id=target,
                    kind=p.RELATION_NEAR_3D,distance_m=distance,
                    calculation_frame_id='world')
            if v[0] > POSITION_EPSILON:
                state.relations.add(source_id=source,target_id=target,
                    kind=p.RELATION_LEFT_OF_WORLD_X,distance_m=distance,
                    calculation_frame_id='world')
            elif v[0] < -POSITION_EPSILON:
                state.relations.add(source_id=source,target_id=target,
                    kind=p.RELATION_RIGHT_OF_WORLD_X,distance_m=distance,
                    calculation_frame_id='world')
    require(len(state.relations)<=MAX_DERIVED_RELATIONS, 'RELATION_LIMIT_EXCEEDED')
    state.revision+=1
    state.processed_request_ids.append(command.request_id)
    receipt=p.SceneReceipt(request_sha256=sha(command),
        before_sha256=sha(before) if before is not None else hashlib.sha256(b'INITIAL').digest(),
        after_sha256=sha(state),research_only=True, trace_id=command.trace_id,
        conversation_id=command.conversation_id,task_id=command.task_id,
        request_id=command.request_id)
    return state, receipt


def verify_receipt(before,command,after,receipt,*,admit=None):
    """Replay under supplied policy stub; confirms deterministic structure, NOT host identity."""
    if not isinstance(after,p.SceneSnapshot) or not isinstance(receipt,p.SceneReceipt):
        return False
    try:
        expected, rec=apply(before,command,admit=admit)
        return (after.SerializeToString(deterministic=True)==expected.SerializeToString(deterministic=True)
                and receipt.SerializeToString(deterministic=True)==rec.SerializeToString(deterministic=True))
    except (SceneRejected,ValueError,TypeError):
        return False
