"""C18 host-owned SQLite lifecycle journal, metadata-only restart recovery.

No trace features, labels, prompts, model weights or raw consent documents
are written to this journal. SHA256 chains detect accidental inconsistencies,
NOT deliberate manipulation by an attacker controlling the database. Only the
Lu host may select a path or independently grant storage permission.
"""
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from .adaptation_lifecycle import Lifecycle,verify_lifecycle

MAX_FRAME=16384

def _encode(state:Lifecycle)->bytes:
    verify_lifecycle(state)
    data=json.dumps(asdict(state),sort_keys=True,separators=(",",":")).encode("utf-8")
    if not 0<len(data)<=MAX_FRAME:
        raise ValueError("oversized adaptation lifecycle metadata")
    return data

def _decode(data):
    if type(data) is not bytes or not 0<len(data)<=MAX_FRAME:
        raise ValueError("invalid policy journal snapshot")
    try:
        obj=json.loads(data)
        if type(obj) is not dict or set(obj)!=set(Lifecycle.__dataclass_fields__):
            raise ValueError("unknown journal metadata schema")
        state=Lifecycle(
            obj["workspace_id"],obj["current_policy_digest"],
            obj["fallback_policy_digest"],obj["proposal_id"],
            obj["status"],obj["revision"],tuple(obj["seen_mutations"]),
            obj["receipt_digest"])
        verify_lifecycle(state)
        if _encode(state)!=data:
            raise ValueError("noncanonical policy journal bytes")
        return state
    except (ValueError,TypeError,KeyError,UnicodeError) as exc:
        raise ValueError("invalid or tampered lifecycle journal metadata") from exc

def _successor(before:Lifecycle,after:Lifecycle):
    if (before.workspace_id!=after.workspace_id
            or before.proposal_id!=after.proposal_id
            or before.fallback_policy_digest!=after.fallback_policy_digest
            or after.revision!=before.revision+1
            or len(after.seen_mutations)!=len(before.seen_mutations)+1
            or after.seen_mutations[:len(before.seen_mutations)]!=before.seen_mutations):
        raise ValueError("policy journal custody or revision discontinuity")
    status=before.status;target=after.status
    allowed={
        "prepared":{"active","revoked"},
        "active":{"paused","rolled_back","revoked"},
        "paused":{"active","rolled_back","revoked"},
        "rolled_back":{"revoked"},
        "revoked":set(),
    }
    if target not in allowed[status]:
        raise ValueError("invalid durable adaptation transition")
    if (target in ("rolled_back","revoked") and
            after.current_policy_digest!=after.fallback_policy_digest):
        raise ValueError("rolled-back policy still points to candidate")
    if (target in ("paused","active") and status!="prepared"
            and after.current_policy_digest!=before.current_policy_digest):
        raise ValueError("policy digest changed outside an approved proposal")
    if target=="active" and status=="prepared":
        if after.current_policy_digest==after.fallback_policy_digest:
            raise ValueError("no candidate was activated")

class AdaptationJournal:
    def __init__(self,path:Path):
        if (not isinstance(path,Path) or not path.is_absolute()
                or path.is_symlink() or not path.parent.is_dir()):
            raise ValueError("trusted host-owned absolute SQLite path required")
        self.db=sqlite3.connect(str(path),isolation_level=None,timeout=5)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS adaptation_revisions(
            workspace_id TEXT NOT NULL,
            proposal_id TEXT NOT NULL,
            revision INTEGER NOT NULL,
            prior_sha256 TEXT NOT NULL,
            payload_sha256 TEXT NOT NULL,
            payload BLOB NOT NULL,
            PRIMARY KEY(workspace_id,proposal_id,revision))""")

    def close(self):
        self.db.close()

    def put(self,state:Lifecycle,*,expected_previous:int):
        frame=_encode(state)
        if (type(expected_previous) is not int
                or state.revision!=expected_previous+1):
            raise ValueError("strict lifecycle CAS revision required")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row=self.db.execute(
                "SELECT revision,payload_sha256,payload FROM adaptation_revisions "
                "WHERE workspace_id=? AND proposal_id=? ORDER BY revision DESC LIMIT 1",
                (state.workspace_id,state.proposal_id)).fetchone()
            current=-1 if row is None else row[0]
            if current!=expected_previous:
                raise ValueError("stale adaptation revision")
            if row is None:
                if (state.revision!=0 or state.status!="prepared"
                        or state.seen_mutations
                        or state.current_policy_digest!=state.fallback_policy_digest):
                    raise ValueError("invalid initial policy anchor")
                prior="0"*64
            else:
                original=_decode(row[2])
                if sha256(row[2]).hexdigest()!=row[1]:
                    raise ValueError("existing checkpoint digest mismatch")
                _successor(original,state)
                prior=row[1]
            self.db.execute(
                "INSERT INTO adaptation_revisions"
                "(workspace_id,proposal_id,revision,prior_sha256,payload_sha256,payload)"
                " VALUES (?,?,?,?,?,?)",
                (state.workspace_id,state.proposal_id,state.revision,
                 prior,sha256(frame).hexdigest(),frame))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def restore(self,workspace_id:str,proposal_id:str)->Lifecycle|None:
        rows=self.db.execute(
            "SELECT revision,prior_sha256,payload_sha256,payload FROM adaptation_revisions "
            "WHERE workspace_id=? AND proposal_id=? ORDER BY revision ASC",
            (workspace_id,proposal_id)).fetchall()
        previous_digest="0"*64
        previous_state=None
        for ordinal,(revision,prior,digest,data) in enumerate(rows):
            if (revision!=ordinal or prior!=previous_digest
                    or sha256(data).hexdigest()!=digest):
                raise ValueError("tampered or incomplete adaptation history")
            state=_decode(data)
            if (state.workspace_id!=workspace_id or state.proposal_id!=proposal_id
                    or state.revision!=revision):
                raise ValueError("cross-workspace policy journal substitution")
            if previous_state is not None:
                _successor(previous_state,state)
            elif (state.status!="prepared" or state.seen_mutations
                  or state.current_policy_digest!=state.fallback_policy_digest):
                raise ValueError("missing initial policy anchor")
            previous_state=state
            previous_digest=digest
        return previous_state
