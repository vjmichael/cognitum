"""C14 G10: fail-closed, *synthetic-research-only* causal assurance advisory.

No authority is delegated. Verified calculation/replay, synthetic calibration,
causal identification, and Lu host admission are four distinct concepts.
Calibration reference is a frozen, SHA-pinned G9 result, not caller material.
"""
import hashlib
import json
from pathlib import Path

from cognitum import causal_interval_comparison
from cognitum.proto import causal_assurance_policy_pb2 as pb
from tools import run_c14_p4e_g7_study as g7
from tools import run_c14_p4e_g8_uncertainty as g8
from tools import run_c14_p4e_g9_interval_comparison as g9

EVIDENCE_PATH = (Path(__file__).resolve().parents[1] / "docs" / "components" / "causal" /
                 "P4E-G9-interval-method-calibration-evidence.json")
G9_EVIDENCE_SHA256 = "87f66bdcdac7de9c25a1df0c951053fb8cb4922842b81542a5e9867f01eaf6f9"
POLICY_VERSION = "G10-POLICY-SYNTHETIC-v1"
CALIBRATION_TOLERANCE = 0.025   # advisory only; not a proof of sufficient coverage
MIN_COMPLETED = 150
MIN_COMPLETION_FRACTION = 0.95


def _sha(msg):
    return hashlib.sha256(msg.SerializeToString(deterministic=True)).digest()


def _load_calibration():
    raw = EVIDENCE_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != G9_EVIDENCE_SHA256:
        raise ValueError("CALIBRATION_EVIDENCE_DIGEST_MISMATCH")
    report = json.loads(raw)
    if (report.get("phase") != "C14 P4E G9" or report.get("kind") != "BOUNDED_OFFLINE_RESEARCH_NOT_MODEL_FACING"
            or report.get("numerical_replay_verified") is not True
            or report.get("claims") != {
                "causal_identification_proven": False,
                "host_authorized": False,
                "research_only": True,
                "uncertainty_calibration_is_empirical_not_guarantee": True,
                "windows_security_attested": False,
            }
            or report.get("design", {}).get("confidence") != .95
            or report.get("design", {}).get("resamples") != 399
            or len(report.get("results", [])) != 2000):
        raise ValueError("CALIBRATION_REPORT_INVARIANTS_INVALID")
    return report


def _validate_request(req):
    if not isinstance(req, pb.CausalAssuranceRequest):
        raise TypeError("TYPED_REQUEST_REQUIRED")
    if req.schema_version != 1 or not 1 <= len(req.trace_id) <= 128 or not req.HasField("experiment"):
        raise ValueError("INVALID_ASSURANCE_REQUEST")
    if req.selected_method not in g9.METHODS:
        raise ValueError("UNSUPPORTED_METHOD")
    if not (req.HasField("candidate") and req.HasField("calculation_receipt")):
        raise ValueError("MISSING_CALCULATION_EVIDENCE")


