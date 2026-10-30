"""C12 P4: experimental transition advice as a *non-authoritative* A* tie-breaker.

Only typed, precomputed, host-pinned hint tables are allowed. This is an actual
search algorithm, but NOT a learned model, a sandbox, or a benchmark result.
PREDICTED_DEAD_END cannot prune; all plan/certification checks ignore advice.
"""
from __future__ import annotations

import hashlib
import heapq
import itertools
import re
import time

from cognitum.planning import (
    _decode, _encode, _task, _hmax, _goal, _move, _certify,
    replay_plan, MAX_FRAME, MAX_TIME_MS, MAX_PLAN_LENGTH, MAX_STATES,
)
from cognitum.proto import planning_guidance_pb2 as g
from cognitum.proto import planning_pb2 as p

MAX_HINTS = 256
BACKENDS = frozenset({
    'offline-transition-classifier-v1',
    'offline-relational-guidance-v1',
    'offline-generated-heuristic-v1',
})
REFERENCE = re.compile(r'[A-Za-z0-9:/._#?=&-]{8,256}\Z', re.ASCII)
BACKEND_ID = 'cognitum-guided-astar'
BACKEND_VERSION = 'C12-P4-v1'


def frame(obj):
    return _encode(obj)


def artifact_digest(artifact: g.GuidanceArtifact):
    """Canonical content digest; does NOT authenticate its claimed model origin."""
    copy = g.GuidanceArtifact()
    copy.CopyFrom(artifact)
    copy.ClearField('content_sha256')
    return hashlib.sha256(frame(copy)).digest()


def _validate(request: g.GuidedRequest):
    if request.schema_version != 1 or request.planning.engine != p.ASTAR_HMAX:
        raise ValueError('INVALID_GUIDED_REQUEST')
    if request.planning.timeout_ms > MAX_TIME_MS:
        raise ValueError('INVALID_TIME_BUDGET')
    task = _task(request.planning)
    a = request.guidance
    if (a.schema_version != 1 or a.backend_id not in BACKENDS or
            not REFERENCE.fullmatch(a.source_reference) or
            len(a.model_sha256) != 32 or len(a.hints) > MAX_HINTS or
            len(a.content_sha256) != 32 or a.content_sha256 != artifact_digest(a)):
        raise ValueError('INVALID_GUIDANCE_ARTIFACT')
    seen, table = set(), {}
    for hint in a.hints:
        key = (hint.state_bits, hint.action_index)
        if (key in seen or hint.state_bits >= 1 << task.facts or
                hint.action_index >= len(task.actions) or
                hint.label not in (g.PREFERRED_TRANSITION, g.DISFAVORED_TRANSITION,
                                   g.PREDICTED_DEAD_END)):
            raise ValueError('INVALID_TRANSITION_HINT')
        seen.add(key)
        # Advice modifies *only the secondary sort key*, never feasibility.
        table[key] = {g.PREFERRED_TRANSITION:-1, g.DISFAVORED_TRANSITION:1,
                      g.PREDICTED_DEAD_END:2}[hint.label]
    return task, table


def _guided_search(t, table, deadline):
    serial = itertools.count()
    first = _hmax(t, t.start)
    heap = [(first, 0, 0, next(serial), t.start)]
    best = {t.start: 0}
    predecessor = {}
    expanded = hint_count = 0
    while heap and expanded < t.max_expansions and time.monotonic() < deadline:
        _, _, cost, _, state = heapq.heappop(heap)
        if cost != best[state]:
            continue
        if _goal(t, state):
            path = []
            while state != t.start:
                previous, action_idx = predecessor[state]
                path.append(action_idx)
                state = previous
            path.reverse()
            return path, expanded, len(best), hint_count, 'FOUND'
        expanded += 1
        for i, action in enumerate(t.actions):
            nxt = _move(action, state)
            if nxt is None:
                continue
            new_cost = cost + action.cost
            if new_cost >= best.get(nxt, float('inf')):
                continue
            if nxt not in best and len(best) >= t.max_states:
                return None, expanded, len(best), hint_count, 'RESOURCE_EXHAUSTED'
            h = _hmax(t, nxt)
            if h == float('inf'):
                continue  # Sound ordinary relaxed-reachability check, NOT learned advice.
            rank = table.get((state, i), 0)
            if rank:
                hint_count += 1
            best[nxt] = new_cost
            predecessor[nxt] = (state, i)
            heapq.heappush(heap, (new_cost + h, rank, new_cost, next(serial), nxt))
    return None, expanded, len(best), hint_count, ('RESOURCE_EXHAUSTED' if heap else 'FRONTIER_EXHAUSTED')


