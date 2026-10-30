"""C06/P4 *test-only* durable host policy and ANSF read-lease reference.

This Python class is NOT a trusted native Lu host. A Python constructor, DB,
caller string or Protobuf frame cannot authenticate a user. This module is a
conformance rig for Lu's planned Rust host implementation, not a CE or model
API. Host callers must keep both ANSF mutations and policy mutations behind
one host-held fence and must provide an authenticated principal out-of-band.

Logical tombstones prevent future search/citation disclosure but DO NOT erase
original ANSF entries, FTS5 content, WAL, backups, or historical revisions.
No production right-to-erasure claim may be derived from this reference.
"""

from dataclasses import dataclass
from pathlib import Path
from contextlib import AbstractContextManager
import sqlite3
import threading

from .ansf_read_reference import select_ansf_fts_frames, select_ansf_citation_snapshot
from .memory_evidence import TrustedReadContext, _id
from .proto import memory_pb2 as pb


class HostPolicyError(Exception):
    """Opaque to model-facing callers: no principal, path or content echoed."""


@dataclass(frozen=True, slots=True)
class SyntheticPrincipal:
    """Fixture identity ONLY; NOT a validated credential or permission token."""
    profile_id: str
    workspace_id: str


def _valid_identity(value):
    return _id(value) and len(value) <= 128


