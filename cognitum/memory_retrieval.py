"""C06: pure, host-owned canonical-record retrieval reference.

This module NEVER opens a database, grants access, or mutates memory. Lu supplies
an already-authorized, revision-consistent snapshot of canonical ANSF records.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
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
        if self.revision < 1:
            raise RetrievalError("revision must be positive")
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
        if not self.scope or not 1 <= self.evidence_limit <= 100:
            raise RetrievalError("invalid scope or evidence bound")
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


def _terms(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.casefold(), re.UNICODE))


def retrieve(
    records: Iterable[MemoryEvidence],
    query: MemoryQuery,
    *,
    snapshot_id: str,
    origin_revision: int,
    expected_origin_revision: int | None = None,
) -> MemoryResult:
    """Fail closed on stale snapshots; score only exact authorized records.

    Caller must enforce host authorization BEFORE supplying the snapshot.
    This secondary scope check is defense in depth, not an authorization grant.
    """
    if not snapshot_id or origin_revision < 0:
        raise RetrievalError("invalid host snapshot")
    if expected_origin_revision is not None and origin_revision != expected_origin_revision:
        raise RetrievalError("stale canonical snapshot")
    current = query.as_of or datetime.now(timezone.utc)
    matches: list[tuple[int, MemoryEvidence]] = []
    latest_all: dict[str, MemoryEvidence] = {}
    query_terms = _terms(query.text)
    seen: set[tuple[str, int]] = set()
    for record in records:
        if record.revision > origin_revision:
            raise RetrievalError("record newer than declared snapshot")
        key = (record.source_id, record.revision)
        if key in seen:
            raise RetrievalError("duplicate source revision in snapshot")
        seen.add(key)
        if record.access_scope == query.scope:
            old = latest_all.get(record.source_id)
            if old is None or record.revision > old.revision:
                latest_all[record.source_id] = record
        if record.access_scope != query.scope or record.tombstone:
            continue
        if record.valid_from > current or (
            record.valid_until is not None and current >= record.valid_until
        ):
            continue
        if query.subject is not None and record.subject != query.subject:
            continue
        terms = _terms(record.subject + " " + record.text)
        if query_terms and not query_terms.issubset(terms):
            continue
        matches.append((len(query_terms & terms), record))
    # Return the latest revision of each visible source, never an older correction.
    latest: dict[str, tuple[int, MemoryEvidence]] = {}
    for score, record in matches:
        previous = latest.get(record.source_id)
        if previous is None or record.revision > previous[1].revision:
            latest[record.source_id] = (score, record)
    # IMPORTANT: canonical tombstones and future corrections must suppress older
    # versions, including if the newer revision does not match the query.
    filtered = [
        item for source, item in latest.items()
        if source not in latest_all or latest_all[source].revision == item[1].revision
    ]
    filtered.sort(key=lambda item: (-item[0], -item[1].revision, item[1].source_id))
    return MemoryResult(
        tuple(rec for _, rec in filtered[:query.evidence_limit]),
        IndexStatus(snapshot_id, origin_revision, False),
    )
