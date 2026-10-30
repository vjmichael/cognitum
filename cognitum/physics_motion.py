"""C16 P1 constant-acceleration analytic reference; offline, typed, SI-only.

Exact rational arithmetic proves consistency *within the supplied model*; it
cannot prove physical correspondence or that a transformer chose correct inputs.
Lu authority, sandboxing, deployment and CE registration are explicitly absent.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import re
from google.protobuf.message import DecodeError
from .proto import physics_linear_motion_pb2 as pb

_VERSION = 1
_MAX_INPUT_FRAME = 8192
_MAX_RESULT_FRAME = 196608
_MAX_STEPS = 256
_MAX_TOTAL_SECONDS = 1000
_MAX_INPUT_NUMERATOR = 1_000_000
_MAX_INPUT_DENOMINATOR = 1_000_000
_MAX_RESULT_BITS = 256
_METHOD = 'ANALYTIC_CONSTANT_ACCELERATION_V1'
_LIMITATION = 'EXACT_1D_CONSTANT_ACCELERATION_SI; MODEL_AND_INPUTS_NOT_PHYSICALLY_VERIFIED'
_CANON_INT = re.compile(r'-?(?:0|[1-9][0-9]*)\Z', re.ASCII)
_CANON_DEN = re.compile(r'(?:[1-9][0-9]*)\Z', re.ASCII)


def _decode(data: bytes, cls, max_length: int):
    if type(data) is not bytes or not 0 < len(data) <= max_length:
        raise ValueError('INVALID_OR_OVERSIZED_PROTOBUF_FRAME')
    obj = cls()
    try:
        obj.ParseFromString(data)
    except DecodeError as exc:
        raise ValueError('INVALID_PROTOBUF_WIRE') from exc
    canonical = cls()
    canonical.CopyFrom(obj)
    canonical.DiscardUnknownFields()
    if canonical != obj or obj.SerializeToString(deterministic=True) != data:
        raise ValueError('UNKNOWN_DUPLICATE_OR_NONCANONICAL_PROTOBUF')
    return obj


def _fraction(value: pb.Rational) -> Fraction:
    if not _CANON_INT.fullmatch(value.numerator) or not _CANON_DEN.fullmatch(value.denominator):
        raise ValueError('INVALID_RATIONAL_FORMAT')
    n = int(value.numerator)
    d = int(value.denominator)
    if value.numerator == '-0' or abs(n) > _MAX_INPUT_NUMERATOR or d > _MAX_INPUT_DENOMINATOR:
        raise ValueError('UNBOUNDED_OR_NONCANONICAL_RATIONAL')
    f = Fraction(n, d)
    if f.numerator != n or f.denominator != d:
        raise ValueError('UNREDUCED_RATIONAL')
    return f


def _out(value: Fraction, dest: pb.Rational):
    if value.numerator.bit_length() > _MAX_RESULT_BITS or value.denominator.bit_length() > _MAX_RESULT_BITS:
        raise ValueError('TRAJECTORY_EXCEEDS_EXACT_ARITHMETIC_BUDGET')
    dest.numerator = str(value.numerator)
    dest.denominator = str(value.denominator)


def _validate(request: pb.LinearMotionRequest):
    if request.schema_version != _VERSION:
        raise ValueError('UNSUPPORTED_SCHEMA_VERSION')
    if request.unit_system != 'SI:m,s,kg':
        raise ValueError('UNSUPPORTED_OR_MIXED_UNIT_SYSTEM')
    if request.steps < 1 or request.steps > _MAX_STEPS:
        raise ValueError('STEP_BUDGET_EXCEEDED')
    fields = ('initial_position_m', 'initial_velocity_m_per_s', 'acceleration_m_per_s2', 'mass_kg', 'time_step_s')
    if not all(request.HasField(f) for f in fields):
        raise ValueError('MISSING_DIMENSIONED_INPUT')
    x, v, a, m, dt = (_fraction(getattr(request, name)) for name in fields)
    if m <= 0 or dt <= 0 or dt * request.steps > _MAX_TOTAL_SECONDS:
        raise ValueError('INVALID_MASS_OR_TIMESTEP_DOMAIN')
    return x, v, a, m, dt


def calculate(raw: bytes) -> bytes:
    """Verify input framing and produce bounded exact analytical trajectory."""
    req = _decode(raw, pb.LinearMotionRequest, _MAX_INPUT_FRAME)
    x, v, a, m, dt = _validate(req)
    out = pb.LinearMotionResult(schema_version=_VERSION, request_sha256=hashlib.sha256(raw).digest(),
                                method=_METHOD, arithmetic_verified=True, physical_model_validated=False,
                                host_approved=False, limitation=_LIMITATION)
    initial_ke = m * v * v / 2
    for step in range(req.steps + 1):
        t = dt * step
        p = x + v * t + a * t * t / 2
        vel = v + a * t
        ke = m * vel * vel / 2
        work = m * a * (p - x)
        if ke - initial_ke != work:
            raise ValueError('ENERGY_WORK_INVARIANT_VIOLATED')
        item = out.samples.add(step=step)
        for name, value in [('time_s', t), ('position_m', p), ('velocity_m_per_s', vel),
                            ('kinetic_energy_j', ke), ('work_j', work)]:
            _out(value, getattr(item, name))
    payload = out.SerializeToString(deterministic=True)
    if not 0 < len(payload) <= _MAX_RESULT_FRAME:
        raise ValueError('TRAJECTORY_OUTPUT_BUDGET_EXCEEDED')
    return payload


def verify(original_request: bytes, candidate_result: bytes) -> bool:
    """Independently recompute byte-for-byte; never conveys host authorization."""
    result = _decode(candidate_result, pb.LinearMotionResult, _MAX_RESULT_FRAME)
    expected = calculate(original_request)
    if not result.arithmetic_verified or result.physical_model_validated or result.host_approved:
        return False
    return candidate_result == expected
