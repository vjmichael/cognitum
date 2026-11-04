"""C15 versioned scene lifecycle: stable IDs, aliases, evidence, tombstones.

Inert state transition reference. All mutations require an explicit trusted
host-admission decision supplied by the caller; a Boolean alone is NOT a Lu
authorization token. Durable custody, OS worker isolation and host permission
checks are integration gates outside this in-memory module.
"""
from dataclasses import dataclass,replace
from math import isfinite
from .spatial_geometry import Frame,Scene,SceneObject,validate as validate_scene

MAX_ALIASES=12
MAX_EVIDENCE=32
MAX_EVENTS=256


@dataclass(frozen=True)
class Evidence:
    source_id:str
    observation_id:str
    observed_at_ms:int
    confidence:float
    coordinate_frame:str
    kind:str             # sensor_detection | manual_annotation | derived
    authorization_ref:str
    source_digest:str


@dataclass(frozen=True)
class Entity:
    obj:SceneObject
    aliases:tuple[str,...]=()
    evidence:tuple[Evidence,...]=()
    state:str="visible"  # visible | occluded | deleted


@dataclass(frozen=True)
class SceneRevision:
    scene_id:str
    revision:int
    frames:tuple[Frame,...]
    entities:tuple[Entity,...]
    epoch:int
    event_ids:tuple[str,...]=()
    workspace_id:str="workspace_default"
    detached:bool=False


@dataclass(frozen=True)
class SceneMutation:
    mutation_id:str
    stable_id:str
    operation:str          # create | update | rename | occlude | reveal | delete
    expected_object_version:int
    object_value:SceneObject|None=None
    alias:str=""
    evidence:Evidence|None=None


def _ident(x):
    return type(x) is str and x.isascii() and x.isidentifier() and 1<=len(x)<=48


def validate_revision(rev:SceneRevision):
    if (type(rev) is not SceneRevision or not _ident(rev.scene_id)
            or type(rev.revision) is not int or rev.revision<0
            or type(rev.entities) is not tuple or len(rev.entities)>64
            or type(rev.event_ids) is not tuple or len(rev.event_ids)>MAX_EVENTS
            or len(set(rev.event_ids))!=len(rev.event_ids)
            or any(not _ident(v) for v in rev.event_ids)
            or not _ident(rev.workspace_id)
            or type(rev.detached) is not bool):
        raise ValueError("invalid scene revision")
    objects=tuple(e.obj for e in rev.entities)
    validate_scene(Scene(rev.frames,objects,rev.epoch))
    alias_owners={}
    for e in rev.entities:
        if (type(e) is not Entity or e.state not in ("visible","occluded","deleted")
                or e.obj.visible!=(e.state=="visible")
                or type(e.aliases) is not tuple or len(e.aliases)>MAX_ALIASES
                or len(set(e.aliases))!=len(e.aliases)
                or type(e.evidence) is not tuple or len(e.evidence)>MAX_EVIDENCE):
            raise ValueError("invalid scene entity")
        if e.obj.stable_id in e.aliases:
            raise ValueError("alias equals stable ID")
        for alias in e.aliases+(e.obj.stable_id,):
            if not _ident(alias) or (alias in alias_owners and alias_owners[alias]!=e.obj.stable_id):
                raise ValueError("ambiguous alias across stable identities")
            alias_owners[alias]=e.obj.stable_id
        keys=set()
        for evidence in e.evidence:
            if (type(evidence) is not Evidence or not _ident(evidence.source_id)
                    or not _ident(evidence.observation_id)
                    or type(evidence.observed_at_ms) is not int
                    or not 0<=evidence.observed_at_ms<=rev.epoch
                    or type(evidence.confidence) not in (int,float)
                    or not isfinite(evidence.confidence)
                    or not 0<=evidence.confidence<=1
                    or evidence.coordinate_frame not in ("world",)+tuple(f.name for f in rev.frames)
                    or evidence.kind not in ("sensor_detection","manual_annotation","derived")
                    or not _ident(evidence.authorization_ref)
                    or type(evidence.source_digest) is not str
                    or len(evidence.source_digest)!=64
                    or any(c not in "0123456789abcdef" for c in evidence.source_digest)):
                raise ValueError("missing or malformed evidence provenance")
            key=(evidence.source_id,evidence.observation_id)
            if key in keys:raise ValueError("duplicate evidence")
            keys.add(key)
    return rev


