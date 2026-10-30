"""C15 P1 versioned, research-only 2D benchmark observations.

Never treat annotation contents, feature hashes or model outputs as authority.
MOTChallenge import/export is lossless for supported geometry and identity fields;
mask input uses *uncompressed*, column-major COCO RLE with exact size check.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from pathlib import Path
from typing import Iterable

from cognitum.proto import benchmark_observation_pb2 as pb

class ObservationRejected(ValueError):
    pass

_IDENT = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}$')
_MAX_FRAME = 10**9
_MAX_OBS = 1_000_000
_MAX_IMAGE_DIM = 100000
_MAX_RLE_RUNS = 100000


def _id(value, key):
    if not isinstance(value, str) or not _IDENT.fullmatch(value):
        raise ObservationRejected('INVALID_' + key)


def _finite(*values):
    return all(math.isfinite(v) for v in values)


def _unknown_free(msg):
    cp = msg.__class__()
    cp.CopyFrom(msg)
    cp.DiscardUnknownFields()
    if cp.SerializeToString(deterministic=True) != msg.SerializeToString(deterministic=True):
        raise ObservationRejected('UNKNOWN_PROTOBUF_FIELD')


def validate(obs: pb.BenchmarkObservation, *, expected_role: int | None = None) -> None:
    if not isinstance(obs, pb.BenchmarkObservation):
        raise ObservationRejected('WRONG_PROTOBUF_TYPE')
    _unknown_free(obs)
    if obs.schema_version != 1 or not obs.research_only or obs.grants_authority:
        raise ObservationRejected('INVALID_RESEARCH_CONTRACT')
    _id(obs.sequence_id, 'SEQUENCE'); _id(obs.observation_id, 'OBSERVATION'); _id(obs.camera_frame, 'CAMERA_FRAME')
    if obs.frame_index < 1 or obs.frame_index > _MAX_FRAME:
        raise ObservationRejected('INVALID_FRAME')
    if obs.role not in (pb.GROUND_TRUTH, pb.DETECTION, pb.TRACKER_PREDICTION) or (expected_role is not None and obs.role != expected_role):
        raise ObservationRejected('INVALID_ROLE')
    if obs.is_ignore_region and obs.role != pb.GROUND_TRUTH:
        raise ObservationRejected('IGNORE_ONLY_IN_GROUND_TRUTH')
    if obs.class_id < 0 or obs.class_id > 100000 or not isinstance(obs.class_label, str) or not obs.class_label or len(obs.class_label) > 128:
        raise ObservationRejected('INVALID_CLASS')
    if obs.HasField('track_id'):
        if obs.track_id <= 0:
            raise ObservationRejected('INVALID_TRACK_ID')
    elif obs.role != pb.DETECTION and not obs.is_ignore_region:
        raise ObservationRejected('MISSING_TRACK_ID')
    if obs.role == pb.DETECTION and obs.HasField('track_id'):
        raise ObservationRejected('DETECTION_MUST_NOT_HAVE_IDENTITY')
    if obs.HasField('confidence'):
        if not _finite(obs.confidence) or not (0 <= obs.confidence <= 1):
            raise ObservationRejected('INVALID_CONFIDENCE')
    elif obs.role == pb.DETECTION:
        raise ObservationRejected('MISSING_CONFIDENCE')
    if obs.HasField('visibility'):
        if obs.role != pb.GROUND_TRUTH or not _finite(obs.visibility) or not 0<=obs.visibility<=1:
            raise ObservationRejected('INVALID_GT_VISIBILITY')
    if obs.HasField('timestamp_ns') and obs.timestamp_ns == 0:
        raise ObservationRejected('INVALID_TIMESTAMP')
    if not (0 < obs.image_width <= _MAX_IMAGE_DIM and 0 < obs.image_height <= _MAX_IMAGE_DIM):
        raise ObservationRejected('INVALID_IMAGE_SIZE')
    if not obs.HasField('bbox') and not obs.HasField('mask'):
        raise ObservationRejected('MISSING_GEOMETRY')
    if obs.HasField('bbox'):
        b = obs.bbox
        if not _finite(b.x, b.y, b.width, b.height) or b.width <= 0 or b.height <= 0:
            raise ObservationRejected('INVALID_BOX')
        # Partly out-of-frame objects are permitted (MOT15 includes negative x).
        if any(abs(v) > 1e7 for v in (b.x, b.y, b.width, b.height)):
            raise ObservationRejected('BOX_UNBOUNDED')
    if obs.HasField('mask'):
        m = obs.mask
        if m.width != obs.image_width or m.height != obs.image_height or not (1 <= len(m.counts) <= _MAX_RLE_RUNS):
            raise ObservationRejected('INVALID_MASK_DIMENSIONS')
        if sum(m.counts) != m.width * m.height or len(m.counts) > m.width * m.height + 1:
            raise ObservationRejected('INVALID_RLE_TOTAL')
        # COCO allows zero first run (foreground at index zero). Any other zero
        # run is noncanonical and is ambiguous without a decoder.
        if any(c == 0 for c in m.counts[1:]):
            raise ObservationRejected('NONCANONICAL_RLE')
    if not obs.HasField('provenance'):
        raise ObservationRejected('MISSING_PROVENANCE')
    p = obs.provenance
    _id(p.dataset_id, 'DATASET'); _id(p.dataset_version, 'DATASET_VERSION')
    _id(p.annotation_version, 'ANNOTATION_VERSION')
    if len(p.source_sha256) != 32 or not p.source_uri or len(p.source_uri) > 1024:
        raise ObservationRejected('INVALID_PROVENANCE')
    _unknown_free(p)


def validate_sequence(observations: Iterable[pb.BenchmarkObservation], *, role: int | None = None, max_rows: int = _MAX_OBS):
    seen=set(); ids=set(); frame_timestamps={}; seqs=set(); counts=0
    for o in observations:
        validate(o, expected_role=role)
        counts += 1
        if counts > max_rows:
            raise ObservationRejected('TOO_MANY_OBSERVATIONS')
        key=(o.sequence_id, o.frame_index, o.observation_id, o.role)
        if key in seen:
            raise ObservationRejected('DUPLICATE_OBSERVATION')
        seen.add(key);seqs.add(o.sequence_id)
        if o.HasField('track_id') and not o.is_ignore_region:
            k=(o.sequence_id,o.frame_index,o.track_id,o.role)
            if k in ids:raise ObservationRejected('DUPLICATE_TRACK_ID_IN_FRAME')
            ids.add(k)
        if o.HasField('timestamp_ns'):
            k=(o.sequence_id,o.frame_index,o.camera_frame)
            if k in frame_timestamps and frame_timestamps[k]!=o.timestamp_ns:
                raise ObservationRejected('INCONSISTENT_FRAME_TIMESTAMP')
            frame_timestamps[k]=o.timestamp_ns
    if len(seqs)>1:raise ObservationRejected('MULTIPLE_SEQUENCES')
    by_cam={}
    for (seq,frame,cam),t in frame_timestamps.items():
        by_cam.setdefault((seq,cam),[]).append((frame,t))
    for stamps in by_cam.values():
        stamps.sort()
        if any(t1 >= t2 for (_,t1),(_,t2) in zip(stamps,stamps[1:])):
            raise ObservationRejected('NONMONOTONIC_TIMESTAMP')
    return counts


def make_observation(*, seq, frame, observation_id, role, class_id, class_label, image_width, image_height, source_bytes,
                     dataset_id, dataset_version, source_uri, annotation_version='v1', camera_frame='camera0',
                     box=None, mask_counts=None, track_id=None, confidence=None, timestamp_ns=None, visibility=None, ignore=False):
    o=pb.BenchmarkObservation(schema_version=1, sequence_id=seq, frame_index=frame,
        observation_id=observation_id, role=role, class_label=class_label, class_id=class_id,
        camera_frame=camera_frame, image_width=image_width, image_height=image_height,
        research_only=True, grants_authority=False, is_ignore_region=ignore)
    if track_id is not None:o.track_id=int(track_id)
    if confidence is not None:o.confidence=float(confidence)
    if timestamp_ns is not None:o.timestamp_ns=int(timestamp_ns)
    if visibility is not None:o.visibility=float(visibility)
    if box is not None:o.bbox.CopyFrom(pb.BoundingBox2D(x=box[0], y=box[1], width=box[2], height=box[3]))
    if mask_counts is not None:o.mask.CopyFrom(pb.UncompressedMaskRLE(width=image_width,height=image_height,counts=list(mask_counts)))
    o.provenance.CopyFrom(pb.ObservationProvenance(dataset_id=dataset_id,dataset_version=dataset_version,
        annotation_version=annotation_version,source_uri=source_uri,source_sha256=hashlib.sha256(source_bytes).digest()))
    validate(o)
    return o


def read_mot_benchmark(path: str|Path, *, seq: str, role: int, width: int, height: int,
                       dataset_id: str, dataset_version: str, source_uri: str,
                       legacy_gt=False, max_bytes=50_000_000, max_rows=_MAX_OBS):
    """Import MOTChallenge 10-column rows; pinned older MOT15 GT may use -1 class/vis.

    Detection input never inherits any ID even when its rows contain a numeric index.
    No ground-truth row is silently relabeled as a tracker prediction.
    """
    if role not in (pb.GROUND_TRUTH, pb.DETECTION, pb.TRACKER_PREDICTION):
        raise ObservationRejected('INVALID_ROLE')
    p=Path(path)
    if not p.is_file() or p.stat().st_size>max_bytes:raise ObservationRejected('INVALID_INPUT_FILE')
    data=p.read_bytes()
    try: text=data.decode('utf-8-sig')
    except UnicodeDecodeError as e:raise ObservationRejected('INVALID_ENCODING') from e
    out=[]
    for i,c in enumerate(csv.reader(io.StringIO(text)),1):
        if not c or not any(v.strip() for v in c):continue
        if len(out)>=max_rows:raise ObservationRejected('TOO_MANY_ROWS')
        if len(c)!=10:raise ObservationRejected('MOT_EXPECTED_TEN_COLUMNS')
        try: vals=[float(v) for v in c]
        except ValueError as e:raise ObservationRejected('NONNUMERIC_ROW') from e
        if not _finite(*vals):raise ObservationRejected('NONFINITE_ROW')
        if vals[0]<1 or vals[0]!=int(vals[0]) or vals[1]!=int(vals[1]):
            raise ObservationRejected('INVALID_MOT_FRAME_ID')
        n=int(vals[0]);ident=int(vals[1]);flag=vals[6]
        if role == pb.GROUND_TRUTH:
            if not legacy_gt and (vals[7]<1 or vals[8]<0 or vals[8]>1):
                raise ObservationRejected('INVALID_MODERN_GT_CLASS_VISIBILITY')
            if legacy_gt and (vals[7]!=-1 or vals[8]!=-1):
                raise ObservationRejected('LEGACY_GT_SENTINEL_EXPECTED')
            ignored=flag==0
            cls=1 if legacy_gt else int(vals[7]); label='pedestrian' if cls==1 else f'class_{cls}'
            track=ident if ident>0 else None
            if track is None and not ignored:raise ObservationRejected('GT_ID_REQUIRED')
            confidence=None
            visibility=None if legacy_gt else vals[8]
        else:
            ignored=False;visibility=None;cls=1;label='pedestrian'
            if role==pb.TRACKER_PREDICTION:
                if ident<=0:raise ObservationRejected('TRACKER_ID_REQUIRED')
                track=ident
            else:track=None
            if flag == -1 and role==pb.TRACKER_PREDICTION:
                confidence=None # MOTChallenge placeholder: unavailable, not a probability
            else:
                confidence=flag
        o=make_observation(seq=seq,frame=n,observation_id=f'{role}-{n}-{i}',role=role,class_id=cls,class_label=label,
            image_width=width,image_height=height,source_bytes=data,dataset_id=dataset_id,dataset_version=dataset_version,
            source_uri=source_uri,box=vals[2:6],track_id=track,confidence=confidence,visibility=visibility,ignore=ignored)
        out.append(o)
    validate_sequence(out,role=role)
    return out


def export_mot_rows(observations: Iterable[pb.BenchmarkObservation], *, role: int):
    obs=list(observations);validate_sequence(obs,role=role)
    if any(x.HasField('mask') for x in obs):
        raise ObservationRejected('MOTS_MASK_CANNOT_BE_DISCARDED_IN_BOX_EVALUATION')
    lines=[]
    for o in sorted(obs,key=lambda x:(x.frame_index,x.observation_id)):
        if not o.HasField('bbox'):
            raise ObservationRejected('MASK_ONLY_REQUIRES_OFFICIAL_MOTS_EVALUATOR')
        b=o.bbox
        if role==pb.GROUND_TRUTH:
            confidence=0 if o.is_ignore_region else 1
            cl=o.class_id;visibility=o.visibility if o.HasField('visibility') else -1 # missing stays unknown
            tail=(cl,visibility,-1)
        else:
            confidence=o.confidence if o.HasField('confidence') else -1;tail=(-1,-1,-1)
        fields=(o.frame_index,o.track_id if o.HasField('track_id') else -1,b.x,b.y,b.width,b.height,confidence,*tail)
        lines.append(','.join(str(v) for v in fields))
    return '\n'.join(lines)+'\n' if lines else ''


def parse_coco_video_uncompressed(payload: dict, *, seq: str, dataset_id: str,
                                  dataset_version: str, source_uri: str, role: int):
    """Restricted COCO-video JSON adapter; rejects compressed masks and ambiguous frame IDs.

    Requires images [{id,frame_index,width,height,video_id,...}] and annotations
    [{id,image_id,category_id,track_id?,bbox?,segmentation?:{counts:[...]}}].
    Does not interpret arbitrary COCO images as a video or invent frame rates.
    """
    if role not in (pb.GROUND_TRUTH,pb.TRACKER_PREDICTION,pb.DETECTION):
        raise ObservationRejected('INVALID_ROLE')
    if not isinstance(payload,dict) or not isinstance(payload.get('images'),list) or not isinstance(payload.get('annotations'),list):
        raise ObservationRejected('INVALID_COCO_DATA')
    raw=json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
    if len(raw)>50_000_000:raise ObservationRejected('JSON_TOO_LARGE')
    ims={}; video_ids=set()
    for im in payload['images']:
        if not isinstance(im,dict) or not all(k in im for k in ('id','frame_index','width','height','video_id')):
            raise ObservationRejected('IMAGE_FRAME_METADATA_REQUIRED')
        k=im['id']
        if not isinstance(k,int) or isinstance(k,bool) or k in ims:raise ObservationRejected('INVALID_IMAGE_ID')
        ims[k]=im;video_ids.add(im['video_id'])
    if len(video_ids)!=1:raise ObservationRejected('INCONSISTENT_VIDEO_ID')
    cat={c['id']:c['name'] for c in payload.get('categories',[]) if isinstance(c,dict) and 'id'in c and 'name'in c}
    out=[]
    for ann in payload['annotations']:
        if not isinstance(ann,dict) or not all(k in ann for k in ('id','image_id','category_id')):
            raise ObservationRejected('INVALID_ANNOTATION')
        if ann['image_id'] not in ims:raise ObservationRejected('UNKNOWN_IMAGE_REFERENCE')
        im=ims[ann['image_id']]
        seg=ann.get('segmentation');counts=None
        if seg is not None:
            if not isinstance(seg,dict) or not isinstance(seg.get('counts'),list) or seg.get('size')!=[im['height'],im['width']]:
                raise ObservationRejected('COMPRESSED_OR_INVALID_COCO_RLE_UNSUPPORTED')
            counts=seg['counts']
        ident=ann.get('track_id')
        if role!=pb.DETECTION and ident is None:raise ObservationRejected('COCO_TRACK_ID_REQUIRED')
        if role==pb.DETECTION and ident is not None:raise ObservationRejected('DETECTION_TRACK_ID_LEAK')
        score=ann.get('score')
        if role!=pb.GROUND_TRUTH and score is None:raise ObservationRejected('COCO_SCORE_REQUIRED')
        o=make_observation(seq=seq,frame=im['frame_index'],observation_id=f'coco-{ann["id"]}',role=role,
            class_id=ann['category_id'],class_label=cat.get(ann['category_id'],f'class_{ann["category_id"]}'),
            image_width=im['width'],image_height=im['height'],source_bytes=raw,
            dataset_id=dataset_id,dataset_version=dataset_version,source_uri=source_uri,
            box=ann.get('bbox'),mask_counts=counts,track_id=ident,confidence=score,
            timestamp_ns=im.get('timestamp_ns'))
        out.append(o)
    validate_sequence(out,role=role)
    return out


def validate_frame(frame: pb.BenchmarkFrame, *, expected_role: int | None = None):
    if not isinstance(frame,pb.BenchmarkFrame):
        raise ObservationRejected('WRONG_FRAME_TYPE')
    _unknown_free(frame)
    if frame.schema_version != 1 or not (1 <= frame.frame_index <= _MAX_FRAME):
        raise ObservationRejected('INVALID_FRAME_CONTRACT')
    _id(frame.sequence_id,'SEQUENCE')
    if len(frame.observations)>100000:
        raise ObservationRejected('FRAME_TOO_LARGE')
    for obs in frame.observations:
        if obs.frame_index != frame.frame_index or obs.sequence_id != frame.sequence_id:
            raise ObservationRejected('FRAME_OBSERVATION_MISMATCH')
    return validate_sequence(frame.observations,role=expected_role)
