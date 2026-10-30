"""C11 P1: offline, typed, bounded integer linear optimization.

A mature HiGHS MILP adapter (through SciPy), optional OR-Tools CP-SAT adapter,
and an exact small-domain *independent* arithmetic receipt checker.
Solver-reported optimality or infeasibility alone is not a checked proof.
All host-authorized flags below are synthetic integration gates, NOT Lu grants.
"""
from __future__ import annotations

import hashlib
import itertools
import math
import re
import time
from dataclasses import dataclass
from typing import Callable

from cognitum.formal_solver import _decode, _encode
from cognitum.proto import optimization_pb2 as p

MAX_FRAME = 64 * 1024
MAX_RESPONSE = 64 * 1024
MAX_VARS = 24
MAX_CONSTRAINTS = 128
MAX_TERMS = 512
MAX_ABS = 1_000_000
MAX_EXACT = 4096
MAX_TIME_MS = 5000
NAME = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,31}\Z', re.ASCII)
TRACE = re.compile(r'[A-Za-z0-9_.:-]{0,64}\Z', re.ASCII)


@dataclass(frozen=True)
class Problem:
    names: tuple[str, ...]
    bounds: tuple[tuple[int, int], ...]
    rows: tuple[tuple[tuple[int, ...], int, int], ...]
    objective: tuple[int, ...]
    sense: int
    domain_states: int
    exact_limit: int
    timeout_ms: int


def _compile(req: p.OptimizeRequest) -> Problem:
    if req.schema_version != 1 or not req.HasField('objective'):
        raise ValueError('UNSUPPORTED_REQUEST_SCHEMA')
    if not (1 <= len(req.variables) <= MAX_VARS) or len(req.constraints) > MAX_CONSTRAINTS:
        raise ValueError('INPUT_SIZE_LIMIT')
    if req.objective.sense not in (p.MINIMIZE, p.MAXIMIZE):
        raise ValueError('INVALID_OBJECTIVE_SENSE')
    if req.timeout_ms > MAX_TIME_MS or req.max_exact_states > MAX_EXACT or not TRACE.fullmatch(req.trace_id):
        raise ValueError('INVALID_RESOURCE_LIMIT')
    if req.backend_id not in ('scipy-highs', 'ortools-cpsat'):
        raise ValueError('UNKNOWN_BACKEND')
    names, bounds = [], []
    for var in req.variables:
        if not NAME.fullmatch(var.name) or var.name in names:
            raise ValueError('DUPLICATE_OR_INVALID_VARIABLE')
        if (abs(var.lower) > MAX_ABS or abs(var.upper) > MAX_ABS or var.lower > var.upper or
                (var.binary and (var.lower, var.upper) != (0, 1))):
            raise ValueError('INVALID_VARIABLE_DOMAIN')
        names.append(var.name)
        bounds.append((int(var.lower), int(var.upper)))
    positions = {name: i for i, name in enumerate(names)}
    total_terms = 0

    def terms_list(terms):
        nonlocal total_terms
        vec = [0] * len(names)
        seen = set()
        total_terms += len(terms)
        if total_terms > MAX_TERMS:
            raise ValueError('INPUT_SIZE_LIMIT')
        for term in terms:
            if term.variable not in positions or term.variable in seen:
                raise ValueError('DUPLICATE_OR_UNKNOWN_TERM_VARIABLE')
            if abs(term.coefficient) > MAX_ABS:
                raise ValueError('COEFFICIENT_OUT_OF_RANGE')
            seen.add(term.variable)
            vec[positions[term.variable]] = int(term.coefficient)
        return tuple(vec)

    obj = terms_list(req.objective.terms)
    rows = []
    for row in req.constraints:
        if row.relation not in (p.LESS_EQUAL, p.GREATER_EQUAL, p.EQUAL):
            raise ValueError('UNKNOWN_RELATION')
        if abs(row.rhs) > MAX_ABS or not TRACE.fullmatch(row.label):
            raise ValueError('INVALID_BOUND_OR_LABEL')
        rows.append((terms_list(row.terms), int(row.relation), int(row.rhs)))
    states = 1
    for lo, hi in bounds:
        states *= (hi - lo + 1)
    return Problem(tuple(names), tuple(bounds), tuple(rows), obj, req.objective.sense,
                   states, req.max_exact_states or MAX_EXACT, req.timeout_ms or 2000)


def _valid_assignment(problem: Problem, values: tuple[int, ...]):
    if len(values) != len(problem.names):
        return False
    if any(type(x) is not int or not lo <= x <= hi for x, (lo, hi) in zip(values, problem.bounds)):
        return False
    for coeffs, relation, rhs in problem.rows:
        left = sum(c * x for c, x in zip(coeffs, values))
        if ((relation == p.LESS_EQUAL and left > rhs) or
            (relation == p.GREATER_EQUAL and left < rhs) or
            (relation == p.EQUAL and left != rhs)):
            return False
    return True


