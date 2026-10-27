"""C03 deterministic *synthetic component* evaluation, with Protobuf only.

Does NOT run Lu, a transformer, a native CE worker or an A/B experiment.
Checks a pinned set of public arithmetic examples with the existing trusted
in-process calculator. Every host/model arm is explicitly NOT EXECUTED.
No real user data, arbitrary expressions, secrets or free-text exception
messages are accepted from a serialized benchmark suite.
"""
from hashlib import sha256
import re

from google.protobuf.message import DecodeError

from .capability_results import ExactRational
from .plugins.calculator import calculate
from .proto import evaluation_pb2 as pb

EVALUATION_SUITE_TYPE_URL = "type.googleapis.com/cognitum.eval.v1.EvaluationSuite"
EVALUATION_REPORT_TYPE_URL = "type.googleapis.com/cognitum.eval.v1.EvaluationReport"
SCHEMA_VERSION = 1
MAX_FRAME = 16 * 1024
_SUITE_ID = "synthetic_calc_v1"
_PLAN_ARMS = (pb.HOST_ONLY, pb.CONVENTIONAL_TOOL,
              pb.COGNITUM_SINGLE, pb.COGNITUM_COMPOSITION)
_FIXTURES = (
    ("decimal", "0.1+0.2", pb.EXACT_RATIONAL, "3/10"),
    ("fraction", "1/3+1/6", pb.EXACT_RATIONAL, "1/2"),
    ("negative", "-(2+3)*4", pb.EXACT_RATIONAL, "-20"),
    ("precedence", "2+3*4", pb.EXACT_RATIONAL, "14"),
    ("power", "2**-3", pb.EXACT_RATIONAL, "1/8"),
    ("big_integer", "9007199254740993+1", pb.EXACT_RATIONAL, "9007199254740994"),
    ("zero_division", "1/0", pb.REJECT_INVALID, ""),
    ("unsafe_function", "__import__('os')", pb.REJECT_INVALID, ""),
    ("resource_limit", "2**1000000", pb.REJECT_INVALID, ""),
    ("unknown_symbol", "x+1", pb.REJECT_INVALID, ""),
)
_HEX64 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_PASS = (pb.EXACT_MATCH, pb.EXPECTED_REJECTION)


def _parse_exact(frame, message_cls):
    if type(frame) is not bytes or not 0 < len(frame) <= MAX_FRAME:
        raise ValueError("invalid or oversized evaluation protobuf frame")
    message = message_cls()
    try:
        message.ParseFromString(frame)
    except DecodeError as err:
        raise ValueError("malformed evaluation protobuf") from err
    trimmed = message_cls()
    trimmed.CopyFrom(message)
    trimmed.DiscardUnknownFields()
    if trimmed != message or message.SerializeToString(deterministic=True) != frame:
        raise ValueError("unknown, duplicate or noncanonical evaluation fields")
    return message


def _serialize(message):
    frame = message.SerializeToString(deterministic=True)
    if not 0 < len(frame) <= MAX_FRAME:
        raise ValueError("evaluation frame exceeds declared limit")
    return frame


def frozen_suite():
    suite = pb.EvaluationSuite(
        schema_version=SCHEMA_VERSION, suite_id=_SUITE_ID,
        tier=pb.COMPONENT_SYNTHETIC, contains_real_user_data=False,
    )
    suite.planned_host_arms.extend(_PLAN_ARMS)
    for case_id, expression, behavior, expected in _FIXTURES:
        if behavior == pb.EXACT_RATIONAL:
            ExactRational(expected)  # strict canonical expected-value oracle
        suite.cases.add(
            case_id=case_id, expression=expression,
            expected_behavior=behavior, expected_rational=expected,
        )
    return suite


def encode_suite():
    return _serialize(frozen_suite())


def decode_suite(frame):
    suite = _parse_exact(frame, pb.EvaluationSuite)
    if suite != frozen_suite():
        raise ValueError("unreviewed synthetic evaluation suite or model-claim metadata")
    return suite


def _run_fixture(suite):
    report = pb.EvaluationReport(
        schema_version=SCHEMA_VERSION,
        suite_sha256=sha256(_serialize(suite)).hexdigest(),
        tier=pb.COMPONENT_SYNTHETIC,
        model_arms_executed=False,
        promotion_evidence=False,
        scope_code="trusted_component_smoke_only",
    )
    report.unexecuted_host_arms.extend(suite.planned_host_arms)
    for case in suite.cases:
        observed, error_code = "", ""
        try:
            observed = calculate(case.expression)
        except ValueError:
            error_code = "invalid_expression"
        if case.expected_behavior == pb.EXACT_RATIONAL:
            verdict = pb.UNEXPECTED_REJECTION if error_code else (
                pb.EXACT_MATCH if observed == case.expected_rational
                else pb.INCORRECT_RESULT
            )
        elif case.expected_behavior == pb.REJECT_INVALID:
            verdict = pb.EXPECTED_REJECTION if error_code else pb.INCORRECT_RESULT
        else:
            raise ValueError("unsupported expected behavior")
        report.cases.add(
            case_id=case.case_id, verdict=verdict,
            observed_rational=observed, error_code=error_code,
        )
    report.total = len(report.cases)
    report.passed = sum(item.verdict in _PASS for item in report.cases)
    return report


def run_component_smoke(frozen_suite_frame):
    """The only runnable v1 tier; no arbitrary model/host arm is accepted."""
    return _run_fixture(decode_suite(frozen_suite_frame))


def encode_component_report():
    return _serialize(run_component_smoke(encode_suite()))


def decode_component_report(frame):
    """Independently recompute the frozen component report before acceptance.

    This is a test fixture checker, NOT a general verifier for signed model
    benchmark results or an authentication/attestation mechanism.
    """
    report = _parse_exact(frame, pb.EvaluationReport)
    expected = run_component_smoke(encode_suite())
    if report != expected:
        raise ValueError("wrong benchmark suite/results, spoofed arm or P3 claims")
    if (not _HEX64.fullmatch(report.suite_sha256)
            or report.model_arms_executed or report.promotion_evidence):
        raise ValueError("invalid synthetic model/promotion evidence claims")
    return report