def _rejected(raw, reason):
    return frame(g.GuidedResult(schema_version=1,
        request_sha256=hashlib.sha256(raw).digest(), status=p.REJECTED,
        reason_code=reason))


class GuidanceRegistry:
    """Host-owned allowlist; cannot be configured by any Protobuf request."""
    def __init__(self, *, enabled=False, approved_artifact_digests=()):
        self.enabled = bool(enabled)
        self._approved = frozenset(approved_artifact_digests)

    def disable(self):
        self.enabled = False

    def solve_frame(self, raw: bytes, *, host_authorized=False):
        begin = time.monotonic_ns()
        if not isinstance(raw, bytes) or len(raw) > MAX_FRAME:
            raise ValueError('INVALID_FRAME')
        if not host_authorized:
            return _rejected(raw, 'HOST_AUTHORIZATION_REQUIRED')
        if not self.enabled:
            return _rejected(raw, 'GUIDED_PLANNING_DISABLED')
        try:
            request = _decode(raw, g.GuidedRequest)
            task, table = _validate(request)
        except ValueError as exc:
            return _rejected(raw, str(exc))
        digest = request.guidance.content_sha256
        if digest not in self._approved:
            return _rejected(raw, 'GUIDANCE_NOT_HOST_APPROVED')
        deadline = time.monotonic() + (request.planning.timeout_ms or MAX_TIME_MS) / 1000
        path, expanded, discovered, hints, reason = _guided_search(task, table, deadline)
        out = g.GuidedResult(schema_version=1, request_sha256=hashlib.sha256(raw).digest(),
            guidance_sha256=digest, status=p.UNKNOWN, expanded=expanded, discovered=discovered,
            applied_hints=hints, reason_code=reason, backend_id=BACKEND_ID,
            backend_version=BACKEND_VERSION)
        if path is not None and len(path) <= MAX_PLAN_LENGTH:
            try:
                out.total_cost = replay_plan(task, path)
                out.actions.extend(path)
                out.plan_verified = True
                out.status = p.VERIFIED_PLAN
            except ValueError:
                out.reason_code = 'INVALID_SOLVER_WITNESS'
        elif path is not None:
            out.reason_code = 'PLAN_TOO_LONG'
        if out.status == p.VERIFIED_PLAN:
            certified, _ = _certify(task, list(out.actions), out.status, deadline)
            if certified:
                out.status = p.VERIFIED_OPTIMAL
                out.optimality_verified = True
                out.reason_code = 'PLAN_CERTIFIED'
        elif out.reason_code == 'FRONTIER_EXHAUSTED':
            certified, _ = _certify(task, None, p.VERIFIED_UNREACHABLE, deadline)
            if certified:
                out.status = p.VERIFIED_UNREACHABLE
                out.optimality_verified = True
                out.reason_code = 'UNREACHABILITY_CERTIFIED'
        out.wall_ns = time.monotonic_ns() - begin
        return frame(out)


