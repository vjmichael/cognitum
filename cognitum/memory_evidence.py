"""C06/P1 synthetic, fail-closed verification of Protobuf memory evidence.

This is a pure offline reference implementation. It does not read ANSF or
other user data, grant identity, open files, register a CE, or expose a model
operation. The caller MUST obtain ``TrustedReadContext`` and the snapshot
from a future authenticated Lu host adapter; arbitrary Protobuf snapshots
and constructed contexts are not proof of authorization.

Indexed candidates are untrusted offsets and digests. Only exact bytes from
canonical records in the host-provided snapshot can become reply excerpts.
A citation handle is a non-secret locator, NOT a capability or access token;
Lu must reauthorize and recheck it when expanding citations.
"""
from dataclasses import dataclass
import hashlib
import hmac
import re

from google.protobuf.message import DecodeError
from .proto import memory_pb2 as pb

SCHEMA_VERSION = 1
QUERY_FRAME_LIMIT = 4096
CANDIDATE_FRAME_LIMIT = 16 * 1024
SNAPSHOT_FRAME_LIMIT = 256 * 1024
REPLY_FRAME_LIMIT = 32 * 1024
MAX_CANONICAL_BYTES = 16 * 1024
MAX_EXCERPT_BYTES = 1024
MAX_CANDIDATES = 64
MAX_RECORDS = 64
MAX_RESULTS = 20
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z", re.ASCII)
_DIGEST = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)


@dataclass(frozen=True, slots=True)
class TrustedReadContext:
    """Host-owned precondition, NOT constructible authority for any real data.

    This type is only a synthetic dependency-injection boundary for P1. The
    planned Lu implementation must authenticate scope and sessions separately,
    then obtain fresh grant and index epochs under a host-controlled lock.
    """
    scope_id: str
    snapshot_id: str
    authorization_epoch: int
    index_epoch: int
    authorized_sessions: frozenset[str]
    allow_historical: bool = False
    active: bool = True


def _strict_decode(blob, message_type, limit):
    if type(blob) is not bytes or not 0 < len(blob) <= limit:
        raise ValueError("missing or oversized protobuf frame")
    obj = message_type()
    try:
        obj.ParseFromString(blob)
    except DecodeError as err:
        raise ValueError("invalid protobuf encoding") from err
    cleaned = message_type()
    cleaned.CopyFrom(obj)
    cleaned.DiscardUnknownFields()
    if cleaned != obj or obj.SerializeToString(deterministic=True) != blob:
        raise ValueError("unknown or noncanonical protobuf fields")
    return obj


def _id(value):
    return type(value) is str and bool(_ID.fullmatch(value))


def _source(ref):
    return all(_id(getattr(ref, name)) for name in
               ("session_id", "chapter_id", "entry_id", "revision_id"))


def _key(ref):
    return (ref.session_id, ref.chapter_id, ref.entry_id, ref.revision_id)


def _query_valid(query):
    if not (_id(query.request_id) and len(query.request_id) <= 64 and
            1 <= query.max_results <= MAX_RESULTS and
            len(query.exact_sources) <= MAX_RESULTS):
        return False
    try:
        text = query.literal_query.encode("utf-8", errors="strict")
    except UnicodeError:
        return False
    if not 1 <= len(text) <= 256 or any(ord(ch) < 32 or ord(ch) == 127
                                       for ch in query.literal_query):
        return False
    exact = [_key(ref) for ref in query.exact_sources]
    return all(_source(ref) for ref in query.exact_sources) and len(set(exact)) == len(exact)


def _context_valid(ctx):
    return (type(ctx) is TrustedReadContext and _id(ctx.scope_id) and
            _id(ctx.snapshot_id) and type(ctx.authorization_epoch) is int and
            ctx.authorization_epoch > 0 and type(ctx.index_epoch) is int and
            ctx.index_epoch > 0 and type(ctx.active) is bool and
            type(ctx.allow_historical) is bool and
            type(ctx.authorized_sessions) is frozenset and
            bool(ctx.authorized_sessions) and
            all(_id(session) for session in ctx.authorized_sessions))


def _citation(context, source, digest, start, length):
    # Domain-separate and length-prefix all fields to avoid ambiguous tuples.
    parts = ("cognitum.C06.P1.citation", context.scope_id,
             context.snapshot_id, str(context.authorization_epoch),
             *(_key(source)), digest, str(start), str(length))
    payload = b"".join(len(p.encode()).to_bytes(4, "big") + p.encode()
                       for p in parts)
    return "ref_" + hashlib.sha256(payload).hexdigest()


def _reply(query, status, evidence=()):
    answer = pb.RetrievalReply(schema_version=SCHEMA_VERSION,
                               request_id=query.request_id if _id(query.request_id) and
                               len(query.request_id) <= 64 else "", status=status)
    answer.evidence.extend(evidence)
    if answer.ByteSize() > REPLY_FRAME_LIMIT:
        answer.ClearField("evidence")
        answer.status = pb.LIMIT
    return answer


