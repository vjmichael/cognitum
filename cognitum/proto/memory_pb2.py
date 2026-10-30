"""Descriptor-backed Protobuf bindings for memory/v1/evidence.proto.

CI compares this module's descriptor with the independently compiled source.
Do not treat any constructed message as an authorization, trusted snapshot or
Lu capability registration.
"""
from google.protobuf import descriptor_pb2 as d
from google.protobuf import descriptor_pool as pool
from google.protobuf.internal import builder

fd = d.FileDescriptorProto()
fd.name = "cognitum/memory/v1/evidence.proto"
fd.package = "cognitum.memory.v1"
fd.syntax = "proto3"

S = d.FieldDescriptorProto.TYPE_STRING
U = d.FieldDescriptorProto.TYPE_UINT32
L = d.FieldDescriptorProto.TYPE_UINT64
B = d.FieldDescriptorProto.TYPE_BOOL
M = d.FieldDescriptorProto.TYPE_MESSAGE
E = d.FieldDescriptorProto.TYPE_ENUM

def enum(name, values):
    node = fd.enum_type.add()
    node.name = name
    for label, number in values:
        value = node.value.add()
        value.name, value.number = label, number

def msg(name, fields):
    node = fd.message_type.add()
    node.name = name
    for index, (field_name, typ, target, repeated) in enumerate(fields, 1):
        field = node.field.add()
        field.name = field_name
        field.number = index
        field.type = typ
        field.label = (d.FieldDescriptorProto.LABEL_REPEATED if repeated
                       else d.FieldDescriptorProto.LABEL_OPTIONAL)
        if target:
            field.type_name = ".cognitum.memory.v1." + target

# Inline descriptors are deliberately simple: no Any, maps or external imports.
enum("RetrievalStatus", [
    ("RETRIEVAL_STATUS_UNSPECIFIED", 0), ("VERIFIED", 1), ("DENIED", 2),
    ("UNAVAILABLE", 3), ("STALE", 4), ("DELETED", 5), ("INVALID", 6),
    ("LIMIT", 7), ("UNSUPPORTED", 8), ("CANCELLED", 9),
])
enum("RevisionKind", [
    ("REVISION_KIND_UNSPECIFIED", 0), ("CURRENT", 1), ("HISTORICAL", 2),
])
msg("SourceRef", [(n, S, None, False) for n in (
    "session_id", "chapter_id", "entry_id", "revision_id")])
msg("MemoryQuery", [
    ("schema_version", U, None, False), ("request_id", S, None, False),
    ("literal_query", S, None, False), ("max_results", U, None, False),
    ("include_historical", B, None, False), ("exact_sources", M, "SourceRef", True),
])
msg("IndexedCandidate", [
    ("source", M, "SourceRef", False), ("content_sha256", S, None, False),
    ("snapshot_id", S, None, False), ("scope_id", S, None, False),
    ("start_utf8_byte", U, None, False), ("length_utf8_byte", U, None, False),
])
msg("CandidateBatch", [
    ("schema_version", U, None, False),
    ("candidates", M, "IndexedCandidate", True),
])
msg("CanonicalRecord", [
    ("source", M, "SourceRef", False), ("current_revision_id", S, None, False),
    ("authorized", B, None, False), ("deleted", B, None, False),
    ("canonical_text", S, None, False),
])
msg("CanonicalSnapshot", [
    ("schema_version", U, None, False), ("snapshot_id", S, None, False),
    ("scope_id", S, None, False), ("authorization_epoch", L, None, False),
    ("index_epoch", L, None, False), ("grant_active", B, None, False),
    ("consistent", B, None, False), ("records", M, "CanonicalRecord", True),
])
msg("MemoryEvidence", [
    ("source", M, "SourceRef", False), ("revision_kind", E, "RevisionKind", False),
    ("content_sha256", S, None, False), ("snapshot_id", S, None, False),
    ("citation_handle", S, None, False), ("start_utf8_byte", U, None, False),
    ("excerpt", S, None, False),
])
msg("RetrievalReply", [
    ("schema_version", U, None, False), ("request_id", S, None, False),
    ("status", E, "RetrievalStatus", False),
    ("evidence", M, "MemoryEvidence", True),
])


msg("CitationLookup", [
    ("schema_version", U, None, False), ("request_id", S, None, False),
    ("citation_handle", S, None, False), ("source", M, "SourceRef", False),
    ("snapshot_id", S, None, False), ("content_sha256", S, None, False),
    ("start_utf8_byte", U, None, False), ("length_utf8_byte", U, None, False),
])
msg("CitationResolution", [
    ("schema_version", U, None, False), ("request_id", S, None, False),
    ("status", E, "RetrievalStatus", False),
    ("evidence", M, "MemoryEvidence", False),
])

DESCRIPTOR = pool.Default().AddSerializedFile(fd.SerializeToString())
builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, "cognitum.proto.memory_pb2", globals())
