"""C06: derived FTS5 retrieval over host-authorized Lu canonical snapshots.

No durable store or identity authority is created. Indexes are rebuilt in an
ephemeral SQLite connection; no file path or external SQL connection accepted.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
import sqlite3
from typing import Iterable


class RetrievalError(ValueError):
    pass


@dataclass(frozen=True)
class MemoryEvidence:
    source_id: str
    revision: int
    access_scope: str
    subject: str
    text: str
    citation_handle: str
    valid_from: datetime
    valid_until: datetime | None = None
    tombstone: bool = False

    def __post_init__(self) -> None:
        if not all((self.source_id, self.access_scope, self.subject, self.citation_handle)):
            raise RetrievalError("source, scope, subject and citation are required")
        if self.revision < 1 or len(self.source_id) > 256 or len(self.access_scope) > 256:
            raise RetrievalError("invalid identity or revision")
        if len(self.subject) > 512 or len(self.text) > 65536:
            raise RetrievalError("oversized canonical source")
        if self.valid_from.tzinfo is None or (
            self.valid_until is not None and self.valid_until.tzinfo is None
        ):
            raise RetrievalError("times must be timezone-aware")
        if self.valid_until is not None and self.valid_until < self.valid_from:
            raise RetrievalError("invalid validity interval")


@dataclass(frozen=True)
class MemoryQuery:
    scope: str
    text: str = ""
    subject: str | None = None
    evidence_limit: int = 10
    as_of: datetime | None = None

    def __post_init__(self) -> None:
        if not self.scope or len(self.scope) > 256 or not 1 <= self.evidence_limit <= 100:
            raise RetrievalError("invalid scope or evidence bound")
        if len(self.text) > 512 or (self.subject is not None and len(self.subject) > 512):
            raise RetrievalError("oversized query")
        if self.as_of is not None and self.as_of.tzinfo is None:
            raise RetrievalError("as_of must be timezone-aware")


@dataclass(frozen=True)
class IndexStatus:
    snapshot_id: str
    origin_revision: int
    staleness: bool


@dataclass(frozen=True)
class MemoryResult:
    evidence: tuple[MemoryEvidence, ...]
    index_status: IndexStatus


def _terms(text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(re.findall(r"\w+", text.casefold(), re.UNICODE)))


def _canonical_visible(
    records: Iterable[MemoryEvidence], query: MemoryQuery, origin_revision: int
) -> list[MemoryEvidence]:
    # Deduplicate and supersede BEFORE scope/time/query filtering. Otherwise
    # an old accessible revision can leak after a later restricted correction.
    latest: dict[str, MemoryEvidence] = {}
    seen: set[tuple[str, int]] = set()
    for count, record in enumerate(records):
        if count >= 100_000:
            raise RetrievalError("canonical snapshot too large")
        if not isinstance(record, MemoryEvidence):
            raise RetrievalError("invalid canonical record")
        if record.revision > origin_revision:
            raise RetrievalError("record newer than declared snapshot")
        key = (record.source_id, record.revision)
        if key in seen:
            raise RetrievalError("duplicate source revision in snapshot")
        seen.add(key)
        old = latest.get(record.source_id)
        if old is None or old.revision < record.revision:
            latest[record.source_id] = record
    now = query.as_of or datetime.now(timezone.utc)
    return [
        r for r in latest.values()
        if r.access_scope == query.scope
        and not r.tombstone
        and r.valid_from <= now
        and (r.valid_until is None or now < r.valid_until)
        and (query.subject is None or r.subject == query.subject)
    ]


def retrieve(
    records: Iterable[MemoryEvidence],
    query: MemoryQuery,
    *,
    snapshot_id: str,
    origin_revision: int,
    expected_origin_revision: int | None = None,
    ranking: str = "fts5",
) -> MemoryResult:
    """Strict snapshot-scoped retrieval; FTS5 BM25 or exact token baseline.

    Caller must first authorize the host snapshot. A scope string here is
    defense in depth only and cannot grant access.
    """
    if not snapshot_id or len(snapshot_id) > 256 or origin_revision < 0:
        raise RetrievalError("invalid host snapshot")
    if expected_origin_revision is not None and origin_revision != expected_origin_revision:
        raise RetrievalError("stale canonical snapshot")
    if ranking not in ("fts5", "exact"):
        raise RetrievalError("unrecognized retrieval ranking")
    visible = _canonical_visible(records, query, origin_revision)
    terms = _terms(query.text)
    if not terms:
        visible.sort(key=lambda r: (-r.revision, r.source_id))
        selected = visible[:query.evidence_limit]
    elif ranking == "exact":
        selected = [r for r in visible
                    if set(terms).issubset(_terms(r.subject + " " + r.text))]
        selected.sort(key=lambda r: (-r.revision, r.source_id))
        selected = selected[:query.evidence_limit]
    else:
        try:
            with sqlite3.connect(":memory:") as connection:
                connection.execute(
                    "CREATE VIRTUAL TABLE evidence USING fts5(subject, body, tokenize='unicode61')"
                )
                # Source content is inserted only AFTER host scope/time filtering.
                connection.executemany(
                    "INSERT INTO evidence(rowid, subject, body) VALUES (?, ?, ?)",
                    ((i + 1, r.subject, r.text) for i, r in enumerate(visible)),
                )
                # Every term is quoted as an FTS5 literal, never user-provided
                # MATCH syntax. Parameter binding also prevents SQL injection.
                match = " AND ".join('"' + t.replace('"', '""') + '"' for t in terms)
                rows = connection.execute(
                    "SELECT rowid FROM evidence WHERE evidence MATCH ? "
                    "ORDER BY bm25(evidence), rowid LIMIT ?",
                    (match, query.evidence_limit),
                ).fetchall()
                selected = [visible[row[0] - 1] for row in rows]
        except sqlite3.Error as error:
            raise RetrievalError("FTS5 unavailable or retrieval failed") from error
    return MemoryResult(tuple(selected), IndexStatus(snapshot_id, origin_revision, False))
