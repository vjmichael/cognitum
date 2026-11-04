"""C18 bounded opt-in sanitized trace store and revocation/tombstone records.

No raw prompts, token sequences, files or connected-account material. A real
Lu host must implement physical persistent erasure and worker isolation.
This in-memory reference retains only event digests after revocation.
"""
from dataclasses import dataclass,replace,asdict
from hashlib import sha256
from math import isfinite
from .adaptation_policy import Trace,_canonical,_id,_digest,MAX_ROWS,MAX_FEATURES,ROUTES,PRIVACY

def _safe_numeric_trace(t,consent,source):
    return (type(t) is Trace and _id(t.event_id)
            and type(t.occurred_ms) is int and t.occurred_ms>=0
            and type(t.retention_until_ms) is int
            and t.retention_until_ms>t.occurred_ms
            and t.consent_receipt==consent and t.source_digest==source
            and t.privacy_class in PRIVACY and _id(t.task_family)
            and t.expected_route in ROUTES
            and type(t.features) is tuple
            and 1<=len(t.features)<=MAX_FEATURES
            and all(type(v) in (float,int) and isfinite(v) and abs(v)<=1e5
                    for v in t.features))


@dataclass(frozen=True)
class TraceCollection:
    workspace_id:str
    consent_receipt:str
    source_digest:str
    revision:int
    status:str                        # collecting | paused | revoked
    traces:tuple[Trace,...]
    tombstoned_event_hashes:tuple[str,...]
    mutation_ids:tuple[str,...]
    integrity_digest:str

def _seal(c):
    material={k:getattr(c,k) for k in TraceCollection.__dataclass_fields__
              if k!="integrity_digest"}
    material["traces"]=[asdict(t) for t in c.traces]
    return replace(c,integrity_digest=sha256(_canonical(material)).hexdigest())

def verify_collection(c):
    if (type(c) is not TraceCollection or not _id(c.workspace_id)
            or not _id(c.consent_receipt) or not _digest(c.source_digest)
            or c.status not in ("collecting","paused","revoked")
            or type(c.revision) is not int or c.revision<0
            or type(c.traces) is not tuple or len(c.traces)>MAX_ROWS
            or any(not _safe_numeric_trace(t,c.consent_receipt,c.source_digest)
                   for t in c.traces)
            or type(c.mutation_ids) is not tuple
            or len(set(c.mutation_ids))!=len(c.mutation_ids)
            or any(not _id(m) for m in c.mutation_ids)
            or type(c.tombstoned_event_hashes) is not tuple
            or any(not _digest(x) for x in c.tombstoned_event_hashes)
            or _seal(c).integrity_digest!=c.integrity_digest):
        raise ValueError("invalid trace-collection integrity")
    return c

def start(workspace_id,consent_receipt,source_digest):
    c=TraceCollection(workspace_id,consent_receipt,source_digest,0,"collecting",
                      (),(),(),"")
    return verify_collection(_seal(c))

def mutate(c,*,decision,mutation_id,expected_revision,host_authorized=False,
           trace=None,now_ms=None):
    verify_collection(c)
    if (host_authorized is not True or not _id(mutation_id)
            or mutation_id in c.mutation_ids
            or type(expected_revision) is not int or expected_revision!=c.revision):
        raise PermissionError("trace source/consent host gate or revision failed")
    if decision=="append" and c.status=="collecting":
        if (not _safe_numeric_trace(trace,c.consent_receipt,c.source_digest)
                or len(c.traces)>=MAX_ROWS
                or type(now_ms) is not int or now_ms<0
                or trace.occurred_ms>now_ms or now_ms>=trace.retention_until_ms
                or trace.event_id in {x.event_id for x in c.traces}
                or (c.traces and trace.occurred_ms<=c.traces[-1].occurred_ms)):
            raise ValueError("invalid/expired duplicate trace")
        out=replace(c,traces=c.traces+(trace,))
    elif decision=="pause" and c.status=="collecting":
        out=replace(c,status="paused")
    elif decision=="resume" and c.status=="paused":
        out=replace(c,status="collecting")
    elif decision=="revoke" and c.status in ("collecting","paused"):
        # Material is scrubbed from this immutable next snapshot; host must
        # independently erase original source and old persisted revisions.
        tombstones=tuple(sha256((x.event_id+"|"+x.source_digest).encode()).hexdigest()
                         for x in c.traces)
        out=replace(c,status="revoked",traces=(),
                    tombstoned_event_hashes=c.tombstoned_event_hashes+tombstones)
    elif decision=="expire" and c.status in ("collecting","paused"):
        if type(now_ms) is not int or now_ms<0:
            raise ValueError("expiry requires current host clock")
        old=tuple(x for x in c.traces if x.retention_until_ms<=now_ms)
        retained=tuple(x for x in c.traces if x.retention_until_ms>now_ms)
        out=replace(c,traces=retained,
                    tombstoned_event_hashes=c.tombstoned_event_hashes+
                    tuple(sha256((x.event_id+"|"+x.source_digest).encode()).hexdigest()
                          for x in old))
    else:
        raise ValueError("invalid trace lifecycle operation")
    return verify_collection(_seal(replace(out,revision=c.revision+1,
                               mutation_ids=c.mutation_ids+(mutation_id,))))

def training_rows(c,*,now_ms,host_authorized=False):
    verify_collection(c)
    if (host_authorized is not True or c.status!="collecting"
            or type(now_ms) is not int or any(x.retention_until_ms<=now_ms
                                            for x in c.traces)):
        raise PermissionError("collection paused, revoked, expired or not admitted")
    return c.traces
