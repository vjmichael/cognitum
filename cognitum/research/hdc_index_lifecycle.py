"""C08 P2 ephemeral HDC derived-index invalidation and guarded delivery.

Experimental candidate IDs ONLY. No host identity, persistence, authorized
memory access, live Lu index or reliable cross-restart revision witness.
The trusted host must supply canonical revision and call invalidate on change.
"""
from __future__ import annotations
from threading import RLock
from .hdc_optional import ID, MAX_BYTES, query
from cognitum.proto import research_optional_pb2 as pb


class EphemeralDerivedIndex:
    """Single-source revision cache that drops *all* bindings after any edit."""
    def __init__(self):
        self._lock = RLock()
        self._revision: str | None = None
        self._records: tuple[tuple[str,str,str], ...] = ()
        self._generation = 0

    @property
    def generation(self):
        with self._lock:
            return self._generation

    def install(self, revision: str, records):
        if not ID.fullmatch(revision) or type(records) not in (list, tuple):
            raise ValueError('INVALID_CANONICAL_REVISION')
        rows = tuple(records)
        if not 1 <= len(rows) <= 32 or any(
            type(r) not in (list,tuple) or len(r) != 3 or
            not all(type(x) is str and ID.fullmatch(x) for x in r) for r in rows
        ) or len({r[0] for r in rows}) != len(rows):
            raise ValueError('INVALID_INDEX_RECORDS')
        records_canonical = tuple((r[0],r[1],r[2]) for r in rows)
        with self._lock:
            if self._revision is not None:
                raise ValueError('MUST_INVALIDATE_BEFORE_NEW_REVISION')
            self._revision = revision
            self._records = records_canonical
            self._generation += 1
            return self._generation

    def invalidate(self, *, reason: str):
        if reason not in ('EDIT','RETRACT','DELETE','SCOPE_REVOKED','RESTORE','SOURCE_REPLACED'):
            raise ValueError('INVALID_INVALIDATION_REASON')
        with self._lock:
            self._revision = None
            self._records = ()
            self._generation += 1
            return self._generation

    def deliver(self, revision: str, role: str, entity: str, top_k: int, sink):
        if not callable(sink):
            raise ValueError('SINK_REQUIRED')
        with self._lock:
            if self._revision is None or revision != self._revision:
                raise ValueError('STALE_OR_UNINITIALIZED_INDEX')
            if type(top_k) is not int or not 1 <= top_k <= 8:
                raise ValueError('INVALID_TOP_K')
            call = pb.HdcQuery(schema_version=1,source_snapshot_id=revision,
                index_snapshot_id=revision,role=role,entity=entity,top_k=top_k)
            for candidate, r, e in self._records:
                call.records.add(candidate_id=candidate,role=r,entity=e)
            payload = call.SerializeToString(deterministic=True)
            if len(payload)>MAX_BYTES:
                raise ValueError('INDEX_QUERY_BUDGET')
            result = query(payload)
            # Guard against C08 result being extended to imply authorization.
            decoded = pb.HdcCandidates.FromString(result)
            if decoded.grants_authority or decoded.source_snapshot_id != self._revision:
                raise ValueError('CANDIDATE_NOT_AUTHORIZED_DATA')
            # Final check + publication under the same lock as invalidation.
            sink(result)
            return self._generation
