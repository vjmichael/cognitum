"""P3 standalone SQLite crash/replay/revocation gate for alpha worker results.

This is a LOCAL reference, not an authenticated Lu grant source, OS sandbox,
process-tree supervisor, or a durable transaction spanning an external sink.
A trusted host must control the database file/path, enrollment, and sink.
A crashed or duplicate execution is denied; automatic retries are not allowed.
"""
from __future__ import annotations
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from .alpha_native import ID

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
  id TEXT PRIMARY KEY, epoch INTEGER NOT NULL DEFAULT 0, revoked INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS requests (
  conversation TEXT NOT NULL, id TEXT NOT NULL, epoch INTEGER NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('PENDING','RUNNING','DELIVERED','FAILED','ABORTED')),
  PRIMARY KEY(conversation,id),
  FOREIGN KEY(conversation) REFERENCES conversations(id)
);
"""

class DurableRequestLedger:
    """Crash-safe local decision journal. No user identity verification."""
    def __init__(self, db_path: Path):
        if not isinstance(db_path, Path) or str(db_path) == ':memory:':
            raise ValueError('HOST_OWNED_FILE_PATH_REQUIRED')
        self.path = db_path
        # Path must be selected by caller's trusted host, not model input.
        with self._connect() as db:
            db.executescript(SCHEMA)
            # New process/instance cannot inherit an in-flight claim.
            db.execute("UPDATE requests SET state='ABORTED' WHERE state='RUNNING'")

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(str(self.path), timeout=3.0, isolation_level=None)
        try:
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA busy_timeout=3000')
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _id(value):
        if type(value) is not str or not ID.fullmatch(value):
            raise ValueError('INVALID_REQUEST_IDENTITY')
        return value

    def issue(self, conversation: str, request: str, *, local_host_approval=False):
        """Records a local host decision; caller's boolean is NOT authenticated."""
        self._id(conversation); self._id(request)
        if local_host_approval is not True:
            raise PermissionError('HOST_APPROVAL_ABSENT')
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT OR IGNORE INTO conversations(id) VALUES(?)', (conversation,))
            epoch, revoked = db.execute('SELECT epoch,revoked FROM conversations WHERE id=?', (conversation,)).fetchone()
            if revoked:
                raise PermissionError('CONVERSATION_REVOKED')
            try:
                db.execute("INSERT INTO requests VALUES(?,?,?,'PENDING')", (conversation, request, epoch))
            except sqlite3.IntegrityError as exc:
                raise ValueError('DUPLICATE_REQUEST_ID_DURABLE') from exc
            db.commit()
            return epoch

    def start(self, conversation: str, request: str, epoch: int):
        self._transition(conversation,request,epoch,'PENDING','RUNNING')

    def fail(self, conversation: str, request: str, epoch: int):
        self._transition(conversation,request,epoch,'RUNNING','FAILED')

    def _transition(self, conversation, request, epoch, before, after):
        self._id(conversation); self._id(request)
        if type(epoch) is not int or epoch < 0:
            raise PermissionError('INVALID_EPOCH')
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT epoch,revoked FROM conversations WHERE id=?',(conversation,)).fetchone()
            if row != (epoch,0) or db.execute(
                'UPDATE requests SET state=? WHERE conversation=? AND id=? AND epoch=? AND state=?',
                (after,conversation,request,epoch,before)).rowcount != 1:
                raise PermissionError('STALE_OR_CONSUMED_REQUEST')
            db.commit()

    def revoke(self, conversation: str):
        self._id(conversation)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT OR IGNORE INTO conversations(id) VALUES(?)',(conversation,))
            db.execute('UPDATE conversations SET revoked=1, epoch=epoch+1 WHERE id=? AND revoked=0',(conversation,))
            db.execute("UPDATE requests SET state='ABORTED' WHERE conversation=? AND state IN ('PENDING','RUNNING')",(conversation,))
            db.commit()

    def publish_once(self, conversation: str, request: str, epoch: int, result: bytes, sink):
        """At-most-once callback attempt; never assert exactly-once external delivery.

        Holds SQLite writer transaction across callback, serializing same-file
        revocation from another process. Failure also permanently consumes request.
        On process crash, recovery aborts RUNNING and will not replay the sink.
        """
        self._id(conversation); self._id(request)
        if type(result) is not bytes or not result or len(result)>16384 or not callable(sink):
            raise ValueError('INVALID_RESULT_OR_SINK')
        if type(epoch) is not int or epoch < 0:
            raise PermissionError('INVALID_EPOCH')
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT c.epoch,c.revoked,r.state FROM conversations c JOIN requests r ON r.conversation=c.id WHERE c.id=? AND r.id=?',(conversation,request)).fetchone()
            if row != (epoch,0,'RUNNING'):
                raise PermissionError('DELIVERY_FENCED_BY_HOST_STATE')
            # Commit either outcome; sink may have accepted a partial delivery.
            # Never retry automatically, even when sink raises.
            error=None
            try: sink(result)
            except Exception as exc: error=exc
            db.execute('UPDATE requests SET state=? WHERE conversation=? AND id=?',('FAILED' if error else 'DELIVERED',conversation,request))
            db.commit()
            if error is not None:
                raise error

    def status(self, conversation: str, request: str):
        self._id(conversation); self._id(request)
        with self._connect() as db:
            row=db.execute('SELECT state FROM requests WHERE conversation=? AND id=?',(conversation,request)).fetchone()
            return row[0] if row else None


def run_journalled(call_wire, local_board, ticket, journal: DurableRequestLedger,
                   epoch: int, sink):
    """Bind the existing actual subprocess loop to persistent at-most-once output.

    The ephemeral lease and durable journal must both authorize publication;
    this remains a test-only host approximation, not real Lu authority.
    """
    from .alpha_lifecycle import run_guarded, LocalLeaseBoard, LocalTicket
    if type(journal) is not DurableRequestLedger or type(local_board) is not LocalLeaseBoard or type(ticket) is not LocalTicket:
        raise TypeError('LOCAL_HOST_REFERENCES_REQUIRED')
    journal.start(ticket.conversation_id, ticket.request_id, epoch)
    try:
        run_guarded(call_wire, local_board, ticket,
                    lambda reply:journal.publish_once(ticket.conversation_id,
                                                       ticket.request_id, epoch, reply, sink))
    except Exception:
        try: journal.fail(ticket.conversation_id,ticket.request_id,epoch)
        except PermissionError: pass  # already consumed or explicitly revoked
        raise
