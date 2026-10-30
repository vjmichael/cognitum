"""C15 T2 P2P: read-only structural ↔ C07 event reconciliation.

The supplied frames are NOT authenticated. Only Lu's trusted host can create,
hold and enforce the source/event/binding lease. A Python fake lease is useful
for tests, not a production security boundary. Neither this code nor its output
writes an ANSF/C07 journal, authenticates evidence, or grants tool authority.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Callable, Protocol, TypeVar

from cognitum.proto import spatial_structural_c07_bridge_pb2 as pb
from cognitum.proto import state_pb2 as state
from cognitum import spatial_structural_reconciliation as structural
from cognitum import spatial_ontology_subset as ontology
from cognitum.state_host_gate import HostStateLease, require_host_pass
from cognitum.state_revision import (
    StateLedger, StateInvalid, StateConflict, canonical_event,
)

T = TypeVar('T')
MAX_FRAME_COUNT = 512
MAX_REQUEST_BYTES = 1_400_000
PREFIX = 'spatial.'


class T2C07Rejected(ValueError):
    """Invalid or mismatched structural/C07 evidence. No partial disclosure."""


class HostT2C07Lease(HostStateLease, Protocol):
    def bind_structural_event(self, scope_id: str, t2_event, c07_event: state.StateEvent) -> bool:
        """Host verifies source ownership and exact intent, not just caller IDs."""


def _digest(msg):
    return sha256(msg.SerializeToString(deterministic=True)).digest()


def _source_digest(source):
    return _digest(source)


def _claim_id(event):
    op = event.WhichOneof('change')
    return (event.retract.claim_id if op == 'retract' else
            event.add_type.claim_id if op == 'add_type' else event.add_edge.claim_id)


def _payload(event):
    op = event.WhichOneof('change')
    return (event.add_type.claim if op == 'add_type' else event.add_edge.edge)


def _preflight(req):
    if not (isinstance(req, pb.T2C07BridgeRequest) and ontology._known(req) and
            req.schema_version == 1 and req.research_only and not req.grants_authority and
            req.HasField('structural_request') and req.ByteSize() <= MAX_REQUEST_BYTES and
            1 <= len(req.c07_event_frames) <= MAX_FRAME_COUNT):
        raise T2C07Rejected('INVALID_P2P_REQUEST')
    try:
        candidates, grouped = structural._preflight(req.structural_request)
    except structural.ReconciliationRejected as exc:
        raise T2C07Rejected('INVALID_STRUCTURAL_REQUEST') from exc
    event_map = {}
    claim_owners = {}
    for candidate, sequence in grouped.items():
        for event in sequence:
            cid = _claim_id(event)
            if len(PREFIX + cid) > 128:
                raise T2C07Rejected('CLAIM_IDENTIFIER_TOO_LONG_FOR_C07')
            if event.WhichOneof('change') != 'retract':
                # C07 has a scope-wide claim ID space; P2O IDs were candidate-local.
                if cid in claim_owners:
                    raise T2C07Rejected('C07_GLOBAL_CLAIM_ID_COLLISION')
                claim_owners[cid] = candidate
            elif claim_owners.get(cid) != candidate:
                raise T2C07Rejected('P2O_RETRACTION_WITHOUT_ADD')
            event_map[event.event_id] = event
    # P2O event list may interleave candidates; _preflight preserves per-candidate order.
    return event_map, claim_owners


def publish_host_fenced(req: pb.T2C07BridgeRequest,
                        lease: HostT2C07Lease,
                        publish: Callable[[bytes], T]) -> T:
    """Produce C07-linked P2O audit only inside a host-held read lease.

    The host *must* hold the external lease until the synchronous publish returns,
    and synchronize source deletion/revocation with publication. This callback
    interface itself is not authority, and is not callable by models/plugins.
    """
    event_map, owners = _preflight(req)
    frozen = req.SerializeToString(deterministic=True)
    structural_request = req.structural_request
    scope = structural_request.conversation_id
    require_host_pass(lease.ensure_active)
    ledger = StateLedger(scope)
    linked = {}
    seen_p2o = set()
    seen_c07_ids = set()
    per_candidate_seq = {}
    event_annotations = []
    for frame in req.c07_event_frames:
        try:
            event = canonical_event(frame)
        except StateInvalid as exc:
            raise T2C07Rejected('INVALID_CANONICAL_C07_EVENT') from exc
        if event.scope_id != scope or event.event_id in seen_c07_ids:
            raise T2C07Rejected('C07_SCOPE_OR_DUPLICATE_EVENT')
        seen_c07_ids.add(event.event_id)
        if event.claim_id not in owners:
            raise T2C07Rejected('UNRELATED_C07_CLAIM')
        owner = owners[event.claim_id]
        if (event.subject_id != owner or event.predicate != PREFIX + event.claim_id
                or event.value_kind != state.TEXT):
            raise T2C07Rejected('C07_CLAIM_IDENTITY_MISMATCH')
        matched = event_map.get(event.event_id)
        if matched is not None:
            if matched.candidate_id != owner or _claim_id(matched) != event.claim_id:
                raise T2C07Rejected('EVENT_BINDING_MISMATCH')
            if matched.sequence != per_candidate_seq.get(owner, 0) + 1:
                raise T2C07Rejected('STRUCTURAL_REVISION_ORDER_MISMATCH')
            per_candidate_seq[owner] = matched.sequence
            op = matched.WhichOneof('change')
            if op == 'retract':
                if event.action != state.RETRACT or event.claim_id not in linked:
                    raise T2C07Rejected('RETRACTION_BINDING_MISMATCH')
                value = linked[event.claim_id][0]
            else:
                if event.action != state.ASSERT or event.claim_id in linked:
                    raise T2C07Rejected('ADDITION_BINDING_MISMATCH')
                value = _digest(_payload(matched)).hex()
            if event.value_text != value:
                raise T2C07Rejected('STRUCTURAL_CONTENT_HASH_MISMATCH')
            # An explicit trusted-host binding must cover P2O source and C07 source.
            require_host_pass(lease.bind_structural_event, scope, matched, event)
            if matched.SerializeToString(deterministic=True) != (
                    event_map[matched.event_id].SerializeToString(deterministic=True)):
                raise T2C07Rejected('MUTATED_STRUCTURAL_EVENT')
            linked[event.claim_id] = (value, owner, op)
            seen_p2o.add(event.event_id)
        else:
            if event.claim_id not in linked or event.action not in (
                    state.CHALLENGE, state.CONFIRM, state.EXPIRE, state.TEMPORAL_CORRECT):
                raise T2C07Rejected('UNMAPPED_C07_MUTATION')
            if event.value_text != linked[event.claim_id][0]:
                raise T2C07Rejected('UNMAPPED_C07_CONTENT_CHANGE')
        require_host_pass(lease.admit_event, scope, event)
        require_host_pass(lease.verify_source, scope, event.source, False)
        if event.SerializeToString(deterministic=True) != frame:
            raise T2C07Rejected('MUTATED_C07_EVENT')
        try:
            ledger.apply(event)
        except (StateInvalid, StateConflict) as exc:
            raise T2C07Rejected('INVALID_C07_STATE_TRANSITION') from exc
        if matched is not None:
            view = next((c for c in ledger.projection().claims if c.claim_id == event.claim_id), None)
            if view is None:
                raise T2C07Rejected('C07_CLAIM_MISSING')
            event_annotations.append((matched, event, state.ClaimView.FromString(
                view.SerializeToString(deterministic=True))))
    if seen_p2o != set(event_map):
        raise T2C07Rejected('MISSING_P2O_C07_EVENT_BINDING')
    # Verify each CURRENT source under the SAME held lease, not only history.
    projection = ledger.projection()
    for claim in projection.claims:
        if claim.status in (state.ACTIVE, state.DISPUTED):
            require_host_pass(lease.verify_source, scope, claim.source, True)
    if req.SerializeToString(deterministic=True) != frozen:
        raise T2C07Rejected('MUTATED_BRIDGE_REQUEST')
    try:
        sr = structural.reconcile(structural_request)
    except structural.ReconciliationRejected as exc:
        raise T2C07Rejected('INVALID_P2O_REPLAY') from exc
    out = pb.T2C07BridgeResult(
        schema_version=1, conversation_id=scope,
        request_sha256=sha256(frozen).digest(),
        c07_projection_sha256=_digest(projection), research_only=True)
    out.structural_result.CopyFrom(sr)
    for st, c07, view in event_annotations:
        out.events.add(event_id=st.event_id, candidate_id=st.candidate_id,
                       claim_id=c07.claim_id, c07_action=c07.action,
                       c07_origin=view.origin, c07_uncertainty=view.uncertainty_kind,
                       c07_status_after=view.status, c07_revision_after=view.revision,
                       c07_source_sha256=_source_digest(c07.source))
    active_by_candidate = {c.candidate_id: set(c.active_claim_ids) for c in sr.candidates}
    for c in sorted(projection.claims, key=lambda x: x.claim_id):
        structural_status = ('ACTIVE' if c.claim_id in active_by_candidate[owners[c.claim_id]]
                             else 'RETRACTED')
        review = (c.status != state.ACTIVE if structural_status == 'ACTIVE'
                  else c.status != state.RETRACTED)
        review = review or c.origin in (state.MODEL_HYPOTHESIS, state.IMPORT_OBSERVED) or (
            c.uncertainty_kind != state.UNCERTAINTY_UNSPECIFIED)
        out.claims.add(candidate_id=owners[c.claim_id], claim_id=c.claim_id,
                       structural_status=structural_status, c07_status=c.status,
                       c07_origin=c.origin, c07_uncertainty=c.uncertainty_kind,
                       c07_uncertainty_note=c.uncertainty_note,
                       c07_revision=c.revision, latest_c07_event_id=c.latest_event_id,
                       requires_review=review, c07_source_sha256=_source_digest(c.source))
        out.requires_review |= review
    out.warnings.extend([
        'HOST_VERIFICATION_IS_EXTERNAL_NEVER_INFERRED_FROM_C07_OR_P2O_LABELS',
        'C07_CLAIM_STATUS_DOES_NOT_PROMOTE_STRUCTURAL_HYPOTHESES_TO_FACTS',
        'DISPUTED_OR_EXPIRED_EVIDENCE_REQUIRES_REVIEW_NO_SILENT_RETRACTION',
        'NO_CROSS_CONVERSATION_EVIDENCE_IMPORT_IN_P2P_V1',
        'NO_CANONICAL_STATE_WRITES_NO_AUTOMATIC_HYPOTHESIS_WINNER',
        'SOURCE_SHA256_RECEIPTS_ARE_NOT_SIGNATURES',
    ])
    require_host_pass(lease.ensure_active)
    if req.SerializeToString(deterministic=True) != frozen:
        raise T2C07Rejected('MUTATED_BRIDGE_REQUEST')
    return publish(out.SerializeToString(deterministic=True))