def verify_candidate_batch(query_frame, candidates_frame, snapshot_frame, *, context):
    """Verify synthetic candidate references, returning a typed Protobuf reply.

    A failure returns NO evidence (including when some earlier candidates were
    valid); bytes from rejected canonical records never enter result errors.
    Inputs are bounded, strictly encoded native Protobuf, not JSON. The host
    context and snapshot must be trusted by caller provenance; this function
    does not confer such provenance, and must not be used as an auth gateway.
    """
    fallback = pb.MemoryQuery()
    if not _context_valid(context) or not context.active:
        return _reply(fallback, pb.DENIED)
    if type(query_frame) is bytes and len(query_frame) > QUERY_FRAME_LIMIT:
        return _reply(fallback, pb.LIMIT)
    try:
        query = _strict_decode(query_frame, pb.MemoryQuery, QUERY_FRAME_LIMIT)
    except ValueError:
        return _reply(fallback, pb.INVALID)
    if query.schema_version != SCHEMA_VERSION:
        return _reply(query, pb.UNSUPPORTED)
    if not _query_valid(query):
        return _reply(query, pb.INVALID)
    if snapshot_frame is None or candidates_frame is None:
        return _reply(query, pb.UNAVAILABLE)
    if ((type(candidates_frame) is bytes and len(candidates_frame) > CANDIDATE_FRAME_LIMIT)
            or (type(snapshot_frame) is bytes and len(snapshot_frame) > SNAPSHOT_FRAME_LIMIT)):
        return _reply(query, pb.LIMIT)
    try:
        batch = _strict_decode(candidates_frame, pb.CandidateBatch, CANDIDATE_FRAME_LIMIT)
        snapshot = _strict_decode(snapshot_frame, pb.CanonicalSnapshot, SNAPSHOT_FRAME_LIMIT)
    except ValueError:
        return _reply(query, pb.INVALID)
    if batch.schema_version != SCHEMA_VERSION or snapshot.schema_version != SCHEMA_VERSION:
        return _reply(query, pb.UNSUPPORTED)
    if not snapshot.grant_active:
        return _reply(query, pb.DENIED)
    if snapshot.scope_id != context.scope_id or snapshot.authorization_epoch != context.authorization_epoch:
        return _reply(query, pb.DENIED)
    if (not snapshot.consistent or snapshot.snapshot_id != context.snapshot_id
            or snapshot.index_epoch != context.index_epoch):
        return _reply(query, pb.STALE)
    if len(batch.candidates) > MAX_CANDIDATES or len(snapshot.records) > MAX_RECORDS:
        return _reply(query, pb.LIMIT)
    if query.include_historical and not context.allow_historical:
        return _reply(query, pb.DENIED)

    records = {}
    current_revisions = {}
    for record in snapshot.records:
        if not _source(record.source) or not _id(record.current_revision_id):
            return _reply(query, pb.INVALID)
        key = _key(record.source)
        base = key[:3]
        if key in records:
            return _reply(query, pb.INVALID)
        if base in current_revisions and current_revisions[base] != record.current_revision_id:
            return _reply(query, pb.STALE)
        current_revisions[base] = record.current_revision_id
        try:
            raw = record.canonical_text.encode("utf-8", errors="strict")
        except UnicodeError:
            return _reply(query, pb.INVALID)
        if len(raw) > MAX_CANONICAL_BYTES:
            return _reply(query, pb.LIMIT)
        # For inaccessible or deleted entries the host must omit the bytes.
        # This also limits accidental logs/serialization of revoked payloads.
        if (not record.authorized or record.deleted) and raw:
            return _reply(query, pb.INVALID)
        records[key] = (record, raw)

    requested = {_key(ref) for ref in query.exact_sources}
    seen = set()
    result = []
    for candidate in batch.candidates:
        if not _source(candidate.source):
            return _reply(query, pb.INVALID)
        key = _key(candidate.source)
        if key in seen or (requested and key not in requested):
            return _reply(query, pb.INVALID)
        seen.add(key)
        if candidate.scope_id != context.scope_id or candidate.source.session_id not in context.authorized_sessions:
            return _reply(query, pb.DENIED)
        if candidate.snapshot_id != context.snapshot_id:
            return _reply(query, pb.STALE)
        item = records.get(key)
        if item is None:
            return _reply(query, pb.STALE)
        record, raw = item
        if not record.authorized:
            return _reply(query, pb.DENIED)
        if record.deleted:
            return _reply(query, pb.DELETED)
        is_current = candidate.source.revision_id == record.current_revision_id
        if not is_current and (not query.include_historical or not context.allow_historical):
            return _reply(query, pb.STALE)
        if not _DIGEST.fullmatch(candidate.content_sha256):
            return _reply(query, pb.INVALID)
        digest = hashlib.sha256(raw).hexdigest()
        if not hmac.compare_digest(candidate.content_sha256, digest):
            return _reply(query, pb.STALE)
        start, length = candidate.start_utf8_byte, candidate.length_utf8_byte
        if not 1 <= length <= MAX_EXCERPT_BYTES or start + length > len(raw):
            return _reply(query, pb.LIMIT)
        try:
            excerpt = raw[start:start + length].decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            return _reply(query, pb.INVALID)
        if len(result) < query.max_results:
            out = pb.MemoryEvidence(
                revision_kind=pb.CURRENT if is_current else pb.HISTORICAL,
                content_sha256=digest, snapshot_id=context.snapshot_id,
                citation_handle=_citation(context, candidate.source, digest, start, length),
                start_utf8_byte=start, excerpt=excerpt)
            out.source.CopyFrom(candidate.source)
            result.append(out)
    return _reply(query, pb.VERIFIED, result)


def encode_frame(message):
    """Encode a caller-created Protobuf fixture; never acts as authorization."""
    return message.SerializeToString(deterministic=True)
