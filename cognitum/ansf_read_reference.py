"""C06/P3 schema-faithful ANSF book read *reference*, not a Lu host adapter.

Only a Lu-authenticated, host-owned, query-only SQLite connection and a
synchronized read transaction may be supplied. This module never opens a
path, constructs a grant, migrates ANSF or registers a model tool. Python
runtime objects and a query_only pragma are NOT a security boundary; the
native Rust host must eventually provide that boundary and fence publishing.

Mappings from Lu ANSF (ansf.rs / ansf_revisions.rs pinned in the P3 doc):
  SourceRef.entry_id = original immutable SQLite entry id (decimal string)
  SourceRef.revision_id = exact source entry id (decimal string)
  SourceRef.chapter_id = original/current chapter id (decimal string)
  current_revision_id = newest source entry id in an immutable edit chain
FTS5 ranks hits but cannot authorize or supersede edited content. Every
candidate passes P1 canonical verification before a host-held publication.
"""
import hashlib
import re
import sqlite3

from .memory_evidence import (
    _context_valid, _id, _query_valid, _source, _strict_decode, encode_frame,
    QUERY_FRAME_LIMIT, MAX_RECORDS, MAX_CANONICAL_BYTES,
    CANDIDATE_FRAME_LIMIT, SNAPSHOT_FRAME_LIMIT, MAX_EXCERPT_BYTES,
    SCHEMA_VERSION,
)
from .proto import memory_pb2 as pb

# SQL statements contain only trusted, static identifiers, never user strings.
_HIT_SQL = """
SELECT e.id,e.chapter_id
FROM ansf_entries_fts AS f
JOIN ansf_entries AS e ON e.id=f.rowid
WHERE ansf_entries_fts MATCH ? AND e.session_id=?
  AND (?=1 OR NOT EXISTS(
       SELECT 1 FROM ansf_entry_edits AS link
       WHERE link.session_id=e.session_id AND link.previous_entry_id=e.id))
ORDER BY bm25(ansf_entries_fts),e.id
LIMIT ?
"""
_ENTRY_SQL = """
SELECT id,session_id,chapter_id,message_id,role,content
FROM ansf_entries WHERE session_id=? AND id=?
"""
_EDITS_SQL = """
SELECT original_entry_id,previous_entry_id,revised_entry_id,revision_number,origin
FROM ansf_entry_edits WHERE session_id=? AND original_entry_id=?
ORDER BY revision_number
"""
_ROOT_SQL = """
SELECT original_entry_id FROM ansf_entry_edits
WHERE session_id=? AND revised_entry_id=?
"""


class _BadAnsf(Exception):
    pass


def _literal_fts_phrase(value: str):
    """Tokenize as *data*: never allow FTS operators/column filters or wildcards."""
    words = re.findall(r"\w+", value, flags=re.UNICODE)
    if not words:
        return None
    # FTS tokenization (case-folding, stemming options) is not guaranteed to
    # equal Python substrings; the canonical excerpt still comes from source.
    return " AND ".join('"' + w.replace('"', '""') + '"' for w in words)


def _entry(conn, session, entry_id):
    data = conn.execute(_ENTRY_SQL, (session, entry_id)).fetchone()
    if data is None or data[0] != entry_id or data[1] != session or data[2] < 1:
        raise _BadAnsf("missing/mismatched entry")
    return data


def _head_and_root(conn, session, hit_id):
    original = conn.execute(_ROOT_SQL, (session, hit_id)).fetchone()
    root_id = original[0] if original else hit_id
    root = _entry(conn, session, root_id)
    if root[3].startswith("ansf-revision:"):
        raise _BadAnsf("unlinked/synthetic revision root")
    revisions = conn.execute(_EDITS_SQL, (session, root_id)).fetchall()
    current_id = root_id
    selected = {root_id: root}
    for number, (original_id, prior_id, revised_id, sequence, origin) in enumerate(revisions, 1):
        if (original_id != root_id or prior_id != current_id or sequence != number or
                revised_id in selected or origin not in ("verified_user", "import_observed")):
            raise _BadAnsf("corrupt revision chain")
        revised = _entry(conn, session, revised_id)
        if revised[2] != root[2] or revised[4] != root[4]:
            raise _BadAnsf("cross-chapter/role revision")
        selected[revised_id] = revised
        current_id = revised_id
    if hit_id not in selected:
        raise _BadAnsf("unlinked source entry")
    return root_id, current_id, selected[hit_id]


def _utf8_excerpt(raw: bytes, max_bytes=512):
    # A UTF-8-aligned bounded prefix; independent of hostile FTS hint offsets.
    excerpt = raw[:min(len(raw), max_bytes)].decode("utf-8", errors="ignore").encode("utf-8")
    if not excerpt:
        return None
    return 0, excerpt


