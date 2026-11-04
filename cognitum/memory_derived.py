"""C06 read-only, rebuildable SQLite FTS5 index over Lu-owned ANSF snapshots.

No canonical memory database or mutation endpoint exists here. Only the
Lu host can supply authorized snapshot rows and a capability-scoped query.
The index lives in process memory and is invalidated/rebuilt on revision
changes. Retrieval result text is untrusted quoted evidence, never policy.
"""
from dataclasses import dataclass
from hashlib import sha256
import re
import sqlite3
from typing import Optional

MAX_ROWS=4096
MAX_TEXT=8192
MAX_QUERY=256
MAX_RESULTS=32
TOKEN=re.compile(r"[A-Za-z0-9_]{2,40}")

@dataclass(frozen=True)
class Evidence:
    source_id:str
    source_revision:int
    scope_id:str
    subject:str
    text:str
    citation_handle:str
    valid_from_ms:int
    valid_to_ms:Optional[int]
    tombstoned:bool=False

@dataclass(frozen=True)
class Snapshot:
    owner:str
    snapshot_id:str
    owner_revision:int
    rows:tuple[Evidence,...]

@dataclass(frozen=True)
class Query:
    scope_id:str
    query_text:str
    expected_snapshot_id:str
    expected_owner_revision:int
    max_results:int=8
    as_of_ms:Optional[int]=None
    subject:Optional[str]=None

@dataclass(frozen=True)
class Hit:
    source_id:str
    source_revision:int
    subject:str
    citation_handle:str
    text:str
    score:float
    snapshot_id:str

def _id(value):
    return type(value) is str and 1<=len(value)<=96 and re.fullmatch("[A-Za-z0-9_.:-]+",value) is not None

def validate_snapshot(s:Snapshot):
    if (type(s) is not Snapshot or s.owner!="Lu_ANSF" or not _id(s.snapshot_id)
            or type(s.owner_revision) is not int or s.owner_revision<0
            or type(s.rows) is not tuple or len(s.rows)>MAX_ROWS):
        raise ValueError("invalid or non-Lu canonical snapshot")
    seen=set()
    for r in s.rows:
        if (type(r) is not Evidence or not _id(r.source_id)
                or not _id(r.scope_id) or not _id(r.subject)
                or not _id(r.citation_handle)
                or type(r.source_revision) is not int or r.source_revision<0
                or type(r.text) is not str or len(r.text)>MAX_TEXT
                or type(r.valid_from_ms) is not int or r.valid_from_ms<0
                or (r.valid_to_ms is not None and
                    (type(r.valid_to_ms) is not int or r.valid_to_ms<=r.valid_from_ms))
                or type(r.tombstoned) is not bool
                or (r.scope_id,r.source_id) in seen):
            raise ValueError("malformed, duplicate or ambiguous Lu evidence")
        seen.add((r.scope_id,r.source_id))
    return s

class DerivedIndex:
    def __init__(self,snapshot:Snapshot):
        self.snapshot=validate_snapshot(snapshot)
        self.conn=sqlite3.connect(":memory:")
        try:
            self.conn.execute("CREATE VIRTUAL TABLE evidence_fts USING fts5(text, subject, tokenize='unicode61')")
        except sqlite3.OperationalError as exc:
            self.conn.close()
            raise RuntimeError("SQLite FTS5 backend unavailable") from exc
        self.conn.execute("""CREATE TABLE evidence_meta(
            rowid INTEGER PRIMARY KEY, scope_id TEXT NOT NULL,
            source_id TEXT NOT NULL, revision INTEGER NOT NULL,
            subject TEXT NOT NULL, citation TEXT NOT NULL,
            valid_from INTEGER NOT NULL, valid_to INTEGER, tombstone INTEGER NOT NULL)""")
        self.conn.execute("BEGIN")
        try:
            for i,r in enumerate(snapshot.rows,1):
                self.conn.execute(
                    "INSERT INTO evidence_meta VALUES (?,?,?,?,?,?,?,?,?)",
                    (i,r.scope_id,r.source_id,r.source_revision,r.subject,
                     r.citation_handle,r.valid_from_ms,r.valid_to_ms,int(r.tombstoned)))
                if not r.tombstoned:
                    self.conn.execute("INSERT INTO evidence_fts(rowid,text,subject) VALUES(?,?,?)",
                                      (i,r.text,r.subject))
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            self.conn.close()
            raise

    def close(self):
        self.conn.close()

    def query(self,q:Query)->tuple[Hit,...]:
        if (type(q) is not Query or not _id(q.scope_id)
                or q.expected_snapshot_id!=self.snapshot.snapshot_id
                or type(q.expected_owner_revision) is not int
                or q.expected_owner_revision!=self.snapshot.owner_revision
                or type(q.query_text) is not str or len(q.query_text)>MAX_QUERY
                or type(q.max_results) is not int or not 1<=q.max_results<=MAX_RESULTS
                or (q.as_of_ms is not None and
                    (type(q.as_of_ms) is not int or q.as_of_ms<0))
                or (q.subject is not None and not _id(q.subject))):
            raise ValueError("stale or unauthorized derived-index request")
        tokens=TOKEN.findall(q.query_text)
        if not tokens:
            return ()
        # Quoted tokens and parameter binding block FTS query-language
        # injection; OR semantics support short natural-language recall.
        expression=" OR ".join('"' + t + '"' for t in tokens[:16])
        rows=self.conn.execute(
            """SELECT m.source_id,m.revision,m.subject,m.citation,
                      f.text,bm25(evidence_fts) AS rank
               FROM evidence_fts AS f
               JOIN evidence_meta AS m ON m.rowid=f.rowid
               WHERE evidence_fts MATCH ? AND m.scope_id=?
                 AND m.tombstone=0
                 AND (? IS NULL OR m.subject=?)
                 AND (? IS NULL OR
                      (m.valid_from<=? AND (m.valid_to IS NULL OR ?<m.valid_to)))
               ORDER BY rank ASC,m.source_id ASC LIMIT ?""",
            (expression,q.scope_id,q.subject,q.subject,q.as_of_ms,q.as_of_ms,
             q.as_of_ms,q.max_results)).fetchall()
        return tuple(Hit(a,b,c,d,e,float(-f),self.snapshot.snapshot_id)
                     for a,b,c,d,e,f in rows)

    def exact(self,scope_id:str,source_id:str,*,expected_owner_revision:int)->Optional[Hit]:
        if (not _id(scope_id) or not _id(source_id)
                or type(expected_owner_revision) is not int
                or expected_owner_revision!=self.snapshot.owner_revision):
            raise ValueError("invalid scope or stale owner revision")
        r=self.conn.execute(
            """SELECT m.source_id,m.revision,m.subject,m.citation,f.text
               FROM evidence_meta AS m
               JOIN evidence_fts AS f ON f.rowid=m.rowid
               WHERE m.scope_id=? AND m.source_id=? AND m.tombstone=0""",
            (scope_id,source_id)).fetchone()
        return Hit(*r,0.0,self.snapshot.snapshot_id) if r is not None else None
