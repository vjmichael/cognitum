# -*- coding: utf-8 -*-
"""Descriptor-backed worker protocol message classes, checked against protoc.

Canonical schema: proto/cognitum/worker/v1/worker.proto.
No pickle or JSON is used for worker request/reply transport.
"""
from google.protobuf import descriptor_pb2 as _dp
from google.protobuf import descriptor_pool as _pool
from google.protobuf.internal import builder as _builder

_fd = _dp.FileDescriptorProto()
_fd.name = "cognitum/worker/v1/worker.proto"
_fd.package = "cognitum.worker.v1"
_fd.syntax = "proto3"


def _message(name):
    m = _fd.message_type.add()
    m.name = name
    return m


def _field(m, name, number, typ, *, type_name=None, oneof_index=None):
    f = m.field.add()
    f.name = name
    f.number = number
    f.label = _dp.FieldDescriptorProto.LABEL_OPTIONAL
    f.type = typ
    if type_name:
        f.type_name = type_name
    if oneof_index is not None:
        f.oneof_index = oneof_index


STRING = _dp.FieldDescriptorProto.TYPE_STRING
BYTES = _dp.FieldDescriptorProto.TYPE_BYTES
UINT32 = _dp.FieldDescriptorProto.TYPE_UINT32
BOOL = _dp.FieldDescriptorProto.TYPE_BOOL
MESSAGE = _dp.FieldDescriptorProto.TYPE_MESSAGE

call = _message("WorkerCall")
for name, number, typ in (
    ("protocol_version", 1, UINT32),
    ("call_id", 2, STRING),
    ("native_tool_id", 3, STRING),
    ("operation", 4, STRING),
    ("operation_schema_version", 5, STRING),
    ("input_type_url", 6, STRING),
    ("input", 7, BYTES),
    ("output_type_url", 8, STRING),
    ("timeout_ms", 9, UINT32),
):
    _field(call, name, number, typ)
rr = call.reserved_range.add()
rr.start, rr.end = 10, 16

success = _message("WorkerSuccess")
_field(success, "output_type_url", 1, STRING)
_field(success, "output", 2, BYTES)

failure = _message("WorkerFailure")
_field(failure, "code", 1, STRING)
_field(failure, "retryable", 2, BOOL)

reply = _message("WorkerReply")
reply.oneof_decl.add().name = "outcome"
_field(reply, "protocol_version", 1, UINT32)
_field(reply, "call_id", 2, STRING)
_field(reply, "success", 3, MESSAGE,
       type_name=".cognitum.worker.v1.WorkerSuccess", oneof_index=0)
_field(reply, "failure", 4, MESSAGE,
       type_name=".cognitum.worker.v1.WorkerFailure", oneof_index=0)
rr = reply.reserved_range.add()
rr.start, rr.end = 5, 16

DESCRIPTOR = _pool.Default().AddSerializedFile(_fd.SerializeToString())
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, "cognitum.proto.worker_pb2", globals())