def calculate(req):
    """Return typed *advisory*, never host admission or causal proof.

    Invalid candidate evidence gets a REJECT disposition. Malformed requests
    fail closed by exception before a response can be claimed.
    """
    _validate_request(req)
    output = pb.CausalAssuranceDecision(
        schema_version=1, trace_id=req.trace_id, request_sha256=_sha(req),
        research_only=True, calculation_replay_checked=False,
        causal_assumptions_verified=False, may_issue_causal_claim=False,
        may_recommend_intervention=False, may_trigger_external_action=False,
        authenticated_lu_host=False,
        disposition=pb.CAUSAL_ASSURANCE_REJECT_UNVERIFIED,
        machine_safe_summary="REJECT: unverified evidence. No causal claim or intervention is authorized.",
    )

    # Do not accept caller assertions or signed-off flags as causal truth.
    if not causal_interval_comparison.verify(req.experiment, req.candidate, req.calculation_receipt):
        output.reason_codes.append("CALCULATION_RECEIPT_REPLAY_FAILED")
        return _seal(req, output)
    output.calculation_replay_checked = True
    methods = {m.method: m for m in req.candidate.methods}
    if len(methods) != len(req.candidate.methods) or req.selected_method not in methods:
        output.reason_codes.append("REQUESTED_METHOD_ABSENT_OR_DUPLICATE")
        return _seal(req, output)

    try:
        report = _load_calibration()
        key = f"{req.experiment.scenario}@{req.experiment.sample_size}"
        record = report["summary"][key][req.selected_method]
        if not isinstance(record, dict) or record["attempts"] < 1:
            raise ValueError("CALIBRATION_MISSING")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        output.reason_codes.append("CALIBRATION_SOURCE_NOT_VERIFIED_OR_MISSING")
        return _seal(req, output)

    cal = output.calibration
    cal.scenario = req.experiment.scenario
    cal.method = req.selected_method
    cal.sample_size = req.experiment.sample_size
    cal.attempts = record["attempts"]
    cal.completed = record["computed"]
    cal.nominal_confidence = report["design"]["confidence"]
    cal.eligible_in_synthetic_generator = bool(record["causal_coverage_eligible"])
    cal.source_report_sha256 = bytes.fromhex(G9_EVIDENCE_SHA256)
    cal.caveat = "EMPIRICAL_SYNTHETIC_COVERAGE_NOT_REAL_WORLD_VALIDATION_OR_CAUSAL_PROOF"
    if (record["empirical_coverage"] is not None and record["coverage_wilson_95"] is not None):
        cal.recorded_calibration = True
        cal.observed_coverage = record["empirical_coverage"]
        cal.wilson_lower, cal.wilson_upper = record["coverage_wilson_95"]
        cal.mean_interval_width = record["mean_interval_width"]

    # The G8 partially identified *population* range is NOT a sampling CI.
    # Always report separately; no backdoor/unconfoundedness assumption needed.
    rows, _ = g7.make_fixture(req.experiment.scenario, req.experiment.seed, req.experiment.sample_size)
    bounds = g8.manski_binary_bounds(rows, req.experiment.confidence)
    b = output.partial_bounds
    b.available = True
    b.plug_in_identified_lower = bounds["identified_set_plugin_lower"]
    b.plug_in_identified_upper = bounds["identified_set_plugin_upper"]
    b.population_envelope_lower = bounds["population_coverage_envelope_lower"]
    b.population_envelope_upper = bounds["population_coverage_envelope_upper"]
    b.envelope_nominal_confidence = bounds["envelope_nominal_confidence"]
    b.point_identified = False
    b.interpretation = "BINARY_OUTCOME_PARTIAL_IDENTIFICATION_SET_WITH_SEPARATE_SAMPLING_ENVELOPE"

    if req.requests_intervention_recommendation:
        output.reason_codes.append("INTERVENTION_AUTHORITY_NEVER_GRANTED")
    if req.experiment.scenario == "hidden_confounder":
        output.disposition = pb.CAUSAL_ASSURANCE_ABSTAIN_CONFOUNDING
        output.reason_codes.append("GENERATOR_HAS_KNOWN_HIDDEN_CONFOUNDER")
    elif req.experiment.scenario == "no_overlap":
        output.disposition = pb.CAUSAL_ASSURANCE_ABSTAIN_POSITIVITY
        output.reason_codes.append("POSITIVE_TREATMENT_SUPPORT_MISSING")
    elif not methods[req.selected_method].point_interval_available or methods[req.selected_method].status != "COMPUTED":
        output.disposition = pb.CAUSAL_ASSURANCE_ABSTAIN_METHOD
        output.reason_codes.append("METHOD_DID_NOT_COMPUTE_INTERVAL")
    elif (not cal.recorded_calibration or not cal.eligible_in_synthetic_generator
          or cal.completed < MIN_COMPLETED
          or cal.completed / cal.attempts < MIN_COMPLETION_FRACTION
          or req.experiment.confidence != cal.nominal_confidence
          or (req.selected_method.startswith("PAIRS_BOOT_")
              and req.experiment.bootstrap_resamples != report["design"]["resamples"])):
        output.disposition = pb.CAUSAL_ASSURANCE_ABSTAIN_CALIBRATION
        output.reason_codes.append("INSUFFICIENT_APPLICABLE_CALIBRATION")
    elif cal.observed_coverage < cal.nominal_confidence - CALIBRATION_TOLERANCE:
        output.disposition = pb.CAUSAL_ASSURANCE_ABSTAIN_CALIBRATION
        output.reason_codes.append("EMPIRICAL_SYNTHETIC_UNDERCOVERAGE")
    else:
        output.disposition = pb.CAUSAL_ASSURANCE_DESCRIBE_SYNTHETIC_ONLY
        output.reason_codes.append("SYNTHETIC_DESCRIPTIVE_ONLY")
    output.reason_codes.extend(("IDENTIFICATION_ASSUMPTIONS_NOT_VERIFIED",
                                "CALIBRATION_WILSON_UNCERTAINTY_REMAINS",
                                "NO_LU_HOST_AUTHORIZATION"))
    output.machine_safe_summary = {
        pb.CAUSAL_ASSURANCE_ABSTAIN_CONFOUNDING: "ABSTAIN: known hidden confounding; bounds only, not a point causal effect.",
        pb.CAUSAL_ASSURANCE_ABSTAIN_POSITIVITY: "ABSTAIN: no treatment overlap; bounds only.",
        pb.CAUSAL_ASSURANCE_ABSTAIN_METHOD: "ABSTAIN: requested interval did not compute.",
        pb.CAUSAL_ASSURANCE_ABSTAIN_CALIBRATION: "ABSTAIN: applicable synthetic interval coverage not adequate or not supported.",
        pb.CAUSAL_ASSURANCE_DESCRIBE_SYNTHETIC_ONLY: "DESCRIBE SYNTHETIC RESULT ONLY: assumptions unverified; no intervention recommendation.",
    }[output.disposition]
    return _seal(req, output)


def _seal(req, output):
    return output, pb.CausalAssuranceReceipt(
        request_sha256=_sha(req), result_sha256=_sha(output),
        deterministic_policy_replay_checked=True,
        independent_causal_identification_verified=False,
        authenticated_lu_host=False,
    )


def verify(req, result, receipt):
    if not (isinstance(req, pb.CausalAssuranceRequest)
            and isinstance(result, pb.CausalAssuranceDecision)
            and isinstance(receipt, pb.CausalAssuranceReceipt)):
        return False
    if (not result.research_only or result.causal_assumptions_verified
            or result.may_issue_causal_claim or result.may_recommend_intervention
            or result.may_trigger_external_action or result.authenticated_lu_host
            or receipt.authenticated_lu_host or receipt.independent_causal_identification_verified):
        return False
    try:
        expected, expected_receipt = calculate(req)
        return (result.SerializeToString(deterministic=True) == expected.SerializeToString(deterministic=True)
                and receipt.SerializeToString(deterministic=True) == expected_receipt.SerializeToString(deterministic=True))
    except (TypeError, ValueError, KeyError, OSError):
        return False
