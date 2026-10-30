"""C07/P9 host-fenced contextual intent proposals (no canonical mutation).

Input data and selected_claim_id are selectors, never authority. Only a held
Lu-host lease can bind a persisted turn to a current, source-verified claim.
Even a successful ContextResolution has no write powers or StateEvent fields.
The native Lu host is NOT implemented in this Python reference.
"""
from __future__ import annotations

import re
from typing import Callable, Protocol, TypeVar
from google.protobuf.message import DecodeError

from cognitum.proto import interpretation_pb2 as pb
from cognitum.state_language import (InterpretationInvalid, interpret, validate_turn)
from cognitum.state_host_gate import SourceUnavailable, require_host_pass

MAX_FRAME = 24 * 1024
MAX_ANCHORS = 16
ID = re.compile(r'[A-Za-z0-9_.-]{1,128}\Z')
ENTRY = re.compile(r'[1-9][0-9]{0,19}\Z')
SHA = re.compile(r'[0-9a-f]{64}\Z')
T = TypeVar('T')

class ContextInvalid(ValueError):
    """Malformed, stale-shaped, or unbounded context request."""


class HostContextLease(Protocol):
    """Implemented only by Lu's authenticated, held read/selection authority.

    Each verdict must be an actual bool True. verify_turn compares exact
    canonical text and persisted role, not merely a user-supplied role label.
    verify_anchor checks ownership, present revision head, and undeleted ANSF
    source hash. bind_target attests an unambiguous relation to the turn using
    host-owned conversation state or an authenticated user UI selection.
    The candidate selector alone MUST NOT satisfy bind_target.
    """
    def ensure_active(self) -> bool: ...
    def verify_turn(self, turn: pb.ConversationTurn) -> bool: ...
    def verify_anchor(self, scope_id: str, anchor: pb.ContextAnchor) -> bool: ...
    def bind_target(self, turn: pb.ConversationTurn, anchor: pb.ContextAnchor) -> bool: ...


def _checked(frame: bytes, cls):
    if not frame or len(frame) > MAX_FRAME:
        raise ContextInvalid('invalid context frame length')
    try:
        value = cls.FromString(frame)
    except DecodeError as exc:
        raise ContextInvalid('invalid context protobuf') from exc
    known = cls()
    known.CopyFrom(value)
    known.DiscardUnknownFields()
    if (value.SerializeToString(deterministic=True) != frame or
            known.SerializeToString(deterministic=True) != frame):
        raise ContextInvalid('noncanonical/unknown context fields')
    return value


def decode_window(raw: bytes) -> pb.ContextWindow:
    window = _checked(raw, pb.ContextWindow)
    if window.schema_version != 1 or not window.HasField('turn'):
        raise ContextInvalid('missing context version or turn')
    try:
        # A structured input cannot smuggle a noncanonical nested turn.
        validate_turn(window.turn)
    except InterpretationInvalid as exc:
        raise ContextInvalid('invalid canonical turn') from exc
    if window.turn.prior_decision or window.turn.subject_hint:
        raise ContextInvalid('client supplied decision/hint is not verified context')
    if len(window.anchors) > MAX_ANCHORS:
        raise ContextInvalid('too many anchors')
    seen: set[str] = set()
    for a in window.anchors:
        if (a.scope_id != window.turn.scope_id or
            not all(ID.fullmatch(x) for x in
                    (a.scope_id,a.claim_id,a.subject_id,a.predicate,
                     a.latest_event_id,a.source_session_id,a.source_snapshot_id)) or
            not ENTRY.fullmatch(a.source_revision_entry_id) or
            not SHA.fullmatch(a.source_sha256) or
            not a.active or a.revision == 0 or
            not a.value_text.strip() or '\0' in a.value_text or
            len(a.value_text.encode('utf-8')) > 2048):
            raise ContextInvalid('invalid, inactive, or foreign context anchor')
        if a.claim_id in seen:
            raise ContextInvalid('duplicate claim selector')
        seen.add(a.claim_id)
    if window.selected_claim_id and (
        not ID.fullmatch(window.selected_claim_id) or
        window.selected_claim_id not in seen):
        raise ContextInvalid('unknown or malformed target selector')
    return window


def _abstain(reason: str) -> pb.InterpretationProposal:
    return pb.InterpretationProposal(
        schema_version=1, label=pb.ABSTAIN_UNRESOLVED,
        reason_code=reason, requires_host_review=True,
        may_write_state_directly=False)


def resolve_host_fenced(window_bytes: bytes, lease: HostContextLease,
                        publish: Callable[[bytes], T]) -> T:
    """Verify, resolve and disclose inside the same host-held read lease.

    No context binding, including a caller-selected claim ID, may authorize a
    future StateEvent. On every admission, Lu must re-authenticate mutation
    authority and source/current revision under its own separate write fence.
    """
    window = decode_window(window_bytes)
    require_host_pass(lease.ensure_active)
    turn = window.turn
    require_host_pass(lease.verify_turn, turn)
    for anchor in window.anchors:
        require_host_pass(lease.verify_anchor, turn.scope_id, anchor)
    # Defensive check in case a test host callback mutated an input message.
    if window.SerializeToString(deterministic=True) != window_bytes:
        raise ContextInvalid('host modified context request')

    target = next((a for a in window.anchors if a.claim_id == window.selected_claim_id), None)
    prior = ''
    if target is not None:
        # An untrusted selector is never enough to bind a revision.
        require_host_pass(lease.bind_target, turn, target)
        if window.SerializeToString(deterministic=True) != window_bytes:
            raise ContextInvalid('host modified target binding')
        prior = target.value_text
    interpreted = pb.ConversationTurn()
    interpreted.CopyFrom(turn)
    interpreted.prior_decision = prior
    proposal = interpret(interpreted)
    action_with_prior = (
        pb.CORRECTION_CANDIDATE, pb.CHANGE_OF_MIND_CANDIDATE,
        pb.RETRACTION_CANDIDATE)
    linked = target is not None and proposal.label in action_with_prior
    if target is None and proposal.label == pb.ABSTAIN_UNRESOLVED:
        # Avoid claiming knowledge about why an unbound reference failed.
        proposal = _abstain('UNRESOLVED_OR_MISSING_HOST_TARGET')
    if proposal.label == pb.DECISION_CANDIDATE and target is not None:
        # Explicit new decisions are NOT silently treated as supersessions.
        proposal.reason_code = 'DECISION_REQUIRES_HOST_CLASSIFICATION'
    result = pb.ContextResolution(
        schema_version=1, proposal=proposal,
        target_claim_id=target.claim_id if linked else '',
        target_revision=target.revision if linked else 0,
        target_latest_event_id=target.latest_event_id if linked else '',
        reason_code='VERIFIED_TARGET_PROPOSAL' if linked else 'NO_LINKED_MUTATION',
        requires_host_review=True, may_write_state_directly=False)
    require_host_pass(lease.ensure_active)
    return publish(result.SerializeToString(deterministic=True))
