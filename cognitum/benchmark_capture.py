"""C03 Lu+model benchmark plan and CAPTURE FORMAT validation; no model execution.

Native binary Protobuf is canonical. Host/model identities, timing, energy and
correctness are only *declared* metadata until an independently authorized Lu
collector supplies provenance. No model, worker, OS tools or C02 launcher run.
Validation is structural: it cannot authenticate a publisher or certify metrics.
"""
from dataclasses import dataclass
from hashlib import sha256
import re

from google.protobuf.message import DecodeError
from .proto import benchmark_pb2 as pb

PLAN_TYPE_URL = "type.googleapis.com/cognitum.benchmark.v1.BenchmarkPlan"
CAPTURE_TYPE_URL = "type.googleapis.com/cognitum.benchmark.v1.BenchmarkCapture"
SCHEMA_VERSION = 1
MAX_PLAN_BYTES = 64 * 1024
MAX_CAPTURE_BYTES = 512 * 1024
ARM_ORDER = (pb.HOST_ONLY, pb.CONVENTIONAL_TOOL, pb.COGNITUM_SINGLE,
             pb.COGNITUM_COMPOSITION)
_SHAPE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/+-]{0,127}\Z", re.ASCII)
_SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_UNAVAILABLE = {"lu_ce_bridge_missing", "security_gate_blocked",
                "tool_call_unsupported", "baseline_unavailable",
                "not_scheduled"}
_ERRORS = {"model_error", "provider_unavailable", "tool_not_selected",
           "invalid_arguments", "tool_unavailable", "permission_denied",
           "tool_timed_out", "trial_timed_out", "output_invalid",
           "resource_limit", "evaluation_aborted"}
_FAILURE = {pb.TOOL_SELECTION_FAILED, pb.ARGUMENT_VALIDATION_FAILED,
            pb.TOOL_EXECUTION_FAILED, pb.HOST_DENIED, pb.TIMED_OUT,
            pb.PROVIDER_FAILED}
_COMPLETE = {pb.COMPLETED, pb.ABSTAINED}


def _id(value, field):
    if type(value) is not str or not _SHAPE_ID.fullmatch(value):
        raise ValueError("invalid " + field)


def _sha(value, field):
    if type(value) is not str or not _SHA.fullmatch(value) or value == "0" * 64:
        raise ValueError("invalid " + field)


def _parse(frame, cls, bound):
    if type(frame) is not bytes or not 0 < len(frame) <= bound:
        raise ValueError("invalid/oversized native benchmark Protobuf frame")
    msg = cls()
    try:
        msg.ParseFromString(frame)
    except DecodeError as exc:
        raise ValueError("malformed native benchmark frame") from exc
    known = cls()
    known.CopyFrom(msg)
    known.DiscardUnknownFields()
    if known != msg or msg.SerializeToString(deterministic=True) != frame:
        raise ValueError("noncanonical, unknown or duplicate protobuf fields")
    return msg


def _wire(msg, limit):
    buf = msg.SerializeToString(deterministic=True)
    if not 0 < len(buf) <= limit:
        raise ValueError("benchmark frame outside size limit")
    return buf


def expected_schedule(plan):
    """Order is case- and repeat-rotated A/B/C/D to reduce systematic order bias.

    Same seed is used across all four arms for every task/repetition. This
    is a *design check*, not evidence that sampling was deterministic.
    """
    for repeat in range(plan.inference.repeats):
        for ti, task in enumerate(plan.tasks):
            offset = (repeat + ti) % len(ARM_ORDER)
            for ai in range(len(ARM_ORDER)):
                yield (task.task_id, ARM_ORDER[(ai + offset) % 4],
                       repeat, plan.inference.seed + repeat)


