"""Bounded canonical native C06/C07 Protobuf edge; never confers host grants."""
from __future__ import annotations

from datetime import datetime, timezone

from google.protobuf.message import DecodeError

from .memory_retrieval import MemoryQuery, MemoryResult, RetrievalError
from .state_revision import Action, Origin, StateEvent, StateError
from .proto import memory_state_pb2 as pb

PREFIX = "type.googleapis.com/cognitum.memory.v1."
QUERY_TYPE = PREFIX + "MemoryQuery"
RESULT_TYPE = PREFIX + "MemoryResult"
EVENT_TYPE = PREFIX + "StateEvent"
MAX_QUERY_BYTES = 16 * 1024
MAX_RESULT_BYTES = 128 * 1024
MAX_EVENT_BYTES = 16 * 1024
ORIGINS = {
    pb.USER_DECISION: Origin.USER_DECISION,
    pb.IMPORTED_CLAIM: Origin.IMPORTED_CLAIM,
    pb.MODEL_HYPOTHESIS: Origin.MODEL_HYPOTHESIS,
}
ACTIONS = {
    pb.ASSERT: Action.ASSERT, pb.CONFIRM: Action.CONFIRM,
    pb.CHALLENGE: Action.CHALLENGE, pb.SUPERSEDE: Action.SUPERSEDE,
    pb.RETRACT: Action.RETRACT, pb.EXPIRE: Action.EXPIRE,
    pb.MERGE: Action.MERGE,
}
REVERSE_ORIGINS = {v: k for k, v in ORIGINS.items()}
REVERSE_ACTIONS = {v: k for k, v in ACTIONS.items()}


def _parse(message_type, payload: bytes, limit: int):
    if type(payload) is not bytes or not 0 < len(payload) <= limit:
        raise ValueError("invalid or oversized native payload")
    message = message_type()
    try:
        message.ParseFromString(payload)
    except DecodeError as error:
        raise ValueError("malformed native payload") from error
    clean = message_type()
    clean.CopyFrom(message)
    clean.DiscardUnknownFields()
    if clean != message:
        raise ValueError("unknown fields rejected")
    if message.SerializeToString(deterministic=True) != payload:
        raise ValueError("noncanonical native payload")
    return message


def _wire(message, limit):
    payload = message.SerializeToString(deterministic=True)
    if not 0 < len(payload) <= limit:
        raise ValueError("oversized native payload")
    return payload


def _to_ms(value: datetime) -> int:
    if value.tzinfo is None:
        raise ValueError("timezone-aware time required")
    return int(value.timestamp() * 1000)


def _from_ms(ms: int) -> datetime:
    try:
        return datetime.fromtimestamp(ms / 1000, timezone.utc)
    except (OverflowError, OSError, ValueError) as error:
        raise ValueError("timestamp outside supported range") from error


def encode_query(query: MemoryQuery, snapshot_id: str, revision: int) -> tuple[str, bytes]:
    if not snapshot_id or revision < 0:
        raise ValueError("snapshot pin required")
    message = pb.MemoryQuery(
        scope=query.scope, text=query.text, subject=query.subject or "",
        evidence_limit=query.evidence_limit, expected_snapshot_id=snapshot_id,
        expected_origin_revision=revision,
    )
    if query.as_of is not None:
        message.as_of_unix_ms = _to_ms(query.as_of)
    return QUERY_TYPE, _wire(message, MAX_QUERY_BYTES)


def decode_query(type_url: str, payload: bytes, *, authorized_scope: str, snapshot_id: str,
                 origin_revision: int) -> MemoryQuery:
    if type_url != QUERY_TYPE:
        raise ValueError("unexpected native request type")
    message = _parse(pb.MemoryQuery, payload, MAX_QUERY_BYTES)
    if (not authorized_scope or message.scope != authorized_scope
            or message.expected_snapshot_id != snapshot_id
            or message.expected_origin_revision != origin_revision):
        raise PermissionError("scope or canonical snapshot mismatch")
    if not 1 <= message.evidence_limit <= 100:
        raise RetrievalError("unbounded native query")
    return MemoryQuery(
        scope=message.scope, text=message.text, subject=message.subject or None,
        evidence_limit=message.evidence_limit,
        as_of=_from_ms(message.as_of_unix_ms) if message.as_of_unix_ms else None,
    )


def encode_result(result: MemoryResult) -> tuple[str, bytes]:
    msg = pb.MemoryResult(
        snapshot_id=result.index_status.snapshot_id,
        origin_revision=result.index_status.origin_revision,
        staleness=result.index_status.staleness,
    )
    for evidence in result.evidence:
        item = msg.evidence.add(
            source_id=evidence.source_id, revision=evidence.revision,
            access_scope=evidence.access_scope, subject=evidence.subject,
            text=evidence.text, citation_handle=evidence.citation_handle,
            valid_from_unix_ms=_to_ms(evidence.valid_from),
        )
        if evidence.valid_until is not None:
            item.valid_until_unix_ms = _to_ms(evidence.valid_until)
    return RESULT_TYPE, _wire(msg, MAX_RESULT_BYTES)


def _set_scalar(message, value):
    if type(value) is str:
        message.text_value = value
    elif type(value) is bool:
        message.bool_value = value
    elif type(value) is int:
        message.integer_value = value
    else:
        raise ValueError("invalid scalar type")


def encode_event(event: StateEvent, *, scope: str) -> tuple[str, bytes]:
    if not scope:
        raise ValueError("host scope required")
    msg = pb.StateEvent(
        event_id=event.event_id, entity=event.entity,
        predicate=event.predicate, origin=REVERSE_ORIGINS[event.origin],
        actor_authority=event.actor_authority,
        expected_revision=event.expected_revision,
        effective_unix_ms=_to_ms(event.effective_time),
        recorded_unix_ms=_to_ms(event.recorded_time),
        action=REVERSE_ACTIONS[event.action], source_id=event.source_id,
        scope=scope,
    )
    _set_scalar(msg, event.typed_value)
    return EVENT_TYPE, _wire(msg, MAX_EVENT_BYTES)


def decode_event(type_url: str, payload: bytes, *, authorized_scope: str) -> StateEvent:
    if type_url != EVENT_TYPE:
        raise ValueError("unexpected native event type")
    msg = _parse(pb.StateEvent, payload, MAX_EVENT_BYTES)
    if not authorized_scope or msg.scope != authorized_scope:
        raise PermissionError("host scope mismatch")
    if msg.origin not in ORIGINS or msg.action not in ACTIONS:
        raise StateError("invalid native state enum")
    scalar = msg.WhichOneof("value")
    if scalar not in ("text_value", "integer_value", "bool_value"):
        raise StateError("typed value required")
    return StateEvent(
        event_id=msg.event_id, entity=msg.entity, predicate=msg.predicate,
        typed_value=getattr(msg, scalar),
        origin=ORIGINS[msg.origin], actor_authority=msg.actor_authority,
        expected_revision=msg.expected_revision,
        effective_time=_from_ms(msg.effective_unix_ms),
        recorded_time=_from_ms(msg.recorded_unix_ms),
        action=ACTIONS[msg.action], source_id=msg.source_id,
    )
