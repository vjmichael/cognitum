"""C06/P2 read-only, linear *literal* candidate baseline over injected snapshots.

This is a deliberately simple comparator, not semantic search, an ANSF
adapter, an index persisted to disk, a model-facing tool or a permissions
source. Only call while holding the host's authenticated source read lease.
The returned protobuf contains source/digest/ranges but NEVER source text.
The host-fenced caller MUST verify candidates against its canonical snapshot
before disclosure. Exact unicode matching is case-sensitive by design; Lu's
existing FTS5/BM25 is the intended later production lexical comparator.
"""
import hashlib

from .memory_evidence import (
    _context_valid, _key, _query_valid, _source, _strict_decode,
    CANDIDATE_FRAME_LIMIT, MAX_CANONICAL_BYTES, MAX_EXCERPT_BYTES,
    MAX_RECORDS, QUERY_FRAME_LIMIT, SCHEMA_VERSION, SNAPSHOT_FRAME_LIMIT,
    encode_frame,
)
from .proto import memory_pb2 as pb


def select_literal_candidates(query_frame, snapshot_frame, *, context):
    """Return (typed RetrievalStatus, protobuf candidate-frame or None).

    Unauthorized/deleted records never contribute hints. No ranking or
    measured retrieval-quality gain is claimed. Offsets are UTF-8 bytes, with
    exact Unicode boundaries and deterministic current-first selection.
    """
    if not _context_valid(context) or not context.active:
        return pb.DENIED, None
    if (type(query_frame) is bytes and len(query_frame) > QUERY_FRAME_LIMIT
            or type(snapshot_frame) is bytes and len(snapshot_frame) > SNAPSHOT_FRAME_LIMIT):
        return pb.LIMIT, None
    try:
        query = _strict_decode(query_frame, pb.MemoryQuery, QUERY_FRAME_LIMIT)
        snap = _strict_decode(snapshot_frame, pb.CanonicalSnapshot, SNAPSHOT_FRAME_LIMIT)
    except ValueError:
        return pb.INVALID, None
    if query.schema_version != SCHEMA_VERSION or snap.schema_version != SCHEMA_VERSION:
        return pb.UNSUPPORTED, None
    if not _query_valid(query):
        return pb.INVALID, None
    if snap.scope_id != context.scope_id or snap.authorization_epoch != context.authorization_epoch or not snap.grant_active:
        return pb.DENIED, None
    if (snap.snapshot_id != context.snapshot_id or not snap.consistent
            or snap.index_epoch != context.index_epoch):
        return pb.STALE, None
    if query.include_historical and not context.allow_historical:
        return pb.DENIED, None
    if len(snap.records) > MAX_RECORDS:
        return pb.LIMIT, None
    exact = {_key(ref) for ref in query.exact_sources}
    hits = []
    for r in snap.records:
        if not _source(r.source) or not r.current_revision_id:
            return pb.INVALID, None
        if r.source.session_id not in context.authorized_sessions or not r.authorized or r.deleted:
            continue
        if r.source.revision_id != r.current_revision_id and not query.include_historical:
            continue
        key = _key(r.source)
        if exact and key not in exact:
            continue
        raw = r.canonical_text.encode("utf-8")
        if len(raw) > MAX_CANONICAL_BYTES:
            return pb.LIMIT, None
        position = r.canonical_text.find(query.literal_query)
        if position < 0:
            continue
        # Use codepoint boundaries before calculating byte offsets. No
        # casefold expansion, tokenization or FTS MATCH expression is used.
        start_char = max(0, position - 24)
        end_char = min(len(r.canonical_text), position + len(query.literal_query) + 48)
        excerpt = r.canonical_text[start_char:end_char]
        while len(excerpt.encode("utf-8")) > MAX_EXCERPT_BYTES:
            end_char -= 1
            excerpt = r.canonical_text[start_char:end_char]
        if not excerpt:
            continue
        start_byte = len(r.canonical_text[:start_char].encode("utf-8"))
        hits.append((r.source.revision_id != r.current_revision_id, key,
                     hashlib.sha256(raw).hexdigest(), start_byte,
                     len(excerpt.encode("utf-8"))))
    hits.sort(key=lambda item: (item[0], item[1]))
    out = pb.CandidateBatch(schema_version=SCHEMA_VERSION)
    for _, key, digest, start, length in hits[:query.max_results]:
        row = out.candidates.add(content_sha256=digest, snapshot_id=context.snapshot_id,
                                 scope_id=context.scope_id,
                                 start_utf8_byte=start, length_utf8_byte=length)
        row.source.session_id, row.source.chapter_id, row.source.entry_id, row.source.revision_id = key
    frame = encode_frame(out)
    if len(frame) > CANDIDATE_FRAME_LIMIT:
        return pb.LIMIT, None
    return pb.VERIFIED, frame
