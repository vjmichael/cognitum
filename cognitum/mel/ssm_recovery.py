"""Host-only MEL custody/journal adapter for accepted SSM-04-R6 checkpoints.

Reuses MEL's trusted Admission/Scope boundary, not a model-facing grant,
plugin registry, second scheduler, worker, credential service or Lu IPC route.
All protected key custody, trusted CAS floor and positive scope authorization
are externally supplied by the installed host. An in-memory test broker does
NOT qualify a genuine OS credential broker.

SQLite FULL/WAL transactions co-commit each accepted input, next authenticated
R6 checkpoint and pending signed output rows. Committed output rows are
at-least-once until an external consumer acknowledges them; external exactly-
once delivery or power-loss durability across an OS broker is not claimed.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import sqlite3

from . import admission as mel_admission
from cognitum.research import ssm_stochastic_checkpoints as cp
from cognitum.research import ssm_stochastic_streaming as stream

SCHEMA = "cognitum.mel.ssm_r6_host_journal.v1"
OUTPUT_SCHEMA = "cognitum.mel.ssm_r6_output.v1"
OUTBOX_MAC = b"cognitum.mel.ssm_r6.outbox.HMAC.v1\x00"
EVENT_MAC = b"cognitum.mel.ssm_r6.event.HMAC.v1\x00"
MAX_EVENT_BYTES = 8192
MAX_OUTPUT_BYTES = 65536
MAX_UNACKED = 4096
MAX_EVENTS = 1000000
ZERO = "0" * 64


def _need(value, message):
    if not value:
        raise ValueError("MEL SSM journal refused: " + message)


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      allow_nan=False, ensure_ascii=True).encode("ascii")


def _hex(raw):
    return hashlib.sha256(raw).hexdigest()


def _int(value, lo, hi, name):
    _need(type(value) is int and lo <= value <= hi, name)
    return value


def _id(value):
    return cp._identifier(value, "journal identity")


def _digest(value):
    _need(type(value) is str and len(value) == 64 and
          all(c in "0123456789abcdef" for c in value), "SHA-256 identifier")
    return value


def _key(provider, scope, stream_id):
    # The key is borrowed from the installed host on each operation, never
    # placed in database rows or kept as an attribute of this adapter.
    _need(callable(getattr(provider, "borrow_key", None)),
          "external credential broker required")
    return cp._auth_key(provider.borrow_key(scope, stream_id))


def _anchor_value(anchor, scope, sid):
    _need(callable(getattr(anchor, "read", None)) and
          callable(getattr(anchor, "advance", None)),
          "external protected monotonic revision store required")
    item = anchor.read(scope, sid)
    _need(type(item) is tuple and len(item) == 2,
          "trusted revision/digest pair")
    revision, digest = item
    _int(revision, 0, 2**63-2, "trusted revision floor")
    _need((digest is None) == (revision == 0),
          "trusted revision/digest alignment")
    if digest is not None:
        _digest(digest)
    return item


def _root_path(path):
    _need(isinstance(path, (str, os.PathLike)),
          "trusted database path type")
    p = Path(path)
    _need(p.is_absolute() and p.name not in ("", ".", "..") and
          p.parent.is_dir() and not p.is_symlink(),
          "absolute nonsymlink journal in existing trusted directory")
    return p


def _scope_context(scope, approved_model_context):
    _need(type(approved_model_context) is bytes and
          16 <= len(approved_model_context) <= 4096,
          "externally approved full model context")
    material = _canonical([scope.session, scope.workspace,
                           scope.subject, scope.turn])
    # The signed R6 checkpoint therefore binds both trusted MEL scope and
    # caller-approved model specification, including model's initial prior.
    return hashlib.sha256(b"MEL.SSM.R6.scope_model.v1\x00" +
                          material + b"\x00" + approved_model_context).digest()


def _observation(time, increment, kind):
    _need(kind in ("increment", "watermark"), "event operation")
    _need(type(time) in (int, float) and math.isfinite(time)
          and 0 <= time <= stream.MAX_CLOCK, "event-time budget")
    if kind == "watermark":
        _need(increment is None, "watermark must not fabricate observation")
        return float(time), None
    if increment is None:
        return float(time), None
    _need(type(increment) in (list, tuple) and 1 <= len(increment) <= 8
          and all(type(v) in (int, float) and math.isfinite(v)
                  and abs(v) <= 1e8 for v in increment),
          "bounded actual integrated increment")
    return float(time), [float(v) for v in increment]


def _release_wire(sid, event_id, revision, x):
    body = dict(schema=OUTPUT_SCHEMA, stream_id=sid, event_id=event_id,
                revision=revision, state_index=x["state_index"],
                state_time=x["state_time"],
                observation_cutoff_time=x["observation_cutoff_time"],
                conditioned_through_time=x["conditioned_through_time"],
                release_time=x["release_time"],
                mean=x["mean"].tolist(), factor=x["factor"].tolist(),
                covariance=x["covariance"].tolist(),
                numerical_certified=False, execution_authorized=False)
    wire = _canonical(body)
    _need(len(wire) <= MAX_OUTPUT_BYTES, "bounded output payload")
    return wire


def _mac(key, domain, data):
    return hmac.new(key, domain + data, hashlib.sha256).hexdigest()


class HostSSMJournal:
    """Trusted-host MEL coordination only; not a new registered MEL operation.

    admission is the *existing* MEL Admission session. allow is a positive
    trusted-host per-call policy hook and can revoke/cancel this stream.
    credential_broker supplies an OS-held secret to the trusted Python host
    for each operation (the module itself never implements OS key storage).
    revision_anchor is an externally protected monotonic CAS store with
    read(scope,id)->(revision,sha256|None) and
    advance(scope,id,old_revision,old_digest,new_revision,new_digest).
    A failed external advance halts this instance; a new instance must
    authenticate and reconcile the durable SQLite snapshot before proceeding.
    """

    def __init__(self, admission, scope, *, stream_id, approved_model_context,
                 credential_broker, revision_anchor, allow, sqlite_path,
                 initial_engine=None):
        _need(type(admission) is mel_admission.Admission and
              type(scope) is mel_admission.Scope and callable(allow),
              "trusted host MEL Admission, Scope and policy required")
        admission._scope(scope)
        self._admission = admission
        self._scope = scope
        self._sid = _id(stream_id)
        self._context = _scope_context(scope, approved_model_context)
        self._broker = credential_broker
        self._anchor = revision_anchor
        self._allow = allow
        self._stalled = False
        self._closed = False
        p = _root_path(sqlite_path)
        # No automatic parent directory creation; installed host owns OS ACL.
        self._connection = sqlite3.connect(str(p), timeout=4.0,
                                           isolation_level=None)
        self._connection.row_factory = sqlite3.Row
        try:
            self._connection.execute("PRAGMA foreign_keys=ON")
            self._connection.execute("PRAGMA trusted_schema=OFF")
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA synchronous=FULL")
            self._connection.execute("PRAGMA busy_timeout=4000")
            self._connection.executescript("""
                CREATE TABLE IF NOT EXISTS stream_snapshot (
                    stream_id TEXT PRIMARY KEY, scope_digest TEXT NOT NULL,
                    revision INTEGER NOT NULL, checkpoint BLOB NOT NULL,
                    checkpoint_sha TEXT NOT NULL, last_event TEXT NOT NULL,
                    chain_mac TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS event_journal (
                    stream_id TEXT NOT NULL, event_id TEXT NOT NULL,
                    request_sha TEXT NOT NULL, revision INTEGER NOT NULL,
                    checkpoint_sha TEXT NOT NULL, prior_chain TEXT NOT NULL,
                    chain_mac TEXT NOT NULL,
                    PRIMARY KEY (stream_id,event_id)
                );
                CREATE TABLE IF NOT EXISTS output_outbox (
                    output_id TEXT PRIMARY KEY, stream_id TEXT NOT NULL,
                    event_id TEXT NOT NULL, body BLOB NOT NULL,
                    body_sha TEXT NOT NULL, body_mac TEXT NOT NULL,
                    acknowledged INTEGER NOT NULL DEFAULT 0
                        CHECK (acknowledged IN (0,1))
                );
            """)
            self._with_host("open")
            self._initialize_or_recover(initial_engine)
        except BaseException:
            self._connection.close()
            raise

    def _with_host(self, operation):
        _need(not self._closed and not self._stalled,
              "host journal closed or requires recovery")
        self._admission._scope(self._scope)
        _need(not self._admission._closed and
              self._allow(self._scope, operation) is True,
              "host MEL scope closed, revoked or unauthorized")

    def _begin(self):
        self._connection.execute("BEGIN IMMEDIATE")

    def _rollback(self):
        if self._connection.in_transaction:
            self._connection.rollback()

    def _row(self):
        return self._connection.execute(
            "SELECT * FROM stream_snapshot WHERE stream_id=?",
            (self._sid,)).fetchone()

    def _read_verified(self, key, trusted):
        row = self._row()
        _need(row is not None, "missing previously approved stream")
        _need(row["scope_digest"] == _hex(self._context),
              "checkpoint scope/model binding")
        revision = row["revision"]
        _int(revision, 1, 2**63-2, "snapshot revision")
        sha = _digest(row["checkpoint_sha"])
        _need(_hex(row["checkpoint"]) == sha,
              "snapshot byte digest mismatch")
        floor, pin = trusted
        _need(revision >= floor, "external monotonic revision rollback")
        if revision == floor:
            _need(pin == sha, "external checkpoint pin mismatch")
        rec = cp.restore_stream_checkpoint(
            row["checkpoint"], authentication_key=key,
            expected_stream_id=self._sid, model_context=self._context,
            minimum_revision=max(1, floor), expected_checkpoint_sha256=sha)
        _need(rec["revision"] == revision and
              rec["source_cursor"] == row["last_event"],
              "checkpoint revision/source-cursor mismatch")
        chain = _digest(row["chain_mac"])
        if revision == 1:
            _need(row["last_event"] == "bootstrap" and chain == ZERO,
                  "initial journal head mismatch")
        else:
            last = self._connection.execute(
                "SELECT * FROM event_journal WHERE stream_id=? AND event_id=?",
                (self._sid, row["last_event"])).fetchone()
            _need(last is not None and last["revision"] == revision and
                  last["checkpoint_sha"] == sha and
                  last["chain_mac"] == chain,
                  "journal head / signed checkpoint mismatch")
            evidence = _canonical(dict(stream_id=self._sid,
                event_id=last["event_id"],revision=last["revision"],
                request_sha=last["request_sha"],
                checkpoint_sha=last["checkpoint_sha"],
                prior_chain=last["prior_chain"]))
            _need(hmac.compare_digest(chain, _mac(key, EVENT_MAC, evidence)),
                  "journal head MAC mismatch")
        return row, rec["engine"]

    def _initialize_or_recover(self, initial_engine):
        # One lock encompasses host lifetime check and the transaction, so
        # MEL session closure/cancellation cannot race result publication.
        with self._admission._lock:
            self._with_host("recover")
            self._begin()
            try:
                key = _key(self._broker, self._scope, self._sid)
                trusted = _anchor_value(self._anchor, self._scope, self._sid)
                row = self._row()
                if row is None:
                    _need(trusted == (0, None) and
                          type(initial_engine) is stream.FixedDurationIncrementSmoother,
                          "initial engine requires fresh trusted anchor")
                    wire = cp.serialize_stream_checkpoint(
                        initial_engine, authentication_key=key,
                        stream_id=self._sid, model_context=self._context,
                        revision=1, source_cursor="bootstrap")
                    sha = _hex(wire)
                    self._connection.execute(
                        "INSERT INTO stream_snapshot VALUES (?,?,?,?,?,?,?)",
                        (self._sid, _hex(self._context), 1, wire, sha,
                         "bootstrap", ZERO))
                    next_rev, next_sha = 1, sha
                else:
                    _need(initial_engine is None,
                          "must not replace existing authenticated stream")
                    self._read_verified(key, trusted)
                    next_rev, next_sha = row["revision"], row["checkpoint_sha"]
                self._connection.commit()
            except BaseException:
                self._rollback()
                raise
            self._advance_anchor(trusted, next_rev, next_sha)

    def _advance_anchor(self, old, new_revision, new_sha):
        if old == (new_revision, new_sha):
            return
        try:
            self._anchor.advance(self._scope, self._sid, old[0], old[1],
                                 new_revision, new_sha)
            _need(_anchor_value(self._anchor, self._scope, self._sid) ==
                  (new_revision, new_sha), "anchor post-commit verification")
        except BaseException:
            self._stalled = True
            raise

    def process(self, event_id, *, kind, end_time, increment=None):
        """Commit one input + authenticated snapshot + queued output atomically.

        A caller must NOT publish the returned data. Read pending_outputs,
        verify, deliver and acknowledge it through the protected host. Duplicate
        event_id with exactly equal canonical input never runs computation again.
        """
        _id(event_id)
        timestamp, observation = _observation(end_time, increment, kind)
        request_wire = _canonical(dict(schema=SCHEMA,event_id=event_id,
                   kind=kind,end_time=timestamp,increment=observation))
        _need(len(request_wire) <= MAX_EVENT_BYTES, "bounded request")
        req_sha = _hex(request_wire)
        with self._admission._lock:
            self._with_host("process")
            self._begin()
            try:
                key = _key(self._broker, self._scope, self._sid)
                trusted = _anchor_value(self._anchor, self._scope, self._sid)
                row, engine = self._read_verified(key, trusted)
                duplicate = self._connection.execute(
                    "SELECT request_sha,revision FROM event_journal "
                    "WHERE stream_id=? AND event_id=?",
                    (self._sid,event_id)).fetchone()
                if duplicate is not None:
                    _need(duplicate["request_sha"] == req_sha,
                          "event identity replay with different payload")
                    result = dict(status="duplicate", event_id=event_id,
                                  revision=duplicate["revision"],
                                  committed=False, publish_authorized=False)
                    self._connection.commit()
                    return result
                revision = row["revision"] + 1
                _int(revision, 2, min(2**63-2, MAX_EVENTS+1),
                     "bounded monotonic checkpoint revision")
                if kind == "increment":
                    releases = engine.push(timestamp, observation)
                else:
                    releases = engine.advance_watermark(timestamp)
                _need(len(releases) <= stream.MAX_PENDING,
                      "bounded emissions per event")
                count_unack = self._connection.execute(
                    "SELECT COUNT(*) AS c FROM output_outbox "
                    "WHERE stream_id=? AND acknowledged=0", (self._sid,)).fetchone()["c"]
                _need(count_unack + len(releases) <= MAX_UNACKED,
                      "pending outbox capacity; no silent drop")
                wire = cp.serialize_stream_checkpoint(
                    engine,authentication_key=key,stream_id=self._sid,
                    model_context=self._context,revision=revision,
                    source_cursor=event_id)
                sha = _hex(wire)
                evidence = _canonical(dict(stream_id=self._sid,
                    event_id=event_id,revision=revision,request_sha=req_sha,
                    checkpoint_sha=sha,prior_chain=row["chain_mac"]))
                chain = _mac(key, EVENT_MAC, evidence)
                self._connection.execute(
                    "INSERT INTO event_journal VALUES (?,?,?,?,?,?,?)",
                    (self._sid,event_id,req_sha,revision,sha,
                     row["chain_mac"],chain))
                for release in releases:
                    payload = _release_wire(self._sid,event_id,revision,release)
                    output_id = _hex(b"MEL.SSM.R6.output.v1\x00" + payload)
                    self._connection.execute(
                        "INSERT INTO output_outbox VALUES (?,?,?,?,?,?,0)",
                        (output_id,self._sid,event_id,payload,_hex(payload),
                         _mac(key,OUTBOX_MAC,payload)))
                self._connection.execute(
                    "UPDATE stream_snapshot SET revision=?,checkpoint=?,"
                    "checkpoint_sha=?,last_event=?,chain_mac=? "
                    "WHERE stream_id=? AND revision=?",
                    (revision,wire,sha,event_id,chain,self._sid,row["revision"]))
                _need(self._connection.execute("SELECT changes()").fetchone()[0]==1,
                      "stale stream revision")
                self._with_host("commit")
                self._connection.commit()
            except BaseException:
                self._rollback()
                raise
            # Once committed, a broker failure may leave the trust anchor
            # behind. Fail closed; next process must reopen and reconcile.
            self._advance_anchor(trusted,revision,sha)
            return dict(status="committed", event_id=event_id,
                        revision=revision, committed=True,
                        emitted=len(releases), publish_authorized=False)

    def pending_outputs(self, limit=64):
        _int(limit, 1, 256, "bounded pending-output page")
        with self._admission._lock:
            self._with_host("read_outbox")
            self._begin()
            try:
                key = _key(self._broker, self._scope, self._sid)
                self._read_verified(key,_anchor_value(self._anchor,self._scope,self._sid))
                rows = self._connection.execute(
                    "SELECT * FROM output_outbox "
                    "WHERE stream_id=? AND acknowledged=0 "
                    "ORDER BY rowid LIMIT ?", (self._sid,limit)).fetchall()
                out = []
                for row in rows:
                    raw = row["body"]
                    _need(type(raw) is bytes and
                          1 <= len(raw) <= MAX_OUTPUT_BYTES and
                          _hex(raw) == row["body_sha"] and
                          hmac.compare_digest(row["body_mac"],_mac(key,OUTBOX_MAC,raw)),
                          "outbox record authentication mismatch")
                    item = json.loads(raw)
                    _need(item["schema"] == OUTPUT_SCHEMA and
                          item["stream_id"] == self._sid and
                          item["event_id"] == row["event_id"] and
                          _hex(b"MEL.SSM.R6.output.v1\x00"+raw) == row["output_id"],
                          "outbox record identity mismatch")
                    out.append(dict(output_id=row["output_id"],
                                    body_sha=row["body_sha"],
                                    event_id=row["event_id"],
                                    receipt=item,publish_authorized=False))
                self._connection.commit()
                return tuple(out)
            except BaseException:
                self._rollback()
                raise

    def acknowledge(self, output_id, expected_body_sha):
        """Host records delivery acknowledgment, not external exactly-once."""
        _digest(output_id)
        _digest(expected_body_sha)
        with self._admission._lock:
            self._with_host("ack_outbox")
            self._begin()
            try:
                key = _key(self._broker,self._scope,self._sid)
                self._read_verified(key,_anchor_value(self._anchor,self._scope,self._sid))
                row = self._connection.execute(
                    "SELECT * FROM output_outbox "
                    "WHERE stream_id=? AND output_id=?",
                    (self._sid,output_id)).fetchone()
                _need(row is not None and row["body_sha"]==expected_body_sha,
                      "unknown output / acknowledgment digest mismatch")
                _need(_hex(row["body"])==expected_body_sha and
                      hmac.compare_digest(row["body_mac"],_mac(key,OUTBOX_MAC,row["body"])),
                      "outbox authentication before acknowledgment")
                if not row["acknowledged"]:
                    self._connection.execute(
                        "UPDATE output_outbox SET acknowledged=1 "
                        "WHERE stream_id=? AND output_id=?",
                        (self._sid,output_id))
                self._connection.commit()
                return True
            except BaseException:
                self._rollback()
                raise

    def status(self):
        with self._admission._lock:
            self._with_host("inspect")
            self._begin()
            try:
                key = _key(self._broker,self._scope,self._sid)
                trusted = _anchor_value(self._anchor,self._scope,self._sid)
                row, engine = self._read_verified(key,trusted)
                pending = self._connection.execute(
                    "SELECT COUNT(*) FROM output_outbox "
                    "WHERE stream_id=? AND acknowledged=0",
                    (self._sid,)).fetchone()[0]
                self._connection.commit()
                return dict(method=SCHEMA, revision=row["revision"],
                            checkpoint_sha256=row["checkpoint_sha"],
                            pending_outputs=pending,
                            pending_states=engine.status()["pending_count"],
                            admitted_by_existing_mel_scope=True,
                            installed_os_broker_qualified=False,
                            installed_MEL_route_authorized=False,
                            external_exactly_once_qualified=False)
            except BaseException:
                self._rollback()
                raise

    def close(self):
        if not self._closed:
            self._connection.close()
            self._closed=True
