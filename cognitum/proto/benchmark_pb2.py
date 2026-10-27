# -*- coding: utf-8 -*-
"""Descriptor-backed Protobuf classes for cognitum/benchmark/v1/benchmark.proto.
Actual protoc source/descriptor wire equivalence is verified in GitHub CI.
"""
from google.protobuf import descriptor_pb2 as _d
from google.protobuf import descriptor_pool as _pool
from google.protobuf.internal import builder as _builder

_f = _d.FileDescriptorProto()
_f.name = "cognitum/benchmark/v1/benchmark.proto"
_f.package = "cognitum.benchmark.v1"
_f.syntax = "proto3"

def _enum(name, values):
    e = _f.enum_type.add()
    e.name = name
    for index, label in enumerate(values):
        v = e.value.add()
        v.name, v.number = label, index

_enum("Arm", ["ARM_UNSPECIFIED", "HOST_ONLY", "CONVENTIONAL_TOOL",
               "COGNITUM_SINGLE", "COGNITUM_COMPOSITION"])
_enum("ArmReadiness", ["ARM_READINESS_UNSPECIFIED", "NOT_RUNNABLE",
                       "HOST_APPROVED_RUNNABLE"])
_enum("ToolExpectation", ["TOOL_EXPECTATION_UNSPECIFIED", "TOOL_NOT_REQUIRED",
                          "TOOL_REQUIRED"])
_enum("TrialStatus", ["TRIAL_STATUS_UNSPECIFIED", "NOT_RUN", "COMPLETED",
                      "ABSTAINED", "TOOL_SELECTION_FAILED",
                      "ARGUMENT_VALIDATION_FAILED", "TOOL_EXECUTION_FAILED",
                      "HOST_DENIED", "TIMED_OUT", "PROVIDER_FAILED"])
_enum("ToolDecision", ["TOOL_DECISION_UNSPECIFIED", "NOT_ASSESSED",
                       "APPROPRIATE", "UNNECESSARY_CALL",
                       "MISSED_REQUIRED_CALL", "INCORRECT_CAPABILITY"])
_enum("FinalGrade", ["FINAL_GRADE_UNSPECIFIED", "NOT_GRADED", "CORRECT",
                     "INCORRECT", "APPROPRIATE_ABSTENTION",
                     "INAPPROPRIATE_ABSTENTION"])

def _msg(name):
    m = _f.message_type.add()
    m.name = name
    return m

def _field(m, name, number, t, *, full="", repeated=False, optional=False):
    f = m.field.add()
    f.name = name
    f.number = number
    f.label = (_d.FieldDescriptorProto.LABEL_REPEATED if repeated else
               _d.FieldDescriptorProto.LABEL_OPTIONAL)
    f.type = t
    if full:
        f.type_name = ".cognitum.benchmark.v1." + full
    if optional:
        oneof = m.oneof_decl.add()
        oneof.name = "_" + name
        f.oneof_index = len(m.oneof_decl) - 1
        f.proto3_optional = True

def _reserve(m, start, end):
    r = m.reserved_range.add()
    r.start, r.end = start, end

S = _d.FieldDescriptorProto.TYPE_STRING
U = _d.FieldDescriptorProto.TYPE_UINT32
L = _d.FieldDescriptorProto.TYPE_UINT64
B = _d.FieldDescriptorProto.TYPE_BOOL
E = _d.FieldDescriptorProto.TYPE_ENUM
M = _d.FieldDescriptorProto.TYPE_MESSAGE

inf = _msg("InferenceSettings")
for n, i, t in [
    ("temperature_milli", 1, U), ("top_p_ppm", 2, U),
    ("max_output_tokens", 3, U), ("context_window_tokens", 4, U),
    ("tool_budget", 5, U), ("repeats", 6, U), ("seed", 7, L),
]:
    _field(inf, n, i, t)

