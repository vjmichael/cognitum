"""Canonical read-only C06 search / proposal-only C07 Protobuf transport.

Host authorization must be established before the request is constructed:
a 'host_authorized_scope' string is NOT a permission token or proof.
"""
from hashlib import sha256
from google.protobuf.message import DecodeError
from .proto import host_owned_memory_pb2 as pb
from .memory_derived import Evidence,Snapshot,Query,DerivedIndex
from .belief_proposals import StateEvent,EventSnapshot,propose

MAX_REQUEST=4_000_000
MAX_RESULT=280_000

def _parse(frame,cls,bound):
    if type(frame) is not bytes or not 0<len(frame)<=bound:
        raise ValueError("invalid ANSF wire bound")
    value=cls()
    try:value.ParseFromString(frame)
    except DecodeError as exc:raise ValueError("invalid ANSF wire") from exc
    known=cls();known.CopyFrom(value);known.DiscardUnknownFields()
    if known!=value or value.SerializeToString(deterministic=True)!=frame:
        raise ValueError("unknown or noncanonical ANSF wire fields")
    return value

def _pack(message):
    data=message.SerializeToString(deterministic=True)
    if len(data)>MAX_RESULT:raise ValueError("oversized ANSF response")
    return data

def _evidence(w):
    return Evidence(w.source_id,w.source_revision,w.scope_id,w.subject,w.text,
        w.citation_handle,w.valid_from_ms,
        w.valid_to_ms if w.has_valid_to else None,w.tombstoned)

def execute_query(frame:bytes)->bytes:
    r=_parse(frame,pb.Query,MAX_REQUEST)
    if r.schema_version!=1 or not r.HasField("snapshot") or r.snapshot.schema_version!=1:
        raise ValueError("unsupported memory schema")
    s=Snapshot(r.snapshot.owner,r.snapshot.snapshot_id,
               r.snapshot.owner_revision,tuple(_evidence(x) for x in r.snapshot.rows))
    # This is a derived, in-memory index; never writes to canonical ANSF.
    index=DerivedIndex(s,host_authorized_scope=r.host_authorized_scope)
    try:
        if r.exact_lookup:
            result=index.exact(r.scope_id,r.exact_source_id,
                        expected_owner_revision=r.expected_owner_revision)
            hits=() if result is None else (result,)
            if r.expected_snapshot_id!=s.snapshot_id:
                raise ValueError("stale snapshot")
        else:
            query=Query(r.scope_id,r.query_text,r.expected_snapshot_id,
                        r.expected_owner_revision,r.max_results,
                        r.as_of_ms if r.has_as_of else None,r.subject or None)
            hits=index.query(query)
    finally:index.close()
    out=pb.QueryResult(schema_version=1,status="READ_ONLY",
                       request_sha256=sha256(frame).hexdigest(),
                       limitations=("Lu_is_canonical_owner","evidence_not_trusted_policy",
                                    "source_claims_provided_by_host"))
    for x in hits:
        out.hits.add(source_id=x.source_id,source_revision=x.source_revision,
                     subject=x.subject,citation_handle=x.citation_handle,
                     text=x.text,score=x.score,snapshot_id=x.snapshot_id)
    return _pack(out)

def _event(w):
    return StateEvent(w.event_id,w.scope_id,w.entity,w.predicate,
       w.value_type,w.value,w.origin_source_id,w.actor_authority,
       w.expected_revision,w.effective_ms,w.recorded_ms,w.action,
       w.replaces_event_id,w.reason)

def execute_proposal(frame:bytes)->bytes:
    r=_parse(frame,pb.ProposalRequest,MAX_REQUEST)
    if (r.schema_version!=1 or not r.HasField("snapshot")
            or not r.HasField("event") or r.snapshot.schema_version!=1):
        raise ValueError("unsupported belief schema")
    snap=EventSnapshot(r.snapshot.owner,r.snapshot.snapshot_id,
                       r.snapshot.owner_revision,r.snapshot.scope_id,
                       tuple(_event(x) for x in r.snapshot.events))
    output=propose(snap,_event(r.event),host_authorized_scope=r.host_authorized_scope)
    result=pb.ProposalResult(schema_version=1,status=output.status,
       scope_id=output.scope_id,based_on_snapshot_id=output.based_on_snapshot_id,
       expected_owner_revision=output.expected_owner_revision,
       event_sha256=output.event_sha256,
       request_sha256=sha256(frame).hexdigest(),
       limitations=output.limitations)
    for target,items in ((result.current,output.current),
                         (result.competing,output.competing)):
        for x in items:
            target.add(entity=x.entity,predicate=x.predicate,
                       value_type=x.value_type,value=x.value,status=x.status,
                       source_event_id=x.source_event_id,
                       source_revision=x.source_revision,authority=x.authority,
                       effective_ms=x.effective_ms,
                       conflict_event_ids=x.conflict_event_ids)
    return _pack(result)

def verify(kind,request,response):
    if kind=="query":
        cls=pb.QueryResult;expected=execute_query(request)
    elif kind=="proposal":
        cls=pb.ProposalResult;expected=execute_proposal(request)
    else:
        raise ValueError("unsupported memory operation")
    if _parse(response,cls,MAX_RESULT)!=_parse(expected,cls,MAX_RESULT):
        raise ValueError("forged or stale ANSF result")
    return _parse(response,cls,MAX_RESULT)