def verify_guided_frame(request_frame, result_frame, *, trusted_artifact_sha256=None):
    """Verify request, host pin, plan replay, and independently checked finite proof.

    Evidence validity is conditional on a trusted digest supplied OUTSIDE the request.
    The receipt does not authenticate the publisher or establish Lu host permission.
    """
    request = _decode(request_frame, g.GuidedRequest)
    result = _decode(result_frame, g.GuidedResult)
    receipt = g.GuidedReceipt(request_sha256=hashlib.sha256(request_frame).digest(),
                               result_sha256=hashlib.sha256(result_frame).digest())
    try:
        task, _table = _validate(request)
        digest = request.guidance.content_sha256
        receipt.guidance_sha256 = digest
        if trusted_artifact_sha256 is None or trusted_artifact_sha256 != digest:
            raise ValueError('UNTRUSTED_GUIDANCE_ARTIFACT')
        if result.schema_version != 1 or result.request_sha256 != receipt.request_sha256 or result.host_approved:
            raise ValueError('RESULT_BINDING_MISMATCH')
        if result.status == p.REJECTED:
            raise ValueError('REJECTION_IS_NOT_EVIDENCE')
        if (result.guidance_sha256 != digest or result.backend_id != BACKEND_ID or
                result.backend_version != BACKEND_VERSION):
            raise ValueError('BACKEND_BINDING_MISMATCH')
        if (result.expanded > task.max_expansions or result.discovered > task.max_states or
                result.applied_hints > task.max_expansions * len(task.actions)):
            raise ValueError('INVALID_EXECUTION_COUNTERS')
        if result.status in (p.VERIFIED_PLAN, p.VERIFIED_OPTIMAL):
            if not result.plan_verified or replay_plan(task, list(result.actions)) != result.total_cost:
                raise ValueError('INVALID_PLAN')
        elif result.actions or result.total_cost or result.plan_verified:
            raise ValueError('UNEXPECTED_PLAN')
        if result.optimality_verified != (result.status in (p.VERIFIED_OPTIMAL, p.VERIFIED_UNREACHABLE)):
            raise ValueError('FORGED_OPTIMALITY')
        if result.status in (p.VERIFIED_OPTIMAL, p.VERIFIED_UNREACHABLE):
            expected_reason = ('PLAN_CERTIFIED' if result.status == p.VERIFIED_OPTIMAL
                               else 'UNREACHABILITY_CERTIFIED')
            if result.reason_code != expected_reason:
                raise ValueError('FORGED_PROOF_REASON')
            certified, states = _certify(task, list(result.actions) if result.plan_verified else None,
                                        result.status, time.monotonic() + MAX_TIME_MS / 1000)
            receipt.reachable_states_checked = states
            if not certified:
                raise ValueError('INVALID_COMPLETENESS_CLAIM')
            receipt.optimality_verified = True
        elif result.status == p.UNKNOWN:
            raise ValueError('INCONCLUSIVE_NO_EVIDENCE')
        elif result.status != p.VERIFIED_PLAN:
            raise ValueError('INVALID_STATUS')
        receipt.evidence_valid = True
        receipt.reason_code = 'VERIFIED'
    except ValueError as exc:
        receipt.reason_code = str(exc)
    return frame(receipt)


def make_guided_audit(request_frame, result_frame, *, trusted_artifact_sha256=None):
    request = _decode(request_frame, g.GuidedRequest)
    result = _decode(result_frame, g.GuidedResult)
    receipt = g.GuidedReceipt.FromString(verify_guided_frame(
        request_frame, result_frame, trusted_artifact_sha256=trusted_artifact_sha256))
    return frame(g.GuidedAudit(schema_version=1,
        request_sha256=hashlib.sha256(request_frame).digest(),
        result_sha256=hashlib.sha256(result_frame).digest(),
        guidance_sha256=receipt.guidance_sha256, trace_id=request.planning.trace_id,
        backend_id=result.backend_id, backend_version=result.backend_version,
        status=result.status, wall_ns=result.wall_ns, expanded=result.expanded,
        applied_hints=result.applied_hints, evidence_valid=receipt.evidence_valid,
        optimality_verified=receipt.optimality_verified, reason_code=receipt.reason_code))


def guided_capability_manifest():
    """No learned model is installed merely because a hint format is supported."""
    return (
        dict(id=BACKEND_ID, maturity='experimental_adapter', available=True,
             runtime='precomputed host-pinned advice + local A*',
             learned_model_executed=False),
        dict(id='offline-transition-classifier-v1', maturity='research_source', available=False,
             learned_model_executed=False),
        dict(id='offline-relational-guidance-v1', maturity='research_source', available=False,
             learned_model_executed=False),
        dict(id='offline-generated-heuristic-v1', maturity='research_source', available=False,
             learned_model_executed=False),
    )
