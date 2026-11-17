"""Opt-in C15 confidence-aware ByteTrack sequence reference adapter.

The host owns the observation history, namespace and admission. No hidden
persistent state, implicit backend switching, model-selected imports or scene
mutation. Replay from the same source prefix is the only supported continuation.
Run under host custody for untrusted inputs; Python checks are not OS isolation.
"""
from dataclasses import asdict, dataclass
from hashlib import sha1
from importlib.metadata import distribution, version, PackageNotFoundError
from math import isfinite
from pathlib import Path
from time import monotonic
import re

from .contracts import HostContext, digest
from .spatial_tracking import (Detection, Track, TrackUpdate, validate, MAX_TRACKS,
                               MAX_DETECTIONS)

VERSION="2.6.1"
UPSTREAM="3666546420b0fd564c8e63157a6621efffdfa01a"
WHEEL_SHA256="b5188de630f449958be3ce787fbb0375c69cfde094b6e4b4329cd79a98108501"
BACKEND="c15.bytetrack.2.6.1.fixed.v1"
MAX_FRAMES=512
MAX_OBSERVATIONS=MAX_FRAMES*MAX_DETECTIONS
MAX_MS=30000
MAX_MISSED=4
CONFIG={"lost_track_buffer":MAX_MISSED,"frame_rate":30.,
        "track_activation_threshold":.7,"minimum_consecutive_frames":2,
        "minimum_iou_threshold":.1,"high_conf_det_threshold":.6}
BLOBS={
    "core/base.py":"070703180ead001a39751982bf72a505305f254b",
    "core/bytetrack/__init__.py":"57226e8851e3d327e91a943834ef19275c47ee88",
    "core/bytetrack/tracker.py":"158c31be2186813fb16fbc549cb380cf1af9f8cc",
    "core/bytetrack/tracklet.py":"5d61f3fd6f3aeaab51f26bf00ab77dc4abf0e706",
    "core/bytetrack/utils.py":"6ef243154ee065f1c05b45b1a99c4102d3df59ab",
    "utils/base_tracklet.py":"f807816a73e28d64daffd6348d7610c4b39c5c50",
    "utils/detections.py":"da26025c13113d3f7cba931796c91c722987efe3",
    "utils/iou.py":"dadd6e0d105661b1080c79084e98b0ff6908bd5b",
    "utils/predict_timing.py":"b14a4938f63a90253f5430194e0b0795b9caa3b0",
    "utils/state_representations.py":"98e833b54135fa243e8bf40bd20d30ac0c3071b6",
}
_ID=re.compile(r"[A-Za-z0-9_.:-]{1,48}\Z",re.ASCII)
_SHA=re.compile(r"[0-9a-f]{64}\Z",re.ASCII)
_BUILD=re.compile(r"[0-9a-f]{40}\Z",re.ASCII)

@dataclass(frozen=True)
class Scope:
    workspace_id:str
    subject_id:str
    sequence_id:str
    build_sha:str

@dataclass(frozen=True)
class Frame:
    number:int
    source_id:str
    source_revision:str
    source_sha256:str
    detections:tuple[Detection,...]
    confidence:tuple[float,...]

@dataclass(frozen=True)
class Admission:
    phase:str
    scope_sha256:str
    request_sha256:str
    frame_number:int=0
    frame_sha256:str=""
    receipt_sha256:str=""

@dataclass(frozen=True)
class FrameResult:
    number:int
    frame_sha256:str
    previous_sha256:str
    update:TrackUpdate
    new_ids:tuple[str,...]
    live_internal_count:int
    receipt_sha256:str

@dataclass(frozen=True)
class ReplaySeal:
    scope_sha256:str
    backend_sha256:str
    frames:int
    receipt_sha256:str

@dataclass(frozen=True)
class Outcome:
    status:str
    request_sha256:str=""
    frame_results:tuple[FrameResult,...]=()
    seal:ReplaySeal|None=None
    limitation:str="host_reference_only_no_durable_or_os_custody"

class _Stop(Exception):
    def __init__(self,status):self.status=status

def _valid_str(x,pattern):
    return type(x) is str and pattern.fullmatch(x) is not None

