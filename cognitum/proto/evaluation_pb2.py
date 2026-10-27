# -*- coding: utf-8 -*-
"""Descriptor-backed Protobuf evaluation v1. Source checked with protoc in CI."""
from google.protobuf import descriptor_pb2 as _d
from google.protobuf import descriptor_pool as _pool
from google.protobuf.internal import builder as _builder

_fd = _d.FileDescriptorProto()
_fd.name = "cognitum/eval/v1/evaluation.proto"
_fd.package = "cognitum.eval.v1"
_fd.syntax = "proto3"

def _enum(name, entries):
    obj = _fd.enum_type.add()
    obj.name = name
    for number, entry in enumerate(entries):
        value = obj.value.add()
        value.name, value.number = entry, number

_enum("EvaluationTier", ("EVALUATION_TIER_UNSPECIFIED",
                         "COMPONENT_SYNTHETIC", "LU_MODEL_TASK"))
_enum("HostArm", ("HOST_ARM_UNSPECIFIED", "HOST_ONLY", "CONVENTIONAL_TOOL",
                  "COGNITUM_SINGLE", "COGNITUM_COMPOSITION"))
_enum("ExpectedBehavior", ("EXPECTED_BEHAVIOR_UNSPECIFIED", "EXACT_RATIONAL",
                           "REJECT_INVALID"))
_enum("Verdict", ("VERDICT_UNSPECIFIED", "EXACT_MATCH", "EXPECTED_REJECTION",
                  "INCORRECT_RESULT", "UNEXPECTED_REJECTION"))

def _message(name):
    m = _fd.message_type.add()
    m.name = name
    return m

def _field(obj, name, number, typ, *, type_name="", repeated=False):
    field = obj.field.add()
    field.name = name
    field.number = number
    field.type = typ
    field.label = (_d.FieldDescriptorProto.LABEL_REPEATED if repeated
                   else _d.FieldDescriptorProto.LABEL_OPTIONAL)
    if type_name:
        field.type_name = type_name

STR = _d.FieldDescriptorProto.TYPE_STRING
UINT = _d.FieldDescriptorProto.TYPE_UINT32
ENUM = _d.FieldDescriptorProto.TYPE_ENUM
BOOL = _d.FieldDescriptorProto.TYPE_BOOL
MSG = _d.FieldDescriptorProto.TYPE_MESSAGE

case = _message("EvaluationCase")
_field(case, "case_id", 1, STR)
_field(case, "expression", 2, STR)
_field(case, "expected_behavior", 3, ENUM,
       type_name=".cognitum.eval.v1.ExpectedBehavior")
_field(case, "expected_rational", 4, STR)

suite = _message("EvaluationSuite")
_field(suite, "schema_version", 1, UINT)
_field(suite, "suite_id", 2, STR)
_field(suite, "tier", 3, ENUM, type_name=".cognitum.eval.v1.EvaluationTier")
_field(suite, "cases", 4, MSG, type_name=".cognitum.eval.v1.EvaluationCase",
       repeated=True)
_field(suite, "planned_host_arms", 5, ENUM,
       type_name=".cognitum.eval.v1.HostArm", repeated=True)
_field(suite, "contains_real_user_data", 6, BOOL)
rng = suite.reserved_range.add()
rng.start, rng.end = 7, 16

result = _message("EvaluationCaseResult")
_field(result, "case_id", 1, STR)
_field(result, "verdict", 2, ENUM, type_name=".cognitum.eval.v1.Verdict")
_field(result, "observed_rational", 3, STR)
_field(result, "error_code", 4, STR)

report = _message("EvaluationReport")
_field(report, "schema_version", 1, UINT)
_field(report, "suite_sha256", 2, STR)
_field(report, "tier", 3, ENUM, type_name=".cognitum.eval.v1.EvaluationTier")
_field(report, "cases", 4, MSG,
       type_name=".cognitum.eval.v1.EvaluationCaseResult", repeated=True)
_field(report, "passed", 5, UINT)
_field(report, "total", 6, UINT)
_field(report, "model_arms_executed", 7, BOOL)
_field(report, "promotion_evidence", 8, BOOL)
_field(report, "unexecuted_host_arms", 9, ENUM,
       type_name=".cognitum.eval.v1.HostArm", repeated=True)
_field(report, "scope_code", 10, STR)
rng = report.reserved_range.add()
rng.start, rng.end = 11, 21

DESCRIPTOR = _pool.Default().AddSerializedFile(_fd.SerializeToString())
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
_builder.BuildTopDescriptorsAndMessages(
    DESCRIPTOR, "cognitum.proto.evaluation_pb2", globals())
