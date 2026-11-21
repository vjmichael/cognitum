"""Independent host-controlled SQLite revision CAS for MEL SSM R6 checkpoints.

A separate ACL-protected SQLite database uses FULL synchronous DELETE-journal
transactions, compares expected revisions and exact checkpoint digests, and
authenticates records with a key borrowed from the native OS credential broker.

Do not mistake HMAC-sealed local files for a hardware monotonic counter:
an attacker able to replace/restore BOTH whole trusted files may roll back
the authority, and OS account compromise exposes the HMAC key. A real TPM/
hardware/remote independent anti-rollback floor and protected installer ACL
must be separately provided before production *authoritative* qualification.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path
import sqlite3

from cognitum.research import ssm_stochastic_checkpoints as cp
from . import admission as mel
from .ssm_os_credentials import _root, _scope_key

MAC_DOMAIN=b"cognitum.mel.ssm_r6.revision_CAS.v1\x00"


def _need(test,detail):
    if not test:
        raise ValueError("SSM local revision CAS refused: "+detail)


def _digest(value):
    _need(type(value) is str and len(value)==64 and
          all(c in "0123456789abcdef" for c in value),
          "exact SHA256 hex digest")
    return value


class LocalAuthenticatedRevisionCAS:
    """Host-scoped revision CAS, not a physical anti-rollback root of trust.

    The path must be created/approved by a trusted host, separate from the
    mathematical stream DB. It does not silently recreate a missing file at
    restart (create=False); installer must explicitly approve first creation.
    """

    def __init__(self,directory,credential_broker,*,namespace,
                 create=False):
        self._dir=_root(directory)
        self._namespace=cp._identifier(namespace,"revision namespace")
        _need(callable(getattr(credential_broker,"borrow_key",None)),
              "OS credential custody interface")
        self._broker=credential_broker
        _need(type(create) is bool,"explicit create flag")
        self._path=self._dir/("cog_ssm_"+self._namespace+".revisions.sqlite")
        _need(not self._path.is_symlink(),"database symlink")
        if create:
            # The host must explicitly make a new authority. Never truncate.
            try:
                fd=os.open(self._path,os.O_RDWR|os.O_CREAT|os.O_EXCL,0o600)
                os.close(fd)
            except FileExistsError:
                pass
        _need(self._path.is_file(),"existing protected authority DB required")
        if os.name=="posix":
            _need(not(self._path.stat().st_mode&0o077),"owner-only DB")
        self._db=sqlite3.connect(str(self._path),timeout=4,isolation_level=None)
        self._db.row_factory=sqlite3.Row
        try:
            self._db.execute("PRAGMA journal_mode=DELETE")
            self._db.execute("PRAGMA synchronous=FULL")
            self._db.execute("PRAGMA trusted_schema=OFF")
            self._db.execute("PRAGMA busy_timeout=4000")
            self._db.execute("""CREATE TABLE IF NOT EXISTS anchor (
                scoped_stream TEXT PRIMARY KEY,
                revision INTEGER NOT NULL CHECK (revision>=1),
                checkpoint_sha TEXT NOT NULL,
                record_mac TEXT NOT NULL)""")
        except BaseException:
            self._db.close()
            raise

    def _identity(self,scope,sid):
        _need(type(scope) is mel.Scope,"reviewed MEL Scope")
        return _scope_key(scope,sid,self._namespace)

    def _signature(self,scope,sid,revision,digest):
        key=cp._auth_key(self._broker.borrow_key(scope,sid))
        raw=(MAC_DOMAIN+self._identity(scope,sid).encode("ascii")+
             b"\x00"+str(revision).encode("ascii")+b"\x00"+
             digest.encode("ascii"))
        return hmac.new(key,raw,hashlib.sha256).hexdigest()

    def _read_in_transaction(self,scope,sid):
        identity=self._identity(scope,sid)
        row=self._db.execute("SELECT * FROM anchor WHERE scoped_stream=?",
                             (identity,)).fetchone()
        if row is None:
            # An *empty* DB can only be used for explicit bootstrap by the
            # trusted installer; deletion of an older row is beyond local CAS.
            return (0,None)
        revision=row["revision"]
        _need(type(revision) is int and 1<=revision<2**63-1,
              "stored revision")
        digest=_digest(row["checkpoint_sha"])
        _need(type(row["record_mac"]) is str and
              hmac.compare_digest(row["record_mac"],
                                  self._signature(scope,sid,revision,digest)),
              "stored anchor MAC mismatch")
        return revision,digest

    def read(self,scope,sid):
        self._db.execute("BEGIN IMMEDIATE")
        try:
            result=self._read_in_transaction(scope,sid)
            self._db.commit()
            return result
        except BaseException:
            self._db.rollback()
            raise

    def advance(self,scope,sid,old_revision,old_digest,
                new_revision,new_digest):
        _need(type(old_revision) is int and 0<=old_revision<2**63-1
              and type(new_revision) is int
              and old_revision<new_revision<2**63-1,
              "strictly monotonic revision")
        _need((old_digest is None)==(old_revision==0),"prior anchor pair")
        if old_digest is not None:_digest(old_digest)
        _digest(new_digest)
        self._db.execute("BEGIN IMMEDIATE")
        try:
            prior=self._read_in_transaction(scope,sid)
            _need(prior==(old_revision,old_digest),
                  "atomic revision or exact digest CAS mismatch")
            signed=self._signature(scope,sid,new_revision,new_digest)
            if old_revision==0:
                self._db.execute(
                    "INSERT INTO anchor VALUES (?,?,?,?)",
                    (self._identity(scope,sid),new_revision,new_digest,signed))
            else:
                cursor=self._db.execute(
                    "UPDATE anchor SET revision=?,checkpoint_sha=?,record_mac=? "
                    "WHERE scoped_stream=? AND revision=? AND checkpoint_sha=?",
                    (new_revision,new_digest,signed,self._identity(scope,sid),
                     old_revision,old_digest))
                _need(cursor.rowcount==1,"stale revision update")
            self._db.commit()
        except BaseException:
            self._db.rollback()
            raise

    def close(self):
        self._db.close()