class DurableAnsfPolicy:
    """SQLite WAL fixture: irreversible revocations and logical tombstones.

    A shared lock synchronizes the fixture's leases, mutations and publish.
    Reopening the DB with a new instance simulates a process restart; no user
    data is persisted in this *policy* database, only IDs and tombstones.
    """

    def __init__(self, db_path: Path):
        self.lock = threading.RLock()
        self._active_leases = 0
        self._conn = sqlite3.connect(str(db_path), isolation_level=None,
                                     check_same_thread=False)
        try:
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=FULL")
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS session_policy(
                    session_id TEXT PRIMARY KEY NOT NULL,
                    profile_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
                    allow_historical INTEGER NOT NULL CHECK(allow_historical IN (0,1)),
                    authorization_epoch INTEGER NOT NULL DEFAULT 1 CHECK(authorization_epoch>0),
                    index_epoch INTEGER NOT NULL DEFAULT 1 CHECK(index_epoch>0),
                    source_dirty INTEGER NOT NULL DEFAULT 0 CHECK(source_dirty IN (0,1))
                );
                CREATE TRIGGER IF NOT EXISTS session_owner_immutable
                BEFORE UPDATE OF session_id,profile_id,workspace_id ON session_policy
                BEGIN SELECT RAISE(ABORT,'immutable owner binding'); END;
                CREATE TRIGGER IF NOT EXISTS session_policy_no_delete
                BEFORE DELETE ON session_policy
                BEGIN SELECT RAISE(ABORT,'immutable enrollment'); END;
                CREATE TRIGGER IF NOT EXISTS session_policy_no_reenable
                BEFORE UPDATE OF enabled ON session_policy
                WHEN OLD.enabled=0 AND NEW.enabled=1
                BEGIN SELECT RAISE(ABORT,'revocation is terminal'); END;
                CREATE TABLE IF NOT EXISTS logical_tombstones(
                    session_id TEXT NOT NULL REFERENCES session_policy(session_id),
                    original_entry_id INTEGER NOT NULL CHECK(original_entry_id>0),
                    PRIMARY KEY(session_id,original_entry_id)
                );
                CREATE TRIGGER IF NOT EXISTS tombstone_no_update
                BEFORE UPDATE ON logical_tombstones
                BEGIN SELECT RAISE(ABORT,'tombstones are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS tombstone_no_delete
                BEFORE DELETE ON logical_tombstones
                BEGIN SELECT RAISE(ABORT,'tombstones are immutable'); END;
            """)
        except Exception:
            self._conn.close()
            raise

    def close(self):
        with self.lock:
            self._writable()
            self._conn.close()

    def _writable(self):
        # Reentrant host callbacks cannot acknowledge a mutation within a
        # read lease and then have its transaction silently rolled back.
        if self._active_leases:
            raise HostPolicyError("mutation attempted during fenced read")

    def _row(self, session_id):
        return self._conn.execute(
            "SELECT profile_id,workspace_id,enabled,allow_historical,authorization_epoch,index_epoch "
            " ,source_dirty FROM session_policy WHERE session_id=?", (session_id,)).fetchone()

    def _require(self, principal, session_id, *, active=True):
        if (type(principal) is not SyntheticPrincipal or
                not _valid_identity(principal.profile_id) or
                not _valid_identity(principal.workspace_id) or
                not _valid_identity(session_id)):
            raise HostPolicyError("denied")
        row = self._row(session_id)
        if (row is None or row[:2] != (principal.profile_id, principal.workspace_id)
                or (active and row[2] != 1)):
            raise HostPolicyError("denied")
        return row

    def enroll(self, principal: SyntheticPrincipal, session_id: str, *, allow_historical=False):
        """Trusted fixture setup, not a public request handler."""
        if (type(principal) is not SyntheticPrincipal or
                not _valid_identity(principal.profile_id) or
                not _valid_identity(principal.workspace_id) or
                not _valid_identity(session_id) or type(allow_historical) is not bool):
            raise HostPolicyError("invalid enrollment")
        with self.lock:
            self._writable()
            row = self._row(session_id)
            if row is not None:
                if row[:2] != (principal.profile_id, principal.workspace_id) or row[3] != int(allow_historical):
                    raise HostPolicyError("immutable enrollment")
                return False
            self._conn.execute(
                "INSERT INTO session_policy(session_id,profile_id,workspace_id,allow_historical) "
                "VALUES (?,?,?,?)",
                (session_id,principal.profile_id,principal.workspace_id,int(allow_historical)))
            return True

    def revoke(self, principal: SyntheticPrincipal, session_id: str):
        """Acknowledge revocation only after all in-flight fenced publishing ends."""
        with self.lock:
            self._writable()
            row = self._require(principal, session_id, active=False)
            if row[2] == 0:
                return False
            self._conn.execute("UPDATE session_policy SET enabled=0,authorization_epoch=authorization_epoch+1 "
                               "WHERE session_id=?", (session_id,))
            return True

    def advance_index(self, principal: SyntheticPrincipal, session_id: str):
        """Fixture epoch bump for synthetic non-source index updates.

        Host must serialize ANSF writes under this SAME lock. The two SQLite
        databases are not jointly atomic; crash recovery must bump/reconcile
        the index before returning search results. This does not solve that.
        """
        with self.lock:
            self._writable()
            self._require(principal, session_id)
            self._conn.execute("UPDATE session_policy SET index_epoch=index_epoch+1 "
                               "WHERE session_id=?", (session_id,))

    def tombstone(self, principal: SyntheticPrincipal, session_id: str, root_id: int,
                  source_conn: sqlite3.Connection):
        """Record a durable *logical* root tombstone; no source modification.

        Only the host may supply `source_conn` and the root ID, after the
        authenticated user requests deletion. Validate the immutable ANSF
        root before writing so arbitrary model-supplied IDs cannot be used.
        """
        if type(root_id) is not int or root_id < 1 or type(source_conn) is not sqlite3.Connection:
            raise HostPolicyError("invalid tombstone")
        with self.lock:
            self._writable()
            self._require(principal, session_id)
            try:
                workspace = source_conn.execute(
                    "SELECT workspace_id FROM ansf_sessions WHERE id=?", (session_id,)).fetchone()
                original = source_conn.execute(
                    "SELECT id,message_id FROM ansf_entries WHERE session_id=? AND id=?",
                    (session_id, root_id)).fetchone()
                revision = source_conn.execute(
                    "SELECT 1 FROM ansf_entry_edits WHERE session_id=? AND revised_entry_id=?",
                    (session_id, root_id)).fetchone()
            except sqlite3.Error:
                raise HostPolicyError("unavailable") from None
            if (not workspace or workspace[0] != principal.workspace_id or
                    not original or original[1].startswith("ansf-revision:") or revision):
                raise HostPolicyError("invalid tombstone")
            # Tombstone + epoch bump are one durable transaction. An exception
            # or interrupted commit must not expose only one half of the change.
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                before = self._conn.total_changes
                self._conn.execute(
                    "INSERT OR IGNORE INTO logical_tombstones(session_id,original_entry_id) VALUES (?,?)",
                    (session_id, root_id))
                if self._conn.total_changes == before:
                    self._conn.execute("COMMIT")
                    return False
                self._conn.execute(
                    "UPDATE session_policy SET index_epoch=index_epoch+1 WHERE session_id=?",
                    (session_id,))
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            return True

    def begin_source_update(self, principal: SyntheticPrincipal, session_id: str):
        """Durably fence readers BEFORE an external ANSF source transaction.

        A host MUST call this before touching the source DB, then commit the
        ANSF write, reconcile derived indexes, and call finish_source_update.
        If a crash happens between these steps, source_dirty survives restart
        and ALL subsequent retrieval is denied pending trusted reconciliation.
        This cannot detect bypassing writers; only native Lu can enforce that.
        """
        with self.lock:
            self._writable()
            self._require(principal, session_id)
            if self._row(session_id)[6]:
                raise HostPolicyError("source requires reconciliation")
            self._conn.execute("UPDATE session_policy SET source_dirty=1 WHERE session_id=?",
                               (session_id,))

    def finish_source_update(self, principal: SyntheticPrincipal, session_id: str):
        """Trusted fixture recovery after ANSF commit + index reconciliation.

        The caller must independently verify source/catalog completeness. This
        method intentionally does NOT inspect source bytes or assert durability.
        """
        with self.lock:
            self._writable()
            self._require(principal, session_id)
            if not self._row(session_id)[6]:
                raise HostPolicyError("no source update pending")
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._conn.execute(
                    "UPDATE session_policy SET source_dirty=0,index_epoch=index_epoch+1 "
                    "WHERE session_id=? AND source_dirty=1", (session_id,))
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise

    def _tombstones(self, session_id):
        return frozenset(row[0] for row in self._conn.execute(
            "SELECT original_entry_id FROM logical_tombstones WHERE session_id=?",
            (session_id,)))


class _HeldAnsfRead(AbstractContextManager):
    """Fixture lease: policy lock spans read, recheck and synchronous publish."""

    def __init__(self, gateway):
        self.host = gateway
        self._transaction = False
        self._policy_transaction = False
        self._prior_query_only = None

    def __enter__(self):
        self.host.policy.lock.acquire()
        try:
            if self.host.policy._active_leases:
                raise HostPolicyError("nested fenced read forbidden")
            # An SQLite write reservation on the durable policy DB is held
            # through synchronous publish. Independent policy connections and
            # separate processes cannot acknowledge revocation/deletion ahead
            # of this read, even if they do not share the Python RLock.
            self.host.policy._conn.execute("BEGIN IMMEDIATE")
            self._policy_transaction = True
            self.host.policy._active_leases += 1
            self._bound = False
            self._record = None
            self._ctx = TrustedReadContext(scope_id=self.host.principal.profile_id,
                snapshot_id="denied", authorization_epoch=1, index_epoch=1,
                authorized_sessions=frozenset({self.host.session_id}), active=False)
            try:
                record = self.host.policy._require(self.host.principal, self.host.session_id)
                self._prior_query_only = self.host.conn.execute(
                    "PRAGMA query_only").fetchone()[0]
                self.host.conn.execute("PRAGMA query_only=ON")
                self.host.conn.execute("BEGIN")
                self._transaction = True
                source = self.host.conn.execute(
                    "SELECT workspace_id FROM ansf_sessions WHERE id=?",
                    (self.host.session_id,)).fetchone()
                if not source or source[0] != self.host.principal.workspace_id or record[6]:
                    return self
                self._record = record
                self._bound = True
                self._ctx = TrustedReadContext(
                    scope_id=self.host.principal.profile_id,
                    snapshot_id=f"snap:{self.host.session_id}:{record[4]}:{record[5]}",
                    authorization_epoch=record[4], index_epoch=record[5],
                    authorized_sessions=frozenset({self.host.session_id}),
                    allow_historical=bool(record[3]), active=True)
            except (HostPolicyError, sqlite3.Error):
                pass
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, exc_type, exc, tb):
        try:
            if self._transaction:
                self.host.conn.execute("ROLLBACK")
        finally:
            try:
                if self._prior_query_only is not None:
                    self.host.conn.execute(
                        "PRAGMA query_only=" + ("ON" if self._prior_query_only else "OFF"))
            finally:
                try:
                    if self._policy_transaction:
                        self.host.policy._active_leases -= 1
                        self.host.policy._conn.execute("ROLLBACK")
                finally:
                    self.host.policy.lock.release()
        return False

    @property
    def context(self):
        return self._ctx

    @property
    def snapshot_frame(self):
        # This lease does not create a snapshot outside its ANSF operations.
        raise RuntimeError("no detached canonical source")

    def ansf_fts_frames(self, frame):
        if not self._bound:
            return pb.DENIED, None, None
        return select_ansf_fts_frames(
            frame, self.host.conn, context=self._ctx, session_id=self.host.session_id,
            tombstoned_roots=self.host.policy._tombstones(self.host.session_id))

    def ansf_citation_snapshot(self, frame):
        if not self._bound:
            return pb.DENIED, None
        return select_ansf_citation_snapshot(
            frame, self.host.conn, context=self._ctx, session_id=self.host.session_id,
            tombstoned_roots=self.host.policy._tombstones(self.host.session_id))

    def recheck(self):
        if self.host.cancelled.is_set():
            return pb.CANCELLED
        if not self._bound:
            return pb.DENIED
        try:
            row = self.host.policy._require(self.host.principal, self.host.session_id)
        except HostPolicyError:
            return pb.DENIED
        if row[6]:
            return pb.UNAVAILABLE
        if row[4] != self._ctx.authorization_epoch:
            return pb.DENIED
        if row[5] != self._ctx.index_epoch:
            return pb.STALE
        return pb.VERIFIED

    def publish(self, frame):
        if not self._bound and pb.RetrievalReply.FromString(frame).status == pb.VERIFIED:
            raise HostPolicyError("unauthorized publication")
        if self.host.cancelled.is_set():
            raise HostPolicyError("cancelled before publication")
        # Sink must be synchronous, non-queuing, atomic and host-controlled.
        self.host.sink(frame)


class ReferenceAnsfGateway:
    """Construct ONLY within a synthetic trusted fixture. No file/path opening."""
    def __init__(self, policy: DurableAnsfPolicy, conn: sqlite3.Connection,
                 principal: SyntheticPrincipal, session_id: str, *, sink):
        if (type(policy) is not DurableAnsfPolicy or type(conn) is not sqlite3.Connection
                or type(principal) is not SyntheticPrincipal or
                not _valid_identity(principal.profile_id) or
                not _valid_identity(principal.workspace_id) or
                not _valid_identity(session_id) or not callable(sink)):
            raise HostPolicyError("invalid gateway")
        self.policy = policy
        self.conn = conn
        self.principal = principal
        self.session_id = session_id
        self.sink = sink
        self.cancelled = threading.Event()

    def acquire(self):
        return _HeldAnsfRead(self)

    def cancel(self):
        # Host-controlled signal may be set without waiting for the read lock.
        self.cancelled.set()
