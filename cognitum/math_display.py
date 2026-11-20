"""Numerical presentation preferences, independent of mathematical evaluation.

This module MUST NOT be invoked by mathematical computation, evidence hashing,
certification or numerical validation. Only presentation consumers may use it.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import json
import math

MAX_SETTINGS_BYTES = 1024
MAX_EXPONENT = 308
DEFAULT_EXPONENT = 3


@dataclass(frozen=True, slots=True)
class MathDisplaySettings:
    """Standard mode suppresses only DISPLAY of tiny nonzero approximate reals."""

    simplify_near_zero: bool = True
    cutoff_exponent: int = DEFAULT_EXPONENT

    def __post_init__(self):
        if type(self.simplify_near_zero) is not bool:
            raise ValueError('simplify_near_zero must be boolean')
        if type(self.cutoff_exponent) is not int or not 1 <= self.cutoff_exponent <= MAX_EXPONENT:
            raise ValueError('cutoff_exponent must be integer from 1 through 308')

    @property
    def threshold(self) -> Decimal:
        return Decimal(1).scaleb(-self.cutoff_exponent)

    def to_json(self) -> str:
        return json.dumps({
            'schema_version': 1,
            'simplify_near_zero': self.simplify_near_zero,
            'cutoff_exponent': self.cutoff_exponent,
        }, sort_keys=True, separators=(',', ':'))

    @classmethod
    def from_json(cls, raw: str) -> 'MathDisplaySettings':
        if type(raw) is not str or not 0 < len(raw.encode('utf-8')) <= MAX_SETTINGS_BYTES:
            raise ValueError('settings size/type')
        try:
            values = json.loads(raw, parse_constant=lambda v: (_ for _ in ()).throw(ValueError('nonfinite setting')))
        except (json.JSONDecodeError, UnicodeError, RecursionError) as e:
            raise ValueError('invalid settings JSON') from e
        if type(values) is not dict or set(values) != {'schema_version', 'simplify_near_zero', 'cutoff_exponent'}:
            raise ValueError('settings fields')
        if type(values['schema_version']) is not int or values['schema_version'] != 1:
            raise ValueError('settings version')
        return cls(values['simplify_near_zero'], values['cutoff_exponent'])


@dataclass(frozen=True, slots=True)
class DisplayNumber:
    shown: str
    full_precision: str
    approximate_zero: bool
    nonfinite: bool = False


def render_number(value, settings: MathDisplaySettings | None = None, *, exact: bool = False) -> DisplayNumber:
    """Render without mutating or replacing the value. Approximation is visibly marked.

    Exact quantities (Fractions, certificate strings or exact=True) are never
    suppressed. Complex values are not simplified componentwise because even a
    small imaginary eigenvalue can be mathematically significant.
    """
    s = settings if settings is not None else MathDisplaySettings()
    if not isinstance(s, MathDisplaySettings) or type(exact) is not bool:
        raise ValueError('presentation arguments')
    if type(value) is bool:
        raise ValueError('boolean is not a numerical result')
    if isinstance(value, str):
        if not exact:
            raise ValueError('untyped numeric string')
        if not value or len(value) > 2048:
            raise ValueError('exact value size')
        return DisplayNumber(value, value, False)
    if isinstance(value, Fraction):
        raw = str(value)
        return DisplayNumber(raw, raw, False)
    if isinstance(value, complex):
        raw = str(value)
        return DisplayNumber(raw, raw, False, not math.isfinite(value.real) or not math.isfinite(value.imag))
    if isinstance(value, Decimal):
        raw = str(value)
        if not value.is_finite():
            return DisplayNumber(raw, raw, False, True)
        magnitude = abs(value)
    elif type(value) in (int, float):
        raw = str(value)
        if type(value) is float and not math.isfinite(value):
            return DisplayNumber(raw, raw, False, True)
        magnitude = abs(Decimal(raw))
    else:
        raise ValueError('unsupported scalar: convert explicitly at presentation boundary')
    if exact or not s.simplify_near_zero or magnitude == 0:
        return DisplayNumber(raw, raw, False)
    if magnitude < s.threshold:
        return DisplayNumber('≈ 0', raw, True)
    return DisplayNumber(raw, raw, False)


def render_vector(values, settings: MathDisplaySettings | None = None, *, exact: bool = False) -> tuple[DisplayNumber, ...]:
    if type(values) not in (list, tuple) or len(values) > 4096:
        raise ValueError('vector shape/budget')
    return tuple(render_number(value, settings, exact=exact) for value in values)