def validate_plan(plan):
    if not isinstance(plan, pb.BenchmarkPlan):
        raise TypeError("typed BenchmarkPlan required")
    if plan.schema_version != SCHEMA_VERSION or plan.includes_raw_user_content:
        raise ValueError("unsupported benchmark version or raw user data")
    for f in ("plan_id", "dataset_id", "model_id", "backend_id",
              "quantization_id", "platform_id", "hardware_profile_id"):
        _id(getattr(plan, f), f)
    for f in ("dataset_sha256", "scoring_rubric_sha256", "lu_build_sha256",
              "model_artifact_sha256", "host_policy_sha256",
              "model_context_sha256"):
        _sha(getattr(plan, f), f)
    if not plan.HasField("inference"):
        raise ValueError("missing model inference settings")
    inf = plan.inference
    if (inf.temperature_milli > 2000 or not 1 <= inf.top_p_ppm <= 1_000_000
            or not 1 <= inf.max_output_tokens <= 65_536
            or not inf.max_output_tokens <= inf.context_window_tokens <= 1_048_576
            or not 1 <= inf.repeats <= 8
            or not 0 <= inf.tool_budget <= 16
            or inf.seed > (1 << 64) - inf.repeats):
        raise ValueError("nonreproducible or unsupported inference settings")
    if len(plan.arms) != 4 or tuple(a.arm for a in plan.arms) != ARM_ORDER:
        raise ValueError("exactly A/B/C/D arms in canonical order are required")
    for arm in plan.arms:
        _id(arm.comparator_id, "comparator")
        _sha(arm.comparator_build_sha256, "comparator build")
        _sha(arm.tool_catalog_sha256, "tool catalog")
        if arm.readiness not in (pb.NOT_RUNNABLE, pb.HOST_APPROVED_RUNNABLE):
            raise ValueError("arm availability must be declared")
        if arm.readiness == pb.NOT_RUNNABLE:
            if arm.unavailable_reason_code not in _UNAVAILABLE:
                raise ValueError("missing explicit arm-unavailability reason")
        elif arm.unavailable_reason_code:
            raise ValueError("runnable arm cannot also be unavailable")
        ids = tuple(arm.enabled_native_tool_ids)
        if (len(ids) != len(set(ids)) or len(ids) > 16
                or any(not _SHAPE_ID.fullmatch(v) for v in ids)
                or len(ids) > inf.tool_budget):
            raise ValueError("tool manifest budget, duplicate or identifier mismatch")
        cog = tuple(x for x in ids if x.startswith("cognitum."))
        if arm.arm in (pb.HOST_ONLY, pb.CONVENTIONAL_TOOL) and cog:
            raise ValueError("baseline cannot contain experimental Cognitum CE")
        if arm.arm == pb.CONVENTIONAL_TOOL and not ids:
            raise ValueError("conventional comparator arm requires an actual pinned tool")
        if arm.arm == pb.COGNITUM_SINGLE and len(cog) != 1:
            raise ValueError("single-CE arm must declare exactly one Cognitum tool")
        if arm.arm == pb.COGNITUM_COMPOSITION and len(cog) < 2:
            raise ValueError("composed arm needs at least two distinct Cognitum tools")
    if not 1 <= len(plan.tasks) <= 32:
        raise ValueError("task metadata count outside bound")
    seen = set()
    for task in plan.tasks:
        _id(task.task_id, "task id")
        _sha(task.task_sha256, "task hash")
        if task.task_id in seen or task.expected_tool_use not in (
                pb.TOOL_REQUIRED, pb.TOOL_NOT_REQUIRED):
            raise ValueError("duplicate task or missing tool-use oracle")
        seen.add(task.task_id)
    got = tuple((t.task_id, t.arm, t.repeat_index, t.seed) for t in plan.schedule)
    if got != tuple(expected_schedule(plan)):
        raise ValueError("incomplete/unbalanced trial assignment or changed seeds")
    _wire(plan, MAX_PLAN_BYTES)
    return plan


def encode_plan(plan):
    return _wire(validate_plan(plan), MAX_PLAN_BYTES)


def decode_plan(frame):
    return validate_plan(_parse(frame, pb.BenchmarkPlan, MAX_PLAN_BYTES))


def _metric_consistency(res):
    if res.HasField("first_token_latency_ms"):
        if (not res.HasField("end_to_end_latency_ms")
                or res.first_token_latency_ms > res.end_to_end_latency_ms):
            raise ValueError("TTFT cannot exceed/miss measured total latency")
    if res.HasField("rejected_tool_calls"):
        if (not res.HasField("attempted_tool_calls")
                or res.rejected_tool_calls > res.attempted_tool_calls):
            raise ValueError("rejected calls cannot exceed attempted calls")


@dataclass(frozen=True)
class CaptureShapeReview:
    """No claim that a model, host collector, or OS measurements are genuine."""
    format_valid: bool
    observed_trials: int
    planned_trials: int
    model_execution_authenticated: bool = False
    paired_effect_verified: bool = False
    promotion_evidence: bool = False


