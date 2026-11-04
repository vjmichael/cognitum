"""C07 pure reconciliation proposals over canonical Lu ANSF event snapshots.

Cognitum NEVER persists a claim, mints actor authority, or advances a
canonical revision. A Lu host owns append/CAS/idempotency, timestamps,
identity, access grants, deletion and snapshot publication. This component
only validates a host-labeled event, derives a tentative view and returns
a nonauthoritative proposal. Imported and model statements are not truths.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import re

ACTIONS=frozenset(("ASSERT","CONFIRM","CHALLENGE","SUPERSEDE",
                   "RETRACT","EXPIRE","MERGE"))
AUTHORITIES=frozenset(("user_decision","imported_claim","model_hypothesis"))
STATUSES=frozenset(("asserted","confirmed","challenged","superseded",
                    "retracted","expired"))
MAX_EVENTS=2048
MAX_VALUE=1024

@dataclass(frozen=True)
class StateEvent:
    event_id:str
    scope_id:str
    entity:str
    predicate:str
    value_type:str
    value:str
    origin_source_id:str
    actor_authority:str
    expected_revision:int
    effective_ms:int
    recorded_ms:int
    action:str
    replaces_event_id:str=""
    reason:str=""

@dataclass(frozen=True)
class EventSnapshot:
    owner:str
    snapshot_id:str
    owner_revision:int
    scope_id:str
    events:tuple[StateEvent,...]

@dataclass(frozen=True)
class Belief:
    entity:str
    predicate:str
    value_type:str
    value:str
    status:str
    source_event_id:str
    source_revision:int
    authority:str
    effective_ms:int
    conflict_event_ids:tuple[str,...]

@dataclass(frozen=True)
class Proposal:
    status:str
    scope_id:str
    based_on_snapshot_id:str
    expected_owner_revision:int
    event:StateEvent
    current:tuple[Belief,...]
    competing:tuple[Belief,...]
    event_sha256:str
    limitations:tuple[str,...]=(
        "proposal_not_Lu_transaction_or_permission",
        "historical_evidence_and_authority_claimed_by_host",
        "user_decisions_not_overwritten_by_import_or_model",
        "event_history_must_be_committed_by_canonical_ANSF_owner",
    )

def _id(x):
    return type(x) is str and re.fullmatch(r"[A-Za-z0-9_.:-]{1,96}",x) is not None

def _validate_event(e):
    if (type(e) is not StateEvent
            or not all(_id(getattr(e,k)) for k in
                       ("event_id","scope_id","entity","predicate","origin_source_id"))
            or e.actor_authority not in AUTHORITIES or e.action not in ACTIONS
            or e.value_type not in ("string","integer","boolean","json_scalar")
            or type(e.value) is not str or len(e.value)>MAX_VALUE
            or type(e.reason) is not str or len(e.reason)>512
            or type(e.expected_revision) is not int or e.expected_revision<0
            or type(e.effective_ms) is not int or e.effective_ms<0
            or type(e.recorded_ms) is not int or e.recorded_ms<e.effective_ms
            or (e.replaces_event_id!="" and not _id(e.replaces_event_id))):
        raise ValueError("invalid typed claim event")
    if e.action in ("RETRACT","SUPERSEDE","EXPIRE","MERGE","CHALLENGE","CONFIRM") and not e.replaces_event_id:
        raise ValueError("revision action needs exact target event")
    if e.action=="ASSERT" and e.replaces_event_id:
        raise ValueError("initial assertion cannot silently replace a claim")
    if e.value_type=="integer":
        if not re.fullmatch(r"-?(0|[1-9][0-9]{0,17})",e.value):
            raise ValueError("invalid canonical integer")
    elif e.value_type=="boolean" and e.value not in ("true","false"):
        raise ValueError("invalid canonical boolean")
    elif e.value_type=="json_scalar":
        try: obj=json.loads(e.value)
        except (ValueError,TypeError) as exc:raise ValueError("malformed JSON scalar") from exc
        if obj is None or type(obj) not in (str,int,float,bool) or len(e.value)>MAX_VALUE:
            raise ValueError("JSON scalar only; no arbitrary executable data")
    return e

def validate_snapshot(s):
    if (type(s) is not EventSnapshot or s.owner!="Lu_ANSF"
            or not _id(s.snapshot_id) or not _id(s.scope_id)
            or type(s.owner_revision) is not int or s.owner_revision<0
            or type(s.events) is not tuple or len(s.events)>MAX_EVENTS):
        raise ValueError("unsupported canonical Lu event snapshot")
    seen=set()
    for e in s.events:
        _validate_event(e)
        if e.scope_id!=s.scope_id or e.event_id in seen:
            raise ValueError("cross-scope or duplicate canonical event")
        seen.add(e.event_id)
    return s

def _derive(events):
    # Stable, deterministic event-order replay; a challenge is not itself
    # proof that a statement is false. Status records remain retrievable.
    entries={}
    order=[]
    for index,e in enumerate(events):
        _validate_event(e)
        previous=entries.get(e.replaces_event_id) if e.replaces_event_id else None
        if e.action!="ASSERT" and previous is None:
            raise ValueError("unknown revised claim")
        if previous and (previous.entity!=e.entity or previous.predicate!=e.predicate):
            raise ValueError("cross-subject claim revision")
        if e.action in ("SUPERSEDE","RETRACT","EXPIRE","MERGE") and previous:
            entries[e.replaces_event_id]=Belief(
                previous.entity,previous.predicate,previous.value_type,
                previous.value,{"SUPERSEDE":"superseded","RETRACT":"retracted",
                 "EXPIRE":"expired","MERGE":"superseded"}[e.action],
                previous.source_event_id,previous.source_revision,
                previous.authority,previous.effective_ms,previous.conflict_event_ids)
        elif e.action=="CHALLENGE" and previous:
            entries[e.replaces_event_id]=Belief(
                previous.entity,previous.predicate,previous.value_type,
                previous.value,"challenged",previous.source_event_id,
                previous.source_revision,previous.authority,previous.effective_ms,
                tuple(sorted(set(previous.conflict_event_ids+(e.event_id,)))))
        elif e.action=="CONFIRM" and previous:
            entries[e.replaces_event_id]=Belief(
                previous.entity,previous.predicate,previous.value_type,
                previous.value,"confirmed",previous.source_event_id,
                previous.source_revision,previous.authority,previous.effective_ms,
                previous.conflict_event_ids)
        status=("asserted" if e.action in ("ASSERT","SUPERSEDE","MERGE") else
                "confirmed" if e.action=="CONFIRM" else
                "challenged" if e.action=="CHALLENGE" else
                "retracted" if e.action=="RETRACT" else "expired")
        if e.event_id in entries:
            raise ValueError("duplicate event id in revision chain")
        entries[e.event_id]=Belief(e.entity,e.predicate,e.value_type,e.value,
            status,e.event_id,index,e.actor_authority,e.effective_ms,())
        order.append(e.event_id)
    live=tuple(entries[key] for key in order
               if entries[key].status in ("asserted","confirmed","challenged"))
    # Rival active values are presented side-by-side; do not automatically
    # select a model/imported assertion over an explicit user decision.
    return live,tuple(entries[key] for key in order)

def propose(snapshot:EventSnapshot,event:StateEvent,*,host_authorized_scope:str):
    validate_snapshot(snapshot)
    _validate_event(event)
    if (not _id(host_authorized_scope) or host_authorized_scope!=snapshot.scope_id
            or event.scope_id!=host_authorized_scope
            or event.expected_revision!=snapshot.owner_revision
            or any(x.event_id==event.event_id for x in snapshot.events)
            or len(snapshot.events)>=MAX_EVENTS):
        raise ValueError("stale, replayed or cross-scope event")
    target=next((x for x in snapshot.events if x.event_id==event.replaces_event_id),None)
    if (event.replaces_event_id and target is not None
            and (target.entity!=event.entity or target.predicate!=event.predicate)):
        raise ValueError("revised claim changes subject or predicate")
    if (target is not None and event.actor_authority!="user_decision"
            and target.actor_authority=="user_decision"
            and event.action in ("SUPERSEDE","RETRACT","EXPIRE","MERGE","CONFIRM")):
        raise ValueError("imported/model evidence cannot revise user decision authority")
    if (target is not None and event.action in ("CONFIRM","RETRACT","EXPIRE")
            and (event.value_type!=target.value_type or event.value!=target.value)):
        raise ValueError("confirmation/retraction must reference the original typed value")
    live,all_entries=_derive(snapshot.events+(event,))
    current=tuple(x for x in live if x.entity==event.entity and x.predicate==event.predicate)
    conflicting=tuple(x for x in current if x.value!=event.value)
    payload=json.dumps([event.event_id,event.scope_id,event.entity,event.predicate,
                        event.value_type,event.value,event.origin_source_id,
                        event.actor_authority,event.expected_revision,
                        event.effective_ms,event.recorded_ms,event.action,
                        event.replaces_event_id,event.reason],
                       separators=(",",":"),ensure_ascii=True).encode()
    return Proposal("HOST_COMMIT_REQUIRED",snapshot.scope_id,snapshot.snapshot_id,
                    snapshot.owner_revision,event,current,conflicting,
                    sha256(payload).hexdigest())

def current_view(snapshot:EventSnapshot,*,host_authorized_scope:str):
    validate_snapshot(snapshot)
    if host_authorized_scope!=snapshot.scope_id:
        raise ValueError("unauthorized scope")
    return _derive(snapshot.events)[0]
