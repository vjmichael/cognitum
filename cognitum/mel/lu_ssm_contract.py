"""COG-LU-IPC-01C-R1: reviewed Cognitum SSM typed domain contract.

Only an *inert* Lu workspace v0 PURE_COMPUTE capability proposal and a
strict source/typed-byte/domain verifier. No handler, grants, runtime
registration, active SSM worker, broker, credential, checkpoint decryption,
result publishing or modifications to Lu Core.

Lu-owned CapabilityInvoke.origin is checked against a separate trusted host
origin. The SSM TypedValue carries no independent authority. Checkpoint SHA
and revision are matched against separately observed host-approved anchors;
a caller-supplied SHA/revision by itself proves nothing.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import re

from google.protobuf.message import DecodeError

from .vendor.lu.workspace.v0 import workspace_pb2 as workspace
from .vendor.cognitum.ssm.v1 import ssm_pb2 as pb
from . import lu_workspace_contract as lu
from cognitum.research import ssm_stochastic_increments as inc
from cognitum.research import ssm_stochastic_streaming as streaming

SCHEMA = "cognitum.mel.ssm.v1.reviewed_source_candidate"
OPERATION = "cognitum.ssm.fixed_duration.advance.v1"
INPUT_URL = "type.googleapis.com/cognitum.mel.ssm.v1.SsmAdvanceRequest"
OUTPUT_URL = "type.googleapis.com/cognitum.mel.ssm.v1.SsmAdvanceResult"
MAX_BYTES = 64 * 1024
MAX_OUTPUTS = streaming.MAX_PENDING
MAX_REVISION = min(2**63-2, streaming.MAX_EVENTS+1)
SOURCE_RELATIVE = "cognitum/ssm/v1/ssm.proto"
# The original Git source SHA is pinned after creation of this first review.
SOURCE_GIT_SHA = "SEAL_WITH_EXACT_SOURCE_BLOB"
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}\Z",re.ASCII)
ORIGIN_NAME = re.compile(r"[A-Za-z0-9_.:/-]{1,128}\Z",re.ASCII)
REASON = re.compile(r"[A-Za-z0-9_.:/-]{1,96}\Z",re.ASCII)


def _need(ok,reason):
    if not ok:
        raise ValueError("Cognitum typed SSM IPC refused: "+reason)


def _sha(value,what):
    _need(type(value) is bytes and len(value)==32 and any(value),
          what+" requires verified 32-byte digest")
    return value


def _identity(value,label):
    _need(type(value) is str and IDENTIFIER.fullmatch(value) is not None,
          label+" bounded identifier")
    return value


def _canonical(obj):
    return obj.SerializeToString(deterministic=True)


def _strict(raw, cls, max_bytes=MAX_BYTES):
    _need(type(raw) is bytes and 0<len(raw)<=max_bytes,
          "bounded exact Protobuf message bytes")
    try:
        obj=cls.FromString(raw)
    except (ValueError,DecodeError,RecursionError) as exc:
        raise ValueError("Cognitum typed SSM IPC refused: invalid Protobuf") from exc
    obj.DiscardUnknownFields()
    _need(_canonical(obj)==raw,"noncanonical, duplicate or unknown Protobuf")
    return obj


def _source():
    path=Path(__file__).resolve().parent/"vendor"/SOURCE_RELATIVE
    raw=path.read_bytes()
    git_sha=hashlib.sha1(b"blob "+str(len(raw)).encode("ascii")+b"\x00"+raw).hexdigest()
    _need(git_sha==SOURCE_GIT_SHA,"unreviewed SSM Protobuf source drift")
    _need(pb.DESCRIPTOR.name==SOURCE_RELATIVE and
          pb.DESCRIPTOR.package=="cognitum.mel.ssm.v1",
          "native compiled SSM descriptor mismatch")
    return raw


def proposed_capability():
    """Unregistered PURE_COMPUTE descriptor; never installed/model-visible."""
    raw=_source()
    approved=lu.proposal()
    _need(not approved["registered"] and not approved["execution_authorized"]
          and not approved["host_grant_issued"],
          "Lu provider must remain source-only")
    _need(OPERATION==lu.SSM_PENDING_OPERATION,"reserved Lu SSM name drift")
    descriptor=workspace.CapabilityDescriptor(
        capability_id=OPERATION,capability_version=1,
        input_type_url=INPUT_URL,output_type_url=OUTPUT_URL,
        declared_effects=[workspace.EFFECT_CLASS_PURE_COMPUTE],
        streams_progress=False,
        display_name="Cognitum fixed-duration stochastic assimilation",
    )
    return dict(
        schema=SCHEMA,
        capability_descriptor_wire=_canonical(descriptor),
        domain_source_git_blob=SOURCE_GIT_SHA,
        domain_source_sha256=hashlib.sha256(raw).hexdigest(),
        domain_protobuf_descriptor_sha256=hashlib.sha256(pb.DESCRIPTOR.serialized_pb).hexdigest(),
        lu_workspace_proto_git_blob=lu.LU_WORKSPACE_PROTO_GIT_BLOB,
        operation_id=OPERATION,
        status="SOURCE_ONLY_NOT_REGISTERED",
        signed_package_enrolled=False,
        native_pure_host_effect_authorized=False,
        installed_core_connected=False,
        model_advertised=False,
        domain_execution_authorized=False)


def validate_five_reviewed_routes():
    """Generate and verify the exact existing five native descriptor shapes."""
    from . import lu_adapter
    proposal=lu.proposal()
    _need(len(proposal["reviewed_mel_bindings"])==5,"five existing MEL routes")
    original={r["operation"]:r for r in lu_adapter.proposal()["routes"]}
    candidates=[]
    for candidate in proposal["register_workspace"]["capabilities"]:
        op=candidate["capability_id"].removeprefix("cognitum.")
        _need(op in original and candidate["capability_id"]=="cognitum."+op,
              "unreviewed capability")
        actual=original[op]
        _need(candidate["input_type_url"]==actual["input_type_url"]
              and candidate["output_type_url"]==actual["output_type_url"]
              and candidate["declared_effects"]==[lu.PURE_EFFECT],
              "native MEL type/effect mismatch")
        d=workspace.CapabilityDescriptor(
            capability_id=candidate["capability_id"],
            capability_version=candidate["capability_version"],
            input_type_url=candidate["input_type_url"],
            output_type_url=candidate["output_type_url"],
            declared_effects=[workspace.EFFECT_CLASS_PURE_COMPUTE],
            streams_progress=False,
            display_name=candidate["display_name"],
        )
        _need(workspace.CapabilityDescriptor.FromString(_canonical(d))==d,
              "Lu descriptor did not Protobuf roundtrip")
        candidates.append(_canonical(d))
    _need(len(candidates)==5,"complete five-route MEL selection")
    return tuple(sorted(candidates))


def _origin(value):
    _need(type(value) is workspace.OriginRefs,
          "trusted Lu OriginRefs message")
    data=tuple(getattr(value,name) for name in
               ("workspace_ref","conversation_ref","user_turn_ref",
                "task_ref","operation_ref"))
    _need(all(type(x) is str and ORIGIN_NAME.fullmatch(x) is not None
              for x in data),"bounded host origin fields")
    return data


@dataclass(frozen=True, slots=True)
class SsmCandidate:
    """Strictly validated candidate data. It is NOT an admission/grant."""
    original_operation_ref: str
    stream_id: str
    event_id: str
    kind: str
    end_time: float
    increment: tuple[float,...] | None
    expected_revision: int
    prior_sha256: bytes
    prior_cursor: str
    typed_request_sha256: str
    publication_authorized: bool = False
    execution_authorized: bool = False


def inspect_invoke(raw, *, trusted_origin, approved_stream_id,
                   approved_model_context_sha256, anchor_revision, anchor_digest,
                   source_cursor, last_observation_time, last_watermark_time,
                   sensor_dimension):
    """Check exact independently observed host limits, without dispatch.

    The trusted host must have authenticated the installed Core OS peer,
    authenticated *original* turn, live per-call Lu grant and native type URL
    BEFORE any active dispatch. This function makes no such assertion.
    """
    _source()
    host_origin=_origin(trusted_origin)
    _identity(approved_stream_id,"trusted stream")
    _sha(approved_model_context_sha256,"approved model context")
    _need(type(anchor_revision) is int and
          1<=anchor_revision<=MAX_REVISION,
          "trusted external revision floor")
    _sha(anchor_digest,"trusted checkpoint SHA")
    _need(type(source_cursor) is str and len(source_cursor)<=128 and
          all(32<=ord(x)<=126 for x in source_cursor),
          "trusted source cursor")
    _need(type(sensor_dimension) is int and 1<=sensor_dimension<=8,
          "trusted sensor dimension")
    _need(type(last_observation_time) in (int,float) and
          type(last_watermark_time) in (int,float) and
          math.isfinite(last_observation_time) and
          math.isfinite(last_watermark_time) and
          0<=last_observation_time<=last_watermark_time<=streaming.MAX_CLOCK,
          "trusted original causal clock")
    wire=_strict(raw,workspace.CapabilityInvoke)
    _need(wire.HasField("origin") and _origin(wire.origin)==host_origin,
          "original user-turn/operation identity mismatch")
    _need(wire.capability_id==OPERATION and wire.capability_version==1
          and wire.deadline_unix_ms>0 and len(wire.input_refs)==0,
          "unregistered effect/version or raw object references")
    _need(wire.HasField("input") and wire.input.type_url==INPUT_URL,
          "exact registered SSM request type URL required")
    data=_strict(wire.input.encoded_message,pb.SsmAdvanceRequest)
    _identity(data.stream_id,"stream")
    _identity(data.event_id,"event")
    _need(data.stream_id==approved_stream_id and
          data.event_id==host_origin[-1],
          "stream/event idempotency mismatch")
    _need(data.expected_revision==anchor_revision and
          data.expected_checkpoint_sha256==anchor_digest and
          data.approved_model_context_sha256==approved_model_context_sha256 and
          data.expected_source_cursor==source_cursor,
          "trusted checkpoint revision, digest, model or cursor mismatch")
    _need(math.isfinite(data.end_time) and
          0<=data.end_time<=streaming.MAX_CLOCK,
          "bounded finite event time")
    if data.kind==pb.ADVANCE_KIND_INCREMENT:
        _need(last_watermark_time<data.end_time and
              last_observation_time<data.end_time and
              0<data.end_time-last_observation_time<=inc.MAX_DT,
              "strict causal increment clock")
        if data.missing_increment:
            _need(not data.increment,"missing observation must not carry values")
            inc_values=None
        else:
            _need(len(data.increment)==sensor_dimension and
                  all(math.isfinite(v) and abs(v)<=1e8 for v in data.increment),
                  "actual integrated increment dimension/range")
            inc_values=tuple(data.increment)
        kind="increment"
    elif data.kind==pb.ADVANCE_KIND_WATERMARK:
        _need(not data.missing_increment and not data.increment and
              data.end_time>=last_watermark_time,
              "watermark cannot fabricate observation or rewind time")
        kind="watermark"
        inc_values=None
    else:
        raise ValueError("Cognitum typed SSM IPC refused: unknown event kind")
    return SsmCandidate(
        original_operation_ref=host_origin[-1],stream_id=data.stream_id,
        event_id=data.event_id,kind=kind,end_time=data.end_time,
        increment=inc_values,expected_revision=anchor_revision,
        prior_sha256=anchor_digest,prior_cursor=source_cursor,
        typed_request_sha256=hashlib.sha256(wire.input.encoded_message).hexdigest())


def inspect_result(raw, *, prepared):
    """Untrusted domain receipt candidate, never a publication permission.

    Real host must match Cognitum's independently signed journal/outbox
    receipts and Lu's durable original operation before acknowledging.
    """
    _need(type(prepared) is SsmCandidate and
          not prepared.execution_authorized and
          not prepared.publication_authorized,
          "reviewed unprivileged SSM candidate")
    result=_strict(raw,pb.SsmAdvanceResult)
    _need(result.stream_id==prepared.stream_id and
          result.event_id==prepared.event_id and
          result.request_sha256==bytes.fromhex(prepared.typed_request_sha256),
          "original event and request digest")
    _need(result.pending_release_count<=MAX_OUTPUTS,
          "bounded outbox release count")
    if result.disposition==pb.ADVANCE_DISPOSITION_COMMITTED:
        _need(result.observed_revision==prepared.expected_revision+1
              and len(result.observed_checkpoint_sha256)==32
              and any(result.observed_checkpoint_sha256)
              and not result.reason_code,
              "committed revision/outbox candidate mismatch")
        status="committed"
    elif result.disposition==pb.ADVANCE_DISPOSITION_DUPLICATE:
        _need(1<=result.observed_revision<=prepared.expected_revision
              and len(result.observed_checkpoint_sha256)==32
              and not result.pending_release_count and not result.reason_code,
              "duplicate cannot publish or invent a future revision")
        status="duplicate"
    elif result.disposition in (
           pb.ADVANCE_DISPOSITION_REFUSED,pb.ADVANCE_DISPOSITION_FAILED,
           pb.ADVANCE_DISPOSITION_CANCELLED,pb.ADVANCE_DISPOSITION_UNCERTAIN):
        _need(result.observed_revision==0 and
              not result.observed_checkpoint_sha256 and
              not result.pending_release_count and
              REASON.fullmatch(result.reason_code) is not None,
              "terminal refusal/uncertain outcome cannot claim output")
        status="not_committed"
    else:
        raise ValueError("Cognitum typed SSM IPC refused: unknown result status")
    return dict(status=status,domain_result_sha256=hashlib.sha256(raw).hexdigest(),
                publication_authorized=False,original_grant_issued=False,
                installed_core_peer_qualified=False,
                host_journal_reconciliation_required=True)
