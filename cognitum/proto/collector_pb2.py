# -*- coding: utf-8 -*-
"""Protobuf bindings for Lu collector receipt. Compiler-checked by CI.

Source: proto/cognitum/benchmark/v1/collector.proto
"""
from google.protobuf import descriptor_pb2 as _d
from google.protobuf import descriptor_pool as _pool
from google.protobuf.internal import builder as _builder

_f = _d.FileDescriptorProto()
_f.name = "cognitum/benchmark/v1/collector.proto"
_f.package = "cognitum.benchmark.v1"
_f.syntax = "proto3"

e = _f.enum_type.add()
e.name = "CollectorSource"
for index, label in enumerate(("COLLECTOR_SOURCE_UNSPECIFIED", "LU_HOST_DECLARED")):
    v = e.value.add()
    v.name, v.number = label, index

def _msg(name):
    m = _f.message_type.add()
    m.name = name
    return m

def _field(message, name, number, typ, full=""):
    f = message.field.add()
    f.name, f.number, f.type = name, number, typ
    f.label = _d.FieldDescriptorProto.LABEL_OPTIONAL
    if full:
        f.type_name = ".cognitum.benchmark.v1." + full

def _reserve(message, start, end):
    r = message.reserved_range.add()
    r.start, r.end = start, end

S = _d.FieldDescriptorProto.TYPE_STRING
B = _d.FieldDescriptorProto.TYPE_BOOL
BY = _d.FieldDescriptorProto.TYPE_BYTES
U = _d.FieldDescriptorProto.TYPE_UINT32
L = _d.FieldDescriptorProto.TYPE_UINT64
E = _d.FieldDescriptorProto.TYPE_ENUM

receipt = _msg("CollectorReceipt")
for n, k, t, ref in (
    ("schema_version", 1, U, ""),
    ("plan_sha256", 2, S, ""),
    ("capture_sha256", 3, S, ""),
    ("challenge_nonce", 4, S, ""),
    ("collector_id", 5, S, ""),
    ("collector_build_sha256", 6, S, ""),
    ("lu_build_sha256", 7, S, ""),
    ("model_artifact_sha256", 8, S, ""),
    ("run_id", 9, S, ""),
    ("collected_at_unix_ms", 10, L, ""),
    ("reported_observed_trials", 11, U, ""),
    ("declared_source", 12, E, "CollectorSource"),
    ("contains_raw_user_data", 13, B, ""),
    ("execution_security_verified", 14, B, ""),
):
    _field(receipt, n, k, t, ref)
_reserve(receipt, 15, 30)

signed = _msg("SignedCollectorReceipt")
_field(signed, "serialized_receipt", 1, BY)
_field(signed, "signature_ed25519", 2, BY)
_field(signed, "signing_key_id", 3, S)
_reserve(signed, 4, 16)

DESCRIPTOR = _pool.Default().AddSerializedFile(_f.SerializeToString())
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
_builder.BuildTopDescriptorsAndMessages(
    DESCRIPTOR, "cognitum.proto.collector_pb2", globals())
