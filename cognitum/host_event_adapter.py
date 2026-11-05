"""C07 transactional reference for a *host-supplied* SQLite connection.

Lu must authorize a request and own the connection, schema and durability.
No database paths are accepted and this code never creates a standalone store.
The schema below is a test contract to reconcile with Lu ANSF before production.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import hashlib
import json
import sqlite3
from typing import Callable

from .state_revision import Action, Origin, StateError, StateEvent, replay


# A host may apply this schema to its OWN transactional test database.
# Production requires mapping to Lu's existing ANSF event/journal tables.
HOST_TEST_SCHEMA = """
CREATE TABLE IF NOT EXISTS cognitum_reference_events(
    scope TEXT NOT NULL,
    event_id TEXT NOT NULL,
    entity TEXT NOT NULL,
    predicate TEXT NOT NULL,
    revision INTEGER NOT NULL,
    payload TEXT NOT NULL,
    digest TEXT NOT NULL,
    PRIMARY KEY(scope, event_id),
    UNIQUE(scope, entity, predicate, revision)
);
CREATE INDEX IF NOT EXISTS cognitum_reference_entity_events
    ON cognitum_reference_events(scope, entity, predicate, revision);
"""


def _canonical(event: StateEvent) -> str:
    raw = asdict(event)
    raw["origin"] = event.origin.value
    raw["action"] = event.action.value
    raw["effective_time"] = event.effective_time.isoformat()
    raw["recorded_time"] = event.recorded_time.isoformat()
    return json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _decode(payload: str) -> StateEvent:
    obj = json.loads(payload)
    if set(obj) != set(StateEvent.__dataclass_fields__):
        raise StateError("unexpected persisted event fields")
    obj["origin"] = Origin(obj["origin"])
    obj["action"] = Action(obj["action"])
    obj["effective_time"] = datetime.fromisoformat(obj["effective_time"])
    obj["recorded_time"] = datetime.fromisoformat(obj["recorded_time"])
    return StateEvent(**obj)


def append_authorized(
    connection: sqlite3.Connection,
    event: StateEvent,
    *,
    scope: str,
    host_authorize: Callable[[str, StateEvent], bool],
) -> int:
    """Atomic, replay-validated append, returning effective claim revision.

    `host_authorize` must be a Lu-supplied policy callback. Its True response
    is a host-side decision; the event's actor_authority is NOT proof.
    Caller owns schema and connection. DB locks serialize writers.
    """
    if not isinstance(connection, sqlite3.Connection) or not scope:
        raise StateError("host SQLite connection and scope required")
    if connection.in_transaction:
        raise StateError("append requires its own top-level host transaction")
    if host_authorize(scope, event) is not True:
        raise PermissionError("host rejected event mutation")
    payload = _canonical(event)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    try:
        connection.execute("BEGIN IMMEDIATE")
        prior = connection.execute(
            "SELECT digest, revision FROM cognitum_reference_events "
            "WHERE scope=? AND event_id=?", (scope, event.event_id),
        ).fetchone()
        if prior is not None:
            if prior[0] != digest:
                raise StateError("event ID reused with different payload")
            connection.commit()
            return int(prior[1])
        rows = connection.execute(
            "SELECT payload, digest FROM cognitum_reference_events "
            "WHERE scope=? AND entity=? AND predicate=? ORDER BY revision",
            (scope, event.entity, event.predicate),
        ).fetchall()
        history = []
        for old_payload, old_digest in rows:
            if hashlib.sha256(old_payload.encode("utf-8")).hexdigest() != old_digest:
                raise StateError("persisted event digest mismatch")
            history.append(_decode(old_payload))
        # Validate every revision in the authoritative event history and
        # the proposed transition before materializing an append.
        claim = replay((*history, event)).claims[0]
        connection.execute(
            "INSERT INTO cognitum_reference_events "
            "(scope, event_id, entity, predicate, revision, payload, digest) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (scope, event.event_id, event.entity, event.predicate,
             claim.revision, payload, digest),
        )
        connection.commit()
        return claim.revision
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise


def read_claim(
    connection: sqlite3.Connection, *, scope: str, entity: str, predicate: str
):
    """Read one claim; no cross-scope query or implicit authorization."""
    rows = connection.execute(
        "SELECT payload, digest FROM cognitum_reference_events "
        "WHERE scope=? AND entity=? AND predicate=? ORDER BY revision",
        (scope, entity, predicate),
    ).fetchall()
    history = []
    for payload, digest in rows:
        if hashlib.sha256(payload.encode("utf-8")).hexdigest() != digest:
            raise StateError("persisted event digest mismatch")
        history.append(_decode(payload))
    result = replay(history)
    return result.claims[0] if result.claims else None