def select_ansf_fts_frames(query_frame, conn, *, context, session_id,
                           tombstoned_roots):
    """Produce (status, candidate_frame, snapshot_frame) under a HOST lease.

    The host authenticates the profile/book ownership and caller, owns this
    connection, provides epoch-bound context and tombstone policy, and holds
    its read/revocation fence. Calls outside that host boundary are NOT safe
    with private user data. Output frames alone are never proof of authority.

    Requires sqlite3.Connection already inside a read transaction and
    PRAGMA query_only=ON. No filesystem paths, writes or network. All errors
    are opaque and fail closed, with no source bytes in exceptions/statuses.
    """
    if (not _context_valid(context) or not context.active or
            not _id(session_id) or session_id not in context.authorized_sessions or
            type(tombstoned_roots) is not frozenset or
            not all(type(x) is int and x > 0 for x in tombstoned_roots)):
        return pb.DENIED, None, None
    if type(query_frame) is bytes and len(query_frame) > QUERY_FRAME_LIMIT:
        return pb.LIMIT, None, None
    try:
        query = _strict_decode(query_frame, pb.MemoryQuery, QUERY_FRAME_LIMIT)
    except ValueError:
        return pb.INVALID, None, None
    if query.schema_version != SCHEMA_VERSION:
        return pb.UNSUPPORTED, None, None
    if not _query_valid(query):
        return pb.INVALID, None, None
    if query.include_historical and not context.allow_historical:
        return pb.DENIED, None, None
    if any(ref.session_id != session_id for ref in query.exact_sources):
        return pb.DENIED, None, None
    match = _literal_fts_phrase(query.literal_query)
    if match is None:
        return pb.INVALID, None, None
    if type(conn) is not sqlite3.Connection or not conn.in_transaction:
        return pb.UNAVAILABLE, None, None
    try:
        if conn.execute("PRAGMA query_only").fetchone()[0] != 1:
            return pb.UNAVAILABLE, None, None
        # Fail closed if book session is absent. Scope/ownership is separately
        # established by Lu's host, never by a row or caller-selected path.
        if conn.execute("SELECT 1 FROM ansf_sessions WHERE id=?", (session_id,)).fetchone() is None:
            return pb.UNAVAILABLE, None, None
        raw_hits = conn.execute(_HIT_SQL, (match, session_id, int(query.include_historical), MAX_RECORDS)).fetchall()
        exact = {(r.session_id, r.chapter_id, r.entry_id, r.revision_id)
                 for r in query.exact_sources}
        batch = pb.CandidateBatch(schema_version=SCHEMA_VERSION)
        snapshot = pb.CanonicalSnapshot(schema_version=SCHEMA_VERSION,
                                        snapshot_id=context.snapshot_id,
                                        scope_id=context.scope_id,
                                        authorization_epoch=context.authorization_epoch,
                                        index_epoch=context.index_epoch,
                                        consistent=True, grant_active=True)
        seen = set()
        for hit_id, chapter_id in raw_hits:
            root_id, current_id, row = _head_and_root(conn, session_id, hit_id)
            if root_id in tombstoned_roots:
                # A tombstone never exposes source text, metadata, or hit hints.
                # A named exact source will instead fail closed as deleted.
                if any(int(r.entry_id) == root_id for r in query.exact_sources
                       if r.entry_id.isdecimal()):
                    return pb.DELETED, None, None
                continue
            if not query.include_historical and hit_id != current_id:
                # Old FTS hits MUST NOT produce citations for superseded text.
                continue
            if chapter_id != row[2]:
                raise _BadAnsf("chapter mismatch")
            source = (session_id, str(row[2]), str(root_id), str(hit_id))
            if source in seen or (exact and source not in exact):
                continue
            seen.add(source)
            raw = row[5].encode("utf-8", errors="strict")
            if len(raw) > MAX_CANONICAL_BYTES:
                return pb.LIMIT, None, None
            excerpt = _utf8_excerpt(raw, min(512, MAX_EXCERPT_BYTES))
            if excerpt is None:
                continue
            start, excerpt_bytes = excerpt
            rec = snapshot.records.add(current_revision_id=str(current_id),
                                       authorized=True, deleted=False,
                                       canonical_text=row[5])
            rec.source.session_id, rec.source.chapter_id, rec.source.entry_id, rec.source.revision_id = source
            hit = batch.candidates.add(content_sha256=hashlib.sha256(raw).hexdigest(),
                                       scope_id=context.scope_id,
                                       snapshot_id=context.snapshot_id,
                                       start_utf8_byte=start,
                                       length_utf8_byte=len(excerpt_bytes))
            hit.source.CopyFrom(rec.source)
            if len(batch.candidates) >= query.max_results:
                break
        candidate_frame = encode_frame(batch)
        snapshot_frame = encode_frame(snapshot)
        if len(candidate_frame) > CANDIDATE_FRAME_LIMIT or len(snapshot_frame) > SNAPSHOT_FRAME_LIMIT:
            return pb.LIMIT, None, None
        return pb.VERIFIED, candidate_frame, snapshot_frame
    except (sqlite3.Error, _BadAnsf, UnicodeError, ValueError, TypeError, OverflowError):
        return pb.UNAVAILABLE, None, None


