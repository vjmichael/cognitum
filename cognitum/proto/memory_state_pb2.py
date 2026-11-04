"""Generated-equivalent descriptor binding for C06/C07 typed memory/state v1.

The exact descriptor is compiler-parity checked in C06/C07 CI.
"""
from google.protobuf import descriptor_pb2 as _pb
from google.protobuf import descriptor_pool as _pool
from google.protobuf.internal import builder as _builder

_fd = _pb.FileDescriptorProto()
_fd.name = "cognitum/memory/v1/memory_state.proto"
_fd.package = "cognitum.memory.v1"
_fd.syntax = "proto3"

for name, members in (
    ("ClaimOrigin", (("CLAIM_ORIGIN_UNSPECIFIED", 0), ("USER_DECISION", 1),
                     ("IMPORTED_CLAIM", 2), ("MODEL_HYPOTHESIS", 3))),
    ("StateAction", (("STATE_ACTION_UNSPECIFIED", 0), ("ASSERT", 1),
                     ("CONFIRM", 2), ("CHALLENGE", 3), ("SUPERSEDE", 4),
                     ("RETRACT", 5), ("EXPIRE", 6), ("MERGE", 7))),
):
    enum = _fd.enum_type.add()
    enum.name = name
    for label, number in members:
        value = enum.value.add()
        value.name, value.number = label, number

T = _pb.FieldDescriptorProto
S, I64, U32, U64, B, SI64, E, M = (
    T.TYPE_STRING, T.TYPE_INT64, T.TYPE_UINT32, T.TYPE_UINT64,
    T.TYPE_BOOL, T.TYPE_SINT64, T.TYPE_ENUM, T.TYPE_MESSAGE,
)


def _msg(name, fields, oneofs=(), optional=()):
    message = _fd.message_type.add()
    message.name = name
    for oneof in oneofs:
        message.oneof_decl.add(name=oneof)
    for label, number, typ, type_name, repeated, oneof in fields:
        field = message.field.add()
        field.name, field.number, field.type = label, number, typ
        field.label = T.LABEL_REPEATED if repeated else T.LABEL_OPTIONAL
        if type_name:
            field.type_name = type_name
        if oneof is not None:
            field.oneof_index = oneof
        if label in optional:
            field.proto3_optional = True


_msg("MemoryQuery", [
    ("scope", 1, S, "", False, None), ("text", 2, S, "", False, None),
    ("subject", 3, S, "", False, None), ("evidence_limit", 4, U32, "", False, None),
    ("as_of_unix_ms", 5, I64, "", False, None),
    ("expected_snapshot_id", 6, S, "", False, None),
    ("expected_origin_revision", 7, U64, "", False, None),
])
_msg("MemoryEvidence", [
    ("source_id", 1, S, "", False, None),
    ("revision", 2, U64, "", False, None),
    ("access_scope", 3, S, "", False, None),
    ("subject", 4, S, "", False, None),
    ("text", 5, S, "", False, None),
    ("citation_handle", 6, S, "", False, None),
    ("valid_from_unix_ms", 7, I64, "", False, None),
    ("valid_until_unix_ms", 8, I64, "", False, 0),
], ("_valid_until_unix_ms",), ("valid_until_unix_ms",))
_msg("MemoryResult", [
    ("evidence", 1, M, ".cognitum.memory.v1.MemoryEvidence", True, None),
    ("snapshot_id", 2, S, "", False, None),
    ("origin_revision", 3, U64, "", False, None),
    ("staleness", 4, B, "", False, None),
])
_msg("StateEvent", [
    ("event_id", 1, S, "", False, None),
    ("entity", 2, S, "", False, None),
    ("predicate", 3, S, "", False, None),
    ("text_value", 4, S, "", False, 0),
    ("integer_value", 5, SI64, "", False, 0),
    ("bool_value", 6, B, "", False, 0),
    ("origin", 7, E, ".cognitum.memory.v1.ClaimOrigin", False, None),
    ("actor_authority", 8, S, "", False, None),
    ("expected_revision", 9, U64, "", False, None),
    ("effective_unix_ms", 10, I64, "", False, None),
    ("recorded_unix_ms", 11, I64, "", False, None),
    ("action", 12, E, ".cognitum.memory.v1.StateAction", False, None),
    ("source_id", 13, S, "", False, None),
    ("scope", 14, S, "", False, None),
], ("value",))
_msg("BeliefRecord", [
    ("entity", 1, S, "", False, None),
    ("predicate", 2, S, "", False, None),
    ("text_value", 3, S, "", False, 0),
    ("integer_value", 4, SI64, "", False, 0),
    ("bool_value", 5, B, "", False, 0),
    ("origin", 6, E, ".cognitum.memory.v1.ClaimOrigin", False, None),
    ("status", 7, S, "", False, None),
    ("revision", 8, U64, "", False, None),
    ("source_refs", 9, S, "", True, None),
    ("conflict_refs", 10, S, "", True, None),
    ("last_event_id", 11, S, "", False, None),
], ("value",))

DESCRIPTOR = _pool.Default().AddSerializedFile(_fd.SerializeToString())
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
_builder.BuildTopDescriptorsAndMessages(
    DESCRIPTOR, "cognitum.proto.memory_state_pb2", globals()
)