def _value(problem: Problem, values: tuple[int, ...]):
    return sum(c * x for c, x in zip(problem.objective, values))


def _exact_certificate(problem: Problem):
    """Independent finite proof, or None if it would exceed the host's cap."""
    if problem.domain_states > problem.exact_limit:
        return None
    best, witness = None, None
    count = 0
    for tup in itertools.product(*(range(lo, hi + 1) for lo, hi in problem.bounds)):
        count += 1
        if not _valid_assignment(problem, tup):
            continue
        val = _value(problem, tup)
        if best is None or ((val < best) if problem.sense == p.MINIMIZE else (val > best)):
            best, witness = val, tup
    return best, witness, count


def _scipy_highs(problem: Problem, timeout_ms: int):
    # scipy.optimize.milp delegates to the independently maintained HiGHS engine.
    import numpy as np
    import scipy
    from scipy.optimize import Bounds, LinearConstraint, milp
    cost = np.asarray(problem.objective, dtype=np.float64)
    if problem.sense == p.MAXIMIZE:
        cost = -cost
    constraints = []
    if problem.rows:
        a = np.asarray([row[0] for row in problem.rows], dtype=np.float64)
        lb = np.asarray([rhs if op in (p.GREATER_EQUAL, p.EQUAL) else -np.inf for _, op, rhs in problem.rows])
        ub = np.asarray([rhs if op in (p.LESS_EQUAL, p.EQUAL) else np.inf for _, op, rhs in problem.rows])
        constraints = [LinearConstraint(a, lb, ub)]
    out = milp(cost, integrality=np.ones(len(problem.names), dtype=int),
               bounds=Bounds([b[0] for b in problem.bounds], [b[1] for b in problem.bounds]),
               constraints=constraints, options={'time_limit': timeout_ms / 1000.0, 'mip_rel_gap': 0.0})
    status = {0: 'OPTIMAL', 1: 'LIMIT', 2: 'INFEASIBLE', 3: 'UNBOUNDED'}.get(int(out.status), 'ERROR')
    vals = None if out.x is None else tuple(float(x) for x in out.x)
    return status, vals, f'scipy-{scipy.__version__}/HiGHS'


def _ortools_cpsat(problem: Problem, timeout_ms: int):
    from ortools.sat.python import cp_model
    import ortools
    model = cp_model.CpModel()
    xs = [model.new_int_var(lo, hi, name) for name, (lo, hi) in zip(problem.names, problem.bounds)]
    for coeff, rel, rhs in problem.rows:
        expr = sum(c * x for c, x in zip(coeff, xs))
        if rel == p.LESS_EQUAL:
            model.add(expr <= rhs)
        elif rel == p.GREATER_EQUAL:
            model.add(expr >= rhs)
        else:
            model.add(expr == rhs)
    objective = sum(c * x for c, x in zip(problem.objective, xs))
    if problem.sense == p.MINIMIZE:
        model.minimize(objective)
    else:
        model.maximize(objective)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = timeout_ms / 1000
    solver.parameters.num_search_workers = 1
    result = solver.solve(model)
    status = ({cp_model.OPTIMAL: 'OPTIMAL', cp_model.FEASIBLE: 'FEASIBLE',
               cp_model.INFEASIBLE: 'INFEASIBLE', cp_model.UNKNOWN: 'LIMIT',
               cp_model.MODEL_INVALID: 'ERROR'}).get(result, 'ERROR')
    vals = tuple(int(solver.value(x)) for x in xs) if result in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None
    return status, vals, 'ortools-' + getattr(ortools, '__version__', 'unknown')


