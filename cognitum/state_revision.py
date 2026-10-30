"""C07/P1 deterministic, offline event-sourced belief/goal *projection*.

The trusted Lu host MUST authenticate each canonical event, verify its C06
source reference, enforce writer permissions, persist an append-only event log,
and own erasure/retention. Merely constructing StateEvent/HostOrigin is NEVER
an authority. No model/tool-facing mutation route or canonical state DB here.

Replays are pure, bounded and fail before partial batch publication. A claim's
original source is kept in the immutable event history. Conflicting claims are
visible together; no inferred winner, truth or confidence is fabricated.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from itertools import islice
import re
import threading
from typing import Iterable, Callable, TypeVar

from cognitum.state_host_gate import HostStateLease, require_host_pass

from google.protobuf.message import DecodeError
from cognitum.proto import state_pb2 as pb

T = TypeVar("T")
MAX_EVENTS = 10000
MAX_CLAIMS = 1000
MAX_CONFLICTS = 4096
MAX_EVENT_BYTES = 8192
MAX_TEXT_BYTES = 2048
MAX_UNCERTAINTY_NOTE_BYTES = 512
ID = re.compile(r"[A-Za-z0-9_.-]{1,128}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
NUM = re.compile(r"[1-9][0-9]*\Z")

class StateConflict(ValueError):
    """Stale revision, contradictory event identity, or invalid transition."""

class StateInvalid(ValueError):
    """Malformed input, unauthorized-type promotion, or unbounded event."""


def canonical_event(frame: bytes) -> pb.StateEvent:
    if not frame or len(frame) > MAX_EVENT_BYTES:
        raise StateInvalid('invalid event frame length')
    try:
        value = pb.StateEvent.FromString(frame)
    except DecodeError as exc:
        raise StateInvalid('bad protobuf') from exc
    known_only = pb.StateEvent()
    known_only.CopyFrom(value)
    known_only.DiscardUnknownFields()
    if (value.SerializeToString(deterministic=True) != frame
        or known_only.SerializeToString(deterministic=True) != frame):
        raise StateInvalid('noncanonical or unknown protobuf fields')
    return value


def _id(text: str) -> bool:
    return bool(ID.fullmatch(text))


def _value(kind: int, raw: str) -> str:
    if kind == pb.TEXT:
        if not raw.strip() or len(raw.encode('utf-8')) > MAX_TEXT_BYTES or '\0' in raw:
            raise StateInvalid('invalid text value')
        return raw
    if kind == pb.INTEGER:
        if len(raw) > 128:
            raise StateInvalid('integer too long')
        try:
            canonical = str(int(raw))
        except (ValueError, OverflowError) as exc:
            raise StateInvalid('integer expected') from exc
        if canonical != raw:
            raise StateInvalid('noncanonical integer')
        return canonical
    if kind == pb.DECIMAL:
        if len(raw) > 128 or not re.fullmatch(r'-?(0|[1-9][0-9]*)(\.[0-9]+)?',raw):
            raise StateInvalid('noncanonical decimal')
        try:
            if not Decimal(raw).is_finite():
                raise StateInvalid('nonfinite decimal')
        except InvalidOperation as exc:
            raise StateInvalid('bad decimal') from exc
        return raw
    if kind == pb.BOOLEAN:
        if raw not in ('true','false'):
            raise StateInvalid('boolean must be true/false')
        return raw
    raise StateInvalid('unknown value kind')


def _validate(evt: pb.StateEvent, scope: str) -> None:
    if evt.schema_version != 1 or evt.scope_id != scope:
        raise StateInvalid('schema or scope mismatch')
    if not all(map(_id,(evt.event_id,evt.scope_id,evt.claim_id,evt.subject_id,evt.predicate))):
        raise StateInvalid('invalid identity')
    if evt.origin not in (pb.USER_VERIFIED,pb.HOST_OBSERVED,pb.IMPORT_OBSERVED,pb.MODEL_HYPOTHESIS):
        raise StateInvalid('unknown provenance')
    if evt.action not in (pb.ASSERT,pb.CONFIRM,pb.CHALLENGE,pb.SUPERSEDE,pb.RETRACT,pb.EXPIRE,pb.TEMPORAL_CORRECT):
        raise StateInvalid('unknown action')
    _value(evt.value_kind,evt.value_text)
    if evt.valid_until_ms < 0 or (evt.valid_until_ms != 0 and
        evt.valid_until_ms <= evt.effective_at_ms):
        raise StateInvalid('invalid exclusive validity bound')
    if evt.uncertainty_kind not in (
        pb.UNCERTAINTY_UNSPECIFIED, pb.EXPLICITLY_UNCERTAIN,
        pb.CONDITIONAL, pb.OPEN_QUESTION):
        raise StateInvalid('unknown uncertainty qualifier')
    if (len(evt.uncertainty_note.encode('utf-8')) > MAX_UNCERTAINTY_NOTE_BYTES
        or '\0' in evt.uncertainty_note):
        raise StateInvalid('invalid qualifier note')
    if (evt.uncertainty_kind == pb.UNCERTAINTY_UNSPECIFIED) != (not evt.uncertainty_note.strip()):
        raise StateInvalid('explicit uncertainty requires a note; no invented confidence')
    if evt.action not in (pb.ASSERT,pb.SUPERSEDE):
        if evt.uncertainty_kind != pb.UNCERTAINTY_UNSPECIFIED or evt.uncertainty_note:
            raise StateInvalid('only value assertions can introduce uncertainty')
        if evt.action != pb.TEMPORAL_CORRECT and evt.valid_until_ms:
            raise StateInvalid('non-value event cannot change validity bound')
    if evt.action == pb.TEMPORAL_CORRECT:
        if not _id(evt.corrects_event_id):
            raise StateInvalid('temporal correction must identify previous event')
    elif evt.corrects_event_id:
        raise StateInvalid('unexpected temporal predecessor')
    if evt.recorded_at_ms <= 0 or evt.effective_at_ms <= 0:
        raise StateInvalid('missing event time')
    if not evt.HasField('source'):
        raise StateInvalid('missing source provenance')
    source = evt.source
    if (not _id(source.session_id) or not NUM.fullmatch(source.root_entry_id)
        or not NUM.fullmatch(source.revision_entry_id)
        or not SHA.fullmatch(source.content_sha256)
        or not _id(source.snapshot_id)):
        raise StateInvalid('invalid canonical source reference')
    if len(evt.SerializeToString(deterministic=True)) > MAX_EVENT_BYTES:
        raise StateInvalid('oversized event')


def _view(evt: pb.StateEvent, revision: int, status: int) -> pb.ClaimView:
    out = pb.ClaimView(
        scope_id=evt.scope_id,claim_id=evt.claim_id,subject_id=evt.subject_id,
        predicate=evt.predicate,value_kind=evt.value_kind,value_text=evt.value_text,
        origin=evt.origin,status=status,revision=revision,latest_event_id=evt.event_id,
        effective_at_ms=evt.effective_at_ms, valid_until_ms=evt.valid_until_ms,
        uncertainty_kind=evt.uncertainty_kind, uncertainty_note=evt.uncertainty_note,
    )
    out.source.CopyFrom(evt.source)
    return out


class StateLedger:
    """Derived revisioned projection; host identity/source validation is EXTERNAL."""
    def __init__(self, scope_id: str, *, require_host: bool = False):
        if not _id(scope_id): raise StateInvalid('invalid scope')
        self.scope_id = scope_id
        self._require_host = require_host
        self._events: dict[str,bytes] = {}
        self._claims: dict[str,pb.ClaimView] = {}
        self._history: list[bytes] = []
        # Serialize CAS, batch commit, and snapshots for concurrent callers.
        self._lock = threading.RLock()
        # Host admission and publication callbacks cannot mutate this ledger.
        self._host_callback_owner: int | None = None

    def _reject_callback_mutation(self) -> None:
        if self._host_callback_owner == threading.get_ident():
            raise StateInvalid('reentrant mutation from host callback')

    def apply(self, event: pb.StateEvent) -> bool:
        with self._lock:
            self._reject_callback_mutation()
            if self._require_host:
                raise StateInvalid('host admission required')
            return self._apply_unlocked(event)

    def _apply_unlocked(self, event: pb.StateEvent) -> bool:
        """Apply a canonical source-verified *host-admitted* event.

        Returns False only for exact duplicate event IDs. A conflicting replay,
        stale expected revision, or unauthorized provenance transition fails.
        """
        _validate(event,self.scope_id)
        raw = event.SerializeToString(deterministic=True)
        # Object-level callers are not exempt from the strict wire gate.
        canonical_event(raw)
        prior_raw = self._events.get(event.event_id)
        if prior_raw is not None:
            if prior_raw != raw: raise StateConflict('event ID reused with different bytes')
            return False
        if len(self._events) >= MAX_EVENTS: raise StateInvalid('event budget exhausted')
        old = self._claims.get(event.claim_id)
        if event.action == pb.ASSERT:
            if old is not None or event.expected_revision != 0:
                raise StateConflict('claim already exists or nonzero initial revision')
            if len(self._claims) >= MAX_CLAIMS: raise StateInvalid('claim budget exhausted')
            newer = _view(event,1,pb.ACTIVE)
        else:
            if old is None or event.expected_revision != old.revision:
                raise StateConflict('missing claim or stale expected revision')
            if old.status in (pb.RETRACTED,pb.EXPIRED):
                raise StateConflict('terminal claim cannot be rewritten')
            if ((event.subject_id,event.predicate) != (old.subject_id,old.predicate)
                or (event.value_kind,event.value_text) != (old.value_kind,old.value_text)
                and event.action != pb.SUPERSEDE):
                raise StateConflict('identity/value mismatch')
            if event.recorded_at_ms < self._recorded_at(old.latest_event_id):
                raise StateConflict('record chronology regressed')
            # Retroactive corrections need a separate, explicit temporal event
            # with host-side review; never silently make them current.
            if (event.action != pb.TEMPORAL_CORRECT
                and event.effective_at_ms < old.effective_at_ms):
                raise StateConflict('effective chronology regressed')
            if event.action == pb.CONFIRM:
                if event.origin not in (pb.USER_VERIFIED,pb.HOST_OBSERVED):
                    raise StateInvalid('unverified claim cannot confirm')
                status=pb.ACTIVE
            elif event.action == pb.CHALLENGE:
                status=pb.DISPUTED
            elif event.action == pb.TEMPORAL_CORRECT:
                if event.corrects_event_id != old.latest_event_id:
                    raise StateConflict('temporal correction predecessor mismatch')
                if (event.value_kind,event.value_text) != (old.value_kind,old.value_text):
                    raise StateConflict('temporal correction cannot change value')
                end = event.valid_until_ms or old.valid_until_ms
                if end and end <= event.effective_at_ms:
                    raise StateConflict('corrected interval is empty')
                if (event.effective_at_ms == old.effective_at_ms and end == old.valid_until_ms):
                    raise StateConflict('temporal correction must change interval')
                if event.origin not in (pb.USER_VERIFIED,pb.HOST_OBSERVED):
                    raise StateInvalid('temporal correction requires verified writer')
                if old.origin == pb.USER_VERIFIED and event.origin != pb.USER_VERIFIED:
                    raise StateInvalid('host cannot demote user-verified temporal provenance')
                status=old.status
            elif event.action == pb.SUPERSEDE:
                # Model/import observations never rewrite human-/host-confirmed
                # claims; they can assert competing, traceable hypotheses.
                if (old.origin in (pb.USER_VERIFIED,pb.HOST_OBSERVED)
                    and event.origin not in (pb.USER_VERIFIED,pb.HOST_OBSERVED)):
                    raise StateInvalid('lower provenance cannot supersede confirmed claim')
                status=pb.ACTIVE
            elif event.action == pb.RETRACT:
                if (old.origin in (pb.USER_VERIFIED,pb.HOST_OBSERVED)
                    and event.origin not in (pb.USER_VERIFIED,pb.HOST_OBSERVED)):
                    raise StateInvalid('lower provenance cannot retract confirmed claim')
                status=pb.RETRACTED
            elif event.action == pb.EXPIRE:
                if event.effective_at_ms < self._effective_at(old.latest_event_id):
                    raise StateConflict('expiry before current effective timestamp')
                if (old.origin in (pb.USER_VERIFIED,pb.HOST_OBSERVED)
                    and event.origin not in (pb.USER_VERIFIED,pb.HOST_OBSERVED)):
                    raise StateInvalid('lower provenance cannot expire confirmed claim')
                status=pb.EXPIRED
            else:
                raise StateInvalid('unsupported action')
            newer = _view(event,old.revision+1,status)
            if event.action not in (pb.ASSERT,pb.SUPERSEDE):
                newer.uncertainty_kind = old.uncertainty_kind
                newer.uncertainty_note = old.uncertainty_note
                if event.action == pb.TEMPORAL_CORRECT:
                    newer.valid_until_ms = event.valid_until_ms or old.valid_until_ms
                else:
                    newer.valid_until_ms = old.valid_until_ms
            if event.action in (pb.CHALLENGE, pb.RETRACT, pb.EXPIRE):
                newer.effective_at_ms=old.effective_at_ms
                # A challenge or terminal marker must not replace provenance
                # of the original value with the marker writer's identity.
                newer.origin=old.origin
                newer.source.CopyFrom(old.source)
            elif event.action == pb.CONFIRM:
                newer.effective_at_ms=old.effective_at_ms
                # Verification may promote an unverified hypothesis, but a
                # lower-ranked observer cannot demote an existing human claim.
                rank={pb.MODEL_HYPOTHESIS:0,pb.IMPORT_OBSERVED:1,
                      pb.HOST_OBSERVED:2,pb.USER_VERIFIED:3}
                if rank[event.origin] < rank[old.origin]:
                    newer.origin=old.origin
                    newer.source.CopyFrom(old.source)
        self._events[event.event_id]=raw
        self._claims[event.claim_id]=newer
        self._history.append(raw)
        return True

    def _recorded_at(self, event_id: str) -> int:
        return pb.StateEvent.FromString(self._events[event_id]).recorded_at_ms

    def _effective_at(self, event_id: str) -> int:
        return pb.StateEvent.FromString(self._events[event_id]).effective_at_ms

    def apply_batch(self, events: Iterable[pb.StateEvent]) -> int:
        """All-or-nothing derived publication, with no partial valid prefix."""
        with self._lock:
            self._reject_callback_mutation()
            if self._require_host:
                raise StateInvalid('host admission required')
            return self._batch_unlocked(events)

    def _batch_unlocked(self, events: Iterable[pb.StateEvent]) -> int:
        pending = list(islice(events,MAX_EVENTS+1))
        if len(pending)>MAX_EVENTS: raise StateInvalid('batch budget exhausted')
        temp = StateLedger(self.scope_id)
        temp._events=self._events.copy()
        temp._claims=self._claims.copy()
        temp._history=self._history.copy()
        count=0
        for event in pending:
            count+=int(temp.apply(event))
        self._events,self._claims,self._history=temp._events,temp._claims,temp._history
        return count

    def apply_host_batch(self, events: Iterable[pb.StateEvent], lease: HostStateLease) -> int:
        """Atomically admit events under a Lu-host-held *mutation* lease.

        The host authenticates the originating action and verifies C06 evidence.
        No model-supplied grant, event field or scope string provides authority.
        Strict True verdicts and one final active-lease check precede commit.
        """
        pending = list(islice(events, MAX_EVENTS + 1))
        if len(pending) > MAX_EVENTS:
            raise StateInvalid('batch budget exhausted')
        with self._lock:
            self._reject_callback_mutation()
            self._host_callback_owner = threading.get_ident()
            try:
                require_host_pass(lease.ensure_active)
                frozen: list[pb.StateEvent] = []
                for event in pending:
                    # Freeze mutable Protobuf objects before trusting host
                    # admission; caller or verifier may otherwise change them.
                    raw = event.SerializeToString(deterministic=True)
                    candidate = canonical_event(raw)
                    _validate(candidate, self.scope_id)
                    require_host_pass(lease.admit_event, self.scope_id, candidate)
                    require_host_pass(lease.verify_source, self.scope_id, candidate.source, True)
                    if candidate.SerializeToString(deterministic=True) != raw:
                        raise StateInvalid('host check mutated event')
                    frozen.append(canonical_event(raw))
                # Work on a disposable projection; never commit a partial batch.
                temp = StateLedger(self.scope_id)
                temp._events = self._events.copy()
                temp._claims = self._claims.copy()
                temp._history = self._history.copy()
                applied = sum(bool(temp._apply_unlocked(e)) for e in frozen)
                require_host_pass(lease.ensure_active)
                self._events, self._claims, self._history = (
                    temp._events, temp._claims, temp._history
                )
                return applied
            finally:
                self._host_callback_owner = None

    def publish_host_fenced(self, lease: HostStateLease, publish: Callable[[bytes], T]) -> T:
        """Publish an entirely verified Protobuf state within Lu's held lease.

        Rechecks *all* event sources for retained, authorized, undeleted
        historical provenance. Active claims additionally need a CURRENT
        canonical revision. A deleted ancestor forces host reconciliation;
        merely superseding an older revision must not destroy history.
        Returning the projection outside this callback bypasses the fence.
        """
        with self._lock:
            self._reject_callback_mutation()
            self._host_callback_owner = threading.get_ident()
            try:
                require_host_pass(lease.ensure_active)
                sources_seen: set[bytes] = set()
                for raw in self._history:
                    event = canonical_event(raw)
                    source_key = event.source.SerializeToString(deterministic=True)
                    if source_key not in sources_seen:
                        require_host_pass(lease.verify_source, self.scope_id, event.source, False)
                        sources_seen.add(source_key)
                projection = self._projection_unlocked()
                for claim in projection.claims:
                    if claim.status in (pb.ACTIVE, pb.DISPUTED):
                        require_host_pass(lease.verify_source, self.scope_id, claim.source, True)
                require_host_pass(lease.ensure_active)
                result = projection.SerializeToString(deterministic=True)
                # Host MUST synchronously deliver while holding its lease.
                return publish(result)
            finally:
                self._host_callback_owner = None

    def publish_host_as_of(self, query: pb.AsOfQuery, lease: HostStateLease,
                           publish: Callable[[bytes], T]) -> T:
        """Deliver historical-only bytes inside a *held* authenticated Lu lease.

        Reverify every retained source, including events outside the requested
        knowledge cutoff: a subsequently deleted source invalidates publication
        until the host reconciles the derived journal. Historical citations do
        not require being the *current* revision; all require retained rights.
        """
        from cognitum.state_temporal import canonical_as_of_query, _project_locked
        checked = canonical_as_of_query(query.SerializeToString(deterministic=True))
        if checked.scope_id != self.scope_id:
            raise StateInvalid('historical scope mismatch')
        with self._lock:
            self._reject_callback_mutation()
            self._host_callback_owner = threading.get_ident()
            try:
                require_host_pass(lease.ensure_active)
                sources: set[bytes] = set()
                for raw in self._history:
                    event = canonical_event(raw)
                    source_raw = event.source.SerializeToString(deterministic=True)
                    if source_raw not in sources:
                        require_host_pass(lease.verify_source, self.scope_id, event.source, False)
                        sources.add(source_raw)
                answer = _project_locked(self, checked)
                require_host_pass(lease.ensure_active)
                return publish(answer.SerializeToString(deterministic=True))
            finally:
                self._host_callback_owner = None

    def history(self) -> tuple[bytes,...]:
        with self._lock:
            return tuple(self._history)

    def projection(self) -> pb.StateProjection:
        """Offline diagnostic only; NOT evidence that any source is still live."""
        with self._lock:
            if self._require_host:
                raise StateInvalid('host evidence recheck required')
            return self._projection_unlocked()

    def _projection_unlocked(self) -> pb.StateProjection:
        result=pb.StateProjection(schema_version=1,scope_id=self.scope_id)
        for claim in sorted(self._claims.values(),key=lambda v:v.claim_id):
            result.claims.add().CopyFrom(claim)
        open_claims=[c for c in result.claims if c.status in (pb.ACTIVE,pb.DISPUTED)]
        for i,a in enumerate(open_claims):
            for b in open_claims[i+1:]:
                if ((a.subject_id,a.predicate)==(b.subject_id,b.predicate)
                    and (a.value_kind,a.value_text)!=(b.value_kind,b.value_text)):
                    if len(result.conflicts) >= MAX_CONFLICTS:
                        raise StateInvalid('conflict projection budget exceeded')
                    result.conflicts.add(first_claim_id=a.claim_id,
                        second_claim_id=b.claim_id,predicate=a.predicate,subject_id=a.subject_id)
        return result

    @classmethod
    def replay(cls,scope_id: str,history: Iterable[bytes]) -> StateLedger:
        state=cls(scope_id)
        state.apply_batch(canonical_event(item) for item in history)
        return state