def _validate(scope,frames,context,expected_build,timeout_ms,resume):
    if (type(scope) is not Scope or type(context) is not HostContext
            or (scope.workspace_id,scope.subject_id)!=(context.workspace_id,context.subject_id)
            or context.allow_research is not False or scope.build_sha!=expected_build):
        raise _Stop("DENIED")
    if (not all(_valid_str(x,_ID) for x in (scope.workspace_id,scope.subject_id,scope.sequence_id))
            or not _valid_str(scope.build_sha,_BUILD)
            or type(timeout_ms) is not int or not 1<=timeout_ms<=MAX_MS
            or type(frames) is not tuple or not 1<=len(frames)<=MAX_FRAMES):
        raise ValueError("invalid bounded sequence")
    for n,frame in enumerate(frames,1):
        if (type(frame) is not Frame or type(frame.number) is not int or frame.number!=n
                or not _valid_str(frame.source_id,_ID) or not _valid_str(frame.source_revision,_ID)
                or not _valid_str(frame.source_sha256,_SHA)
                or type(frame.confidence) is not tuple or len(frame.confidence)!=len(frame.detections)):
            raise ValueError("invalid ordered source frame")
        validate((),frame.detections)
        if (any(d.source!=frame.source_id for d in frame.detections)
                or any(type(x) not in (int,float) or not isfinite(x) or not 0<=x<=1
                       for x in frame.confidence)):
            raise ValueError("invalid source or confidence")
    scope_hash=digest(asdict(scope))
    if resume is not None:
        if (type(resume) is not ReplaySeal or resume.scope_sha256!=scope_hash
                or not _valid_str(resume.backend_sha256,_SHA) or not _valid_str(resume.receipt_sha256,_SHA)
                or type(resume.frames) is not int or not 1<=resume.frames<=len(frames)):
            raise ValueError("invalid replay seal")
    return scope_hash,tuple(digest(asdict(f)) for f in frames)

def _engine():
    # Fixed reviewed distribution; the installation gate separately checks the
    # complete wheel SHA256. Guard known behavior-bearing source files before import.
    try:
        dist=distribution("trackers")
        if dist.version!=VERSION:raise _Stop("UNSUPPORTED")
        for name,expected in BLOBS.items():
            path=Path(dist.locate_file("trackers/"+name))
            if not path.is_file() or path.is_symlink() or path.stat().st_size>1_000_000:
                raise _Stop("UNSUPPORTED")
            raw=path.read_bytes()
            if sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()!=expected:
                raise _Stop("UNSUPPORTED")
        import numpy as np
        import supervision as sv
        from trackers import ByteTrackTracker
        identity=digest({"backend":BACKEND,"commit":UPSTREAM,"wheel":WHEEL_SHA256,
                         "config":dict(CONFIG),"versions":{k:version(k) for k in
                            ("trackers","numpy","scipy","supervision","opencv-python")}})
        return np,sv,ByteTrackTracker(**CONFIG),identity
    except (ImportError,PackageNotFoundError,OSError):
        raise _Stop("UNSUPPORTED")

def _id(namespace,number):
    return "bt_"+namespace[:16]+"_"+str(number)

def _adapt(np,sv,engine,frame,namespace,previous,max_seen):
    ds=frame.detections
    boxes=np.asarray([[d.x,d.y,d.x+d.width,d.y+d.height] for d in ds],dtype=np.float64).reshape(-1,4)
    confidence=np.asarray(frame.confidence,dtype=np.float64)
    raw=sv.Detections(xyxy=boxes.copy(),confidence=confidence.copy(),
                      data={"c15_index":np.arange(len(ds),dtype=np.int64)})
    if len(engine.tracks)>MAX_TRACKS:raise _Stop("RESOURCE_LIMIT")
    out=engine.update(raw)
    if len(engine.tracks)>MAX_TRACKS:raise _Stop("RESOURCE_LIMIT")
    alive=engine.tracked_objects
    if (len(out)!=len(ds) or out.tracker_id is None
            or alive.tracker_id is None or len(alive)>MAX_TRACKS):
        raise ValueError("incomplete tracker partition")
    observed={}
    indices=set()
    if len(ds):
        idx=np.asarray(out.data.get("c15_index"))
        tids=np.asarray(out.tracker_id)
        if (idx.shape!=(len(ds),) or tids.shape!=(len(ds),)
                or idx.dtype.kind not in "iu" or tids.dtype.kind not in "iu"
                or out.confidence is None):
            raise ValueError("invalid tracker output types")
        for i,j,t in zip(range(len(ds)),idx,tids):
            j,t=int(j),int(t)
            if (j in indices or not 0<=j<len(ds) or t< -1
                    or not np.array_equal(out.xyxy[i],boxes[j])
                    or out.confidence[i]!=confidence[j]):
                raise ValueError("tracker modified source observation")
            indices.add(j)
            if t>=0:
                if t in observed:raise ValueError("duplicate matched track")
                observed[t]=j
    if indices!=set(range(len(ds))):raise ValueError("missing observation")
    ids=np.asarray(alive.tracker_id)
    if ids.shape!=(len(alive),) or ids.dtype.kind not in "iu":
        raise ValueError("invalid alive identities")
    live={int(t) for t in ids}
    if (len(live)!=len(alive) or any(t<0 or t>=MAX_OBSERVATIONS for t in live)
            or not set(observed)<=live or not np.isfinite(alive.xyxy).all()):
        raise ValueError("invalid alive track set")
    new=live-set(previous)
    if (not new<=set(observed) or any(t<=max_seen for t in new)
            or any(t<0 for t in observed)):
        raise ValueError("unobserved new or recycled identity")
    result={}
    for t in sorted(live):
        name=_id(namespace,t)
        if t in observed:
            d=ds[observed[t]]
            result[t]=Track(name,d.x,d.y,d.width,d.height,0,d.source)
        else:
            old=previous[t]
            if old.missed>=MAX_MISSED:raise ValueError("expired identity retained")
            result[t]=Track(name,old.x,old.y,old.width,old.height,old.missed+1,old.last_source)
    matches=tuple(sorted((_id(namespace,t),ds[j].detection_id) for t,j in observed.items()))
    used=set(observed.values())
    update=TrackUpdate(tuple(result[t] for t in sorted(result)),matches,
        tuple(d.detection_id for j,d in enumerate(ds) if j not in used),
        tuple(_id(namespace,t) for t in sorted(set(previous)-live)),
        limitations=("caller_supplied_detections_not_authenticated",
            "bytetrack_motion_association_not_physical_identity_proof",
            "unmatched_tracks_are_last_observed_boxes_not_new_observations",
            "sequence_scoped_ids_no_cross_backend_migration"))
    validate(update.tracks,ds)
    return update,tuple(_id(namespace,t) for t in sorted(new)),result,max([max_seen,*live])