arm = _msg("ArmConfiguration")
for args in [
    ("arm", 1, E, "Arm"), ("readiness", 2, E, "ArmReadiness"),
    ("comparator_id", 3, S, ""), ("comparator_build_sha256", 4, S, ""),
    ("tool_catalog_sha256", 5, S, ""),
    ("enabled_native_tool_ids", 6, S, ""),
    ("unavailable_reason_code", 7, S, ""),
]:
    name, number, t, full = args
    _field(arm, name, number, t, full=full,
           repeated=name == "enabled_native_tool_ids")

task = _msg("TaskReference")
_field(task, "task_id", 1, S)
_field(task, "task_sha256", 2, S)
_field(task, "expected_tool_use", 3, E, full="ToolExpectation")

scheduled = _msg("ScheduledTrial")
_field(scheduled, "task_id", 1, S)
_field(scheduled, "arm", 2, E, full="Arm")
_field(scheduled, "repeat_index", 3, U)
_field(scheduled, "seed", 4, L)

plan = _msg("BenchmarkPlan")
_field(plan, "schema_version", 1, U)
for name, number in [
    ("plan_id", 2), ("dataset_id", 3), ("dataset_sha256", 4),
    ("scoring_rubric_sha256", 5), ("lu_build_sha256", 6),
    ("model_artifact_sha256", 7), ("model_id", 8), ("backend_id", 9),
    ("quantization_id", 10), ("host_policy_sha256", 11),
    ("platform_id", 12), ("hardware_profile_id", 13),
    ("model_context_sha256", 14),
]:
    _field(plan, name, number, S)
_field(plan, "inference", 15, M, full="InferenceSettings")
_field(plan, "arms", 16, M, full="ArmConfiguration", repeated=True)
_field(plan, "tasks", 17, M, full="TaskReference", repeated=True)
_field(plan, "schedule", 18, M, full="ScheduledTrial", repeated=True)
_field(plan, "includes_raw_user_content", 19, B)
_reserve(plan, 20, 30)

resource = _msg("ResourceObservation")
for name, number, typ in [
    ("end_to_end_latency_ms", 1, L),
    ("first_token_latency_ms", 2, L),
    ("peak_host_ram_bytes", 3, L),
    ("peak_gpu_memory_bytes", 4, L),
    ("energy_millijoules", 5, L),
    ("input_tokens", 6, L), ("output_tokens", 7, L),
    ("attempted_tool_calls", 8, U), ("rejected_tool_calls", 9, U),
    ("cost_micro_usd", 10, L),
]:
    _field(resource, name, number, typ, optional=True)

trial = _msg("TrialCapture")
_field(trial, "task_id", 1, S)
_field(trial, "arm", 2, E, full="Arm")
_field(trial, "repeat_index", 3, U)
_field(trial, "seed", 4, L)
_field(trial, "status", 5, E, full="TrialStatus")
_field(trial, "tool_decision", 6, E, full="ToolDecision")
_field(trial, "final_grade", 7, E, full="FinalGrade")
_field(trial, "error_code", 8, S)
_field(trial, "answer_sha256", 9, S)
_field(trial, "resources", 10, M, full="ResourceObservation")

capture = _msg("BenchmarkCapture")
_field(capture, "schema_version", 1, U)
_field(capture, "plan_sha256", 2, S)
_field(capture, "capture_id", 3, S)
_field(capture, "host_collector_id", 4, S)
_field(capture, "host_collector_build_sha256", 5, S)
_field(capture, "trials", 6, M, full="TrialCapture", repeated=True)
_field(capture, "claims_production_promotion", 7, B)
_field(capture, "includes_raw_user_content", 8, B)
_reserve(capture, 9, 20)

DESCRIPTOR = _pool.Default().AddSerializedFile(_f.SerializeToString())
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
_builder.BuildTopDescriptorsAndMessages(
    DESCRIPTOR, "cognitum.proto.benchmark_pb2", globals())