def select_ansf_citation_snapshot(lookup_frame, conn, *, context, session_id,
                                  tombstoned_roots):
    """Return a host-read status and canonical ANSF snapshot for ONE locator.

    A citation is never authority; only use this while holding the same
    authenticated read/revocation fence as search. The returned snapshot must
    be fed to verify_citation_lookup before synchronous fenced publication.
    """
    from .memory_host_gate import CITATION_FRAME_LIMIT  # avoids import cycle
    if (not _context_valid(context) or not context.active or
            not _id(session_id) or session_id not in context.authorized_sessions or
            type(tombstoned_roots) is not frozenset or
            not all(type(x) is int and x > 0 for x in tombstoned_roots)):
        return pb.DENIED, None
    if type(lookup_frame) is bytes and len(lookup_frame) > CITATION_FRAME_LIMIT:
        return pb.LIMIT, None
    try:
        lookup = _strict_decode(lookup_frame, pb.CitationLookup, CITATION_FRAME_LIMIT)
    except ValueError:
        return pb.INVALID, None
    if lookup.schema_version != SCHEMA_VERSION:
        return pb.UNSUPPORTED, None
    from .memory_host_gate import _HANDLE
    from .memory_evidence import _DIGEST
    if not (_source(lookup.source) and _id(lookup.request_id) and
            len(lookup.request_id) <= 64 and _HANDLE.fullmatch(lookup.citation_handle) and
            _id(lookup.snapshot_id) and _DIGEST.fullmatch(lookup.content_sha256) and
            1 <= lookup.length_utf8_byte <= MAX_EXCERPT_BYTES and
            lookup.start_utf8_byte <= MAX_CANONICAL_BYTES):
        return pb.INVALID, None
    if lookup.source.session_id != session_id:
        return pb.DENIED, None
    if lookup.snapshot_id != context.snapshot_id:
        return pb.STALE, None
    if type(conn) is not sqlite3.Connection or not conn.in_transaction:
        return pb.UNAVAILABLE, None
    # Canonical decimal entry IDs are minted by Lu's SQLite, never by a model.
    def _positive_decimal(value):
        return value.isascii() and value.isdecimal() and value[0] != "0" and int(value) > 0
    if not all(_positive_decimal(v) for v in (lookup.source.entry_id,
                                                 lookup.source.chapter_id,
                                                 lookup.source.revision_id)):
        return pb.INVALID, None
    try:
        if conn.execute("PRAGMA query_only").fetchone()[0] != 1:
            return pb.UNAVAILABLE, None
        root_id = int(lookup.source.entry_id)
        hit_id = int(lookup.source.revision_id)
        actual_root, current_id, row = _head_and_root(conn, session_id, hit_id)
        if actual_root != root_id or str(row[2]) != lookup.source.chapter_id:
            return pb.STALE, None
        if root_id in tombstoned_roots:
            return pb.DELETED, None
        content = row[5]
        if len(content.encode("utf-8", errors="strict")) > MAX_CANONICAL_BYTES:
            return pb.LIMIT, None
        snap = pb.CanonicalSnapshot(schema_version=SCHEMA_VERSION,
                                    snapshot_id=context.snapshot_id,
                                    scope_id=context.scope_id,
                                    authorization_epoch=context.authorization_epoch,
                                    index_epoch=context.index_epoch,
                                    grant_active=True, consistent=True)
        rec = snap.records.add(current_revision_id=str(current_id),
                               authorized=True, deleted=False, canonical_text=content)
        rec.source.CopyFrom(lookup.source)
        frame = encode_frame(snap)
        if len(frame) > SNAPSHOT_FRAME_LIMIT:
            return pb.LIMIT, None
        return pb.VERIFIED, frame
    except (sqlite3.Error, _BadAnsf, UnicodeError, ValueError, TypeError, OverflowError):
        return pb.UNAVAILABLE, None
