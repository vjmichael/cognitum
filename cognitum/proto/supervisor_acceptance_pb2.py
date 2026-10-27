# -*- coding: utf-8 -*-
"""Descriptor-backed Protobuf classes. Compiler equivalence checked in CI.

Source: proto/cognitum/security/v1/supervisor_acceptance.proto
Not a production security attestation or authorization mechanism.
"""
from google.protobuf import descriptor_pb2 as _d
from google.protobuf import descriptor_pool as _pool
from google.protobuf.internal import builder as _builder

_f = _d.FileDescriptorProto()
_f.name = "cognitum/security/v1/supervisor_acceptance.proto"
_f.package = "cognitum.security.v1"
_f.syntax = "proto3"

def _enum(name, items):
    enum = _f.enum_type.add()
    enum.name = name
    for n, i in enumerate(items):
        v = enum.value.add()
        v.name, v.number = n, i

_enum("Platform", [
    "PLATFORM_UNSPECIFIED", "PLATFORM_ALL", "PLATFORM_WINDOWS",
    "PLATFORM_LINUX", "PLATFORM_MACOS",
])
_enum("ProbeKind", [
    "PROBE_UNSPECIFIED", "HOST_IDENTITY_AND_GRANTS",
    "MODEL_FORGED_AUTHORITY", "REPLAYED_OR_STALE_CALL",
    "UNREGISTERED_TOOL_OR_EFFECT", "SANDBOX_UNAVAILABLE",
    "PRIVATE_FILE_READ", "OUT_OF_SCOPE_WRITE", "NETWORK_DNS_LOOPBACK",
    "SENSITIVE_HANDLE_INHERITANCE", "PROCESS_TREE_BREAKAWAY",
    "RESOURCE_LIMITS", "TIMEOUT_AND_CANCEL", "REVOKE_DURING_CALL",
    "WORKSPACE_CE_UNLOAD", "LATE_REPLY_AFTER_REVOKE",
    "AUDIT_SECRET_LEAKAGE",
])
_enum("Expected", [
    "EXPECTED_UNSPECIFIED", "EXPECT_DENY", "EXPECT_KILL_AND_REAP",
    "EXPECT_RESOURCE_ENFORCEMENT", "EXPECT_REJECT_LATE_RESULT",
    "EXPECT_PRESERVE_UNRELATED", "EXPECT_METADATA_ONLY",
])

def _msg(name):
    m = _f.message_type.add()
    m.name = name
    return m

def _field(message, name, number, type_, *, type_name="", repeated=False):
    field = message.field.add()
    field.name, field.number, field.type = name, number, type_
    field.label = (_d.FieldDescriptorProto.LABEL_REPEATED if repeated
                   else _d.FieldDescriptorProto.LABEL_OPTIONAL)
    if type_name:
        field.type_name = type_name

STRING = _d.FieldDescriptorProto.TYPE_STRING
ENUM = _d.FieldDescriptorProto.TYPE_ENUM
MESSAGE = _d.FieldDescriptorProto.TYPE_MESSAGE
UINT32 = _d.FieldDescriptorProto.TYPE_UINT32
BOOL = _d.FieldDescriptorProto.TYPE_BOOL

probe = _msg("SupervisorProbe")
_field(probe, "id", 1, STRING)
_field(probe, "kind", 2, ENUM, type_name=".cognitum.security.v1.ProbeKind")
_field(probe, "platform", 3, ENUM, type_name=".cognitum.security.v1.Platform")
_field(probe, "expected", 4, ENUM, type_name=".cognitum.security.v1.Expected")
_field(probe, "description", 5, STRING)
r = probe.reserved_range.add()
r.start, r.end = 6, 16

plan = _msg("SupervisorAcceptancePlan")
_field(plan, "schema_version", 1, UINT32)
_field(plan, "ce_id", 2, STRING)
_field(plan, "worker_wire_type", 3, STRING)
_field(plan, "probes", 4, MESSAGE,
       type_name=".cognitum.security.v1.SupervisorProbe", repeated=True)
_field(plan, "production_launch_enabled", 5, BOOL)
r = plan.reserved_range.add()
r.start, r.end = 6, 16

DESCRIPTOR = _pool.Default().AddSerializedFile(_f.SerializeToString())
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
_builder.BuildTopDescriptorsAndMessages(
    DESCRIPTOR, "cognitum.proto.supervisor_acceptance_pb2", globals())