def execute(scope,frames,context,*,expected_build_sha,admit,source_current,cancelled,
            timeout_ms=MAX_MS,resume=None):
    """Return complete typed frame results or an empty fail-closed outcome.

    Callbacks must originate in trusted host code. They are not serialized
    grants. Prefix replay seals are digests, not authenticated persistence;
    host must verify ownership/current revision and persist atomically.
    """
    request=""
    try:
        namespace,hashes=_validate(scope,frames,context,expected_build_sha,timeout_ms,resume)
        if not all(callable(x) for x in (admit,source_current,cancelled)):
            raise _Stop("DENIED")
        request=digest({"scope":namespace,"backend":BACKEND,"frames":hashes,
                        "timeout_ms":timeout_ms,"resume":asdict(resume) if resume else None})
    except _Stop as e:return Outcome(e.status,request)
    except (TypeError,ValueError,AttributeError,OverflowError):return Outcome("INVALID_INPUT",request)

    deadline=monotonic()+timeout_ms/1000.
    def check(frame=None):
        if cancelled() is not False:raise _Stop("CANCELLED")
        if monotonic()>=deadline:raise _Stop("TIMED_OUT")
        if frame is not None and source_current(frame,context) is not True:raise _Stop("STALE_SOURCE")
        if monotonic()>=deadline:raise _Stop("TIMED_OUT")
    def authorize(phase,n=0,frame_hash="",receipt=""):
        if admit(Admission(phase,namespace,request,n,frame_hash,receipt),context) is not True:
            raise _Stop("DENIED")
    try:
        check();authorize("sequence");check()
        np,sv,engine,backend_hash=_engine()
        if resume is not None and resume.backend_sha256!=backend_hash:raise _Stop("REPLAY_MISMATCH")
        history=[];previous={};max_seen=-1
        parent=digest({"scope":namespace,"backend":backend_hash})
        for frame,frame_hash in zip(frames,hashes):
            check(frame);authorize("associate",frame.number,frame_hash,parent);check(frame)
            update,new,previous,max_seen=_adapt(np,sv,engine,frame,namespace,previous,max_seen)
            check(frame)
            value={"scope":namespace,"backend":backend_hash,"frame":frame_hash,
                   "parent":parent,"update":asdict(update),"new_ids":new,"internal_count":len(engine.tracks)}
            receipt=digest(value)
            authorize("verify",frame.number,frame_hash,receipt);check(frame)
            history.append(FrameResult(frame.number,frame_hash,parent,update,new,len(engine.tracks),receipt))
            parent=receipt
            if resume is not None and frame.number==resume.frames and parent!=resume.receipt_sha256:
                raise _Stop("REPLAY_MISMATCH")
        for frame in frames:check(frame)
        authorize("publish",len(frames),hashes[-1],parent)
        for frame in frames:check(frame)
        check()
        return Outcome("COMPLETED",request,tuple(history),ReplaySeal(namespace,backend_hash,len(frames),parent))
    except _Stop as e:return Outcome(e.status,request)
    except Exception:return Outcome("VERIFICATION_FAILED",request)
