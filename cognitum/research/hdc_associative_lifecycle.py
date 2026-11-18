"""Research-only, revision-bound derived SDM cache. Host owns canonical state.

No file access, authorization, network, or implicit production routing. The
checkpoint is an untrusted cache witness: restore always rebuilds from the
independent host snapshot and compares the complete deterministic witness.
"""
from __future__ import annotations

from copy import copy
from dataclasses import dataclass
import hashlib
import json
import secrets
from threading import RLock

import numpy as np

from .hdc_associative import Cleanup, SparseDistributed, _bipolar
from .hdc_algebra import Spec
from .hdc_canonical import CanonicalRelation, verify_hdc_candidates
from .hdc_optional import ID, bound, query
from cognitum.proto import research_optional_pb2 as pb

D = 256
MAX_RECORDS = 4096
MAX_DELTA = 128
MAX_CHECKPOINT = 4 * 1024 * 1024


def _bits(data: bytes):
    return np.where(np.unpackbits(np.frombuffer(data, np.uint8)), 1, -1).astype(np.int8)


def relation_key(role, entity):
    return _bits(bound(role, entity).to_bytes(32, 'big'))


def _value(record):
    data = json.dumps([record.source_id, record.revision], separators=(',', ':')).encode('ascii')
    return _bits(hashlib.sha256(b'cognitum-D1-derived-value-v1\0' + data).digest())


def _identity(snapshot, revision):
    if not isinstance(snapshot, str) or not ID.fullmatch(snapshot) or type(revision) is not int or not 1 <= revision <= 2**63 - 1:
        raise ValueError('invalid snapshot identity')


def _record(row, max_revision):
    if not isinstance(row, CanonicalRelation) or type(row.tombstone) is not bool or type(row.scope) is not str or type(row.citation_handle) is not str or row.revision > max_revision:
        raise ValueError('invalid host record')
    return row


def _latest(records, revision):
    latest = {}; seen = set()
    for i, row in enumerate(records):
        if i >= 100000: raise ValueError('snapshot input budget')
        row = _record(row, revision)
        key = (row.source_id, row.revision)
        if key in seen: raise ValueError('duplicate source revision')
        seen.add(key)
        if row.source_id not in latest or latest[row.source_id].revision < row.revision:
            latest[row.source_id] = row
        if len(latest) > MAX_RECORDS: raise ValueError('source count budget')
    return latest


@dataclass(frozen=True)
class Proposal:
    instance: str
    snapshot: str
    revision: int
    generation: int
    source_id: str
    source_revision: int
    score: float
    margin: float


