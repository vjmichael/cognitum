"""C15 P2L: appearance-aware MOT association, offline and research-only.

No model weights, detector, ground-truth identities or Lu authority enter this
module. Matched IDs are forced *hypotheses* solely for benchmark export. The
handcrafted pixel-histogram encoder is a reproducible CPU comparator, NOT ReID.
External descriptor vectors are never regarded as independently authenticated.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
import hashlib
import io
import math
from typing import Mapping

from cognitum.spatial_p2k_dense_identity import (
    Detection, Params, Track, validate_parameters, DenseAssociationRejected,
)
from cognitum.spatial_appearance_evidence import assess, AppearanceRejected
from cognitum.proto import spatial_appearance_pb2 as pb

ENCODER_ID = 'c15.p2l.gray4x4hist8.v1'
ENCODER_DIGEST = hashlib.sha256(b'C15:P2L:GRAY:4X4:8BINS:128D:V1').digest()
CONVERSATION = 'c15_p2l_offline'
MAX_FRAME_BYTES = 32 * 1024 * 1024
MAX_DIMS = (8192, 8192)

class P2LRejected(ValueError):
    pass


def observation_id(sequence: str, d: Detection, index: int) -> str:
    """Bind a descriptor to frame + ordinal + box without retaining source ID."""
    if type(index) is not int or index < 0:
        raise P2LRejected('INVALID_ORDINAL')
    data = f'{sequence}|{d.frame}|{index}|{d.x:.17g}|{d.y:.17g}|{d.w:.17g}|{d.h:.17g}'
    return 'box.' + hashlib.sha256(data.encode('ascii')).hexdigest()


def _image(image_bytes: bytes):
    if not isinstance(image_bytes, bytes) or not 0 < len(image_bytes) <= MAX_FRAME_BYTES:
        raise P2LRejected('INVALID_FRAME_BYTES')
    from PIL import Image, ImageOps
    try:
        im = Image.open(io.BytesIO(image_bytes))
        if im.width > MAX_DIMS[0] or im.height > MAX_DIMS[1] or im.width < 2 or im.height < 2:
            raise P2LRejected('INVALID_IMAGE_DIMENSIONS')
        im.load()
        im = ImageOps.exif_transpose(im).convert('L')
        return im
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise P2LRejected('INVALID_IMAGE') from exc


def histogram_vector(image_bytes: bytes, d: Detection) -> tuple[float, ...]:
    """Deterministic 4x4-grid, 8-bin grayscale descriptor (not learned ReID)."""
    import numpy as np
    im = _image(image_bytes)
    if not isinstance(d, Detection) or not all(math.isfinite(v) for v in (d.x,d.y,d.w,d.h)) or d.w <= 0 or d.h <= 0:
        raise P2LRejected('INVALID_CROP_BOX')
    left = max(0, math.floor(d.x)); top = max(0, math.floor(d.y))
    right = min(im.width, math.ceil(d.x + d.w)); bottom = min(im.height, math.ceil(d.y + d.h))
    if right - left < 4 or bottom - top < 4:
        raise P2LRejected('UNUSABLE_CROP')
    crop = np.asarray(im.crop((left,top,right,bottom)), dtype=np.uint8)
    # Avoid resize interpolation, use actual pixel bins for each spatial tile.
    hist = np.zeros(128, dtype=np.float64)
    for ry in range(4):
        for rx in range(4):
            yy0 = ry * crop.shape[0] // 4
            yy1 = (ry+1) * crop.shape[0] // 4
            xx0 = rx * crop.shape[1] // 4
            xx1 = (rx+1) * crop.shape[1] // 4
            tile = crop[yy0:yy1, xx0:xx1]
            if tile.size == 0:
                raise P2LRejected('EMPTY_TILE')
            hist[(ry*4+rx)*8:(ry*4+rx+1)*8] = np.bincount((tile//32).flatten(),minlength=8)/tile.size
    magnitude = float(np.linalg.norm(hist))
    if not math.isfinite(magnitude) or magnitude <= 0:
        raise P2LRejected('INVALID_HISTOGRAM')
    # Protobuf float32 roundtripping is covered by structural norm tolerance.
    return tuple(float(x) for x in (hist/magnitude))


def descriptor_from_frame(*, image_bytes: bytes, detection: Detection, index: int,
                          sequence: str, conversation_id: str=CONVERSATION) -> pb.AppearanceDescriptor:
    vec = histogram_vector(image_bytes, detection)
    spec = pb.AppearanceDescriptor(schema_version=1, model_id=ENCODER_ID,
        image_source_id=sequence, detection_id=observation_id(sequence,detection,index),
        conversation_id=conversation_id, frame=detection.frame,
        encoder_sha256=ENCODER_DIGEST, frame_sha256=hashlib.sha256(image_bytes).digest(),
        vector=vec, research_only=True, grants_authority=False)
    assess(spec)
    return spec


def descriptors_from_frames(frames: Mapping[int,list[Detection]], image_bytes: Mapping[int,bytes],
                             *, sequence: str, conversation_id: str=CONVERSATION) -> dict[tuple[int,int],pb.AppearanceDescriptor]:
    """Extract strictly image-derived baseline features, never GT or source IDs."""
    if set(image_bytes) != {f for f,dets in frames.items() if dets}:
        raise P2LRejected('IMAGE_FRAME_SET_MISMATCH')
    return {(frame,i):descriptor_from_frame(image_bytes=image_bytes[frame],detection=d,index=i,sequence=sequence,conversation_id=conversation_id)
            for frame,dets in frames.items() for i,d in enumerate(dets)}


@dataclass(frozen=True)
class AppearanceConfig:
    appearance_weight: float = 8.0
    max_cosine_distance: float = 0.85
    momentum: float = 0.6
    near_tie_margin: float = 0.75


def _validate_conf(cfg: AppearanceConfig):
    if not isinstance(cfg,AppearanceConfig) or not all(math.isfinite(x) for x in
        (cfg.appearance_weight,cfg.max_cosine_distance,cfg.momentum,cfg.near_tie_margin)):
        raise P2LRejected('INVALID_APPEARANCE_CONFIG')
    if not (0<cfg.appearance_weight<=100 and 0<=cfg.max_cosine_distance<=2 and
            0<=cfg.momentum<1 and 0<=cfg.near_tie_margin<=100):
        raise P2LRejected('INVALID_APPEARANCE_CONFIG')


def assign_with_appearance(frames: Mapping[int,list[Detection]], *, num_frames: int, sequence: str,
    image_bytes: Mapping[int,bytes], descriptors: Mapping[tuple[int,int],pb.AppearanceDescriptor],
    mode: str='velocity', params: Params=Params(), config: AppearanceConfig=AppearanceConfig(),
    expected_model_id: str=ENCODER_ID, expected_encoder_digest: bytes=ENCODER_DIGEST,
    expected_conversation_id: str=CONVERSATION):
    """Assign forced top-1 labels only after complete provenance-format validation.

    Caller must supply actual matching image bytes, never merely hash assertions.
    Source authenticity and model execution remain *unattested* despite hashes.
    """
    import numpy as np
    from scipy.optimize import linear_sum_assignment
    validate_parameters(params);_validate_conf(config)
    if mode not in ('position','velocity') or type(num_frames)!=int or not 1<=num_frames<=100000:
        raise P2LRejected('INVALID_MODE_OR_FRAME_COUNT')
    if not sequence or len(sequence)>128 or not all(c.isascii() and (c.isalnum() or c in '-_:.') for c in sequence):
        raise P2LRejected('INVALID_SEQUENCE')
    if not expected_model_id or len(expected_encoder_digest)!=32:
        raise P2LRejected('INVALID_PINNED_ENCODER')
    if any(type(f)!=int or not 1<=f<=num_frames for f in frames):raise P2LRejected('INVALID_FRAME_INDEX')
    expected_keys = {(f,i) for f,dets in frames.items() for i in range(len(dets))}
    if not expected_keys: raise P2LRejected('NO_APPEARANCE_OBSERVATIONS')
    if set(descriptors) != expected_keys: raise P2LRejected('INCOMPLETE_OR_EXTRA_APPEARANCE')
    if set(image_bytes) != {f for f,dets in frames.items() if dets}:
        raise P2LRejected('IMAGE_FRAME_SET_MISMATCH')
    if len(expected_keys)>500_000:raise P2LRejected('DATASET_CAPACITY_EXCEEDED')
    validated={}
    for f,dets in frames.items():
        if len(dets)>params.max_boxes:raise P2LRejected('DENSITY_EXCEEDS_CAPACITY')
        digest=hashlib.sha256(image_bytes[f]).digest() if dets else None
        if dets: _image(image_bytes[f])  # full decode validates real frame bytes
        for i,d in enumerate(dets):
            if not isinstance(d,Detection) or d.frame!=f or not all(math.isfinite(v) for v in (d.x,d.y,d.w,d.h)) or d.w<=0 or d.h<=0:
                raise P2LRejected('INVALID_DETECTION')
            spec=descriptors[(f,i)]
            try: assess(spec)
            except AppearanceRejected as exc: raise P2LRejected('INVALID_DESCRIPTOR') from exc
            if (spec.frame!=f or spec.image_source_id!=sequence or
                spec.detection_id!=observation_id(sequence,d,i) or
                spec.model_id!=expected_model_id or spec.encoder_sha256!=expected_encoder_digest or
                spec.frame_sha256!=digest or spec.conversation_id!=expected_conversation_id):
                raise P2LRejected('DESCRIPTOR_BINDING_MISMATCH')
            vec=np.array(spec.vector,dtype=np.float64)
            vec/=np.linalg.norm(vec)
            validated[(f,i)]=vec
    states={};features={};next_tid=1;outputs={};counts=Counter()
    for frame in range(1,num_frames+1):
        states={tid:t for tid,t in states.items() if frame-t.frame<=params.max_gap_frames}
        features={tid:vec for tid,vec in features.items() if tid in states}
        dets=frames.get(frame,[])
        if len(states)>params.max_tracks:raise P2LRejected('ACTIVE_TRACK_LIMIT')
        if not dets:
            counts['frames_without_detections']+=1;continue
        active=sorted(states.values(),key=lambda t:t.tid);n=len(dets);t=len(active)
        matrix=np.full((n,t+n),1e12,dtype=np.float64)
        matrix[:,t:]=params.unmatched_cost+1e-10*np.arange(n)[None,:]
        for i,d in enumerate(dets):
            cx,cy=d.center
            for j,old in enumerate(active):
                dt=frame-old.frame
                px=old.x + (old.vx*dt if mode=='velocity' and old.hits>=2 else 0)
                py=old.y + (old.vy*dt if mode=='velocity' and old.hits>=2 else 0)
                distance=math.hypot(cx-px,cy-py)
                cosine=float(np.dot(validated[(frame,i)],features[old.tid]))
                appearance=max(0.,min(2.,1.-cosine))
                cost=0.5*(distance/params.sigma_px)**2+config.appearance_weight*appearance
                if (distance<=params.max_speed_px_per_frame*dt+3*params.sigma_px and
                    appearance<=config.max_cosine_distance and cost<=params.unmatched_cost):
                    matrix[i,j]=cost+1e-9*j
        rows,cols=linear_sum_assignment(matrix)
        if len(rows)!=n:raise P2LRejected('INCOMPLETE_ASSIGNMENT')
        result=[None]*n
        for i,j in zip(rows.tolist(),cols.tolist()):
            cx,cy=dets[i].center;vec=validated[(frame,i)]
            if j<t and matrix[i,j]<1e11:
                old=active[j];dt=frame-old.frame
                vx=(cx-old.x)/dt;vy=(cy-old.y)/dt
                track=Track(old.tid,cx,cy,frame,vx,vy,old.hits+1)
                states[old.tid]=track
                updated=config.momentum*features[old.tid]+(1-config.momentum)*vec
                norm=np.linalg.norm(updated)
                features[old.tid]=(updated/norm) if norm>1e-12 else vec
                result[i]=old.tid;counts['matched_boxes']+=1
                alt=np.delete(matrix[i,:t],j) if t>1 else np.array([])
                alternative=min(float(alt.min()) if len(alt) else float('inf'),params.unmatched_cost)
                if alternative-matrix[i,j]<=config.near_tie_margin:
                    counts['heuristically_near_tied_matches']+=1
            else:
                tid=next_tid;next_tid+=1
                states[tid]=Track(tid,cx,cy,frame);features[tid]=vec
                result[i]=tid;counts['new_identity_proposals']+=1
        if len(states)>params.max_tracks:raise P2LRejected('ACTIVE_TRACK_LIMIT')
        if len(set(result))!=n:raise P2LRejected('DUPLICATE_FRAME_IDS')
        outputs[frame]=result
        counts['observed_frames']+=1;counts['input_boxes']+=n
        counts['max_active_tracks']=max(counts['max_active_tracks'],len(states))
        counts['max_frame_boxes']=max(counts['max_frame_boxes'],n)
        if n>1:counts['multi_object_frames_without_identity_proof']+=1
    counts['unattested_appearance_descriptors']=len(expected_keys)
    counts['frames_without_detections']=num_frames-counts['observed_frames']
    counts['forced_top1_research_only']=1
    return outputs,dict(counts)