def resolve(rev:SceneRevision,name:str,*,include_deleted:bool=False)->Entity:
    validate_revision(rev)
    if rev.detached:
        raise ValueError("workspace detached; scene lookup prohibited")
    matches=[e for e in rev.entities
             if name==e.obj.stable_id or name in e.aliases]
    if len(matches)!=1 or (matches[0].state=="deleted" and not include_deleted):
        raise ValueError("unknown, deleted or ambiguous object identity")
    return matches[0]


def mutate(rev:SceneRevision,change:SceneMutation,*,expected_revision:int,
           admitted_by_trusted_host:bool=False)->SceneRevision:
    """Host adapter MUST independently enforce source authorization first.

    Caller's Boolean alone cannot be used as a security boundary.
    """
    validate_revision(rev)
    if rev.detached:
        raise ValueError("detached workspace is immutable")
    if (type(change) is not SceneMutation or type(expected_revision) is not int
            or expected_revision!=rev.revision or admitted_by_trusted_host is not True
            or not _ident(change.mutation_id) or change.mutation_id in rev.event_ids
            or not _ident(change.stable_id)
            or change.operation not in ("create","update","rename","occlude","reveal","delete")
            or type(change.expected_object_version) is not int
            or change.expected_object_version<0):
        raise ValueError("unauthorized, stale or invalid scene change")
    old=next((e for e in rev.entities if e.obj.stable_id==change.stable_id),None)
    if change.operation=="create":
        if old is not None or change.expected_object_version!=0 or change.object_value is None:
            raise ValueError("cannot create duplicate stable ID")
        if (change.object_value.stable_id!=change.stable_id
                or change.object_value.version!=1 or change.evidence is None):
            raise ValueError("creation requires first version and provenance")
        entity=Entity(change.object_value,(),(change.evidence,),
                      "visible" if change.object_value.visible else "occluded")
        updated=rev.entities+(entity,)
    else:
        if old is None or old.state=="deleted" or old.obj.version!=change.expected_object_version:
            raise ValueError("object missing, deleted or stale")
        if change.operation=="update":
            if (change.object_value is None or change.object_value.stable_id!=old.obj.stable_id
                    or change.object_value.version!=old.obj.version+1
                    or change.evidence is None or change.object_value.timestamp_ms<old.obj.timestamp_ms):
                raise ValueError("update requires newer object and evidence")
            new=replace(old,obj=change.object_value,
                        evidence=old.evidence+(change.evidence,),
                        state="visible" if change.object_value.visible else "occluded")
        elif change.operation=="rename":
            if not _ident(change.alias) or change.alias in old.aliases or change.evidence is None:
                raise ValueError("alias and evidence required")
            new=replace(old,obj=replace(old.obj,version=old.obj.version+1),
                        aliases=old.aliases+(change.alias,),
                        evidence=old.evidence+(change.evidence,))
        else:
            target={"occlude":"occluded","reveal":"visible","delete":"deleted"}[change.operation]
            if change.evidence is None:
                raise ValueError("state transition requires provenance")
            new=replace(old,obj=replace(old.obj,version=old.obj.version+1,
                                        visible=(target=="visible")),
                        evidence=old.evidence+(change.evidence,),
                        state=target)
        updated=tuple(new if e.obj.stable_id==old.obj.stable_id else e
                      for e in rev.entities)
    result=replace(rev,entities=updated,revision=rev.revision+1,
                   event_ids=rev.event_ids+(change.mutation_id,))
    return validate_revision(result)


def detach_workspace(rev:SceneRevision,*,expected_revision:int,
                     event_id:str,admitted_by_trusted_host:bool=False)->SceneRevision:
    """Irreversible local detachment barrier; host must authorize externally."""
    validate_revision(rev)
    if (rev.detached or admitted_by_trusted_host is not True
            or type(expected_revision) is not int or expected_revision!=rev.revision
            or not _ident(event_id) or event_id in rev.event_ids):
        raise ValueError("invalid or unauthorized scene workspace detachment")
    return validate_revision(replace(
        rev,revision=rev.revision+1,event_ids=rev.event_ids+(event_id,),
        detached=True))