class OptimizationRegistry:
    """Host-controlled synthetic admission. No model can enable this registry."""
    def __init__(self, *, enabled=False):
        self.enabled = bool(enabled)
        self.backends: dict[str, Callable] = {'scipy-highs': _scipy_highs, 'ortools-cpsat': _ortools_cpsat}

    def disable(self):
        self.enabled = False

    def run_frame(self, frame: bytes, *, host_authorized=False) -> bytes:
        req = _decode(frame, p.OptimizeRequest, MAX_FRAME)
        result = p.OptimizeResult(schema_version=1, request_sha256=hashlib.sha256(frame).digest(),
                                  backend_id=req.backend_id, trace_id=req.trace_id, status=p.REJECTED,
                                  reason_code='HOST_AUTHORIZATION_REQUIRED')
        if not host_authorized:
            return _encode(result, MAX_RESPONSE)
        if not self.enabled:
            result.reason_code = 'REGISTRY_DISABLED'
            return _encode(result, MAX_RESPONSE)
        start = time.monotonic_ns()
        try:
            problem = _compile(req)
            backend = self.backends.get(req.backend_id)
            if backend is None:
                raise ValueError('BACKEND_NOT_REGISTERED')
            claim, values, version = backend(problem, problem.timeout_ms)
            result.backend_version = str(version)[:80]
            result.backend_claim = claim
            if claim not in {'OPTIMAL', 'FEASIBLE', 'INFEASIBLE', 'LIMIT', 'UNBOUNDED', 'ERROR'}:
                raise ValueError('UNRECOGNIZED_SOLVER_STATUS')
            candidate = None
            if values is not None:
                if len(values) != len(problem.names) or any(not math.isfinite(float(x)) for x in values):
                    raise ValueError('INVALID_SOLVER_WITNESS')
                # Never use untrusted rounded doubles as proofs. Exact integral check first.
                if any(abs(float(x) - round(float(x))) > 1e-6 for x in values):
                    raise ValueError('FRACTIONAL_INTEGER_WITNESS')
                candidate = tuple(int(round(float(x))) for x in values)
                if not _valid_assignment(problem, candidate):
                    raise ValueError('WITNESS_FALSIFIES_CONSTRAINTS')
                if claim not in ('OPTIMAL', 'FEASIBLE', 'LIMIT'):
                    raise ValueError('INCONSISTENT_SOLVER_RESPONSE')
            exact = _exact_certificate(problem)
            if exact is not None:
                best, witness, count = exact
                result.exact_states_checked = count
                if best is None:
                    if candidate is not None:
                        raise ValueError('SOLVER_DISAGREES_WITH_EXACT_ORACLE')
                    result.status = p.VERIFIED_INFEASIBLE
                    result.optimality_verified = True
                    result.reason_code = 'EXHAUSTIVE_INFEASIBILITY_CHECKED'
                elif candidate is not None and _value(problem, candidate) == best:
                    result.status = p.VERIFIED_OPTIMAL
                    result.witness_verified = True
                    result.optimality_verified = True
                    result.reason_code = 'EXHAUSTIVE_OPTIMUM_CHECKED'
                    result.objective_value = best
                    result.assignment.extend(p.IntAssignment(name=n, value=x) for n, x in zip(problem.names, candidate))
                elif candidate is None:
                    # Honest mismatch: backend didn't return a witness; no fabricated assignment.
                    result.status = p.UNKNOWN
                    result.reason_code = 'NO_SOLVER_WITNESS'
                else:
                    result.status = p.VERIFIED_FEASIBLE
                    result.witness_verified = True
                    result.reason_code = 'NONOPTIMAL_WITNESS_CHECKED'
                    result.objective_value = _value(problem, candidate)
                    result.assignment.extend(p.IntAssignment(name=n, value=x) for n, x in zip(problem.names, candidate))
            elif candidate is not None:
                result.status = p.VERIFIED_FEASIBLE
                result.witness_verified = True
                result.objective_value = _value(problem, candidate)
                result.reason_code = 'WITNESS_VERIFIED_OPTIMALITY_UNPROVEN'
                result.assignment.extend(p.IntAssignment(name=n, value=x) for n, x in zip(problem.names, candidate))
            else:
                result.status = p.UNKNOWN
                result.reason_code = 'BACKEND_CLAIM_UNVERIFIED'
        except (ValueError, ImportError, RuntimeError, TypeError, OverflowError, OSError) as exc:
            result.status = p.REJECTED if isinstance(exc, ValueError) and str(exc) in {
                'UNSUPPORTED_REQUEST_SCHEMA', 'INPUT_SIZE_LIMIT', 'INVALID_OBJECTIVE_SENSE',
                'INVALID_RESOURCE_LIMIT', 'UNKNOWN_BACKEND', 'DUPLICATE_OR_INVALID_VARIABLE',
                'INVALID_VARIABLE_DOMAIN', 'DUPLICATE_OR_UNKNOWN_TERM_VARIABLE',
                'COEFFICIENT_OUT_OF_RANGE', 'UNKNOWN_RELATION', 'INVALID_BOUND_OR_LABEL'
            } else p.UNKNOWN
            result.reason_code = (str(exc) if isinstance(exc, ValueError) else 'BACKEND_NOT_AVAILABLE')[:80]
        finally:
            result.wall_ns = time.monotonic_ns() - start
        return _encode(result, MAX_RESPONSE)


