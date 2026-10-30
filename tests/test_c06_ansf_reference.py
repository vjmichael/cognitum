"""C06/P3 against disposable SQLite fixtures mirroring pinned Lu ANSF DDL.

No user's Lu data, paths, real credentials or active CE/tool are used.
"""
import sqlite3
import threading
import unittest
from dataclasses import replace

from cognitum.ansf_read_reference import select_ansf_fts_frames, select_ansf_citation_snapshot
from cognitum.memory_evidence import TrustedReadContext, encode_frame, verify_candidate_batch
from cognitum.memory_host_gate import dispatch_host_fenced
from cognitum.proto import memory_pb2 as pb


SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE ansf_sessions (
 id TEXT PRIMARY KEY NOT NULL, workspace_id TEXT NOT NULL,
 title TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE ansf_chapters (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 session_id TEXT NOT NULL REFERENCES ansf_sessions(id),
 title TEXT NOT NULL, summary TEXT NOT NULL DEFAULT '',
 start_entry_id INTEGER, end_entry_id INTEGER,
 closed INTEGER NOT NULL DEFAULT 0 CHECK(closed IN (0,1))
);
CREATE TABLE ansf_entries (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 session_id TEXT NOT NULL REFERENCES ansf_sessions(id),
 chapter_id INTEGER NOT NULL REFERENCES ansf_chapters(id),
 message_id TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('user','assistant','tool_call','tool_result','system')),
 summary TEXT NOT NULL, content TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(session_id,message_id)
);
CREATE VIRTUAL TABLE ansf_entries_fts USING fts5(
 summary,content,content='ansf_entries',content_rowid='id');
CREATE TRIGGER ansf_entries_index_insert AFTER INSERT ON ansf_entries BEGIN
 INSERT INTO ansf_entries_fts(rowid,summary,content)
 VALUES(new.id,new.summary,new.content);
