"""C07: deterministic, effect-free claim revision for Lu-owned event streams.

The host is responsible for durable atomic writes, identity, access grants and
idempotency enforcement. This reducer independently validates replay semantics.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Iterable


class StateError(ValueError):
    pass


class Action(str, Enum):
    ASSERT = "ASSERT"
    CONFIRM = "CONFIRM"
    CHALLENGE = "CHALLENGE"
    SUPERSEDE = "SUPERSEDE"
    RETRACT = "RETRACT"
    EXPIRE = "EXPIRE"


class Origin(str, Enum):
    USER_DECISION = "USER_DECISION"
    IMPORTED_CLAIM = "IMPORTED_CLAIM"
    MODEL_HYPOTHESIS = "MODEL_HYPOTHESIS"


@dataclass(frozen=True)
class StateEvent:
    event_id: str
    entity: str
    predicate: str
    typed_value: str | int | bool
    origin: Origin
    actor_authority: str
    expected_revision: int
    effective_time: datetime
    recorded_time: datetime
    action: Action
    source_id: str

    def __post_init__(self) -> None:
        if not all((self.event_id, self.entity, self.predicate, self.actor_authority, self.source_id)):
            raise StateError("missing event identity, authority or source")
        if not isinstance(self.origin, Origin) or not isinstance(self.action, Action):
            raise StateError("unsupported typed origin or action")
        if type(self.typed_value) not in (str, int, bool):
            raise StateError("typed value must be exact string, integer or boolean")
        if type(self.typed_value) is str and len(self.typed_value) > 4096:
            raise StateError("typed value exceeds bound")
        if type(self.typed_value) is int and not -(2 ** 63) <= self.typed_value < 2 ** 63:
            raise StateError("integer outside signed 64-bit range")
        if any(len(s) > 256 for s in (
            self.event_id, self.entity, self.predicate, self.actor_authority, self.source_id,
        )):
            raise StateError("oversized event identity")
        if self.expected_revision < 0:
            raise StateError("negative revision")
        if self.effective_time.tzinfo is None or self.recorded_time.tzinfo is None:
            raise StateError("timestamps must be timezone-aware")
        if self.action in (Action.ASSERT, Action.SUPERSEDE) and self.typed_value == "":
            raise StateError("assertions require a typed value")


@dataclass(frozen=True)
class BeliefRecord:
    entity: str
    predicate: str
    typed_value: str | int | bool | None
    origin: Origin | None
    status: str
    revision: int
    source_refs: tuple[str, ...]
    conflict_refs: tuple[str, ...]
    last_event_id: str | None


@dataclass(frozen=True)
class StateSnapshot:
    claims: tuple[BeliefRecord, ...]
    event_count: int


def replay(events: Iterable[StateEvent]) -> StateSnapshot:
    """Replay already-authorized canonical host events in durable append order.

    A repeat event ID with identical content is idempotent; conflicting reuse
    fails closed. Each (entity, predicate) uses optimistic expected_revision.
    CHALLENGE never silently changes an asserted value or provenance.
    """
    current: dict[tuple[str, str], BeliefRecord] = {}
    seen: dict[str, StateEvent] = {}
    for count, event in enumerate(events):
        if count >= 100_000:
            raise StateError("event history too large")
        if not isinstance(event, StateEvent):
            raise StateError("invalid event")
        old_event = seen.get(event.event_id)
        if old_event is not None:
            if old_event != event:
                raise StateError("event ID reused with different payload")
            continue
        key = (event.entity, event.predicate)
        old = current.get(key)
        revision = old.revision if old else 0
        if event.expected_revision != revision:
            raise StateError("stale expected revision")
        if event.action != Action.ASSERT and old is None:
            raise StateError("cannot revise absent claim")
        if event.action == Action.ASSERT and old and old.status not in ("RETRACTED", "EXPIRED"):
            raise StateError("assert requires absent or inactive claim")
        if event.action in (Action.SUPERSEDE, Action.CONFIRM, Action.CHALLENGE) and old and old.status in ("RETRACTED", "EXPIRED"):
            raise StateError("cannot revise inactive claim")
        if event.action in (Action.RETRACT, Action.EXPIRE) and old and old.status in ("RETRACTED", "EXPIRED"):
            raise StateError("already inactive")
        if event.action == Action.ASSERT:
            value, origin, status = event.typed_value, event.origin, "ACTIVE"
            sources, conflicts = (event.source_id,), ()
        else:
            assert old is not None
            value = event.typed_value if event.action == Action.SUPERSEDE else old.typed_value
            origin = event.origin if event.action == Action.SUPERSEDE else old.origin
            status = {
                Action.SUPERSEDE: "ACTIVE",
                Action.CONFIRM: "ACTIVE",
                Action.CHALLENGE: "CHALLENGED",
                Action.RETRACT: "RETRACTED",
                Action.EXPIRE: "EXPIRED",
            }[event.action]
            sources = tuple(dict.fromkeys((*old.source_refs, event.source_id)))
            conflicts = tuple(dict.fromkeys((*old.conflict_refs, event.source_id))) if event.action == Action.CHALLENGE else old.conflict_refs
        current[key] = BeliefRecord(
            event.entity, event.predicate, value, origin, status, revision + 1,
            sources, conflicts, event.event_id
        )
        seen[event.event_id] = event
    return StateSnapshot(tuple(current[k] for k in sorted(current)), len(seen))
