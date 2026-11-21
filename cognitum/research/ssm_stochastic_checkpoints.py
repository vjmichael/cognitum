"""COG-05-SSM-04-R6: authenticated, bounded, restartable R5 stream checkpoints.

The caller owns the authentication key, immutable model-context bytes, stream ID,
monotonic revision floor, durable input log and any exactly-once output journal.
This module cannot supply OS key custody or make the external cursor authoritative.

The versioned canonical UTF-8 JSON envelope is HMAC-SHA256 authenticated before
any reconstructed state is returned. No pickle, dynamic type import, embedded
code, embedded key, timestamp-dependent bytes or unauthenticated recovery.

Atomic file writes fsync the new file and, on POSIX, its containing directory;
Windows may not expose directory fsync. Storage location and its parent directory
must be protected by the caller. Checkpoints are authenticated, NOT encrypted.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import re
import secrets
from pathlib import Path

import numpy as np

from . import ssm_stochastic as core
from . import ssm_stochastic_increments as inc
from . import ssm_stochastic_streaming as streaming

SCHEMA = "cognitum.ssm04r6.streaming_checkpoint.v1"
ENVELOPE = "cognitum.ssm04r6.authenticated_envelope.v1"
MAC_DOMAIN = b"Cognitum.SSM04R6.StreamCheckpoint.HMAC-SHA256.v1\x00"
MAX_CHECKPOINT_BYTES = 4 * 1024 * 1024
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}\Z", re.ASCII)
_TOP = frozenset(("envelope_schema", "payload", "mac"))
_PAYLOAD = frozenset(("schema", "stream_id", "model_context_sha256",
                      "revision", "source_cursor", "state"))
_STATE = frozenset(("n", "k", "generator", "rate", "duration", "max_pending",
                    "filter_mean", "filter_factor", "last_time", "watermark",
                    "index", "count", "missing", "released", "peak", "clips",
                    "log_likelihood", "states", "pairs"))
_STATE_NODE = frozenset(("index", "time", "mean", "factor"))
_PAIR_NODE = frozenset(("mean", "factor"))


def _need(ok, message):
    if not ok:
        raise ValueError("invalid authenticated R6 checkpoint: " + message)


def _keys(obj, fields, label):
    _need(type(obj) is dict and set(obj) == fields, label + " schema")
    return obj


def _integer(value, minimum, maximum, name):
    _need(type(value) is int and minimum <= value <= maximum, name + " budget")
    return value


def _number(value, minimum, maximum, name):
    _need(type(value) in (int, float) and math.isfinite(value)
          and minimum <= value <= maximum, name + " finite range")
    return float(value)


def _matrix(value, shape, name):
    _need(type(value) is list and len(value) == shape[0] and
          all(type(row) is list and len(row) == shape[1] for row in value),
          name + " shape")
    flat = [v for row in value for v in row]
    _need(all(type(v) in (int, float) and math.isfinite(v) and abs(v) <= 1e8
              for v in flat), name + " finite element")
    return np.array(value, dtype=float)


def _vector(value, count, name):
    _need(type(value) is list and len(value) == count and
          all(type(v) in (int, float) and math.isfinite(v) and abs(v) <= 1e8
              for v in value), name + " finite shape")
    return np.array(value, dtype=float)


def _context_digest(model_context):
    _need(type(model_context) is bytes and 16 <= len(model_context) <= 4096,
          "externally provided model context bytes")
    return hashlib.sha256(model_context).hexdigest()


def _auth_key(authentication_key):
    _need(type(authentication_key) is bytes and
          32 <= len(authentication_key) <= 128,
          "externally held HMAC key (32..128 bytes)")
    return authentication_key


def _identifier(value, name):
    _need(type(value) is str and _ID.fullmatch(value) is not None,
          name + " ASCII identifier")
    return value


def _cursor(value):
    _need(type(value) is str and len(value) <= 128 and
          all(32 <= ord(c) <= 126 for c in value),
          "source cursor printable ASCII budget")
    return value


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _unique_pairs(pairs):
    obj = {}
    for key, value in pairs:
        _need(key not in obj, "duplicate JSON object key")
        obj[key] = value
    return obj


def _reject_constant(value):
    raise ValueError("invalid authenticated R6 checkpoint: nonfinite JSON constant")


def _encode_state(engine):
    _need(type(engine) is streaming.FixedDurationIncrementSmoother,
          "requires exact R5 streaming engine")
    states = [{"index": s.index, "time": s.time, "mean": s.mean.tolist(),
               "factor": s.factor.tolist()} for s in engine._states]
    pairs = [{"mean": p.mean.tolist(), "factor": p.factor.tolist()}
             for p in engine._pairs]
    return dict(n=engine._n, k=engine._k,
                generator=engine._generator.tolist(), rate=engine._rate.tolist(),
                duration=engine.duration, max_pending=engine.max_pending_states,
                filter_mean=engine._m.tolist(), filter_factor=engine._S.tolist(),
                last_time=engine._time, watermark=engine._watermark,
                index=engine._index, count=engine._count,
                missing=engine._missing, released=engine._released,
                peak=engine._peak, clips=engine._clips,
                log_likelihood=engine._ll, states=states, pairs=pairs)


def _decode_state(record):
    """Validate every key, bounded allocation and R5 event/state invariant."""
    _keys(record, _STATE, "stream state")
    n = _integer(record["n"], 1, inc.MAX_N, "state dimension")
    k = _integer(record["k"], 1, inc.MAX_K, "observation dimension")
    size = n + k
    duration = _number(record["duration"], 0, streaming.MAX_DURATION, "duration")
    limit = _integer(record["max_pending"], 1, streaming.MAX_PENDING,
                     "pending state limit")
    generator = _matrix(record["generator"], (size, size), "generator")
    rate = _matrix(record["rate"], (size, size), "joint covariance rate")
    _need(np.array_equal(generator[:n, n:], np.zeros((n, k))) and
          np.array_equal(generator[n:, n:], np.zeros((k, k))),
          "continuous-time generator structure")
    A = core.square(generator[:n, :n])
    Q = core.cov(rate[:n, :n], n)
    H = core.array(generator[n:, :n], 2)
    R = core.cov(rate[n:, n:], k, True)
    _need(np.linalg.cond(R) <= 1e12, "sensor noise condition number")
    N = rate[:n, n:]
    _need(np.allclose(rate[n:, :n], N.T, rtol=0, atol=1e-12),
          "joint noise cross covariance symmetry")
    inc._psd_root(rate, title="restored joint process/sensor rate")
    last = _number(record["last_time"], 0, streaming.MAX_CLOCK, "last event time")
    watermark = _number(record["watermark"], last, streaming.MAX_CLOCK,
                        "watermark")
    index = _integer(record["index"], 0, streaming.MAX_EVENTS, "state index")
    count = _integer(record["count"], 0, streaming.MAX_EVENTS, "event count")
    missing = _integer(record["missing"], 0, count, "missing count")
    released = _integer(record["released"], 0, count + 1, "released count")
    peak = _integer(record["peak"], 0, limit, "peak pending count")
    clips = _integer(record["clips"], 0, 1000000000, "eigenvalue clip count")
    ll = _number(record["log_likelihood"], -1e16, 1e16, "log likelihood")
    _need(count == index, "event count / last index mismatch")
    mean = _vector(record["filter_mean"], n, "current filtered mean")
    root = _matrix(record["filter_factor"], (n, n), "current filtered factor")
    state_data = record["states"]
    pair_data = record["pairs"]
    _need(type(state_data) is list and type(pair_data) is list and
          len(state_data) <= limit and len(pair_data) == max(0, len(state_data)-1)
          and len(state_data) + released == count + 1 and
          peak >= len(state_data), "bounded contiguous retained history")
    states = []
    for j, node in enumerate(state_data):
        _keys(node, _STATE_NODE, "retained state")
        expected_index = released + j
        _need(_integer(node["index"], 0, count, "retained index") == expected_index,
              "contiguous retained state indices")
        t = _number(node["time"], 0, last, "retained state time")
        if states:
            _need(t > states[-1].time, "strictly increasing state clock")
        _need(t + duration > watermark, "expired pending state was not released")
        states.append(streaming._State(expected_index, t,
                 _vector(node["mean"], n, "retained mean"),
                 _matrix(node["factor"], (n, n), "retained factor")))
    if states:
        _need(states[-1].index == count and states[-1].time == last and
              np.allclose(states[-1].mean, mean, atol=1e-11, rtol=1e-10) and
              np.allclose(states[-1].factor @ states[-1].factor.T,
                          root @ root.T, atol=1e-10, rtol=1e-9),
              "current filter / most recent retained state mismatch")
    else:
        _need(duration == 0 or watermark >= last + duration,
              "unreleased state missing from retained history")
    pairs = []
    for j, node in enumerate(pair_data):
        _keys(node, _PAIR_NODE, "adjacent conditional pair")
        pair_mean = _vector(node["mean"], 2*n, "conditional pair mean")
        pair_root = _matrix(node["factor"], (2*n, 2*n),
                            "conditional pair factor")
        later = states[j+1]
        _need(np.allclose(pair_mean[n:], later.mean, atol=1e-10, rtol=1e-9)
              and np.allclose(pair_root[n:, :] @ pair_root[n:, :].T,
                              later.factor @ later.factor.T,
                              atol=1e-10, rtol=1e-9),
              "conditional joint pair / endpoint state mismatch")
        pairs.append(streaming._Pair(pair_mean, pair_root))
    # Exact G/Q/R structure is reconstructed, not imported from serialized code.
    result = object.__new__(streaming.FixedDurationIncrementSmoother)
    result._n, result._k = n, k
    result._generator, result._rate = generator, rate
    result.duration, result.max_pending_states = duration, limit
    result._m, result._S = mean, root
    result._time, result._watermark = last, watermark
    result._index, result._count = index, count
    result._missing, result._released = missing, released
    result._peak, result._clips, result._ll = peak, clips, ll
    result._states, result._pairs = states, pairs
    # Initial release, if any, was already emitted and must never be duplicated.
    result.initial_releases = ()
    return result


def serialize_stream_checkpoint(engine, *, authentication_key, stream_id,
                                model_context, revision, source_cursor=""):
    """Deterministic authenticated bytes. Never persist the caller-owned key.

    The caller binds model_context to the complete approved model setup,
    including initial prior; no model authority is inferred from the JSON.
    Revision is an externally managed, strictly monotonic checkpoint number;
    a trusted persistent floor is required on restoration to resist rollback.
    Source cursor is a caller-owned input-journal cursor.
    """
    key = _auth_key(authentication_key)
    identifier = _identifier(stream_id, "stream id")
    model_hash = _context_digest(model_context)
    _integer(revision, 1, 2**63-1, "checkpoint revision")
    _cursor(source_cursor)
    state = _encode_state(engine)
    _decode_state(state)  # fail closed on an inconsistent live state
    payload = dict(schema=SCHEMA, stream_id=identifier,
                   model_context_sha256=model_hash, revision=revision,
                   source_cursor=source_cursor, state=state)
    mac = hmac.new(key, MAC_DOMAIN + _canonical(payload), hashlib.sha256).hexdigest()
    blob = _canonical(dict(envelope_schema=ENVELOPE, payload=payload, mac=mac))
    _need(len(blob) <= MAX_CHECKPOINT_BYTES, "serialized byte budget")
    return blob


def restore_stream_checkpoint(blob, *, authentication_key, expected_stream_id,
                              model_context, minimum_revision=1,
                              expected_checkpoint_sha256=None):
    """Authenticate before constructing state; never mutate a live engine.

    minimum_revision and optional exact SHA-256 anchor MUST come from an
    independently trusted monotonic store, not the untrusted checkpoint.
    Snapshot-only continuation is deterministic. Exactly-once external input
    replay/output delivery requires a transactional caller-owned journal.
    """
    key = _auth_key(authentication_key)
    identifier = _identifier(expected_stream_id, "expected stream id")
    model_hash = _context_digest(model_context)
    _integer(minimum_revision, 1, 2**63-1, "minimum trusted revision")
    _need(type(blob) is bytes and 0 < len(blob) <= MAX_CHECKPOINT_BYTES,
          "input byte budget")
    digest = hashlib.sha256(blob).hexdigest()
    if expected_checkpoint_sha256 is not None:
        _need(type(expected_checkpoint_sha256) is str and
              re.fullmatch(r"[a-f0-9]{64}", expected_checkpoint_sha256) is not None
              and hmac.compare_digest(digest, expected_checkpoint_sha256),
              "external checkpoint digest anchor")
    try:
        obj = json.loads(blob.decode("utf-8"), object_pairs_hook=_unique_pairs,
                         parse_constant=_reject_constant)
    except (UnicodeError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError("invalid authenticated R6 checkpoint: strict JSON decoding") from exc
    _keys(obj, _TOP, "authenticated envelope")
    _need(obj["envelope_schema"] == ENVELOPE and
          type(obj["mac"]) is str and
          re.fullmatch(r"[a-f0-9]{64}", obj["mac"]) is not None,
          "envelope version / MAC shape")
    payload = _keys(obj["payload"], _PAYLOAD, "checkpoint payload")
    _need(payload["schema"] == SCHEMA, "payload version")
    revision = _integer(payload["revision"], 1, 2**63-1, "revision")
    _need(revision >= minimum_revision, "trusted revision anti-rollback floor")
    _need(_identifier(payload["stream_id"], "stream id") == identifier,
          "stream identity mismatch")
    _need(type(payload["model_context_sha256"]) is str and
          hmac.compare_digest(payload["model_context_sha256"], model_hash),
          "externally approved model context mismatch")
    _cursor(payload["source_cursor"])
    try:
        signed = _canonical(payload)
        expected_mac = hmac.new(key, MAC_DOMAIN + signed, hashlib.sha256).hexdigest()
        _need(hmac.compare_digest(obj["mac"], expected_mac),
              "HMAC authentication refused")
        _need(blob == _canonical(obj), "noncanonical checkpoint encoding")
    except (TypeError, ValueError, OverflowError) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith("invalid authenticated R6 checkpoint"):
            raise
        raise ValueError("invalid authenticated R6 checkpoint: canonical encoding") from exc
    # Authentication and external stream/model binding complete; now validate.
    engine = _decode_state(payload["state"])
    return core.receipt(
        method="authenticated_durable_R6_stream_checkpoint_restore",
        engine=engine, revision=revision, stream_id=identifier,
        source_cursor=payload["source_cursor"],
        checkpoint_sha256=digest, model_context_sha256=model_hash,
        checkpoint_authentication="HMAC-SHA256", uses_future=False,
        caller_owned_monotonic_floor_required=True,
        caller_owned_exactly_once_journal_required=True)


def _path(path):
    _need(isinstance(path, (str, os.PathLike)), "trusted checkpoint path type")
    p = Path(path)
    _need(p.is_absolute() and p.name not in ("", ".", "..") and
          p.parent.is_dir(), "absolute path in pre-existing trusted directory")
    _need(not p.is_symlink(), "checkpoint symlink refused")
    return p


def atomic_write_checkpoint(path, blob):
    """Exclusive same-directory temp + fsync + atomic replace (+ POSIX dir fsync).

    Caller ensures exclusive writer custody and an ACL-protected parent directory.
    Windows Python lacks portable directory-fsync; no unconditional power-loss
    durability guarantee is made there.
    """
    p = _path(path)
    _need(type(blob) is bytes and 0 < len(blob) <= MAX_CHECKPOINT_BYTES,
          "checkpoint write size")
    temp = p.parent / ("." + p.name + "." + secrets.token_hex(12) + ".tmp")
    fd = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(str(temp), flags, 0o600)
        view = memoryview(blob)
        while view:
            n = os.write(fd, view)
            _need(n > 0, "partial checkpoint write failure")
            view = view[n:]
        os.fsync(fd)
        os.close(fd);fd=None
        _need(not p.is_symlink(), "target symlink race refused")
        os.replace(str(temp), str(p))
        if os.name == "posix":
            dfd = os.open(str(p.parent), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:os.fsync(dfd)
            finally:os.close(dfd)
    finally:
        if fd is not None:os.close(fd)
        try:temp.unlink()
        except FileNotFoundError:pass


def read_checkpoint(path):
    """Bounded, no-final-symlink read; authenticate with restore separately."""
    p = _path(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(str(p), flags)
    try:
        data = bytearray()
        while len(data) <= MAX_CHECKPOINT_BYTES:
            part = os.read(fd, min(65536, MAX_CHECKPOINT_BYTES + 1 - len(data)))
            if not part:break
            data.extend(part)
        _need(0 < len(data) <= MAX_CHECKPOINT_BYTES, "checkpoint read size")
        return bytes(data)
    finally:
        os.close(fd)