def verify_optimization_frame(request_frame: bytes, result_frame: bytes) -> bytes:
    """Re-check exact witness/finite optimum independently of all solver libraries.

    Does NOT attest backend provenance, timing, or a real Lu host authorization.
    """
    receipt = p.OptimizeReceipt(request_sha256=hashlib.sha256(request_frame).digest(),
                                result_sha256=hashlib.sha256(result_frame).digest(),
                                reason_code='UNVERIFIED')
    try:
        req = _decode(request_frame, p.OptimizeRequest, MAX_FRAME)
        res = _decode(result_frame, p.OptimizeResult, MAX_RESPONSE)
        problem = _compile(req)
        if (res.schema_version != 1 or res.request_sha256 != receipt.request_sha256 or
                res.backend_id != req.backend_id or res.trace_id != req.trace_id or res.host_approved):
            raise ValueError('UNBOUND_RESULT')
        if res.status in (p.REJECTED, p.UNKNOWN):
            if res.assignment or res.witness_verified or res.optimality_verified:
                raise ValueError('FALSE_ASSURANCE')
            return _encode(receipt, MAX_RESPONSE)
        exact = _exact_certificate(problem)
        if res.status == p.VERIFIED_INFEASIBLE:
            if (res.assignment or res.witness_verified or not res.optimality_verified or
                    exact is None or exact[0] is not None or res.exact_states_checked != exact[2]):
                raise ValueError('UNPROVEN_INFEASIBILITY')
            receipt.optimality_verified = True
            receipt.evidence_valid = True
            receipt.states_checked = exact[2]
            receipt.reason_code = 'FINITE_INFEASIBILITY_RECHECKED'
            return _encode(receipt, MAX_RESPONSE)
        if res.status not in (p.VERIFIED_FEASIBLE, p.VERIFIED_OPTIMAL):
            raise ValueError('INVALID_RESULT_STATUS')
        if not res.witness_verified or len(res.assignment) != len(problem.names):
            raise ValueError('MISSING_WITNESS')
        if [a.name for a in res.assignment] != list(problem.names):
            raise ValueError('WITNESS_ORDER_OR_VARIABLE')
        values = tuple(int(a.value) for a in res.assignment)
        if not _valid_assignment(problem, values) or _value(problem, values) != res.objective_value:
            raise ValueError('WITNESS_FALSIFIES_PROBLEM')
        if res.status == p.VERIFIED_OPTIMAL or res.optimality_verified:
            if (res.status != p.VERIFIED_OPTIMAL or not res.optimality_verified or
                    exact is None or exact[0] != res.objective_value or
                    res.exact_states_checked != exact[2]):
                raise ValueError('UNPROVEN_OPTIMALITY')
            receipt.optimality_verified = True
            receipt.states_checked = exact[2]
        elif res.optimality_verified:
            raise ValueError('FALSE_OPTIMALITY_CLAIM')
        receipt.evidence_valid = True
        receipt.reason_code = 'EXACT_WITNESS_RECHECKED'
    except (ValueError, TypeError, OverflowError):
        receipt.reason_code = 'INVALID_OR_UNBOUND_EVIDENCE'
    return _encode(receipt, MAX_RESPONSE)


def make_optimization_audit(request_frame: bytes, result_frame: bytes) -> bytes:
    """Data-minimized, reproducible audit observation; NOT authenticated host evidence."""
    req = _decode(request_frame, p.OptimizeRequest, MAX_FRAME)
    res = _decode(result_frame, p.OptimizeResult, MAX_RESPONSE)
    if (res.schema_version != 1 or res.request_sha256 != hashlib.sha256(request_frame).digest() or
            res.backend_id != req.backend_id or res.trace_id != req.trace_id or res.host_approved):
        raise ValueError('UNBOUND_AUDIT_EVIDENCE')
    checked = p.OptimizeReceipt.FromString(verify_optimization_frame(request_frame, result_frame))
    if (res.status in (p.VERIFIED_OPTIMAL, p.VERIFIED_FEASIBLE, p.VERIFIED_INFEASIBLE) and
            (not checked.evidence_valid or checked.optimality_verified != res.optimality_verified)):
        raise ValueError('UNVERIFIED_AUDIT_ASSURANCE')
    if res.status in (p.UNKNOWN, p.REJECTED) and (res.witness_verified or res.optimality_verified or res.assignment):
        raise ValueError('FALSE_AUDIT_ASSURANCE')
    audit = p.OptimizationAudit(
        schema_version=1, request_sha256=res.request_sha256,
        result_sha256=hashlib.sha256(result_frame).digest(), trace_id=req.trace_id,
        backend_id=req.backend_id, backend_version=res.backend_version, status=res.status,
        reason_code=res.reason_code, wall_ns=res.wall_ns, witness_verified=res.witness_verified,
        optimality_verified=res.optimality_verified)
    return _encode(audit, MAX_RESPONSE)
