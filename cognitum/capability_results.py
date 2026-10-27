"""Cognitum-owned typed result contract v1 (NOT Lu's native Protobuf ABI).

A strict, bounded representation of computational claims and failure outcomes.
This module cannot execute tools, grant permissions or register a Lu extension.
The legacy Runtime Response remains backward compatible; conversion is opt-in.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import json
import re

RESULT_SCHEMA_VERSION = "1.0.0"
_MAX_WIRE_BYTES = 16 * 1024
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z", re.ASCII)
_RATIONAL = re.compile(r"(?:0|[1-9][0-9]*|-[1-9][0-9]*)(?:/[1-9][0-9]*)?\Z", re.ASCII)
_DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]{1,3})?\Z", re.ASCII)
_STATUSES = frozenset({"completed", "validated", "invalid_input", "unavailable",
                        "denied", "timed_out", "error"})
_FAILURE_CODES = {
    "invalid_input": frozenset({"invalid_request", "invalid_operation_input", "plugin_invalid_input"}),
    "unavailable": frozenset({"capability_unavailable"}),
    "denied": frozenset({"identity_scope_mismatch", "permission_denied",
                         "effectful_execution_not_implemented",
                         "replay_requires_inert_deterministic_operation"}),
    "timed_out": frozenset({"plugin_timed_out"}),
    "error": frozenset({"plugin_error", "invalid_plugin_response_or_worker_failure"}),
}
_LIMITATIONS = frozenset({
    "intent_not_verified", "not_executed", "no_computed_answer",
    "uncertainty_unquantified", "bounds_not_probabilistic",
    "retrieval_not_truth", "no_permission_conferred",
})
_EVIDENCE_KINDS = frozenset({"computation", "source_snapshot", "checkpoint"})


def _opaque(value, label):
    if type(value) is not str or not _ID.fullmatch(value):
        raise ValueError(f"invalid {label}")
    return value


def _decimal(value):
    if type(value) is not str or len(value) > 80 or not _DECIMAL.fullmatch(value):
        raise ValueError("invalid bounded decimal")
    try:
        number = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("invalid decimal") from error
    if not number.is_finite():
        raise ValueError("non-finite decimal")
    return number


def _fields(value, required, label):
    if type(value) is not dict or set(value) != set(required):
        raise ValueError(f"invalid {label} fields")
    return value


@dataclass(frozen=True)
class ExactRational:
    """Exact arithmetic on an already-formalized expression, not intent proof."""
    value: str

    def __post_init__(self):
        if type(self.value) is not str or len(self.value) > 1024 or not _RATIONAL.fullmatch(self.value):
            raise ValueError("invalid rational representation")
        number = Fraction(self.value)
        if str(number) != self.value or max(number.numerator.bit_length(), number.denominator.bit_length()) > 1024:
            raise ValueError("rational must be reduced, canonical, and bounded")

    def to_dict(self):
        return {"kind": "exact_rational", "value": self.value}


@dataclass(frozen=True)
class NumericalEstimate:
    """A decimal estimate. Bounds are not a calibrated confidence interval."""
    value: str
    method: str
    lower: str | None = None
    upper: str | None = None

    def __post_init__(self):
        actual = _decimal(self.value)
        _opaque(self.method, "numerical method")
        if (self.lower is None) != (self.upper is None):
            raise ValueError("both interval endpoints are required")
        if self.lower is not None:
            if not _decimal(self.lower) <= actual <= _decimal(self.upper):
                raise ValueError("estimate must lie within ordered bounds")

    def to_dict(self):
        return {"kind": "numerical_estimate", "value": self.value, "method": self.method,
                "lower": self.lower, "upper": self.upper}


@dataclass(frozen=True)
class RetrievedReferences:
    """Untrusted retrieval candidates tied to a matching indexed source snapshot.

    Snapshot equality checks metadata coherence, NOT authorization or truth.
    """
    candidates: tuple[str, ...]
    source_snapshot_id: str
    index_source_snapshot_id: str

    def __post_init__(self):
        if type(self.candidates) is not tuple or not 1 <= len(self.candidates) <= 64:
            raise ValueError("retrieval candidates must be a bounded tuple")
        for candidate in self.candidates:
            _opaque(candidate, "candidate id")
        if len(set(self.candidates)) != len(self.candidates):
            raise ValueError("duplicate retrieval candidate")
        _opaque(self.source_snapshot_id, "source snapshot")
        _opaque(self.index_source_snapshot_id, "indexed source snapshot")
        if self.source_snapshot_id != self.index_source_snapshot_id:
            raise ValueError("stale derived index for source snapshot")

    def to_dict(self):
        return {"kind": "retrieved_references", "candidates": list(self.candidates),
                "source_snapshot_id": self.source_snapshot_id,
                "index_source_snapshot_id": self.index_source_snapshot_id}


@dataclass(frozen=True)
class EvidenceRef:
    """Opaque reference only; never a source excerpt, model prompt or grant."""
    kind: str
    ref: str

    def __post_init__(self):
        if type(self.kind) is not str or self.kind not in _EVIDENCE_KINDS:
            raise ValueError("unknown evidence kind")
        _opaque(self.ref, "evidence ref")

    def to_dict(self):
        return {"kind": self.kind, "ref": self.ref}


@dataclass(frozen=True)
class CapabilityFailure:
    """Sanitized error category. No free-form exception text is serialized."""
    code: str
    retryable: bool = False

    def __post_init__(self):
        if type(self.code) is not str or not any(
            self.code in codes for codes in _FAILURE_CODES.values()
        ):
            raise ValueError("unknown failure code")
        if type(self.retryable) is not bool:
            raise ValueError("retryable must be boolean")

    def to_dict(self):
        return {"code": self.code, "retryable": self.retryable}


CapabilityValue = ExactRational | NumericalEstimate | RetrievedReferences


@dataclass(frozen=True)
class CapabilityResult:
    """Discriminated, closed success/failure envelope for Cognitum prototypes."""
    request_id: str
    correlation_id: str
    operation: str
    operation_schema_version: str
    status: str
    value: CapabilityValue | None = None
    failure: CapabilityFailure | None = None
    evidence: tuple[EvidenceRef, ...] = ()
    limitations: tuple[str, ...] = ("no_computed_answer",)

    def __post_init__(self):
        from .contracts import version  # independently versioned from Lu core v1
        for field in ("request_id", "correlation_id", "operation"):
            _opaque(getattr(self, field), field)
        version(self.operation_schema_version)
        if type(self.status) is not str or self.status not in _STATUSES:
            raise ValueError("unknown execution status")
        if type(self.evidence) is not tuple or len(self.evidence) > 32 or any(
            not isinstance(item, EvidenceRef) for item in self.evidence
        ):
            raise ValueError("invalid evidence")
        if len({(item.kind, item.ref) for item in self.evidence}) != len(self.evidence):
            raise ValueError("duplicate evidence")
        if type(self.limitations) is not tuple or not 1 <= len(self.limitations) <= 8 or any(
            type(item) is not str or item not in _LIMITATIONS for item in self.limitations
        ) or len(set(self.limitations)) != len(self.limitations):
            raise ValueError("invalid limitations")
        if self.status == "completed":
            if not isinstance(self.value, (ExactRational, NumericalEstimate, RetrievedReferences)):
                raise ValueError("completed call requires typed value")
            if self.failure is not None or not self.evidence:
                raise ValueError("completed call requires evidence and cannot carry a failure")
            if isinstance(self.value, ExactRational):
                required = {"intent_not_verified"}
            elif isinstance(self.value, NumericalEstimate):
                uncertainty_code = ("uncertainty_unquantified" if self.value.lower is None
                                    else "bounds_not_probabilistic")
                required = {"intent_not_verified", uncertainty_code}
            else:
                required = {"retrieval_not_truth", "no_permission_conferred"}
            if not required <= set(self.limitations):
                raise ValueError("mandatory epistemic limitation absent")
        else:
            if self.value is not None or self.evidence:
                raise ValueError("non-completed call cannot claim computed values or evidence")
            if self.status == "validated":
                if self.failure is not None or "not_executed" not in self.limitations:
                    raise ValueError("validation alone is not execution")
            else:
                if not isinstance(self.failure, CapabilityFailure):
                    raise ValueError("failed call requires typed failure")
                if self.failure.code not in _FAILURE_CODES[self.status]:
                    raise ValueError("failure code does not match status")
                if self.status not in {"error", "timed_out", "unavailable"} and self.failure.retryable:
                    raise ValueError("denials and bad arguments are not retryable")
                if "no_computed_answer" not in self.limitations:
                    raise ValueError("failure must disclose absence of computed answer")

    @property
    def assurance(self):
        if isinstance(self.value, ExactRational):
            return "exact_arithmetic"
        if isinstance(self.value, NumericalEstimate):
            return "numerical"
        if isinstance(self.value, RetrievedReferences):
            return "heuristic"
        return "unverified"

    @property
    def interpretation(self):
        return "assumption_bound" if self.status == "completed" else "unresolved"

    def to_dict(self):
        result = {
            "schema_version": RESULT_SCHEMA_VERSION,
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "operation": self.operation,
            "operation_schema_version": self.operation_schema_version,
            "status": self.status,
            "value": self.value.to_dict() if self.value is not None else None,
            "assurance": self.assurance,
            "interpretation": self.interpretation,
            "failure": self.failure.to_dict() if self.failure is not None else None,
            "evidence": [item.to_dict() for item in self.evidence],
            "limitations": list(self.limitations),
        }
        if len(json.dumps(result, sort_keys=True, allow_nan=False).encode("utf-8")) > _MAX_WIRE_BYTES:
            raise ValueError("typed result wire budget exceeded")
        return result


def from_dict(raw):
    """Strict round-trip decoder; ignores no unknown fields and trusts no caller."""
    expected = ("schema_version", "request_id", "correlation_id", "operation",
                "operation_schema_version", "status", "value", "assurance",
                "interpretation", "failure", "evidence", "limitations")
    _fields(raw, expected, "capability result")
    if raw["schema_version"] != RESULT_SCHEMA_VERSION:
        raise ValueError("unsupported result contract")
    value = raw["value"]
    if value is not None:
        if type(value) is not dict or type(value.get("kind")) is not str:
            raise ValueError("invalid capability value")
        kind = value["kind"]
        if kind == "exact_rational":
            _fields(value, ("kind", "value"), "exact value")
            value = ExactRational(value["value"])
        elif kind == "numerical_estimate":
            _fields(value, ("kind", "value", "method", "lower", "upper"), "numerical value")
            value = NumericalEstimate(value["value"], value["method"], value["lower"], value["upper"])
        elif kind == "retrieved_references":
            _fields(value, ("kind", "candidates", "source_snapshot_id",
                            "index_source_snapshot_id"), "retrieval value")
            if type(value["candidates"]) is not list:
                raise ValueError("candidate list expected")
            value = RetrievedReferences(tuple(value["candidates"]), value["source_snapshot_id"],
                                        value["index_source_snapshot_id"])
        else:
            raise ValueError("unknown value kind")
    failure = raw["failure"]
    if failure is not None:
        _fields(failure, ("code", "retryable"), "failure")
        failure = CapabilityFailure(failure["code"], failure["retryable"])
    ev = raw["evidence"]
    limits = raw["limitations"]
    if type(ev) is not list or type(limits) is not list:
        raise ValueError("invalid evidence or limitation arrays")
    evidence = []
    for entry in ev:
        _fields(entry, ("kind", "ref"), "evidence")
        evidence.append(EvidenceRef(entry["kind"], entry["ref"]))
    result = CapabilityResult(
        request_id=raw["request_id"], correlation_id=raw["correlation_id"],
        operation=raw["operation"], operation_schema_version=raw["operation_schema_version"],
        status=raw["status"], value=value, failure=failure,
        evidence=tuple(evidence), limitations=tuple(limits))
    if raw["assurance"] != result.assurance or raw["interpretation"] != result.interpretation:
        raise ValueError("fabricated assurance or interpretation")
    result.to_dict()  # exercise wire limit for decoded untrusted data, too
    return result


def from_json(raw):
    """Decode with duplicate JSON-key rejection before validating semantics."""
    if type(raw) is not str or len(raw.encode("utf-8")) > _MAX_WIRE_BYTES:
        raise ValueError("oversized or invalid result JSON")

    def no_duplicate_keys(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate JSON field")
            value[key] = item
        return value

    return from_dict(json.loads(raw, object_pairs_hook=no_duplicate_keys))


def from_runtime_response(response, operation_schema_version="1.0.0"):
    """Opt-in adapter for the existing exact calculator and negative outcomes.

    Inert exact calculator only. Unsupported successful operations fail closed
    until their domain-specific adapter is separately designed and tested.
    """
    from .contracts import Response
    if not isinstance(response, Response):
        raise TypeError("expected trusted runtime Response")
    base = dict(request_id=response.request_id, correlation_id=response.correlation_id,
                operation=response.operation, operation_schema_version=operation_schema_version)
    if response.execution_status == "completed":
        if not (response.operation == "calc.rational"
                and response.assurance == "exact_arithmetic"
                and response.outcome == {"kind": "value"}
                and type(response.result) is dict
                and set(response.result) == {"value"}
                and response.interpretation.get("level") == "assumption_bound"
                and response.evidence == [{"kind": "computation", "ref": response.request_id}]
                and response.error is None):
            raise ValueError("unsupported or contradictory legacy success result")
        return CapabilityResult(status="completed", value=ExactRational(response.result["value"]),
                                evidence=(EvidenceRef("computation", response.request_id),),
                                limitations=("intent_not_verified",), **base)
    if (response.result is not None or response.evidence or response.outcome is not None
            or response.assurance != "unverified" or response.interpretation.get("level") != "unresolved"):
        raise ValueError("legacy non-success response made a computed claim")
    if response.execution_status == "validated":
        if response.error is not None:
            raise ValueError("validation cannot carry an error")
        return CapabilityResult(status="validated", limitations=("not_executed",), **base)
    status = response.execution_status
    if status not in _FAILURE_CODES:
        raise ValueError("unknown runtime failure status")
    code = response.error if response.error is not None else (
        "capability_unavailable" if status == "unavailable" else None)
    if code not in _FAILURE_CODES[status]:
        raise ValueError("unrecognized runtime error category")
    return CapabilityResult(status=status, failure=CapabilityFailure(
        code, status == "timed_out"),
        limitations=("no_computed_answer",), **base)
