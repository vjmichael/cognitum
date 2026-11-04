"""C06/C07 SQLite-derived index and transactional host-reference acceptance."""
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from cognitum.host_event_adapter import (
    HOST_TEST_SCHEMA, append_authorized, read_claim,
)
from cognitum.memory_retrieval import MemoryEvidence, MemoryQuery, RetrievalError, retrieve
from cognitum.state_revision import Action, Origin, StateError, StateEvent

T = datetime(2026, 11, 4, tzinfo=timezone.utc)


def memory(source="s1", revision=1, *, scope="alice", text="colony supplies",
           tombstone=False):
    return MemoryEvidence(source, revision, scope, "colony", text,
                          f"cite:{source}:{revision}", T, None, tombstone)


def event(eid, action, revision, value="ready", source="user"):
    return StateEvent(eid, "ship", "status", value, Origin.USER_DECISION,
                      "host-opaque", revision, T, T, action, source)


def connection():
    db = sqlite3.connect(":memory:", isolation_level=None)
    db.executescript(HOST_TEST_SCHEMA)
    return db


def allow(scope, event):
    return scope == "alice"


def test_fts5_bm25_scopes_revisions_and_negative_lookup():
    records = [memory("s1", text="ship colony emergency water supply"),
               memory("s2", scope="bob", text="ship colony emergency water supply"),
               memory("s3", text="ship colony water"),
               memory("s4", text="unrelated geology")]
    query = MemoryQuery("alice", "ship colony emergency", as_of=T)
    got = retrieve(iter(records), query, snapshot_id="snapshot", origin_revision=1)
    assert [r.source_id for r in got.evidence] == ["s1"]
    assert got.index_status.staleness is False
    assert retrieve(records, MemoryQuery("bob", "geology", as_of=T),
                    snapshot_id="snapshot", origin_revision=1).evidence == ()


def test_scope_change_and_tombstone_suppress_past_revisions():
    records = [memory(), memory(revision=2, scope="bob", text="secret")]
    got = retrieve(iter(records), MemoryQuery("alice", "supplies", as_of=T),
                   snapshot_id="new", origin_revision=2)
    assert got.evidence == ()
    tombstoned = [memory(), memory(revision=2, tombstone=True)]
    for rank in ("fts5", "exact"):
        got = retrieve(iter(tombstoned), MemoryQuery("alice", "supplies", as_of=T),
                       snapshot_id="new", origin_revision=2, ranking=rank)
        assert got.evidence == ()


def test_query_injection_is_literal():
    records = [memory(text='host approved "colony" OR secret'),
               memory("s2", text="nothing relevant")]
    result = retrieve(records, MemoryQuery("alice", '" OR *', as_of=T),
                      snapshot_id="s", origin_revision=1)
    assert result.evidence == ()
    with pytest.raises(RetrievalError, match="oversized"):
        MemoryQuery("alice", "a" * 513)


def test_temporal_effective_interval():
    record = MemoryEvidence("s", 1, "alice", "colony", "supply",
                            "cite:s", T, T + timedelta(seconds=1))
    assert len(retrieve([record], MemoryQuery("alice", as_of=T),
                        snapshot_id="s", origin_revision=1).evidence) == 1
    assert not retrieve([record], MemoryQuery("alice", as_of=T + timedelta(seconds=1)),
                        snapshot_id="s", origin_revision=1).evidence


def test_durable_append_and_reopen_after_crash(tmp_path):
    path = tmp_path / "host_owned.sqlite"
    with sqlite3.connect(path, isolation_level=None) as db:
        db.executescript(HOST_TEST_SCHEMA)
        assert append_authorized(db, event("a", Action.ASSERT, 0),
                                 scope="alice", host_authorize=allow) == 1
        assert append_authorized(db, event("b", Action.CHALLENGE, 1, source="observer"),
                                 scope="alice", host_authorize=allow) == 2
    with sqlite3.connect(path, isolation_level=None) as db:
        claim = read_claim(db, scope="alice", entity="ship", predicate="status")
        assert claim.revision == 2
        assert claim.status == "CHALLENGED"
        assert claim.conflict_refs == ("observer",)
        assert append_authorized(db, event("b", Action.CHALLENGE, 1, source="observer"),
                                 scope="alice", host_authorize=allow) == 2
        with pytest.raises(StateError, match="stale"):
            append_authorized(db, event("c", Action.CONFIRM, 1),
                              scope="alice", host_authorize=allow)
        assert read_claim(db, scope="alice", entity="ship", predicate="status").revision == 2


def test_host_denial_no_effect_and_cross_scope_isolation():
    with connection() as db:
        with pytest.raises(PermissionError):
            append_authorized(db, event("a", Action.ASSERT, 0), scope="bob",
                              host_authorize=allow)
        assert read_claim(db, scope="bob", entity="ship", predicate="status") is None
        assert append_authorized(db, event("a", Action.ASSERT, 0), scope="alice",
                                 host_authorize=allow) == 1
        assert read_claim(db, scope="bob", entity="ship", predicate="status") is None


def test_idempotency_collision_rejects_different_payload():
    with connection() as db:
        append_authorized(db, event("a", Action.ASSERT, 0), scope="alice",
                          host_authorize=allow)
        with pytest.raises(StateError, match="reused"):
            append_authorized(db, event("a", Action.ASSERT, 0, value="forged"),
                              scope="alice", host_authorize=allow)
        assert read_claim(db, scope="alice", entity="ship", predicate="status").revision == 1


def test_digest_tamper_detected():
    with connection() as db:
        append_authorized(db, event("a", Action.ASSERT, 0), scope="alice",
                          host_authorize=allow)
        db.execute("UPDATE cognitum_reference_events SET payload='{}' WHERE event_id='a'")
        with pytest.raises(StateError, match="digest mismatch"):
            read_claim(db, scope="alice", entity="ship", predicate="status")


def test_real_sqlite_racing_writers_only_one_commit(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    path = tmp_path / "writer-race.sqlite"
    with sqlite3.connect(path, isolation_level=None) as db:
        db.executescript(HOST_TEST_SCHEMA)
    barrier = Barrier(2)

    def write(eid):
        db = sqlite3.connect(path, isolation_level=None, timeout=10)
        try:
            barrier.wait(timeout=10)
            return append_authorized(
                db, event(eid, Action.ASSERT, 0), scope="alice",
                host_authorize=allow,
            )
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(write, "a"), executor.submit(write, "b")]
        outcomes = []
        for future in futures:
            try:
                outcomes.append(future.result())
            except StateError as error:
                outcomes.append(str(error))
    assert sum(x == 1 for x in outcomes) == 1
    assert sum(isinstance(x, str) and "stale" in x for x in outcomes) == 1
    with sqlite3.connect(path, isolation_level=None) as db:
        count = db.execute(
            "SELECT COUNT(*) FROM cognitum_reference_events WHERE scope='alice'"
        ).fetchone()[0]
        assert count == 1
