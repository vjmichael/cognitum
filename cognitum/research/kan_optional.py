"""C09: optional, bounded portable K4 KAN checkpoint inference (NO training).

K4 portable inference is user-owned research, reused with exact source hash.
Only caller-supplied checkpoint bytes with an externally pinned SHA are allowed.
No default registry entry, model advertisement, Lu authority, or OS sandbox.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import io
import json
import re
import zipfile
import numpy as np
from google.protobuf.message import DecodeError
from cognitum.proto import research_optional_pb2 as pb
from .kan_portable import PortableKAN

MAX_FRAME=8192
MAX_ZIP=131072
MAX_UNPACKED=262144
DECIMAL=re.compile(r'-?(?:0|[1-9][0-9]{0,5})(?:\.[0-9]{1,6})?\Z',re.ASCII)
HEX=re.compile(r'[0-9a-f]{64}\Z',re.ASCII)

@dataclass(frozen=True)
class ResearchPolicy:
    research_enabled: bool=False
    expected_checkpoint_sha256: str=''
    # This local flag does not grant Lu authority or attest consent.


def _parse(cls,raw):
    if type(raw) is not bytes or not 0<len(raw)<=MAX_FRAME:raise ValueError('INVALID_FRAME_SIZE')
    req=cls()
    try:req.ParseFromString(raw)
    except DecodeError as e:raise ValueError('INVALID_PROTOBUF') from e
    copy=cls();copy.CopyFrom(req);copy.DiscardUnknownFields()
    if req!=copy or req.SerializeToString(deterministic=True)!=raw:raise ValueError('NONCANONICAL_PROTOBUF')
    return req


def _load(checkpoint:bytes):
    if type(checkpoint) is not bytes or not 0<len(checkpoint)<=MAX_ZIP:
        raise ValueError('CHECKPOINT_SIZE_LIMIT')
    try:
        with zipfile.ZipFile(io.BytesIO(checkpoint)) as z:
            names=z.namelist()
            if (len(names)>28 or len(set(names))!=len(names)
                or any(not n.endswith('.npy') or '/' in n or '\\' in n or '..' in n for n in names)
                or sum(x.file_size for x in z.infolist())>MAX_UNPACKED):
                raise ValueError('UNSAFE_CHECKPOINT_ARCHIVE')
    except (zipfile.BadZipFile,OSError) as e:
        raise ValueError('INVALID_CHECKPOINT_ZIP') from e
    try:
        with np.load(io.BytesIO(checkpoint),allow_pickle=False) as z:
            if '__meta_json__' not in z.files:raise ValueError('MISSING_KAN_METADATA')
            md=json.loads(z['__meta_json__'].item())
            if type(md) is not dict or set(md)!={'format','version','layers'} or md['format']!='zogzoo-kan-v3-npz' or md['version']!=1:
                raise ValueError('INVALID_KAN_METADATA')
            infos=md['layers']
            if type(infos) is not list or not 1<=len(infos)<=2:
                raise ValueError('INVALID_LAYER_COUNT')
            expected={'__meta_json__'};layers=[];width=None
            for i,info in enumerate(infos):
                if (type(info) is not dict or set(info)!={'kind','degree','base','bias'}
                    or info['kind'] not in ('rbf','spline') or type(info['degree']) is not int
                    or not 0<=info['degree']<=3 or type(info['base']) is not bool or type(info['bias']) is not bool):
                    raise ValueError('INVALID_LAYER_DESCRIPTOR')
                required=['grid','spline','mask']+(['base'] if info['base'] else [])+(['bias'] if info['bias'] else [])
                expected.update(f'l{i}_{key}' for key in required)
                lay={key:np.asarray(z[f'l{i}_{key}'],dtype=np.float32) if key in required else None for key in ('grid','spline','mask','base','bias')}
                grid,spline,mask=lay['grid'],lay['spline'],lay['mask']
                if (grid.ndim!=2 or spline.ndim!=3 or mask.ndim!=2 or
                    grid.shape[0]<1 or grid.shape[0]>8 or grid.shape[1]<3 or grid.shape[1]>12 or
                    spline.shape[0]<1 or spline.shape[0]>8 or spline.shape[1]!=grid.shape[0] or
                    spline.shape[2] != (grid.shape[1] if info['kind']=='rbf' else grid.shape[1]-info['degree']-1) or
                    mask.shape != spline.shape[:2] or (width is not None and width != grid.shape[0]) or
                    not np.all(np.diff(grid,axis=1)>0) or
                    (lay['base'] is not None and lay['base'].shape!=mask.shape) or
                    (lay['bias'] is not None and lay['bias'].shape!=(spline.shape[0],))):
                    raise ValueError('INVALID_KAN_ARRAY_SHAPE')
                if any(not np.isfinite(v).all() or np.max(np.abs(v))>1e5 for v in lay.values() if v is not None):
                    raise ValueError('INVALID_KAN_WEIGHTS')
                width=spline.shape[0]
                lay.update(kind=info['kind'],degree=info['degree'])
                layers.append(lay)
            if set(z.files)!=expected:raise ValueError('UNKNOWN_KAN_CHECKPOINT_MEMBERS')
    except (KeyError,TypeError,IndexError,ValueError,json.JSONDecodeError) as e:
        raise ValueError('INVALID_KAN_CHECKPOINT') from e
    return PortableKAN(layers)


def predict(raw:bytes,checkpoint:bytes,policy:ResearchPolicy) -> bytes:
    if type(policy) is not ResearchPolicy or policy.research_enabled is not True:
        raise PermissionError('RESEARCH_DEFAULT_DISABLED')
    req=_parse(pb.KanRequest,raw)
    if (req.schema_version!=1 or not HEX.fullmatch(req.checkpoint_sha256)
        or req.checkpoint_sha256!=policy.expected_checkpoint_sha256
        or hashlib.sha256(checkpoint).hexdigest()!=req.checkpoint_sha256):
        raise ValueError('CHECKPOINT_PIN_MISMATCH')
    if not 1<=len(req.feature_values)<=8 or any(not DECIMAL.fullmatch(v) for v in req.feature_values):
        raise ValueError('INVALID_FEATURES')
    model=_load(checkpoint)
    values=np.asarray([float(x) for x in req.feature_values],dtype=np.float32)
    grid=model.layers[0]['grid']
    if len(values)!=grid.shape[0] or np.any(values<grid[:,0]) or np.any(values>grid[:,-1]):
        raise ValueError('OUT_OF_DISTRIBUTION_OR_FEATURE_WIDTH')
    result=model(values[None,:])
    if result.ndim!=2 or result.shape[0]!=1 or result.shape[1]>8 or not np.isfinite(result).all() or np.any(np.abs(result)>1e6):
        raise ValueError('INVALID_PREDICTION')
    out=pb.KanPrediction(predicted_values=[format(float(v),'.9g') for v in result[0]],
       checkpoint_sha256=req.checkpoint_sha256,method='K4_PORTABLE_KAN_NUMPY_RESEARCH',
       limitation='APPROXIMATE_NO_CALIBRATION_OR_HOST_AUTHORITY')
    payload=out.SerializeToString(deterministic=True)
    if len(payload)>MAX_FRAME:raise ValueError('OUTPUT_TOO_LARGE')
    return payload
