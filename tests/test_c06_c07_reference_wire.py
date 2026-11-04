"""Strict canonical C06/C07 Protobuf native acceptance."""
from datetime import datetime, timezone

import pytest

from cognitum.memory_retrieval import MemoryEvidence, MemoryQuery, MemoryResult, IndexStatus
from cognitum.memory_state_wire import (
    EVENT_TYPE, QUERY_TYPE, RESULT_TYPE, decode_event, decode_query,
    encode_event, encode_query, encode_result,
)
from cognitum.proto import memory_state_pb2 as pb
from cognitum.state_revision import Action, Origin, StateEvent, StateError

T = datetime(2026, 11, 4, tzinfo=timezone.utc)


def event(value):
    return StateEvent("event", "colony", "population", value,
                      Origin.USER_DECISION, "host-opaque", 0,
                      T, T, Action.ASSERT, "source")


@pytest.mark.parametrize("value", ["active", 3, False, True, -42])
def test_typed_event_round_trip(value):
    url, payload = encode_event(event(value), scope="alice")
    assert url == EVENT_TYPE
    got = decode_event(url, payload, authorized_scope="alice")
    assert type(got.typed_value) is type(value)
    assert got.typed_value == value
    with pytest.raises(PermissionError):
        decode_event(url, payload, authorized_scope="bob")


def test_memory_query_snapshot_and_scope_are_required():
    query = MemoryQuery("alice", "probe signal", evidence_limit=3, as_of=T)
    url, payload = encode_query(query, "snap", 9)
    result = decode_query(url, payload, authorized_scope="alice",
                          snapshot_id="snap", origin_revision=9)
    assert result == query
    with pytest.raises(PermissionError):
        decode_query(url, payload, authorized_scope="alice",
                     snapshot_id="snap", origin_revision=10)
    with pytest.raises(PermissionError):
        decode_query(url, payload, authorized_scope="bob",
                     snapshot_id="snap", origin_revision=9)


def test_unknown_and_noncanonical_field_rejected():
    url, payload = encode_event(event("ready"), scope="alice")
    with pytest.raises(ValueError, match="unknown"):
        decode_event(url, payload + b"\x98\x06\x01", authorized_scope="alice")
    # A duplicate singular field is legal Protobuf but forbidden here.
    with pytest.raises(ValueError, match="noncanonical"):
        decode_event(url, payload + b"\x0a\x05event", authorized_scope="alice")
    with pytest.raises(ValueError, match="oversized"):
        decode_event(url, payload + b"x" * (16 * 1024), authorized_scope="alice")


def test_reject_unset_oneof_and_unknown_enum():
    msg = pb.StateEvent(
        event_id="event", entity="colony", predicate="population",
        scope="alice", origin=pb.USER_DECISION, action=pb.ASSERT,
        actor_authority="host-opaque", source_id="source",
    )
    with pytest.raises(StateError, match="typed value"):
        decode_event(EVENT_TYPE, msg.SerializeToString(deterministic=True),
                     authorized_scope="alice")
    msg.text_value = "ok"
    msg.origin = 999
    with pytest.raises(StateError, match="enum"):
        decode_event(EVENT_TYPE, msg.SerializeToString(deterministic=True),
                     authorized_scope="alice")


def test_memory_result_emits_native_citations():
    source = MemoryEvidence("s", 1, "alice", "colony", "water is available",
                            "cite:s", T)
    result = MemoryResult((source,), IndexStatus("snap", 1, False))
    url, payload = encode_result(result)
    assert url == RESULT_TYPE
    msg = pb.MemoryResult.FromString(payload)
    assert msg.evidence[0].citation_handle == "cite:s"
    assert msg.evidence[0].valid_from_unix_ms == int(T.timestamp() * 1000)
