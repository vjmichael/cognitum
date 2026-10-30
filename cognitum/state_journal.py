"""C07/P3–P4 crash-safe *derived* state-event journal (offline reference).

Lu ANSF is the ONLY canonical owner of message content and user authority.
This rebuildable cache records host-admitted typed state events, NOT a second
canonical transcript. All admission/publication requires a Lu-host-held lease.
The lease object is a Python protocol placeholder, not authentication.

Safety properties within the trusted single-host-process model:
* SQLite FULL-sync transactions atomically persist each accepted batch and head.
* BEGIN IMMEDIATE serializes independent connections and prevents stale CAS.
* Strict replay verifies ordinal, canonical Protobuf, hash chain, head and
  reducer state. No partial projection is published after corruption.
* No saved grant, current-evidence flag, or cached authenticated projection:
  every publication re-verifies *all* historical/current ANSF evidence.
* SQLite log integrity is NOT cryptographic authentication: a malicious local
  writer can rewrite the database and its unkeyed digests; a trusted Lu host
  must confine filesystem access, authenticate the caller and manage erasure.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from itertools import islice
from pathlib import Path
import re
import sqlite3
import stat
import threading
from typing import Callable, Iterable, TypeVar

from cognitum.proto import state_pb2 as pb
from cognitum.state_host_gate import HostStateLease, HostDeletionLease, require_host_pass
from cognitum.state_revision import (
    MAX_EVENTS, StateLedger, StateInvalid, StateConflict, canonical_event, _id,
)

T = TypeVar('T')
SCHEMA_VERSION = 1
ZERO_HASH = '0' * 64
MAX_JOURNAL_EVENT_BYTES = 8192
HEX64 = re.compile(r'[0-9a-f]{64}\Z')


class JournalUnavailable(ValueError):
    """Storage unavailable or invalid; no data or SQL details disclosed."""


class JournalCorrupt(JournalUnavailable):
    """Durable event chain cannot be deterministically replayed."""


@dataclass(frozen=True)
class JournalReceipt:
    applied: int
    sequence: int
    head_sha256: str


@dataclass(frozen=True)
class RebuildReceipt:
    removed_claims: int
    removed_events: int
    retained_events: int
    generation: int
    head_sha256: str


def _digest(previous: str, sequence: int, frame: bytes) -> str:
    return sha256(bytes.fromhex(previous) + sequence.to_bytes(8, 'big')
                  + len(frame).to_bytes(4, 'big') + frame).hexdigest()


class StateJournal:
    """Host-embedded, scope-pinned SQLite projection event cache.

    The host must keep its *external* mutation/read lease held throughout the
    journal operation and synchronize ANSF deletes/revocations with delivery.
    Do not expose this class or its callback parameters to models or workers.
    """

    def __init__(self, path: Path, scope_id: str):
        if not _id(scope_id):
            raise StateInvalid('invalid scope')
        self.scope_id = scope_id
        self._lock = threading.RLock()
        self._callback_owner: int | None = None
        self._closed = False
        path = Path(path)
        # Defense-in-depth only. TOCTOU-resistant Windows/Unix directory
        # confinement requires Lu's capability-based native file handles.
        if path.is_symlink() or (path.exists() and not stat.S_ISREG(path.stat().st_mode)):
            raise JournalUnavailable('journal path unavailable')
        try:
            self._db = sqlite3.connect(path, isolation_level=None,
                                       check_same_thread=False, timeout=10)
            self._db.execute('PRAGMA busy_timeout=10000')
            self._db.execute('PRAGMA journal_mode=WAL')
            self._db.execute('PRAGMA synchronous=FULL')
            self._db.execute('PRAGMA foreign_keys=ON')
            self._db.executescript('''
                CREATE TABLE IF NOT EXISTS c07_meta (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    version INTEGER NOT NULL,
                    scope_id TEXT NOT NULL,
                    last_seq INTEGER NOT NULL CHECK(last_seq>=0),
                    head_hash TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS c07_rebuild_meta (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    generation INTEGER NOT NULL CHECK(generation>=0)
                );
                INSERT OR IGNORE INTO c07_rebuild_meta VALUES (1,0);
                CREATE TABLE IF NOT EXISTS c07_retired_event_ids (
                    event_id_sha256 TEXT PRIMARY KEY NOT NULL
                );
                CREATE TABLE IF NOT EXISTS c07_events (
                    seq INTEGER PRIMARY KEY CHECK(seq>=1),
                    event_id TEXT NOT NULL UNIQUE,
                    frame BLOB NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS c07_events_no_update
                BEFORE UPDATE ON c07_events BEGIN
                    SELECT RAISE(ABORT,'derived event rows immutable'); END;
                CREATE TRIGGER IF NOT EXISTS c07_events_no_delete
                BEFORE DELETE ON c07_events BEGIN
                    SELECT RAISE(ABORT,'derived event rows immutable'); END;
            ''')
            self._db.execute('BEGIN IMMEDIATE')
            try:
                row=self._db.execute('SELECT version,scope_id,last_seq,head_hash FROM c07_meta WHERE singleton=1').fetchone()
                if row is None:
                    if self._db.execute('SELECT count(*) FROM c07_events').fetchone()[0]:
                        raise JournalCorrupt('missing journal head')
                    self._db.execute('INSERT INTO c07_meta VALUES (1,?,?,?,?)',
                                     (SCHEMA_VERSION, scope_id, 0, ZERO_HASH))
                elif row[0] != SCHEMA_VERSION or row[1] != scope_id:
                    raise JournalCorrupt('scope/version mismatch')
                self._db.execute('COMMIT')
            except BaseException:
                self._db.execute('ROLLBACK')
                raise
            with self._transaction():
                self._load_locked()  # detect startup corruption before accepting work
        except (sqlite3.Error, OSError) as exc:
            self.close()
            raise JournalUnavailable('journal unavailable') from None
        except BaseException:
            self.close()
            raise

    def _assert_not_nested(self):
        if self._closed:
            raise JournalUnavailable('journal closed')
        if self._callback_owner == threading.get_ident():
            raise JournalUnavailable('reentrant journal call')

    def _transaction(self):
        from contextlib import contextmanager
        @contextmanager
        def transaction():
            self._db.execute('BEGIN IMMEDIATE')
            try:
                yield
                self._db.execute('COMMIT')
            except BaseException:
                self._db.execute('ROLLBACK')
                raise
        return transaction()

    def _generation_locked(self) -> int:
        row=self._db.execute('SELECT generation FROM c07_rebuild_meta WHERE singleton=1').fetchone()
        if row is None or not isinstance(row[0],int) or row[0]<0:
            raise JournalCorrupt('missing or corrupt derived-cache generation')
        return row[0]

    def generation(self) -> int:
        """Diagnostic revision for optimistic concurrency, NOT authorization."""
        with self._lock:
            self._assert_not_nested()
            with self._transaction():
                self._load_locked()
                return self._generation_locked()

    def _load_locked(self) -> tuple[StateLedger,int,str]:
        self._generation_locked()  # Fail closed on missing or modified generation.
        meta = self._db.execute('SELECT version,scope_id,last_seq,head_hash FROM c07_meta WHERE singleton=1').fetchone()
        if meta is None or meta[0] != SCHEMA_VERSION or meta[1] != self.scope_id:
            raise JournalCorrupt('journal head mismatch')
        _,_,last_seq,head=meta
        if not isinstance(last_seq,int) or last_seq<0 or last_seq>MAX_EVENTS:
            raise JournalCorrupt('journal length invalid')
        if not isinstance(head,str) or not HEX64.fullmatch(head):
            raise JournalCorrupt('journal head hash malformed')
        previous=ZERO_HASH
        frames=[]
        seq=0
        rows=self._db.execute('SELECT seq,event_id,frame,previous_hash,event_hash FROM c07_events ORDER BY seq')
        for ordinal,event_id,frame,prev,current in rows:
            seq+=1
            if seq > MAX_EVENTS or ordinal != seq or not isinstance(frame,bytes) or len(frame)>MAX_JOURNAL_EVENT_BYTES:
                raise JournalCorrupt('journal gap or oversized frame')
            if (not isinstance(prev,str) or not isinstance(current,str)
                or not HEX64.fullmatch(prev) or not HEX64.fullmatch(current)
                or prev != previous or current != _digest(previous,seq,frame)):
                raise JournalCorrupt('journal hash chain invalid')
            try:
                parsed=canonical_event(frame)
                if parsed.event_id != event_id:
                    raise JournalCorrupt('event identity mismatch')
            except StateInvalid:
                raise JournalCorrupt('invalid durable protobuf event') from None
            frames.append(frame)
            previous=current
        if seq != last_seq or head != previous:
            raise JournalCorrupt('journal head mismatch')
        try:
            offline=StateLedger.replay(self.scope_id,frames)
        except (StateInvalid, ValueError) as exc:
            raise JournalCorrupt('nonreplayable event transitions') from None
        gated=StateLedger(self.scope_id,require_host=True)
        gated._events=offline._events
        gated._claims=offline._claims
        gated._history=offline._history
        return gated,seq,previous

    def apply_host_batch(self, events: Iterable[pb.StateEvent], lease: HostStateLease) -> JournalReceipt:
        """Durably persist an all-or-nothing host-authorized CAS batch.

        A duplicate event does not create a new row. A conflicting duplicate
        and stale claim revision are both rejected after loading the latest
        committed state from SQLite (including from other host connections).
        """
        pending=list(islice(events,MAX_EVENTS+1))
        if len(pending)>MAX_EVENTS:
            raise StateInvalid('batch budget exhausted')
        # Freeze before entering the transaction; host will independently
        # verify the origin and source for these exact canonical bytes.
        frozen=[canonical_event(item.SerializeToString(deterministic=True)) for item in pending]
        with self._lock:
            self._assert_not_nested()
            self._callback_owner=threading.get_ident()
            try:
                with self._transaction():
                    ledger,seq,previous=self._load_locked()
                    original_length=len(ledger.history())
                    for event in frozen:
                        digest_id=sha256(event.event_id.encode('utf-8')).hexdigest()
                        if self._db.execute(
                            'SELECT 1 FROM c07_retired_event_ids WHERE event_id_sha256=?',
                            (digest_id,)).fetchone() is not None:
                            raise StateConflict('retired event ID may not be reused')
                    applied=ledger.apply_host_batch(frozen,lease)
                    tail=ledger.history()[original_length:]
                    if len(tail)!=applied:
                        raise JournalCorrupt('replay cardinality mismatch')
                    for frame in tail:
                        seq+=1
                        parsed=canonical_event(frame)
                        digest=_digest(previous,seq,frame)
                        self._db.execute('INSERT INTO c07_events (seq,event_id,frame,previous_hash,event_hash) VALUES (?,?,?,?,?)',
                                         (seq,parsed.event_id,frame,previous,digest))
                        previous=digest
                    self._db.execute('UPDATE c07_meta SET last_seq=?,head_hash=? WHERE singleton=1',
                                     (seq,previous))
                    require_host_pass(lease.ensure_active)
                return JournalReceipt(applied=applied,sequence=seq,head_sha256=previous)
            except sqlite3.Error:
                raise JournalUnavailable('journal write unavailable') from None
            finally:
                self._callback_owner=None

    def rebuild_after_host_deletion(
        self, deleted_sources: Iterable[pb.SourceEvidence], lease: HostDeletionLease,
        *, expected_generation: int, expected_head_sha256: str,
    ) -> RebuildReceipt:
        """Host-fenced, crash-atomic removal of dependent DERIVED claim histories.

        Only Lu's authenticated deletion authority can attest each tombstone.
        The external Lu lease MUST cover validation, this transaction, and its
        completion (including synchronizing independent ANSF mutations). A
        source-list is a candidate, not a grant. To avoid replaying orphaned
        corrections, a source deletion removes the *entire* affected claim
        chain, even when another source in the chain remains valid. Remaining
        claims must pass fresh retained AND current canonical-source checks.

        This is logical derived-data compaction, NOT secure physical erasure:
        SQLite WAL/free pages, backup files and copies need Lu-managed purge.
        The original authoritative ANSF history remains under Lu control.
        """
        candidates=list(islice(deleted_sources,MAX_EVENTS+1))
        if not candidates or len(candidates)>MAX_EVENTS:
            raise StateInvalid('invalid deletion-source batch')
        wanted=set()
        for source in candidates:
            raw=source.SerializeToString(deterministic=True)
            without_unknown=pb.SourceEvidence.FromString(raw)
            without_unknown.DiscardUnknownFields()
            if (not raw or len(raw)>512 or
                raw != without_unknown.SerializeToString(deterministic=True) or
                not source.session_id):
                raise StateInvalid('noncanonical deletion-source reference')
            wanted.add(raw)
        if (not isinstance(expected_generation,int) or expected_generation<0 or
            not isinstance(expected_head_sha256,str) or not HEX64.fullmatch(expected_head_sha256)):
            raise StateInvalid('invalid expected rebuild head')
        with self._lock:
            self._assert_not_nested()
            self._callback_owner=threading.get_ident()
            try:
                with self._transaction():
                    ledger,sequence,head=self._load_locked()
                    prior_generation=self._generation_locked()
                    if (prior_generation != expected_generation or head != expected_head_sha256):
                        raise StateConflict('derived journal head changed')
                    originals=[canonical_event(raw) for raw in ledger.history()]
                    matched_sources={e.source.SerializeToString(deterministic=True)
                                     for e in originals} & wanted
                    if matched_sources != wanted:
                        raise StateInvalid('deletion source not present in journal')
                    require_host_pass(lease.ensure_active)
                    for raw in sorted(wanted):
                        source=pb.SourceEvidence.FromString(raw)
                        require_host_pass(lease.confirm_source_deleted, self.scope_id, source)
                    affected={e.claim_id for e in originals
                              if e.source.SerializeToString(deterministic=True) in wanted}
                    remaining=[e for e in originals if e.claim_id not in affected]
                    candidate=StateLedger.replay(self.scope_id,
                         (e.SerializeToString(deterministic=True) for e in remaining))
                    # Rebuild with a gated ledger to reject all missing, stale,
                    # revoked or unexpectedly changed surviving sources.
                    gated=StateLedger(self.scope_id, require_host=True)
                    gated._events=candidate._events
                    gated._claims=candidate._claims
                    gated._history=candidate._history
                    gated.publish_host_fenced(lease,lambda _raw: None)
                    # No public write path may delete rows. The host-only rebuild
                    # disables the immutability trigger *within* the transaction
                    # and restores it before commit; interruption rolls back all.
                    for event in originals:
                        if event.claim_id in affected:
                            digest_id=sha256(event.event_id.encode('utf-8')).hexdigest()
                            self._db.execute(
                                'INSERT OR IGNORE INTO c07_retired_event_ids VALUES (?)',
                                (digest_id,))
                    self._db.execute('DROP TRIGGER c07_events_no_delete')
                    self._db.execute('DELETE FROM c07_events')
                    self._db.execute("""CREATE TRIGGER c07_events_no_delete
                        BEFORE DELETE ON c07_events BEGIN
                        SELECT RAISE(ABORT,'derived event rows immutable'); END""")
                    next_seq=0
                    previous=ZERO_HASH
                    for event in remaining:
                        frame=event.SerializeToString(deterministic=True)
                        next_seq+=1
                        digest=_digest(previous,next_seq,frame)
                        self._db.execute("""INSERT INTO c07_events
                            (seq,event_id,frame,previous_hash,event_hash) VALUES (?,?,?,?,?)""",
                            (next_seq,event.event_id,frame,previous,digest))
                        previous=digest
                    self._db.execute('UPDATE c07_meta SET last_seq=?,head_hash=? WHERE singleton=1',
                                     (next_seq,previous))
                    self._db.execute('UPDATE c07_rebuild_meta SET generation=? WHERE singleton=1',
                                     (prior_generation+1,))
                    # Abort if the held authority was revoked during work.
                    require_host_pass(lease.ensure_active)
                return RebuildReceipt(removed_claims=len(affected),
                    removed_events=sequence-next_seq,retained_events=next_seq,
                    generation=prior_generation+1,head_sha256=previous)
            except sqlite3.Error:
                raise JournalUnavailable('derived rebuild unavailable') from None
            finally:
                self._callback_owner=None

    def publish_host_fenced(self, lease: HostStateLease, publish: Callable[[bytes], T]) -> T:
        """Reconstruct, verify ALL sources, then publish under held host lease.

        Separate SQLite readers/writers serialize on this transaction. The
        caller's Lu lease additionally synchronizes ANSF mutation/revocation;
        SQLite alone cannot authenticate those external security changes.
        """
        with self._lock:
            self._assert_not_nested()
            self._callback_owner=threading.get_ident()
            try:
                with self._transaction():
                    ledger,_,_=self._load_locked()
                    return ledger.publish_host_fenced(lease,publish)
            except sqlite3.Error:
                raise JournalUnavailable('journal read unavailable') from None
            finally:
                self._callback_owner=None

    def publish_host_as_of(self, query: pb.AsOfQuery, lease: HostStateLease,
                           publish: Callable[[bytes], T]) -> T:
        """Rebuild and deliver historical-only bitemporal state under host lease.

        The transaction pins the derived snapshot, while Lu MUST additionally
        fence canonical ANSF deletion/revocation for the complete callback.
        """
        with self._lock:
            self._assert_not_nested()
            self._callback_owner = threading.get_ident()
            try:
                with self._transaction():
                    ledger,_,_ = self._load_locked()
                    return ledger.publish_host_as_of(query, lease, publish)
            except sqlite3.Error:
                raise JournalUnavailable('historical journal read unavailable') from None
            finally:
                self._callback_owner = None

    def reconcile_host_fenced(self, lease: HostStateLease) -> dict[str,object]:
        """Rebuild and verify references under one snapshot; disclose no claims.

        The successful check only applies to the *current* host lease; this
        receipt is NEVER a reusable grant, authenticated evidence or a cache
        of verification status. The host must still fence concurrent ANSF
        revocation/deletion while calling this method.
        """
        with self._lock:
            self._assert_not_nested()
            self._callback_owner=threading.get_ident()
            try:
                with self._transaction():
                    ledger,sequence,head=self._load_locked()
                    digest=ledger.publish_host_fenced(
                        lease, lambda frame:sha256(frame).hexdigest())
                    return {'event_count':sequence,'journal_head_sha256':head,
                            'derived_projection_sha256':digest,
                            'verified_this_call':True}
            except sqlite3.Error:
                raise JournalUnavailable('journal reconciliation unavailable') from None
            finally:
                self._callback_owner=None

    def head(self) -> tuple[int,str]:
        """Diagnostic metadata only, NEVER proof of host source authorization."""
        with self._lock:
            self._assert_not_nested()
            try:
                with self._transaction():
                    _,seq,head=self._load_locked()
                return seq,head
            except sqlite3.Error:
                raise JournalUnavailable('journal read unavailable') from None

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._assert_not_nested()
            self._closed=True
            if getattr(self,'_db',None) is not None:
                self._db.close()

    def __enter__(self):
        return self

    def __exit__(self,*_):
        self.close()
