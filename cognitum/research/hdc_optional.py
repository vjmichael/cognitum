"""C08: bounded, deterministic BSC role/entity binding, experimental only.

Derived candidate IDs are NOT authorized citations. Requires caller-supplied
fresh canonical snapshot and an equal versioned index snapshot. No Lu access.
Original BSC concept and archived K4 models were examined, NOT bulk imported.
"""
from __future__ import annotations
import hashlib
import re
from google.protobuf.message import DecodeError
from cognitum.proto import research_optional_pb2 as pb

ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,79}\Z', re.ASCII)
MAX_BYTES = 16384
DIM = 256


def _parse(cls, raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError('INVALID_FRAME_SIZE')
    obj=cls()
    try: obj.ParseFromString(raw)
    except DecodeError as exc: raise ValueError('MALFORMED_PROTOBUF') from exc
    known=cls();known.CopyFrom(obj);known.DiscardUnknownFields()
    if known != obj or obj.SerializeToString(deterministic=True) != raw:
        raise ValueError('NONCANONICAL_PROTOBUF')
    return obj


def _atomic(label, value):
    # Type-separated domain tags avoid cross-role aliasing.
    return int.from_bytes(hashlib.sha256(b'cognitum-C08-BSC-v1\0' + label + b'\0' + value.encode('ascii')).digest(),'big')


def bound(role, entity):
    if not ID.fullmatch(role) or not ID.fullmatch(entity):
        raise ValueError('INVALID_RELATION_TERM')
    return _atomic(b'role',role) ^ _atomic(b'entity',entity)


def query(raw: bytes) -> bytes:
    req=_parse(pb.HdcQuery,raw)
    if req.schema_version != 1 or not ID.fullmatch(req.source_snapshot_id):
        raise ValueError('INVALID_HDC_REQUEST')
    if req.index_snapshot_id != req.source_snapshot_id:
        raise ValueError('STALE_INDEX_SNAPSHOT')
    if not 1 <= req.top_k <= 8 or not 1 <= len(req.records) <= 32:
        raise ValueError('HDC_RESOURCE_LIMIT')
    probe=bound(req.role,req.entity)
    seen=set();scores=[]
    for item in req.records:
        if not ID.fullmatch(item.candidate_id) or item.candidate_id in seen:
            raise ValueError('INVALID_OR_DUPLICATE_CANDIDATE')
        seen.add(item.candidate_id)
        score=(probe^bound(item.role,item.entity)).bit_count()
        scores.append((score,item.candidate_id))
    scores.sort(key=lambda x:(x[0],x[1]))
    result=pb.HdcCandidates(source_snapshot_id=req.source_snapshot_id,
        candidate_ids=[id for _,id in scores[:req.top_k]],
        hamming_distance=[distance for distance,_ in scores[:req.top_k]],
        assurance='BSC_RESEARCH_CANDIDATES_NOT_GROUND_TRUTH')
    out=result.SerializeToString(deterministic=True)
    if len(out)>MAX_BYTES:raise ValueError('OUTPUT_TOO_LARGE')
    return out
