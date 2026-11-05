"""C15 optional deterministic OpenCV HSV segmentation on supplied frames.

No raw camera/file reads, auto-detection, neural classifier or implicit Lu
permissions. Results are repeatable derived evidence with exact input and
mask digests, not semantic object truth or authenticated sensor provenance.
"""
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from .spatial_cv_features import MAX_ENCODED_BYTES,MAX_PIXELS


@dataclass(frozen=True)
class SegmentationResult:
    status:str
    input_sha256:str
    mask_sha256:str
    encoder_id:str
    source_id:str
    observation_id:str
    frame_index:int
    foreground_pixels:int
    total_pixels:int
    component_count:int
    hsv_lower:tuple[int,int,int]
    hsv_upper:tuple[int,int,int]
    limitations:tuple[str,...]=(
        "threshold_segmentation_not_semantic_object_detection",
        "authorized_frame_claim_must_be_verified_by_host",
        "HSV_color_bounds_caller_selected_not_calibrated",
        "no_Lu_camera_or_filesystem_access",
    )


def segment_color(
    frame_bytes:bytes, *,
    source_id:str,observation_id:str,frame_index:int,
    hsv_lower:tuple[int,int,int],hsv_upper:tuple[int,int,int],
    host_admitted:bool=False,
)->SegmentationResult:
    if host_admitted is not True:
        raise PermissionError("host image admission required")
    if type(frame_bytes) is not bytes or not 1<=len(frame_bytes)<=MAX_ENCODED_BYTES:
        raise ValueError("invalid image size")
    if (type(hsv_lower) is not tuple or type(hsv_upper) is not tuple
            or len(hsv_lower)!=3 or len(hsv_upper)!=3
            or any(type(v) is not int for v in hsv_lower+hsv_upper)
            or any(not 0<=lo<=hi<=end
                   for lo,hi,end in zip(hsv_lower,hsv_upper,(179,255,255)))):
        raise ValueError("unsupported HSV bounds")
    from .spatial_appearance_core import _identifier
    if (not _identifier(source_id) or not _identifier(observation_id)
            or type(frame_index) is not int or frame_index<0):
        raise ValueError("invalid segmentation lineage")
    try:
        import cv2
        import numpy as np
        from PIL import Image,UnidentifiedImageError
    except ImportError as exc:
        raise RuntimeError("opencv_pillow_not_installed") from exc
    try:
        im=Image.open(BytesIO(frame_bytes))
        if (im.format not in ("PNG","JPEG") or im.width<2 or im.height<2
                or im.width*im.height>MAX_PIXELS):
            raise ValueError("unsupported image format or dimensions")
        rgb=np.asarray(im.convert("RGB"),dtype=np.uint8)
    except (OSError,UnidentifiedImageError,Image.DecompressionBombError,
            Image.DecompressionBombWarning,ValueError) as exc:
        raise ValueError("invalid encoded segmentation image") from exc
    hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV)
    mask=cv2.inRange(hsv,np.asarray(hsv_lower,dtype=np.uint8),
                     np.asarray(hsv_upper,dtype=np.uint8))
    count,_,_,_=cv2.connectedComponentsWithStats(mask,connectivity=8)
    total=int(im.width*im.height)
    foreground=int(cv2.countNonZero(mask))
    return SegmentationResult(
        "DERIVED_UNVERIFIED",sha256(frame_bytes).hexdigest(),
        sha256(mask.tobytes()).hexdigest(),
        "opencv_hsv_inrange_connected_components_v1",
        source_id,observation_id,frame_index,foreground,total,max(0,int(count)-1),
        hsv_lower,hsv_upper,
    )