END;
CREATE TABLE ansf_entry_edits (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 session_id TEXT NOT NULL REFERENCES ansf_sessions(id),
 original_entry_id INTEGER NOT NULL REFERENCES ansf_entries(id),
 previous_entry_id INTEGER NOT NULL UNIQUE REFERENCES ansf_entries(id),
 revised_entry_id INTEGER NOT NULL UNIQUE REFERENCES ansf_entries(id),
 revision_number INTEGER NOT NULL CHECK(revision_number>0),
 origin TEXT NOT NULL CHECK(origin IN ('verified_user','import_observed')),
 note TEXT NOT NULL, observed_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(original_entry_id,revision_number)
);
"""


def fresh_db():
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.executescript(SCHEMA)
    for session, workspace in (("sa", "ownerA"), ("sb", "ownerB")):
        conn.execute("INSERT INTO ansf_sessions(id,workspace_id,title) VALUES(?,?,?)",
                     (session, workspace, "Synthetic"))
        conn.execute("INSERT INTO ansf_chapters(session_id,title) VALUES(?,?)",
                     (session, "Synthetic chapter"))
    return conn


def entry(conn, session, text, *, summary="note", role="user"):
    chapter = conn.execute("SELECT id FROM ansf_chapters WHERE session_id=?", (session,)).fetchone()[0]
    cursor = conn.execute(
        "INSERT INTO ansf_entries(session_id,chapter_id,message_id,role,summary,content) "
        "VALUES(?,?,?,?,?,?)", (session, chapter, f"msg-{session}-{conn.total_changes}", role, summary, text))
    return cursor.lastrowid


def edit(conn, session, root, text, *, prior=None, sequence=1, origin="verified_user"):
    if prior is None:
        prior = root
    new_id = entry(conn, session, text)
    conn.execute("INSERT INTO ansf_entry_edits(session_id,original_entry_id,previous_entry_id,"
                 "revised_entry_id,revision_number,origin,note) VALUES(?,?,?,?,?,?,?)",
                 (session, root, prior, new_id, sequence, origin, "synthetic"))
    return new_id


def context(*, historical=False, sessions=frozenset({"sa"})):
    return TrustedReadContext(scope_id="local-profile", snapshot_id="local-snap",
                              authorization_epoch=7, index_epoch=12,
                              authorized_sessions=sessions, allow_historical=historical)


def query(text, *, historical=False, exact=()):
    q = pb.MemoryQuery(schema_version=1, request_id="local-request",
                       literal_query=text, max_results=8, include_historical=historical)
    q.exact_sources.extend(exact)
    return encode_frame(q)


class SyntheticLease:
    def __init__(self, parent):
        self.parent = parent

    def __enter__(self):
        self.parent.lock.acquire()
        self.parent.in_lease = True
        self.parent.conn.execute("PRAGMA query_only=ON")
        self.parent.conn.execute("BEGIN")
        return self

    def __exit__(self, *args):
        self.parent.conn.execute("ROLLBACK")
        self.parent.conn.execute("PRAGMA query_only=OFF")
        self.parent.in_lease = False
        self.parent.lock.release()

    @property
    def context(self):
        return self.parent.ctx

    def ansf_fts_frames(self, frame):
        return select_ansf_fts_frames(frame, self.parent.conn,
                                       context=self.context, session_id="sa",
                                       tombstoned_roots=frozenset(self.parent.tombstones))

    def ansf_citation_snapshot(self, frame):
        return select_ansf_citation_snapshot(frame, self.parent.conn,
                                             context=self.context, session_id="sa",
                                             tombstoned_roots=frozenset(self.parent.tombstones))

    def recheck(self):
        if self.parent.before_recheck:
            self.parent.before_recheck(self.parent)
        if not self.parent.live:
            return pb.DENIED
        if self.parent.cancelled:
            return pb.CANCELLED
        if self.parent.deleted_after_read:
            return pb.DELETED
        if self.parent.epoch != self.context.authorization_epoch:
            return pb.DENIED
        if self.parent.index_epoch != self.context.index_epoch:
            return pb.STALE
        return pb.VERIFIED

    def publish(self, frame):
        assert self.parent.in_lease
        self.parent.published.append(frame)


class SyntheticGateway:
    def __init__(self, conn, *, ctx=None):
        self.conn = conn
        self.ctx = ctx or context()
        self.lock = threading.RLock()
        self.in_lease = False
        self.live = True
        self.cancelled = False
        self.deleted_after_read = False
        self.epoch = self.ctx.authorization_epoch
        self.index_epoch = self.ctx.index_epoch
        self.before_recheck = None
        self.published = []
        self.tombstones = set()

    def acquire(self):
        return SyntheticLease(self)

    def search(self, frame):
        return dispatch_host_fenced("ansf_fts", frame, gateway=self)

    def latest(self):
        return pb.RetrievalReply.FromString(self.published[-1])

    def citation(self, frame):
        return dispatch_host_fenced("ansf_citation", frame, gateway=self)

    def latest_citation(self):
        return pb.CitationResolution.FromString(self.published[-1])


class AnsfSchemaConformanceTests(unittest.TestCase):
    def setUp(self):
        self.db = fresh_db()
        self.addCleanup(self.db.close)
        self.host = SyntheticGateway(self.db)

    def test_fts_reads_only_host_owned_session_and_current_revision(self):
        original = entry(self.db, "sa", "old banana")
        revision = edit(self.db, "sa", original, "new banana α")
        entry(self.db, "sb", "secret banana")
        r = self.host.search(query("banana"))
        self.assertEqual(r.status, pb.VERIFIED)
        self.assertTrue(r.published)
        out = self.host.latest()
        self.assertEqual(len(out.evidence), 1)
        e = out.evidence[0]
        self.assertEqual((e.source.session_id, e.source.entry_id, e.source.revision_id),
                         ("sa", str(original), str(revision)))
        self.assertIn("new banana", e.excerpt)
        self.assertNotIn("secret banana", e.excerpt)
        self.assertEqual(e.revision_kind, pb.CURRENT)

    def test_superseded_only_fts_hit_must_not_reveal_old_record(self):
        orig = entry(self.db, "sa", "replaced keyword")
        edit(self.db, "sa", orig, "revised without the old term")
        self.assertEqual(self.host.search(query("keyword")).status, pb.VERIFIED)
        self.assertFalse(self.host.latest().evidence)

    def test_historical_requires_host_and_query_agreement(self):
        orig = entry(self.db, "sa", "historical archaeology")
        edit(self.db, "sa", orig, "current text")
        self.assertEqual(self.host.search(query("archaeology", historical=True)).status, pb.DENIED)
        self.host.ctx = replace(self.host.ctx, allow_historical=True)
        self.host.published.clear()
        self.assertEqual(self.host.search(query("archaeology", historical=True)).status, pb.VERIFIED)
        e = self.host.latest().evidence[0]
        self.assertEqual(e.revision_kind, pb.HISTORICAL)
        self.assertEqual(e.source.revision_id, str(orig))

    def test_fts_operators_cannot_expand_search_to_other_terms(self):
        entry(self.db, "sa", "alpha")
        entry(self.db, "sa", "beta")
        self.assertEqual(self.host.search(query('alpha OR beta')).status, pb.VERIFIED)
        self.assertFalse(self.host.latest().evidence)
        self.assertEqual(self.host.search(query('alpha*')).status, pb.VERIFIED)
        self.assertEqual(len(self.host.latest().evidence), 1)
        # Query operators are literal lexical input; never an FTS MATCH DSL.
        self.assertEqual(self.host.search(query('title:ghost')).status, pb.VERIFIED)
        self.assertFalse(self.host.latest().evidence)

    def test_host_denials_and_cancellation_drop_verified_evidence(self):
        entry(self.db, "sa", "belonging")
        for attr, value, expected in (("live", False, pb.DENIED),
                                     ("cancelled", True, pb.CANCELLED),
                                     ("deleted_after_read", True, pb.DELETED),
                                     ("epoch", 8, pb.DENIED),
                                     ("index_epoch", 13, pb.STALE)):
            host = SyntheticGateway(self.db)
            host.before_recheck = lambda h, a=attr, v=value: setattr(h, a, v)
            receipt = host.search(query("belonging"))
            self.assertEqual(receipt.status, expected)
            self.assertTrue(receipt.published)
            self.assertFalse(host.latest().evidence)
            self.assertTrue(not host.in_lease)

    def test_tombstone_never_exposes_text_or_candidate_hint(self):
        root = entry(self.db, "sa", "tombstone secret")
        entry(self.db, "sa", "normal secret")
        self.host.tombstones.add(root)
        self.assertEqual(self.host.search(query("secret")).status, pb.VERIFIED)
        self.assertEqual(len(self.host.latest().evidence), 1)
        self.assertIn("normal", self.host.latest().evidence[0].excerpt)
        source = pb.SourceRef(session_id="sa", chapter_id="1", entry_id=str(root),
                              revision_id=str(root))
        self.assertEqual(self.host.search(query("secret", exact=[source])).status, pb.DELETED)
        self.assertFalse(self.host.latest().evidence)

    def test_wrong_session_and_missing_host_read_transaction_fail_closed(self):
        entry(self.db, "sa", "phrase")
        req = query("phrase")
        status, batch, snap = select_ansf_fts_frames(req, self.db, context=context(), session_id="sa", tombstoned_roots=frozenset())
        self.assertEqual(status, pb.UNAVAILABLE)
        self.assertIsNone(batch)
        self.assertIsNone(snap)
        with self.host.acquire():
            s, _, _ = select_ansf_fts_frames(req, self.db, context=context(), session_id="sb", tombstoned_roots=frozenset())
            self.assertEqual(s, pb.DENIED)
            s, _, _ = select_ansf_fts_frames(req, self.db, context=context(), session_id="sa", tombstoned_roots=frozenset())
            self.assertEqual(s, pb.VERIFIED)

    def test_no_direct_model_supplied_candidate_or_sql_path(self):
        entry(self.db, "sa", "authorized")
        self.assertEqual(self.host.search(query("authorized")).status, pb.VERIFIED)
        invalid = self.host.search(query("authorized"))
        self.assertEqual(invalid.status, pb.VERIFIED)
        # Caller-selected candidate injection is rejected for this operation.
        reject = dispatch_host_fenced("ansf_fts", query("authorized"), gateway=self.host,
                                      candidate_frame=b"hostile")
        self.assertEqual(reject.status, pb.INVALID)
        self.assertFalse(self.host.latest().evidence)

    def test_corrupted_immutable_revision_chain_fails_all_evidence(self):
        root = entry(self.db, "sa", "ancient nebula")
        edit(self.db, "sa", root, "new nebula")
        self.db.execute("UPDATE ansf_entry_edits SET previous_entry_id=?", (root + 1,))
        self.assertEqual(self.host.search(query("nebula")).status, pb.UNAVAILABLE)
        self.assertFalse(self.host.latest().evidence)

    def test_snapshot_source_refs_are_decimal_ids_not_model_message_ids(self):
        root = entry(self.db, "sa", "synced message")
        with self.host.acquire() as lease:
            code, hints, snap_frame = lease.ansf_fts_frames(query("synced"))
            self.assertEqual(code, pb.VERIFIED)
            snap = pb.CanonicalSnapshot.FromString(snap_frame)
            self.assertEqual(snap.records[0].source.entry_id, str(root))
            self.assertEqual(snap.records[0].source.revision_id, str(root))
            self.assertEqual(verify_candidate_batch(query("synced"), hints, snap_frame,
                                                     context=self.host.ctx).status, pb.VERIFIED)

    def test_sqlite_fts_multilingual_and_utf8_boundary(self):
        entry(self.db, "sa", "hello αβ snowflake")
        self.assertEqual(self.host.search(query("snowflake")).status, pb.VERIFIED)
        e = self.host.latest().evidence[0]
        self.assertIn("snowflake", e.excerpt)
        self.assertEqual(e.start_utf8_byte, 0)

    def test_ansf_citation_expands_only_live_authorized_current_source(self):
        root = entry(self.db, "sa", "citation live content")
        self.assertEqual(self.host.search(query("citation")).status, pb.VERIFIED)
        evidence = self.host.latest().evidence[0]
        lookup = pb.CitationLookup(schema_version=1, request_id="citation-req",
                                   citation_handle=evidence.citation_handle,
                                   source=evidence.source, snapshot_id=evidence.snapshot_id,
                                   content_sha256=evidence.content_sha256,
                                   start_utf8_byte=evidence.start_utf8_byte,
                                   length_utf8_byte=len(evidence.excerpt.encode()))
        frame = encode_frame(lookup)
        self.assertEqual(self.host.citation(frame).status, pb.VERIFIED)
        self.assertEqual(self.host.latest_citation().evidence.excerpt, "citation live content")
        lookup.citation_handle = "ref_" + "0" * 64
        self.assertEqual(self.host.citation(encode_frame(lookup)).status, pb.STALE)
        self.assertFalse(self.host.latest_citation().HasField("evidence"))
        lookup.citation_handle = evidence.citation_handle
        edit(self.db, "sa", root, "citation revised")
        self.assertEqual(self.host.citation(encode_frame(lookup)).status, pb.STALE)
        self.assertFalse(self.host.latest_citation().HasField("evidence"))
        self.host.tombstones.add(root)
        self.assertEqual(self.host.citation(encode_frame(lookup)).status, pb.DELETED)
        self.assertFalse(self.host.latest_citation().HasField("evidence"))

    def test_ansf_citation_still_fenced_on_revocation_and_cancellation(self):
        entry(self.db, "sa", "citation marker")
        self.host.search(query("citation"))
        e = self.host.latest().evidence[0]
        lookup = pb.CitationLookup(schema_version=1, request_id="citation-req",
                                   citation_handle=e.citation_handle, source=e.source,
                                   snapshot_id=e.snapshot_id, content_sha256=e.content_sha256,
                                   start_utf8_byte=e.start_utf8_byte,
                                   length_utf8_byte=len(e.excerpt.encode()))
        for attr, value, expected in (("live", False, pb.DENIED),
                                     ("cancelled", True, pb.CANCELLED)):
            host = SyntheticGateway(self.db)
            host.before_recheck = lambda h, a=attr, v=value: setattr(h, a, v)
            self.assertEqual(host.citation(encode_frame(lookup)).status, expected)
            self.assertFalse(host.latest_citation().HasField("evidence"))

    def test_unavailable_missing_schema_keeps_reply_empty(self):
        self.db.execute("DROP TABLE ansf_entry_edits")
        entry(self.db, "sa", "missing edits")
        self.assertEqual(self.host.search(query("missing")).status, pb.UNAVAILABLE)
        self.assertFalse(self.host.latest().evidence)


if __name__ == "__main__":
    unittest.main()
