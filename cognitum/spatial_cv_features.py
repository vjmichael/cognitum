"""C15 opt-in, in-memory OpenCV appearance features from host-supplied bytes.

No camera/filesystem acquisition, pretrained model weights, model-generated
code, remote decoding or automatic host permission. Trusted Lu host MUST
authorize the particular frame and source before calling this adapter. PIL
checks dimensions before pixel decode; OpenCV computes an established color
histogram, NOT a calibrated identity embedding or object detector.
"""
from hashlib import sha256
from io import BytesIO
from math import isfinite
from .spatial_appearance_core import Appearance

MAX_ENCODED_BYTES=8*1024*1024
MAX_PIXELS=4096*4096
ENCODER_ID="opencv_hsv_hist_8x4x4_v1"
ENCODER_SHA256=sha256(ENCODER_ID.encode("ascii")).hexdigest()


def from_frame(frame_bytes:bytes,*, source_id:str, observation_id:str,
               detection_id:str, frame_index:int,
               box:tuple[int,int,int,int],
               host_admitted:bool=False)->Appearance:
    """Stateless descriptor. Never interpret caller Boolean as Lu authorization."""
    if host_admitted is not True:
        raise PermissionError("host-origin verified image admission required")
    if type(frame_bytes) is not bytes or not 1<=len(frame_bytes)<=MAX_ENCODED_BYTES:
        raise ValueError("invalid encoded image size")
    if (type(box) is not tuple or len(box)!=4
            or any(type(v) is not int for v in box)
            or any(v<0 for v in box)):
        raise ValueError("invalid pixel crop")
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
            raise ValueError("unsupported or oversized frame")
        x,y,w,h=box
        if not w or not h or x+w>im.width or y+h>im.height:
            raise ValueError("crop outside image bounds")
        rgb=np.asarray(im.convert("RGB").crop((x,y,x+w,y+h)),dtype=np.uint8)
    except (OSError,UnidentifiedImageError,ValueError) as exc:
        raise ValueError("invalid encoded image") from exc
    hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV)
    histogram=cv2.calcHist([hsv],[0,1,2],None,[8,4,4],[0,180,0,256,0,256]).reshape(-1)
    norm=float(np.linalg.norm(histogram))
    if not isfinite(norm) or norm<=0:
        raise ValueError("invalid feature crop")
    normalized=tuple(float(v) for v in histogram/norm)
    descriptor=Appearance(detection_id,normalized,ENCODER_ID,ENCODER_SHA256,
                          source_id,observation_id,frame_index,
                          sha256(frame_bytes).hexdigest())
    # The image bytes are intentionally not retained by this return value.
    from .spatial_appearance_core import _identifier
    if (not all(_identifier(v) for v in (source_id,observation_id,detection_id))
            or type(frame_index) is not int or frame_index<0):
        raise ValueError("invalid feature provenance")
    return descriptor
