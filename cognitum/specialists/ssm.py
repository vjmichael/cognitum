"""Cognitum SSM reference: bounded stable diagonal discrete-time state-space scan.

Actual recurrence h[t]=a*h[t-1]+B*x[t], y[t]=C*h[t]+D*x[t].
Caller-supplied coefficients are NOT learned weights or proof of model quality.
This is a deterministic sequence/state kernel, not Mamba/S4 or causal inference.
There is no persistence, memory access, data loading, file/network I/O or training.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import fsum, isfinite

MAX_STEPS = 64
MAX_DIMS = 8
MAX_ELEMENT = 1000.0
MAX_STATE = 1000000.0

class InvalidSSM(ValueError):
    """An SSM request did not satisfy bounded reference-kernel constraints."""


def _scalar(x: object, *, decay: bool = False, state: bool = False) -> float:
    if type(x) not in (float, int):
        raise InvalidSSM('NONFINITE_OR_NONNUMERIC')
    try:
        y = float(x)
    except (OverflowError, ValueError) as exc:
        raise InvalidSSM('NONFINITE_OR_NONNUMERIC') from exc
    if not isfinite(y):
        raise InvalidSSM('NONFINITE_OR_NONNUMERIC')
    bound = MAX_STATE if state else MAX_ELEMENT
    if abs(y) > bound or (decay and not (0.0 <= y <= 1.0)):
        raise InvalidSSM('STATE_OUT_OF_RANGE' if state else 'COEFFICIENT_OUT_OF_RANGE')
    return y


def _vector(xs: object, n: int | None = None, *, decay: bool = False, state: bool = False) -> tuple[float, ...]:
    if type(xs) is not list or not (1 <= len(xs) <= MAX_DIMS) or (n is not None and len(xs) != n):
        raise InvalidSSM('INVALID_VECTOR_SHAPE')
    return tuple(_scalar(x, decay=decay, state=state) for x in xs)


def _matrix(xs: object, rows: int, cols: int) -> tuple[tuple[float, ...], ...]:
    if type(xs) is not list or len(xs) != rows:
        raise InvalidSSM('INVALID_MATRIX_SHAPE')
    return tuple(_vector(row, cols) for row in xs)


@dataclass(frozen=True)
class DiagonalSSM:
    """Time-invariant, stable-by-construction diagonal linear SSM."""
    a: tuple[float, ...]
    b: tuple[tuple[float, ...], ...]
    c: tuple[tuple[float, ...], ...]
    d: tuple[tuple[float, ...], ...]

    def __post_init__(self):
        # The constructor is public: prevent bypassing from_mapping's bounded
        # shapes and coefficient checks by supplying arbitrary tuples directly.
        if type(self.a) is not tuple or not 1 <= len(self.a) <= MAX_DIMS:
            raise InvalidSSM('INVALID_VECTOR_SHAPE')
        for x in self.a:
            try:
                _scalar(x, decay=True)
            except InvalidSSM as exc:
                raise InvalidSSM('INVALID_DECAY') from exc
        n = len(self.a)
        if type(self.b) is not tuple or len(self.b) != n or not all(type(r) is tuple for r in self.b):
            raise InvalidSSM('INVALID_MATRIX_SHAPE')
        inputs = len(self.b[0]) if self.b else 0
        if not 1 <= inputs <= MAX_DIMS:
            raise InvalidSSM('INVALID_INPUT_DIMENSION')
        if type(self.c) is not tuple or not 1 <= len(self.c) <= MAX_DIMS or not all(type(r) is tuple for r in self.c):
            raise InvalidSSM('INVALID_MATRIX_SHAPE')
        if type(self.d) is not tuple or len(self.d) != len(self.c) or not all(type(r) is tuple for r in self.d):
            raise InvalidSSM('INVALID_MATRIX_SHAPE')
        for rows, width in ((self.b, inputs), (self.c, n), (self.d, inputs)):
            for row in rows:
                if len(row) != width:
                    raise InvalidSSM('INVALID_MATRIX_SHAPE')
                for v in row:
                    _scalar(v)

    @classmethod
    def from_mapping(cls, parameters: object) -> 'DiagonalSSM':
        if type(parameters) is not dict or set(parameters) != {'a', 'b', 'c', 'd'}:
            raise InvalidSSM('INVALID_PARAMETER_KEYS')
        a = _vector(parameters['a'], decay=True)
        if type(parameters['b']) is not list or not parameters['b']:
            raise InvalidSSM('INVALID_MATRIX_SHAPE')
        inputs = len(parameters['b'][0]) if type(parameters['b'][0]) is list else 0
        if inputs < 1 or inputs > MAX_DIMS:
            raise InvalidSSM('INVALID_INPUT_DIMENSION')
        b = _matrix(parameters['b'], len(a), inputs)
        if type(parameters['c']) is not list or not 1 <= len(parameters['c']) <= MAX_DIMS:
            raise InvalidSSM('INVALID_OUTPUT_DIMENSION')
        c = _matrix(parameters['c'], len(parameters['c']), len(a))
        d = _matrix(parameters['d'], len(c), inputs)
        return cls(a,b,c,d)

    def scan(self, inputs: object, initial_state: object = None) -> dict:
        if type(inputs) is not list or not 1 <= len(inputs) <= MAX_STEPS:
            raise InvalidSSM('INVALID_SEQUENCE_LENGTH')
        # A resumable state may legitimately exceed MAX_ELEMENT, which is the
        # limit for external *inputs and coefficients*, not latent state.
        # Validate against MAX_STATE consistently with in-scan overflow checks.
        state = list(_vector(initial_state, len(self.a), state=True) if initial_state is not None else (0.0,) * len(self.a))
        outputs = []
        for step in inputs:
            x = _vector(step, len(self.b[0]))
            state = [fsum((a_i*h_i, *(w*v for w,v in zip(row, x)))) for a_i,h_i,row in zip(self.a,state,self.b)]
            if any(not isfinite(s) or abs(s) > MAX_STATE for s in state):
                raise InvalidSSM('STATE_OVERFLOW')
            y = [fsum((*(w*h for w,h in zip(c_row,state)),*(w*v for w,v in zip(d_row,x))))
                 for c_row,d_row in zip(self.c,self.d)]
            if any(not isfinite(v) or abs(v) > MAX_STATE for v in y):
                raise InvalidSSM('OUTPUT_OVERFLOW')
            outputs.append(y)
        return {
            'outputs': outputs,
            'final_state': state,
            'method': 'BOUNDED_DIAGONAL_LINEAR_SSM_CPU_REFERENCE_V1',
            'limitation': 'CALLER_COEFFICIENTS_NOT_TRAINED_NOT_CAUSAL_NOT_CALIBRATED',
        }


def scan_request(obj: object) -> dict:
    if type(obj) is not dict or set(obj) != {'parameters','inputs','initial_state'}:
        raise InvalidSSM('INVALID_REQUEST_KEYS')
    return DiagonalSSM.from_mapping(obj['parameters']).scan(obj['inputs'],obj['initial_state'])
