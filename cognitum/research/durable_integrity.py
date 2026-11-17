"""P3 local durability for C08 derived index epochs and C09 KAN signer revocation.

These SQLite rows are *host-provided claims*, not authenticated host authority,
license or publisher identity. Only trusted caller-selected DB paths and source
metadata are permissible. No Lu integration, source I/O, or model changes.
"""
from __future__ import annotations
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from .hdc_optional import ID
from .hdc_index_lifecycle import EphemeralDerivedIndex
from .kan_approval import HostTrustedApprover, predict_approved
from .kan_optional import ResearchPolicy

HEX = re.compile(r'[0-9a-f]{64}\Z', re.ASCII)

class ResearchIntegrityLedger:
    def __init__(self, file: Path):
        if not isinstance(file, Path) or str(file)==':memory:':
            raise ValueError('HOST_OWNED_DATABASE_PATH_REQUIRED')
        self.file=file
        with self._db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS sources (id TEXT PRIMARY KEY, epoch INTEGER NOT NULL, revision TEXT NOT NULL, digest TEXT NOT NULL, stale INTEGER NOT NULL, revoked INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS signers (id TEXT PRIMARY KEY, public_key BLOB NOT NULL, model TEXT NOT NULL, training TEXT NOT NULL, revoked INTEGER NOT NULL)')

    @contextmanager
    def _db(self):
        db=sqlite3.connect(str(self.file),timeout=3,isolation_level=None)
        try:
            db.execute('PRAGMA busy_timeout=3000')
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _name(x):
        if type(x) is not str or not ID.fullmatch(x):raise ValueError('INVALID_ID')
    @staticmethod
    def _hex(x):
        if type(x) is not str or not HEX.fullmatch(x):raise ValueError('INVALID_DIGEST')

    def activate_source(self, source: str, revision: str, digest: str, *, expected_epoch: int):
        self._name(source);self._name(revision);self._hex(digest)
        if type(expected_epoch) is not int or expected_epoch < 0:
            raise ValueError('INVALID_SOURCE_EPOCH')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT epoch,stale,revoked,revision FROM sources WHERE id=?',(source,)).fetchone()
            if old is None:
                if expected_epoch != 0:raise PermissionError('SOURCE_EPOCH_NOT_INITIAL')
                db.execute('INSERT INTO sources VALUES(?,?,?, ?,0,0)',(source,0,revision,digest))
            elif old[2] or not old[1] or expected_epoch!=old[0] or revision==old[3]:
                raise PermissionError('SOURCE_REVOKED_LIVE_OR_STALE_EPOCH')
            else:
                db.execute('UPDATE sources SET revision=?,digest=?,stale=0 WHERE id=?',(revision,digest,source))
            db.commit()

    def invalidate_source(self, source: str, *, reason: str):
        self._name(source)
        if reason not in ('EDIT','RETRACT','DELETE','SCOPE_REVOKED','RESTORE','SOURCE_REPLACED'):
            raise ValueError('INVALID_SOURCE_CHANGE')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT epoch,revoked FROM sources WHERE id=?',(source,)).fetchone()
            if row is None:raise ValueError('UNKNOWN_SOURCE')
            if row[1]:raise PermissionError('SOURCE_TERMINALLY_REVOKED')
            epoch=row[0]+1
            db.execute('UPDATE sources SET epoch=?,stale=1,revoked=? WHERE id=?',(epoch,int(reason=='SCOPE_REVOKED'),source))
            db.commit()
            return epoch

    def deliver_hdc(self, source: str, epoch: int, revision: str, digest: str,
                    index: EphemeralDerivedIndex, role: str, entity: str, top_k: int, sink):
        self._name(source);self._name(revision);self._hex(digest)
        if type(epoch) is not int or type(index) is not EphemeralDerivedIndex:
            raise ValueError('INVALID_REFERENCE_INDEX')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT epoch,revision,digest,stale,revoked FROM sources WHERE id=?',(source,)).fetchone()
            if row != (epoch,revision,digest,0,0):
                raise PermissionError('HDC_REVISION_WITNESS_MISMATCH')
            # Cross-process source changes blocked until result callback completes.
            generation=index.deliver(revision,role,entity,top_k,sink)
            db.commit()
            return generation

    def enroll_signer(self, signer: HostTrustedApprover, *, local_host_enrollment=False):
        if type(signer) is not HostTrustedApprover or signer.revoked or local_host_enrollment is not True:
            raise PermissionError('HOST_ENROLLMENT_REQUIRED')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            try: db.execute('INSERT INTO signers VALUES(?,?,?,?,0)',(signer.signer_id,signer.public_key,signer.model_id,signer.training_split_sha256))
            except sqlite3.IntegrityError as e:raise PermissionError('SIGNER_ID_IMMUTABLE') from e
            db.commit()

    def revoke_signer(self, signer_id: str):
        self._name(signer_id)
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('UPDATE signers SET revoked=1 WHERE id=?',(signer_id,)).rowcount!=1:
                raise ValueError('UNKNOWN_SIGNER')
            db.commit()

    def predict_kan(self, signer_id: str, request: bytes, checkpoint: bytes,
                    policy: ResearchPolicy, approval: bytes):
        self._name(signer_id)
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT public_key,model,training,revoked FROM signers WHERE id=?',(signer_id,)).fetchone()
            if row is None or row[3]:raise PermissionError('SIGNER_REVOKED_OR_UNKNOWN')
            trusted=HostTrustedApprover(signer_id,row[0],row[1],row[2])
            # Signature/feature/pin verified by existing C09 implementation.
            result=predict_approved(request,checkpoint,policy,approval,trusted)
            db.commit()
            return result