class DerivedAssociations:
    """One scope-specific, disposable index; serialized local mutation/publication.

    Host must authenticate snapshots and changes, and serialize its own canonical
    revision checks with use of returned evidence. This lock is not a host lock.
    Active source record metadata is solely original-write custody, not authority.
    """
    def __init__(self, addresses, radius, scope, *, limit=32767):
        if not isinstance(scope, str) or not scope or len(scope) > 128:
            raise ValueError('scope required')
        self._scope = scope
        self._sdm = SparseDistributed(addresses, D, radius, limit=limit)
        if self._sdm.key_dim != D: raise ValueError('C08 key dimension')
        self._lock = RLock(); self._snapshot = None; self._revision = 0
        self._generation = 0; self._rows = {}; self._live = False
        self._instance = secrets.token_hex(16)

    def _empty(self):
        s = copy(self._sdm)
        s._counters = np.zeros_like(s._counters); s._counts = np.zeros_like(s._counts)
        return s

    @staticmethod
    def _write(s, row, *, subtract=False):
        s.write(relation_key(row.role, row.entity), _value(row), subtract=subtract)

    def _rebuild(self, records, revision):
        rows = {k:v for k,v in _latest(records, revision).items() if not v.tombstone and v.scope == self._scope}
        s = self._empty()
        for row in rows.values(): self._write(s, row)
        return s, rows

    def install(self, snapshot, revision, records):
        _identity(snapshot, revision)
        with self._lock:
            if self._live or revision <= self._revision: raise ValueError('invalidate or newer revision required')
            generation = self._generation
            s, rows = self._rebuild(records, revision)
            if generation != self._generation: raise ValueError('snapshot changed during rebuild')
            self._sdm, self._rows = s, rows
            self._snapshot, self._revision = snapshot, revision
            self._generation += 1; self._live = True

    def _current(self, snapshot, revision):
        _identity(snapshot, revision)
        if not self._live or (snapshot, revision) != (self._snapshot, self._revision):
            raise ValueError('stale or invalidated derived snapshot')

    def apply(self, *, snapshot, revision, next_snapshot, next_revision, changes):
        """Atomic checked replacement of original writes from an authenticated delta.

        Exact global next revision is required; an empty delta is legal for an
        unrelated canonical change. No arbitrary subtract-by-vector interface.
        Re-scoped and tombstoned records remove the original active write.
        """
        _identity(next_snapshot, next_revision)
        with self._lock:
            self._current(snapshot, revision)
            if next_revision != revision + 1 or next_snapshot == snapshot:
                raise ValueError('nonconsecutive revision or reused current snapshot')
            generation = self._generation
            delta = {}
            for i, row in enumerate(changes):
                if i >= MAX_DELTA: raise ValueError('delta budget')
                row = _record(row, next_revision)
                if row.revision != next_revision or row.source_id in delta:
                    raise ValueError('invalid delta revision or duplicate ID')
                delta[row.source_id] = row
            if generation != self._generation: raise ValueError('snapshot changed during delta acquisition')
            # Stage all changes; overflow or invalid operation leaves old state intact.
            s = copy(self._sdm); s._counters = s._counters.copy(); s._counts = s._counts.copy()
            rows = self._rows.copy()
            for key in delta:
                old = rows.pop(key, None)
                if old is not None: self._write(s, old, subtract=True)
            for key, row in delta.items():
                if not row.tombstone and row.scope == self._scope:
                    self._write(s, row); rows[key] = row
            if len(rows) > MAX_RECORDS: raise ValueError('source count budget')
            self._sdm, self._rows = s, rows
            self._snapshot, self._revision = next_snapshot, next_revision
            self._generation += 1

    def invalidate(self):
        with self._lock:
            self._sdm = self._empty(); self._rows = {}; self._snapshot = None
            self._generation += 1; self._live = False

    def _propose(self, probe, minimum, margin):
        probe = _bipolar(probe, D)
        if not np.isfinite([minimum,margin]).all() or not -1 <= minimum <= 1 or not 0 <= margin <= 2:
            raise ValueError('thresholds')
        raw, count = self._sdm.raw(probe)
        if not count or not raw.any() or not self._rows: return None
        rows = sorted(self._rows.values(), key=lambda r:r.source_id)
        spec = Spec('MAP', D)
        vals = np.stack([_value(r) for r in rows]).astype(np.float32)
        if len(rows) == 1:
            score = float(spec.similarity(raw.astype(np.float32), vals[0]))
            if score < minimum or score <= 0 or score < margin: return None
            i, gap = 0, score  # single-item gap against zero/no-match baseline
        else:
            c = Cleanup(spec, vals).propose(raw.astype(np.float32), minimum=minimum, margin=margin)
            if c is None: return None
            i, score, gap = c.index, c.score, c.margin
            if score <= 0: return None
        row = rows[i]
        return Proposal(self._instance,self._snapshot,self._revision,self._generation,row.source_id,row.revision,score,gap)

    def propose(self, probe, *, snapshot, revision, minimum=.30, margin=.05):
        with self._lock:
            self._current(snapshot, revision)
            return self._propose(probe, minimum, margin)

    def verify(self, proposal, probe, *, role, entity, authorized_scope,
               canonical_snapshot_id, current_snapshot_id, required_revision,
               canonical_records, minimum=.30, margin=.05):
        """Recompute research proposal, then use actual existing C08 verifier.

        C08 checks a one-candidate request, not global SDM ranking. Latest
        revision and citation must also match this index's original write.
        The caller's host snapshot/authorization MUST be independent of cache.
        """
        with self._lock:
            self._current(current_snapshot_id, required_revision)
            if authorized_scope != self._scope or canonical_snapshot_id != current_snapshot_id:
                raise ValueError('scope or snapshot mismatch')
            if not isinstance(proposal, Proposal) or proposal != self._propose(probe, minimum, margin):
                raise ValueError('forged or stale associative proposal')
            row = self._rows[proposal.source_id]
            req = pb.HdcQuery(schema_version=1, source_snapshot_id=current_snapshot_id,
                              index_snapshot_id=current_snapshot_id, role=role, entity=entity, top_k=1)
            req.records.add(candidate_id=row.source_id, role=row.role, entity=row.entity)
            wire = req.SerializeToString(deterministic=True)
            result = verify_hdc_candidates(wire, query(wire), canonical_records=canonical_records,
                         authorized_scope=authorized_scope, canonical_snapshot_id=canonical_snapshot_id,
                         current_snapshot_id=current_snapshot_id, required_revision=required_revision)
            self._current(current_snapshot_id, required_revision)
            if proposal.generation != self._generation: raise ValueError('snapshot changed during verification')
            for hit in result.verified:
                if (hit.revision,hit.citation_handle) == (row.revision,row.citation_handle): return hit
            return None

    def checkpoint(self, *, snapshot, revision):
        """Deterministic bounded bytes; not a canonical record store or MAC."""
        with self._lock:
            self._current(snapshot, revision)
            rows = [[r.source_id,r.revision,r.scope,r.role,r.entity,r.citation_handle]
                    for r in sorted(self._rows.values(), key=lambda x:x.source_id)]
            digest = lambda a: hashlib.sha256(a.tobytes(order='C')).hexdigest()
            # Fixed little-endian counters for portable comparisons.
            doc = dict(schema='D1-derived-v1', snapshot=snapshot, revision=revision,
                       scope=self._scope, radius=self._sdm.radius, limit=self._sdm.limit,
                       shape=list(self._sdm._addresses.shape), addresses=digest(self._sdm._addresses),
                       counters=digest(self._sdm._counters.astype('<i2',copy=False)),
                       counts=digest(self._sdm._counts.astype('<i4',copy=False)),
                       records_digest=hashlib.sha256(json.dumps(rows,ensure_ascii=True,separators=(',',':')).encode()).hexdigest())
            return json.dumps(doc,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('ascii')

    def restore(self, checkpoint, *, snapshot, revision, canonical_records):
        """Rebuild from current authenticated host data; reject stale/tampered cache.

        This deliberately does not trust checkpoint counters or replay old facts.
        The host owns atomic durable checkpoint writes and snapshot acquisition.
        """
        _identity(snapshot, revision)
        if type(checkpoint) is not bytes or not 0 < len(checkpoint) <= MAX_CHECKPOINT:
            raise ValueError('checkpoint budget')
        with self._lock:
            if self._live or revision <= self._revision: raise ValueError('restore only into fresh/newer cache')
            generation = self._generation
            s, rows = self._rebuild(canonical_records, revision)
            if generation != self._generation: raise ValueError('snapshot changed during restore')
            old = (self._sdm,self._rows,self._snapshot,self._revision,self._generation,self._live)
            self._sdm,self._rows,self._snapshot,self._revision,self._live = s,rows,snapshot,revision,True
            try:
                if self.checkpoint(snapshot=snapshot,revision=revision) != checkpoint:
                    raise ValueError('checkpoint mismatch; rebuild from current host')
            except BaseException:
                self._sdm,self._rows,self._snapshot,self._revision,self._generation,self._live = old
                raise
            self._generation += 1
