"""Reviewed, deterministic HDC/KAN resource envelopes (MEL-03C2).

Work units are conservative logical workload proxies, not a measured time,
energy, memory or FLOP certificate. Charge all declared slots, even masked
edges, and charge admitted calls once including failures and cancellations.
No model-controlled cost estimate or approval is accepted.
"""
from dataclasses import dataclass
from . import engines as e
from . import engines_pb2 as pb

MAX_HDC_WORK = 4*e.MAX_DIM*e.MAX_CANDIDATES+e.MAX_CANDIDATES
MAX_KAN_PARAMETERS = 2*(8*12+8*8*12+8*8+8*8+8)
MAX_KAN_WORK = 4*(MAX_KAN_PARAMETERS + 16*2*(8*12*4+8*12*8+8*8+8))


def _bounded(value, lo, hi):
    return type(value) is int and lo <= value <= hi


@dataclass(frozen=True, slots=True)
class _Common:
    request_bytes: int = e.MAX_REQUEST
    result_bytes: int = e.MAX_RESULT
    timeout_ms: int = 3000
    calls: int = 1

    def _check(self):
        if not all(_bounded(x,lo,hi) for x,lo,hi in (
            (self.request_bytes,1,e.MAX_REQUEST),(self.result_bytes,1,e.MAX_RESULT),
            (self.timeout_ms,1,10000),(self.calls,1,16))):
            raise ValueError('invalid engine grant limits')


@dataclass(frozen=True, slots=True)
class HdcLimits(_Common):
    dimensions: int = 4096
    candidates: int = 16
    work: int = MAX_HDC_WORK

    def __post_init__(self):
        self._check()
        if not all(_bounded(x,lo,hi) for x,lo,hi in (
            (self.dimensions,1,e.MAX_DIM),(self.candidates,1,e.MAX_CANDIDATES),
            (self.work,1,16*MAX_HDC_WORK))):
            raise ValueError('invalid HDC grant limits')


@dataclass(frozen=True, slots=True)
class KanLimits(_Common):
    rows: int = 16
    layers: int = 2
    width: int = 8
    knots: int = 12
    parameters: int = MAX_KAN_PARAMETERS
    work: int = MAX_KAN_WORK

    def __post_init__(self):
        self._check()
        if not all(_bounded(x,lo,hi) for x,lo,hi in (
            (self.rows,1,e.MAX_ROWS),(self.layers,1,2),(self.width,1,8),
            (self.knots,3,12),(self.parameters,1,MAX_KAN_PARAMETERS),
            (self.work,1,16*MAX_KAN_WORK))):
            raise ValueError('invalid KAN grant limits')


def limits_type(operation):
    if operation in ('hdc.bind','hdc.query'):return HdcLimits
    if operation=='kan.evaluate':return KanLimits
    raise ValueError('not an engine operation')


def account(call, limits):
    """Compute from validated immutable protobuf only. Return work or None.

    HDC charges four scalar units per compared/bound bit for preparation,
    computation and witness checks, plus query ranking slots. KAN charges
    four times parameter slots plus per-row basis recurrence, dense edge
    accumulation, optional base and output slots across ALL layers. This is
    an administrative cost proxy, not an exact operation-count bound.
    """
    if type(call) is not e.Call or type(limits) is not limits_type(call.operation):
        raise ValueError('wrong resource profile')
    m=call.message
    if call.operation in ('hdc.bind','hdc.query'):
        bind=call.operation=='hdc.bind'
        d=m.bind.left.dimension if bind else m.query.probe.dimension
        count=1 if bind else len(m.query.candidates)
        if d>limits.dimensions or count>limits.candidates:return None
        return 4*d*count+(0 if bind else count)
    k=m.kan
    if k.rows>limits.rows or len(k.layers)>limits.layers:return None
    parameters=0; row_work=0
    for l in k.layers:
        i,o,z=l.inputs,l.outputs,l.knots
        if max(i,o)>limits.width or z>limits.knots:return None
        basis=z if l.basis==pb.RBF else z-l.degree-1
        parameters+=len(l.grid)+len(l.coefficients)+len(l.mask)+len(l.base)+len(l.bias)
        row_work+=i*z*(1+l.degree)+i*basis*o+(i*o if l.base else 0)+o
    if parameters>limits.parameters:return None
    return 4*(parameters+k.rows*row_work)