def validate_capture(plan, capture):
    validate_plan(plan)
    if not isinstance(capture, pb.BenchmarkCapture):
        raise TypeError("typed BenchmarkCapture required")
    if (capture.schema_version != SCHEMA_VERSION
            or capture.claims_production_promotion
            or capture.includes_raw_user_content):
        raise ValueError("invalid capture version/promotion/raw content")
    if capture.plan_sha256 != sha256(encode_plan(plan)).hexdigest():
        raise ValueError("capture does not match immutable plan")
    _id(capture.capture_id, "capture id")
    _id(capture.host_collector_id, "host collector id")
    _sha(capture.host_collector_build_sha256, "collector build")
    if len(capture.trials) != len(plan.schedule):
        raise ValueError("all planned trials must have a record, even if NOT_RUN")
    arms = {a.arm: a for a in plan.arms}
    for observed, scheduled in zip(capture.trials, plan.schedule):
        if (observed.task_id != scheduled.task_id
                or observed.arm != scheduled.arm
                or observed.repeat_index != scheduled.repeat_index
                or observed.seed != scheduled.seed):
            raise ValueError("capture missing/duplicated/mismatched paired trial")
        if observed.status not in _FAILURE | _COMPLETE | {pb.NOT_RUN}:
            raise ValueError("unknown/unspecified execution status")
        if (arms[observed.arm].readiness == pb.NOT_RUNNABLE
                and observed.status != pb.NOT_RUN):
            raise ValueError("unrunnable arm may never claim an observed result")
        has_res = observed.HasField("resources")
        if observed.status == pb.NOT_RUN:
            if (has_res or observed.error_code or observed.answer_sha256
                    or observed.tool_decision != pb.NOT_ASSESSED
                    or observed.final_grade != pb.NOT_GRADED):
                raise ValueError("NOT_RUN cannot contain metrics, grades or output")
        else:
            if not has_res or not observed.resources.HasField("end_to_end_latency_ms"):
                raise ValueError("host-observed trial requires explicit total latency")
            _metric_consistency(observed.resources)
            if observed.tool_decision == pb.TOOL_DECISION_UNSPECIFIED:
                raise ValueError("tool selection accuracy must be assessed or NOT_ASSESSED")
            if observed.status in _FAILURE:
                if (observed.error_code not in _ERRORS or observed.answer_sha256
                        or observed.final_grade != pb.NOT_GRADED):
                    raise ValueError("sanitized failure must not claim graded answer")
            else:
                if observed.error_code or observed.final_grade in (
                        pb.FINAL_GRADE_UNSPECIFIED, pb.NOT_GRADED):
                    raise ValueError("completed/abstained trial requires independent grade")
                if observed.status == pb.COMPLETED:
                    _sha(observed.answer_sha256, "answer digest")
                    if observed.final_grade in (
                            pb.APPROPRIATE_ABSTENTION, pb.INAPPROPRIATE_ABSTENTION):
                        raise ValueError("completed output must not be an abstention grade")
                elif (observed.answer_sha256 or observed.final_grade not in (
                        pb.APPROPRIATE_ABSTENTION, pb.INAPPROPRIATE_ABSTENTION)):
                    raise ValueError("abstained trial cannot claim an answer")
    _wire(capture, MAX_CAPTURE_BYTES)
    return CaptureShapeReview(
        format_valid=True,
        observed_trials=sum(r.status != pb.NOT_RUN for r in capture.trials),
        planned_trials=len(capture.trials),
    )


def encode_capture(plan, capture):
    validate_capture(plan, capture)
    return _wire(capture, MAX_CAPTURE_BYTES)


def decode_capture(plan, frame):
    capture = _parse(frame, pb.BenchmarkCapture, MAX_CAPTURE_BYTES)
    return capture, validate_capture(plan, capture)


def empty_capture_template(plan):
    """A correctly paired, explicitly UNRUN capture; never fake model data."""
    validate_plan(plan)
    capture = pb.BenchmarkCapture(
        schema_version=SCHEMA_VERSION, plan_sha256=sha256(encode_plan(plan)).hexdigest(),
        capture_id="planned-not-executed", host_collector_id="no-host-collector",
        host_collector_build_sha256="f" * 64,
        claims_production_promotion=False,
        includes_raw_user_content=False,
    )
    for row in plan.schedule:
        capture.trials.add(
            task_id=row.task_id, arm=row.arm,
            repeat_index=row.repeat_index, seed=row.seed,
            status=pb.NOT_RUN, tool_decision=pb.NOT_ASSESSED,
            final_grade=pb.NOT_GRADED,
        )
    validate_capture(plan, capture)
    return capture
