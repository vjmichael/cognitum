"""C17/P1: offline scalar Kalman-reference augmentation for typed temporal evidence.

This is NOT a learned state-space model, canonical memory store, Lu CE, OS sandbox,
physical-world certificate, authorization token, or model instruction. The
caller must provide ordered, authorized, dimensionally consistent observations.
"""
from __future__ import annotations

from decimal import Decimal, Context, InvalidOperation, localcontext
import re

from .proto import temporal_filter_pb2 as pb
from google.protobuf.message import DecodeError

MAX_FRAME = 32768
MAX_SAMPLES = 128
MAX_TIME_MS = 604800000  # 7 days from configured zero origin
MAX_GAP_MS = 86400000
MAX_FORECAST_MS = 3600000
LIMIT = Decimal("1000000000")
DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]{0,8})(?:\.[0-9]{1,6})?\Z", re.ASCII)
SOURCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,63}\Z", re.ASCII)
UNIT = re.compile(r"[A-Za-z][A-Za-z0-9._/*-]{0,23}\Z", re.ASCII)
METHOD = "SCALAR_KALMAN_RANDOM_WALK_DECIMAL_REFERENCE"
LIMITATIONS = (
    "SYNTHETIC_OR_CALLER_SUPPLIED_OBSERVATIONS_NOT_AUTHENTICATED",
    "CLASSICAL_RANDOM_WALK_NOT_LEARNED_SSM",
    "UNITS_DECLARED_NOT_PHYSICALLY_VERIFIED",
    "NOT_LU_HOST_AUTHORIZATION_OR_PHYSICAL_CERTIFICATION",
)


def _decimal(text: str, *, positive: bool = False, nonnegative: bool = False) -> Decimal:
    if not isinstance(text, str) or not DECIMAL.fullmatch(text):
        raise ValueError("INVALID_DECIMAL")
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("INVALID_DECIMAL") from exc
    if not number.is_finite() or abs(number) > LIMIT:
        raise ValueError("DECIMAL_OUT_OF_BOUNDS")
    if positive and number <= 0 or nonnegative and number < 0:
        raise ValueError("INVALID_VARIANCE")
    return number


def _text(number: Decimal) -> str:
    if not number.is_finite():
        raise ValueError("NUMERIC_NONFINITE")
    out = format(number, "f")
    if "." in out:
        out = out.rstrip("0").rstrip(".")
    return "0" if out in ("", "-0") else out


def _parse(payload: bytes) -> pb.FilterRequest:
    if type(payload) is not bytes or len(payload) > MAX_FRAME:
        raise ValueError("INVALID_FRAME_SIZE")
    req = pb.FilterRequest()
    try:
        req.ParseFromString(payload)
    except DecodeError as exc:
        raise ValueError("MALFORMED_PROTOBUF") from exc
    canonical = pb.FilterRequest()
    canonical.CopyFrom(req)
    canonical.DiscardUnknownFields()
    if canonical != req or req.SerializeToString(deterministic=True) != payload:
        raise ValueError("NONCANONICAL_PROTOBUF")
    return req


def run_filter(payload: bytes) -> bytes:
    """Recompute a bounded scalar filter. No IO and no side effects."""
    req = _parse(payload)
    if not UNIT.fullmatch(req.units):
        raise ValueError("UNITS_REQUIRED")
    if not 1 <= len(req.samples) <= MAX_SAMPLES:
        raise ValueError("INVALID_SAMPLE_COUNT")
    with localcontext(Context(prec=40)):
        mean = _decimal(req.initial_mean)
        variance = _decimal(req.initial_variance, nonnegative=True)
        q = _decimal(req.process_variance_per_second, nonnegative=True)
        r = _decimal(req.measurement_variance, positive=True)
        last_time = 0
        seen = set()
        assimilated = missing = 0
        for sample in req.samples:
            if not SOURCE.fullmatch(sample.source_id) or sample.source_id in seen:
                raise ValueError("INVALID_OR_DUPLICATE_SOURCE")
            seen.add(sample.source_id)
            if sample.time_ms < last_time or sample.time_ms > MAX_TIME_MS or (sample.time_ms == last_time and len(seen) > 1):
                raise ValueError("NONMONOTONIC_TIME")
            delta = sample.time_ms - last_time
            if delta > MAX_GAP_MS:
                raise ValueError("TIME_GAP_EXCEEDED")
            variance += q * Decimal(delta) / Decimal(1000)
            if sample.HasField("observation"):
                y = _decimal(sample.observation)
                gain = variance / (variance + r)
                mean += gain * (y - mean)
                # Joseph covariance form, preserves positivity against cancellation.
                variance = (1 - gain) ** 2 * variance + gain ** 2 * r
                assimilated += 1
            else:
                missing += 1
            last_time = sample.time_ms
            if not mean.is_finite() or not variance.is_finite() or abs(mean) > LIMIT or variance > LIMIT:
                raise ValueError("FILTER_STATE_OUT_OF_BOUNDS")
        if assimilated == 0:
            raise ValueError("NO_OBSERVED_EVIDENCE")
        future = req.forecast_time_ms
        if future < last_time or future > MAX_TIME_MS or future - last_time > MAX_FORECAST_MS:
            raise ValueError("FORECAST_OUT_OF_BOUNDS")
        variance += q * Decimal(future - last_time) / Decimal(1000)
        if variance > LIMIT:
            raise ValueError("FORECAST_VARIANCE_OUT_OF_BOUNDS")
        result = pb.FilterResult(
            mean=_text(mean), variance=_text(variance), at_time_ms=future,
            assimilated=assimilated, missing=missing, method=METHOD,
            limitations=LIMITATIONS,
        )
        frame = result.SerializeToString(deterministic=True)
        if len(frame) > MAX_FRAME:
            raise ValueError("OUTPUT_TOO_LARGE")
        return frame
