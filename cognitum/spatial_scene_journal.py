"""C15 durable SQLite scene revision custody (trusted host-owned path only).

No untrusted path selection and no permissions by inference. Whole-snapshot
transactions with compare-and-swap revision, deterministic JSON and hash-chain
integrity checks; file/os-level provenance, crash-free persistence or tamper
resistance are NOT authenticated by SQLite hashes alone.
"""
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from .spatial_geometry import Frame,SceneObject
from .spatial_lifecycle import Evidence,Entity,SceneRevision,validate_revision

MAX_SNAPSHOT_BYTES=256*1024
SCHEMA=1


def encode(rev:SceneRevision)->bytes:
    validate_revision(rev)
    data=json.dumps({"schema":SCHEMA,"revision":asdict(rev)},
                    sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")
    if len(data)>MAX_SNAPSHOT_BYTES:
        raise ValueError("oversized scene snapshot")
    return data


def decode(data:bytes)->SceneRevision:
    if type(data) is not bytes or not 0<len(data)<=MAX_SNAPSHOT_BYTES:
        raise ValueError("invalid scene snapshot frame")
    try:
        obj=json.loads(data)
        if type(obj) is not dict or set(obj)!={"schema","revision"} or obj["schema"]!=SCHEMA:
            raise ValueError("unknown snapshot schema")
        r=obj["revision"]
        if type(r) is not dict or set(r)!={"scene_id","revision","frames","entities","epoch","event_ids"}:
            raise ValueError("malformed snapshot fields")
        frames=tuple(Frame(x["name"],x["parent"],tuple(x["translation_m"]),
                           tuple(x["quaternion_xyzw"])) for x in r["frames"])
        entities=[]
        for e in r["entities"]:
            obj=e["obj"]
            scene_obj=SceneObject(
                obj["stable_id"],obj["frame"],tuple(obj["position_m"]),
                tuple(obj["dimensions_m"]),obj["visible"],
                obj["observation_source"],obj["timestamp_ms"],obj["version"],
                tuple(obj.get("orientation_xyzw",[0.,0.,0.,1.])),
                obj.get("geometry_ref","unresolved"),
                obj.get("confidence",0.0),
            )
            ev=tuple(Evidence(**v) for v in e["evidence"])
            entities.append(Entity(scene_obj,tuple(e["aliases"]),ev,e["state"]))
        rev=SceneRevision(r["scene_id"],r["revision"],frames,tuple(entities),
                          r["epoch"],tuple(r["event_ids"]))
        validate_revision(rev)
        if encode(rev)!=data:
            raise ValueError("noncanonical snapshot encoding")
        return rev
    except (KeyError,TypeError,ValueError,OverflowError,UnicodeError) as exc:
        raise ValueError("invalid scene snapshot content") from exc


class SceneJournal:
    """Create with a path supplied by an authorized host; no caller path API."""

    def __init__(self,db_path:Path):
        if type(db_path) is not Path or not db_path.is_absolute():
            raise ValueError("host-owned absolute SQLite path required")
        self.db_path=db_path
        # No path creation or directory traversal by model-issued action.
        if not db_path.parent.is_dir() or db_path.is_symlink():
            raise ValueError("invalid journal parent or symlink")
        self.db=sqlite3.connect(str(db_path),timeout=5,isolation_level=None)
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS scene_revisions(
            scene_id TEXT NOT NULL,
            revision INTEGER NOT NULL,
            prior_sha256 TEXT NOT NULL,
            payload_sha256 TEXT NOT NULL,
            payload BLOB NOT NULL,
            PRIMARY KEY(scene_id,revision))""")

    def close(self):
        self.db.close()

    def put(self,revision:SceneRevision,*,expected_previous:int):
        frame=encode(revision)
        if type(expected_previous) is not int or revision.revision!=expected_previous+1:
            raise ValueError("revision monotonic CAS required")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            previous=self.db.execute(
                "SELECT revision,payload_sha256,payload FROM scene_revisions "
                "WHERE scene_id=? ORDER BY revision DESC LIMIT 1",
                (revision.scene_id,)).fetchone()
            current=-1 if previous is None else previous[0]
            if current!=expected_previous:
                raise ValueError("scene CAS mismatch")
            if previous is not None:
                stored=decode(previous[2])
                if stored.revision!=current or sha256(previous[2]).hexdigest()!=previous[1]:
                    raise ValueError("existing snapshot integrity failure")
                prior_hash=previous[1]
            else:
                prior_hash="0"*64
            self.db.execute(
                "INSERT INTO scene_revisions(scene_id,revision,prior_sha256,payload_sha256,payload)"
                " VALUES (?,?,?,?,?)",
                (revision.scene_id,revision.revision,prior_hash,
                 sha256(frame).hexdigest(),frame))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def restore(self,scene_id:str)->SceneRevision|None:
        rows=self.db.execute(
            "SELECT revision,prior_sha256,payload_sha256,payload FROM scene_revisions "
            "WHERE scene_id=? ORDER BY revision ASC",(scene_id,)).fetchall()
        if not rows:
            return None
        expected_index=0
        previous="0"*64
        most_recent=None
        for revision,prior,digest,payload in rows:
            if revision!=expected_index or prior!=previous or sha256(payload).hexdigest()!=digest:
                raise ValueError("scene revision chain compromised")
            item=decode(payload)
            if item.scene_id!=scene_id or item.revision!=revision:
                raise ValueError("scene identity revision mismatch")
            most_recent=item
            previous=digest
            expected_index+=1
        return most_recent
