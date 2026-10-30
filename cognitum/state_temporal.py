"""C07/P5 bitemporal *historical* state projection. Offline reference only.

Historical answers are NOT the currently authorized memory state. Effective
(valid_at) and recording/knowledge (known_at) clocks are independent.
Corrections are applied only if recorded by known_at; sources remain immutable
ANSF references and are revalidated by the host during *fenced* publication.
No numerical probability or inferred certainty is ever manufactured.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from google.protobuf.message import DecodeError
from cognitum.proto import state_pb2 as pb
from cognitum.state_revision import (
    MAX_CONFLICTS, StateInvalid, StateLedger,
    _id, _view, canonical_event,
)


def canonical_as_of_query(raw: bytes) -> pb.AsOfQuery:
    if not raw or len(raw) > 512:
        raise StateInvalid('invalid historical query size')
    try:
        query = pb.AsOfQuery.FromString(raw)
    except DecodeError as exc:
        raise StateInvalid('invalid historical protobuf query') from exc
    clean = pb.AsOfQuery()
    clean.CopyFrom(query)
    clean.DiscardUnknownFields()
    if (query.SerializeToString(deterministic=True) != raw or
        clean.SerializeToString(deterministic=True) != raw):
        raise StateInvalid('noncanonical historical query')
    if query.schema_version != 1 or not _id(query.scope_id):
        raise StateInvalid('historical query identity mismatch')
    if query.valid_at_ms <= 0 or query.known_at_ms <= 0:
        raise StateInvalid('historical query requires two positive timestamps')
    return query


def _conflicts(claims: Iterable[pb.ClaimView], report: pb.HistoricalProjection) -> None:
    active = [v for v in claims if v.status in (pb.ACTIVE, pb.DISPUTED)]
    for index, a in enumerate(active):
        for b in active[index + 1:]:
            if ((a.subject_id, a.predicate) == (b.subject_id, b.predicate) and
                (a.value_kind, a.value_text) != (b.value_kind, b.value_text)):
                if len(report.conflicts) >= MAX_CONFLICTS:
                    raise StateInvalid('historical conflict budget exceeded')
                report.conflicts.add(first_claim_id=a.claim_id, second_claim_id=b.claim_id,
                                     predicate=a.predicate, subject_id=a.subject_id)


def _claim_at(events: list[pb.StateEvent], valid_at_ms: int,
              include_inactive: bool) -> pb.ClaimView | None:
    """Select a value segment as known at the query's recording cutoff.

    ASSERT/SUPERSEDE create segments; corrections shift that segment's start
    and optionally tighten/replace its bound. Markers change status only from
    their own effective time. The most recently committed eligible value
    segment wins within a single claim ID; *different* claims retain conflicts.
    """
    segments: list[dict] = []
    for event in events:
        if event.action in (pb.ASSERT, pb.SUPERSEDE):
            segments.append({'start': event.effective_at_ms,
                             'until': event.valid_until_ms,
                             'value': event, 'amendments': [],
                             'revision': event.expected_revision + 1})
        else:
            if not segments:  # already validated by canonical reducer replay
                raise StateInvalid('orphan historical transition')
            segment = segments[-1]
            if event.action == pb.TEMPORAL_CORRECT:
                segment['start'] = event.effective_at_ms
                segment['until'] = event.valid_until_ms or segment['until']
            segment['amendments'].append(event)
    eligible = [s for s in segments if s['start'] <= valid_at_ms]
    if not eligible:
        return None
    # A later assertion is a replacement, including retroactive corrections.
    segment = eligible[-1]
    base = segment['value']
    view = _view(base, base.expected_revision + 1, pb.ACTIVE)
    view.effective_at_ms = segment['start']
    view.valid_until_ms = segment['until']
    status = pb.ACTIVE
    for event in segment['amendments']:
        if event.action == pb.TEMPORAL_CORRECT:
            # Retroactive correction of a *value interval*; it is applicable
            # from the corrected start once the correction was recorded.
            view.latest_event_id = event.event_id
            view.revision = event.expected_revision + 1
            view.origin = event.origin
            view.source.CopyFrom(event.source)
        elif event.effective_at_ms <= valid_at_ms:
            view.revision = event.expected_revision + 1
            view.latest_event_id = event.event_id
            if event.action == pb.CHALLENGE:
                status = pb.DISPUTED
            elif event.action == pb.CONFIRM:
                status = pb.ACTIVE
                rank = {pb.MODEL_HYPOTHESIS: 0, pb.IMPORT_OBSERVED: 1,
                        pb.HOST_OBSERVED: 2, pb.USER_VERIFIED: 3}
                if rank[event.origin] >= rank[view.origin]:
                    view.origin = event.origin
                    view.source.CopyFrom(event.source)
            elif event.action == pb.RETRACT:
                status = pb.RETRACTED
            elif event.action == pb.EXPIRE:
                status = pb.EXPIRED
    if segment['until'] and valid_at_ms >= segment['until']:
        status = pb.EXPIRED if status in (pb.ACTIVE, pb.DISPUTED) else status
    if status in (pb.RETRACTED, pb.EXPIRED) and not include_inactive:
        return None
    view.status = status
    return view


def project_as_of(ledger: StateLedger, query: pb.AsOfQuery) -> pb.HistoricalProjection:
    """Diagnostic-only historical projection; no host-source authentication.

    For host-held disclosure use StateLedger.publish_host_as_of / journal's
    equivalent; this function alone MUST NOT be exposed to workers/models.
    """
    raw = query.SerializeToString(deterministic=True)
    checked = canonical_as_of_query(raw)
    with ledger._lock:
        ledger._reject_callback_mutation()
        if ledger._require_host:
            raise StateInvalid('host evidence recheck required')
        return _project_locked(ledger, checked)


def _project_locked(ledger: StateLedger, query: pb.AsOfQuery) -> pb.HistoricalProjection:
    if query.scope_id != ledger.scope_id:
        raise StateInvalid('historical scope mismatch')
    grouped: dict[str, list[pb.StateEvent]] = defaultdict(list)
    for frame in ledger._history:
        event = canonical_event(frame)
        if event.recorded_at_ms <= query.known_at_ms:
            grouped[event.claim_id].append(event)
    result = pb.HistoricalProjection(
        schema_version=1, scope_id=ledger.scope_id,
        valid_at_ms=query.valid_at_ms, known_at_ms=query.known_at_ms,
        historical_only=True,
    )
    selected = []
    for claim_id in sorted(grouped):
        view = _claim_at(grouped[claim_id], query.valid_at_ms, query.include_inactive)
        if view is not None:
            result.claims.add().CopyFrom(view)
            selected.append(view)
    _conflicts(selected, result)
    return result
