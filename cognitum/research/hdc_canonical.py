"""C08 candidate verification against an already authorized Lu ANSF snapshot.

HDC ranking is a hint, never evidence of a relation. Every emitted hit is
revalidated against a canonical host snapshot and its current revisions.
No storage, filesystem, SQLite connection, authority, or model tool is created.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from cognitum.proto import research_optional_pb2 as pb
from cognitum.research.hdc_optional import ID, MAX_BYTES, _parse, query


@dataclass(frozen=True)
class CanonicalRelation:
    source_id: str
    revision: int
    scope: str
    role: str
    entity: str
    citation_handle: str
    tombstone: bool = False

    def __post_init__(self):
        if not ID.fullmatch(self.source_id) or not ID.fullmatch(self.role) or not ID.fullmatch(self.entity):
            raise ValueError("INVALID_CANONICAL_RELATION")
        if not self.scope or len(self.scope) > 128 or not self.citation_handle or len(self.citation_handle) > 256:
            raise ValueError("INVALID_CANONICAL_PROVENANCE")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("INVALID_CANONICAL_REVISION")


@dataclass(frozen=True)
class VerifiedHit:
    source_id: str
    revision: int
    citation_handle: str
    role: str
    entity: str


@dataclass(frozen=True)
class VerificationResult:
    snapshot_id: str
    verified: tuple[VerifiedHit, ...]
    rejected: tuple[str, ...]


def verify_hdc_candidates(
    request_wire: bytes,
    candidate_wire: bytes,
    *,
    canonical_records: Iterable[CanonicalRelation],
    authorized_scope: str,
    canonical_snapshot_id: str,
    current_snapshot_id: str,
    required_revision: int,
) -> VerificationResult:
    """Return only exact, current, host-scoped relation evidence.

    The host must authorize and scope the snapshot before supplying records.
    Caller cannot use any HDC candidate ID as a citation or permission token.
    Both the request and candidate output are independently checked.
    """
    if not authorized_scope or not ID.fullmatch(canonical_snapshot_id) or (
        canonical_snapshot_id != current_snapshot_id
    ) or type(required_revision) is not int or required_revision < 1:
        raise ValueError("STALE_OR_UNAUTHORIZED_CANONICAL_SNAPSHOT")
    req = _parse(pb.HdcQuery, request_wire)
    candidate = _parse(pb.HdcCandidates, candidate_wire)
    if req.schema_version != 1 or req.source_snapshot_id != canonical_snapshot_id or (
        req.index_snapshot_id != canonical_snapshot_id
    ):
        raise ValueError("STALE_HDC_INDEX")
    if candidate.source_snapshot_id != canonical_snapshot_id or candidate.grants_authority:
        raise ValueError("UNTRUSTED_HDC_RESULT")
    if candidate.assurance != "BSC_RESEARCH_CANDIDATES_NOT_GROUND_TRUTH":
        raise ValueError("INVALID_HDC_ASSURANCE")
    if not 1 <= req.top_k <= 8 or not 1 <= len(req.records) <= 32:
        raise ValueError("INVALID_HDC_BUDGET")
    if len(candidate.candidate_ids) != len(candidate.hamming_distance) or (
        len(candidate.candidate_ids) > req.top_k
    ) or len(set(candidate.candidate_ids)) != len(candidate.candidate_ids):
        raise ValueError("INVALID_HDC_CANDIDATE_LIST")
    # Independently recompute the complete ranking, instead of believing a
    # model-supplied or worker-supplied ordered candidate list and distances.
    expected = pb.HdcCandidates.FromString(query(request_wire))
    if list(candidate.candidate_ids) != list(expected.candidate_ids) or (
        list(candidate.hamming_distance) != list(expected.hamming_distance)
    ):
        raise ValueError("FORGED_OR_INCONSISTENT_HDC_RANKING")
    declared = {item.candidate_id: item for item in req.records}
    if len(declared) != len(req.records):
        raise ValueError("DUPLICATE_HDC_SOURCE_ID")

    # Find final canonical revisions BEFORE applying permissions/relations.
    # A re-scoped or tombstoned correction must invalidate old evidence.
    latest: dict[str, CanonicalRelation] = {}
    seen: set[tuple[str, int]] = set()
    for count, record in enumerate(canonical_records):
        if count >= 100_000 or not isinstance(record, CanonicalRelation):
            raise ValueError("INVALID_OR_UNBOUNDED_CANONICAL_SNAPSHOT")
        if record.revision > required_revision:
            raise ValueError("FUTURE_CANONICAL_REVISION")
        identity = (record.source_id, record.revision)
        if identity in seen:
            raise ValueError("DUPLICATE_CANONICAL_REVISION")
        seen.add(identity)
        old = latest.get(record.source_id)
        if old is None or record.revision > old.revision:
            latest[record.source_id] = record

    verified: list[VerifiedHit] = []
    rejected: list[str] = []
    for source_id in candidate.candidate_ids:
        advertised = declared[source_id]
        canonical = latest.get(source_id)
        if canonical is None or canonical.tombstone or canonical.scope != authorized_scope or (
            canonical.role != advertised.role or canonical.entity != advertised.entity
        ) or canonical.role != req.role or canonical.entity != req.entity:
            rejected.append(source_id)
            continue
        verified.append(VerifiedHit(
            source_id, canonical.revision, canonical.citation_handle,
            canonical.role, canonical.entity,
        ))
    return VerificationResult(canonical_snapshot_id, tuple(verified), tuple(rejected))
