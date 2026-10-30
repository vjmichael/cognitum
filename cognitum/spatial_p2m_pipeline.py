"""C15 P2M: bounded appearance-model interface and T1/T2/T3 research handoff.

Standalone Cognitum reference. Does not start external models, import weights,
make camera calibration claims, mutate scene graphs/voxels, or grant Lu authority.
Only the pinned handcrafted histogram is an executable test backend.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import hashlib
import math

from cognitum.proto import spatial_appearance_pipeline_pb2 as pb
from cognitum.proto import spatial_composition_pb2 as t2
from cognitum.spatial_p2k_dense_identity import Detection
from cognitum import spatial_p2l_appearance as p2l, spatial_appearance_evidence as evidence
from cognitum import spatial_composition

PREPROCESS = 'c15.p2l.gray4x4hist8.crop.v1'
MAX_FRAMES = 4
MAX_BOXES_PER_FRAME = 16
MAX_ENCODED_FRAME = 8 * 1024 * 1024
MAX_ENCODED_REQUEST = 20 * 1024 * 1024
MAX_WEIGHTS_BYTES = 512 * 1024 * 1024

class P2MRejected(ValueError):
    pass


def _require(ok: bool, code: str):
    if not ok:
        raise P2MRejected(code)


def _id(v: str):
    return isinstance(v, str) and 0 < len(v) <= 96 and all(
        c.isascii() and (c.isalnum() or c in '-_:.') for c in v
    )


def _digest(obj):
    return hashlib.sha256(obj.SerializeToString(deterministic=True)).digest()


def _known(obj):
    # Protobuf usually retains unknown fields; the P2M research envelope rejects
    # them so a later version cannot silently change processing semantics.
    cleaned = type(obj)()
    cleaned.CopyFrom(obj)
    cleaned.DiscardUnknownFields()
    return cleaned.SerializeToString(deterministic=True) == obj.SerializeToString(deterministic=True)


def histogram_model():
    return pb.P2MModelSpec(model_id=p2l.ENCODER_ID,
        encoder_sha256=p2l.ENCODER_DIGEST, backend=pb.P2M_HISTOGRAM_CPU,
        output_dimension=128, preprocessing_id=PREPROCESS,
        research_only=True, grants_authority=False)


def inspect_model(model: pb.P2MModelSpec, *, weights_path: str | Path | None = None) -> dict:
    """Verify an external model's *file* identity; never deserialize/execute it.

    This is a readiness/compatibility probe, NOT a security sandbox or host
    approval. No implicit download, torch.load, pickle, dynamic import, etc.
    """
    _require(isinstance(model, pb.P2MModelSpec) and _known(model) and
        model.research_only and not model.grants_authority and
        _id(model.model_id) and _id(model.preprocessing_id) and
        len(model.encoder_sha256) == 32 and model.output_dimension == 128,
        'INVALID_MODEL_SPEC')
    if model.backend == pb.P2M_HISTOGRAM_CPU:
        _require(model == histogram_model() and weights_path is None, 'UNPINNED_HISTOGRAM_MODEL')
        return {'status':'ready_bounded_histogram_cpu','can_execute':True,'weights_authenticated':False}
    _require(model.backend == pb.P2M_EXTERNAL_LEARNED_DISABLED and
        len(model.weights_sha256) == 32 and len(model.encoder_sha256) == 32,
        'UNPINNED_EXTERNAL_MODEL')
    if weights_path is None:
        return {'status':'blocked_external_weights_missing','can_execute':False,'weights_authenticated':False}
    path = Path(weights_path)
    _require(not path.is_symlink() and path.is_file(), 'INVALID_WEIGHT_FILE')
    size = path.stat().st_size
    _require(0 < size <= MAX_WEIGHTS_BYTES, 'WEIGHT_SIZE_LIMIT')
    h = hashlib.sha256()
    with path.open('rb') as f:
        while block := f.read(1024 * 1024):
            h.update(block)
    _require(h.digest() == model.weights_sha256, 'WEIGHT_DIGEST_MISMATCH')
    return {'status':'blocked_external_execution_requires_verified_host_worker',
            'can_execute':False,'weights_authenticated':False,
            'weights_digest_verified':True,'weight_bytes':size}


def _validate_request(req: pb.P2MFeatureRequest):
    _require(isinstance(req, pb.P2MFeatureRequest) and
        req.ByteSize() <= MAX_ENCODED_REQUEST + 65536 and _known(req) and
        req.schema_version == 1 and req.research_only and not req.grants_authority and
        _id(req.sequence_id) and _id(req.conversation_id) and _id(req.request_id) and
        req.HasField('model'), 'INVALID_REQUEST')
    status = inspect_model(req.model)
    _require(status['can_execute'], 'EXTERNAL_EXECUTION_DISABLED')
    _require(1 <= len(req.frames) <= MAX_FRAMES, 'FRAME_BATCH_LIMIT')
    raw_bytes = sum(len(f.encoded_image) for f in req.frames)
    _require(raw_bytes <= MAX_ENCODED_REQUEST, 'REQUEST_IMAGE_BYTES_LIMIT')
    frames = {}; images = {}; refs = {}
    for f in req.frames:
        _require(1 <= f.frame <= 100000 and f.frame not in frames and
            _id(f.source_ref) and 1 <= len(f.boxes) <= MAX_BOXES_PER_FRAME and
            0 < len(f.encoded_image) <= MAX_ENCODED_FRAME, 'INVALID_FRAME_BATCH')
        _require(bytes(f.encoded_image).startswith((b'\xff\xd8',b'\x89PNG\r\n\x1a\n')), 'UNSUPPORTED_IMAGE_FORMAT')
        # The image decoder validates pixels and dimensions before any execution.
        try:
            # Reject oversized decompressions BEFORE PIL decodes pixel planes.
            import io
            from PIL import Image
            with Image.open(io.BytesIO(f.encoded_image)) as header:
                _require(header.width * header.height <= 8_000_000,
                         'DECODED_PIXEL_LIMIT')
            image = p2l._image(bytes(f.encoded_image))
        except p2l.P2LRejected as e:
            raise P2MRejected('INVALID_FRAME_IMAGE') from e
        dets=[]
        for b in f.boxes:
            _require(all(math.isfinite(x) for x in (b.x,b.y,b.w,b.h)) and
                b.w > 0 and b.h > 0 and 0 <= b.x < image.width and
                0 <= b.y < image.height and b.x+b.w <= image.width and
                b.y+b.h <= image.height, 'INVALID_IMAGE_BOUND_BOX')
            dets.append(Detection(int(f.frame),b.x,b.y,b.w,b.h))
        frames[int(f.frame)] = dets
        images[int(f.frame)] = bytes(f.encoded_image)
        refs[int(f.frame)] = f.source_ref
    return frames,images,refs


def extract(req: pb.P2MFeatureRequest) -> pb.P2MFeatureResponse:
    frames,images,refs = _validate_request(req)
    descriptors = p2l.descriptors_from_frames(frames,images,sequence=req.sequence_id,
        conversation_id=req.conversation_id)
    out = pb.P2MFeatureResponse(schema_version=1,conversation_id=req.conversation_id,
        sequence_id=req.sequence_id,request_id=req.request_id,request_sha256=_digest(req),
        research_only=True,grants_authority=False)
    out.model.CopyFrom(req.model)
    for frame in sorted(frames):
        out.frames.add(frame=frame,image_sha256=hashlib.sha256(images[frame]).digest(),
            source_ref=refs[frame])
        for i in range(len(frames[frame])):
            out.descriptors.add().CopyFrom(descriptors[frame,i])
    out.warnings.extend(['SOURCE_HASHES_ARE_NOT_SENSOR_AUTHENTICATION',
       'HISTOGRAM_IS_NOT_A_LEARNED_PERSON_REID_MODEL','NO_IDENTITY_OR_ACTION_AUTHORITY'])
    return out


def check_response(req: pb.P2MFeatureRequest, resp: pb.P2MFeatureResponse):
    """Fail closed on unknown schema or changed feature/box binding, not only hashes."""
    _require(isinstance(resp,pb.P2MFeatureResponse) and _known(resp), 'INVALID_RESPONSE')
    expected = extract(req)
    _require(resp.SerializeToString(deterministic=True) == expected.SerializeToString(deterministic=True),
        'FEATURE_RESPONSE_MISMATCH')
    return True


def integration_handoff(req: pb.P2MFeatureRequest, resp: pb.P2MFeatureResponse,
                        assignments: dict[tuple[int,int], int]) -> pb.P2MSpatialHandoff:
    """T1 2D candidate identities and T2 hypothetical references only.

    T3 occupancy/volume and T1 authoritative 3D scene mutation are *blocked*:
    neither camera intrinsics nor world extrinsics nor depth is present.
    """
    check_response(req,resp)
    frames,_,_= _validate_request(req)
    keys = {(frame,idx) for frame,dets in frames.items() for idx in range(len(dets))}
    _require(isinstance(assignments,dict) and set(assignments) == keys, 'ASSIGNMENT_SET_MISMATCH')
    for frame in frames:
        ids = [assignments[frame,idx] for idx in range(len(frames[frame]))]
        _require(all(type(n) is int and 1 <= n <= 1_000_000 for n in ids) and
            len(ids) == len(set(ids)), 'INVALID_CANDIDATE_LABELS')
    by_box = {}
    for descriptor in resp.descriptors:
        by_box[descriptor.detection_id] = descriptor
    _require(len(by_box) == len(resp.descriptors), 'DUPLICATE_DESCRIPTOR')
    handoff=pb.P2MSpatialHandoff(schema_version=1,conversation_id=req.conversation_id,
        sequence_id=req.sequence_id,feature_response_sha256=_digest(resp),
        t1_identity_candidate_only=True,t2_structure_candidate_only=True,
        t3_projection_blocked_without_calibration=True,canonical_scene_mutation_blocked=True,
        research_only=True,grants_authority=False)
    graph=t2.StructureGraph(schema_version=1,graph_id='p2m.'+req.request_id,
        conversation_id=req.conversation_id,research_only=True,grants_authority=False)
    tracks={}
    for frame in sorted(frames):
        for idx,d in enumerate(frames[frame]):
            ident = p2l.observation_id(req.sequence_id,d,idx)
            desc=by_box[ident]
            tid=assignments[frame,idx]
            handoff.candidates.add(frame=frame,tracker_id=tid,detection_id=ident,
                descriptor_sha256=_digest(desc))
            tracks.setdefault(tid,_digest(desc).hex()[:32])
    for tid,origin in sorted(tracks.items()):
        graph.nodes.add(node_id=f'track.{tid}',kind='2d_identity_hypothesis',
            description='Image-space association only; no 3D, structure, or person identity',
            evidence=t2.EVIDENCE_HYPOTHETICAL,source_ref='feature.'+origin)
    _require(len(graph.nodes)<=256,'STRUCTURAL_CAPACITY_LIMIT')
    spatial_composition.validate(graph)
    handoff.t2_hypothetical_graph.CopyFrom(graph)
    handoff.warnings.extend(['T1_IDENTITY_PROPOSAL_ONLY','T2_HYPOTHETICAL_NODES_NO_PART_OF_EDGES',
         'T3_REQUIRES_DEPTH_AND_CAMERA_CALIBRATION','NO_3D_POSE_OR_VOXEL_INFERENCE',
         'HOST_ADMISSION_NOT_PROVIDED','NO_ACTION_AUTHORITY'])
    return handoff


def load_named_frames(frames_dir: Path, frame_numbers: list[int], *, max_files: int = MAX_FRAMES) -> dict[int,bytes]:
    """Bounded, explicit frame file entrypoint, never a recursive video scan."""
    root = Path(frames_dir)
    _require(root.is_dir() and not root.is_symlink() and 1 <= len(frame_numbers) <= max_files <= MAX_FRAMES,
        'INVALID_FRAME_DIRECTORY')
    _require(len(set(frame_numbers))==len(frame_numbers), 'DUPLICATE_FRAME_NUMBER')
    images={}
    for f in frame_numbers:
        _require(type(f) is int and 1<=f<=100000,'INVALID_FRAME_NUMBER')
        path=root / f'{f:06d}.jpg'
        _require(not path.is_symlink() and path.is_file(), 'TRAINING_FRAME_UNAVAILABLE')
        _require(0 < path.stat().st_size <= MAX_ENCODED_FRAME, 'IMAGE_FILE_SIZE_LIMIT')
        images[f]=path.read_bytes()
    return images


def research_pipeline(req: pb.P2MFeatureRequest, *, mode: str = 'velocity'):
    """Bounded end-to-end C15 T1 research flow, never an effectful host action.

    Returns (features, 2D/T2/T3 handoff, diagnostic_counts). Does not infer 3D
    geometry or award identity authority. Entire frame span is budget limited.
    """
    frames,images,_ = _validate_request(req)
    _require(max(frames)-min(frames) <= 256, 'FRAME_SPAN_LIMIT')
    resp=extract(req)
    specmap = {}
    descriptors_by_id={d.detection_id:d for d in resp.descriptors}
    for frame, detections in frames.items():
        for index, d in enumerate(detections):
            specmap[frame,index]=descriptors_by_id[p2l.observation_id(req.sequence_id,d,index)]
    labels,counts=p2l.assign_with_appearance(frames,num_frames=max(frames),
        sequence=req.sequence_id,image_bytes=images,descriptors=specmap,
        expected_conversation_id=req.conversation_id,mode=mode)
    assignments = {(frame,index):labels[frame][index] for frame,dets in frames.items()
                   for index in range(len(dets))}
    return resp,integration_handoff(req,resp,assignments),counts


def build_request_from_frames(*, conversation_id: str, sequence_id: str,
    request_id: str, image_bytes: dict[int, bytes], boxes: dict[int, list[Detection]],
    source_prefix: str = 'frame') -> pb.P2MFeatureRequest:
    """Create a Protobuf request from caller-provided detector boxes and frames.

    Never invent detections, identity IDs, 3D geometry, or camera metadata.
    All model choices remain pinned to the CPU histogram reference.
    """
    _require(set(image_bytes) == set(boxes) and len(image_bytes)>0,
             'INPUT_FRAME_SET_MISMATCH')
    _require(_id(source_prefix),'INVALID_SOURCE_PREFIX')
    req=pb.P2MFeatureRequest(schema_version=1,conversation_id=conversation_id,
       sequence_id=sequence_id,request_id=request_id,research_only=True,
       grants_authority=False)
    req.model.CopyFrom(histogram_model())
    for frame in sorted(boxes):
        _require(type(frame) is int,'INVALID_FRAME_NUMBER')
        f=req.frames.add(frame=frame,encoded_image=image_bytes[frame],
            source_ref=f'{source_prefix}.{frame}')
        for det in boxes[frame]:
            _require(isinstance(det,Detection) and det.frame == frame,
                     'DETECTION_FRAME_MISMATCH')
            f.boxes.add(x=det.x,y=det.y,w=det.w,h=det.h)
    _validate_request(req)
    return req
