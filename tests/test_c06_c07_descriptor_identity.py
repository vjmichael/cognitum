"""Protect the C06/C07 descriptor identity repair and old nested wire bytes."""
from google.protobuf import descriptor_pool, message_factory
import pytest
from cognitum.proto import host_owned_memory_pb2 as host, memory_state_pb2 as typed
from cognitum.memory_state_wire import EVENT_TYPE

# Frozen independently serialized pre-repair ProposalRequest with a nested
# EventSnapshot.events entry and event. This is a wire fixture, not authorization.
PRE_REPAIR_PROPOSAL=bytes.fromhex(
    "0801128201080112074c755f414e53461a0a736e617073686f745f302a0b776f726b7370616365"
    "5f41325c0a0a6465636973696f6e5f31120b776f726b73706163655f411a06636f6c6f6e792206"
    "6c65616465722a06737472696e673204626c75653a08736f757263655f31420d757365725f6465"
    "636973696f6e500a580a62064153534552541a5c0a0a6465636973696f6e5f31120b776f726b73"
    "706163655f411a06636f6c6f6e7922066c65616465722a06737472696e673204626c75653a0873"
    "6f757263655f31420d757365725f6465636973696f6e500a580a6206415353455254220b776f72"
    "6b73706163655f41"
)

def test_both_memory_contracts_register_in_one_pool():
    pool=descriptor_pool.DescriptorPool()
    pool.AddSerializedFile(host.DESCRIPTOR.serialized_pb)
    pool.AddSerializedFile(typed.DESCRIPTOR.serialized_pb)
    a=pool.FindMessageTypeByName("cognitum.memory.v1.StateEvent")
    b=pool.FindMessageTypeByName("cognitum.memory.v1.HostOwnedStateEvent")
    assert a!=b
    assert a.fields_by_name["text_value"].number==4
    assert b.fields_by_name["value"].number==6
    assert b.fields_by_name["scope_id"].number==2
    assert EVENT_TYPE=="type.googleapis.com/cognitum.memory.v1.StateEvent"
    assert host.StateEvent is host.HostOwnedStateEvent
    assert host.ProposalRequest.DESCRIPTOR.fields_by_name["event"].message_type==host.HostOwnedStateEvent.DESCRIPTOR
    assert host.EventSnapshot.DESCRIPTOR.fields_by_name["events"].message_type==host.HostOwnedStateEvent.DESCRIPTOR
    with pytest.raises(TypeError):
        host.ProposalRequest().event.CopyFrom(typed.StateEvent())
    with pytest.raises(TypeError):
        typed.StateEvent().CopyFrom(host.HostOwnedStateEvent())

def test_pre_repair_nested_wire_bytes_are_identical():
    req=host.ProposalRequest.FromString(PRE_REPAIR_PROPOSAL)
    assert req.schema_version==1
    assert req.host_authorized_scope=="workspace_A"
    assert len(req.snapshot.events)==1
    assert req.event==req.snapshot.events[0]
    assert req.event.event_id=="decision_1"
    assert req.event.scope_id=="workspace_A"
    assert req.event.value=="blue"
    assert req.event.actor_authority=="user_decision"
    assert req.event.action=="ASSERT"
    assert req.SerializeToString(deterministic=True)==PRE_REPAIR_PROPOSAL
    pool=descriptor_pool.DescriptorPool()
    pool.AddSerializedFile(typed.DESCRIPTOR.serialized_pb)
    pool.AddSerializedFile(host.DESCRIPTOR.serialized_pb)
    cls=message_factory.GetMessageClass(pool.FindMessageTypeByName("cognitum.memory.v1.ProposalRequest"))
    assert cls.FromString(PRE_REPAIR_PROPOSAL).SerializeToString(deterministic=True)==PRE_REPAIR_PROPOSAL
