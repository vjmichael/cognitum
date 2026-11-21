"""COG-LU-IPC-01C-R1: exact typed domain frames remain inert and bounded."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from cognitum.mel import lu_ssm_contract as s
from cognitum.mel.vendor.cognitum.ssm.v1 import ssm_pb2 as pb
from cognitum.mel.vendor.lu.workspace.v0 import workspace_pb2 as w

STREAM="scientific-stream-1"
ORIGIN=w.OriginRefs(workspace_ref="workspace-1",conversation_ref="conversation-1",
    user_turn_ref="turn-1",task_ref="task-1",operation_ref="event-1")
CTX=hashlib.sha256(b"externally approved mathematical model context").digest()
DIG=hashlib.sha256(b"previous authenticated durable checkpoint").digest()

HOST=dict(
 trusted_origin=ORIGIN,
 approved_stream_id=STREAM,
 approved_model_context_sha256=CTX,
 anchor_revision=1,
 anchor_digest=DIG,
 source_cursor="",
 last_observation_time=0.,
 last_watermark_time=0.,
 sensor_dimension=1,
)


def typed_input(kind=pb.ADVANCE_KIND_INCREMENT,**changes):
    inp=pb.SsmAdvanceRequest(stream_id=STREAM,event_id=ORIGIN.operation_ref,
       expected_revision=1,expected_checkpoint_sha256=DIG,
       approved_model_context_sha256=CTX,expected_source_cursor="",
       kind=kind,end_time=.5,increment=[.2])
    if kind==pb.ADVANCE_KIND_WATERMARK:
        inp.ClearField("increment")
    for k,v in changes.items():
        if k=="increment":
            inp.ClearField("increment")
            inp.increment.extend(v)
        else:setattr(inp,k,v)
    return inp


def invoke(inp=None,**changes):
    if inp is None:inp=typed_input()
    frame=w.CapabilityInvoke(
        origin=ORIGIN,capability_id=s.OPERATION,capability_version=1,
        deadline_unix_ms=123456789, input=w.TypedValue(
            type_url=s.INPUT_URL,
            encoded_message=inp.SerializeToString(deterministic=True)))
    for k,v in changes.items():
        if k=="origin":
            frame.origin.CopyFrom(v)
        else:setattr(frame,k,v)
    return frame.SerializeToString(deterministic=True)


def inspect(raw,**overrides):
    kw=dict(HOST)
    kw.update(overrides)
    return s.inspect_invoke(raw,**kw)


def test_exact_source_git_blob_and_real_generated_ssm_descriptor():
    offer=s.proposed_capability()
    path=Path(s.__file__).resolve().parent/"vendor"/s.SOURCE_RELATIVE
    data=path.read_bytes()
    h=hashlib.sha1(b"blob "+str(len(data)).encode()+b"\x00"+data).hexdigest()
    assert h==s.SOURCE_GIT_SHA=="755562254afdbea686ee33b95567c505f2f85e49"
    assert offer["domain_source_git_blob"]==h
    assert pb.DESCRIPTOR.package=="cognitum.mel.ssm.v1"
    assert offer["operation_id"]==s.OPERATION
    desc=w.CapabilityDescriptor.FromString(offer["capability_descriptor_wire"])
    assert desc.capability_id==s.OPERATION
    assert desc.capability_version==1
    assert desc.input_type_url==s.INPUT_URL
    assert desc.output_type_url==s.OUTPUT_URL
    assert list(desc.declared_effects)==[w.EFFECT_CLASS_PURE_COMPUTE]
    assert not offer["signed_package_enrolled"]
    assert not offer["model_advertised"]
    assert not offer["domain_execution_authorized"]


def test_existing_five_real_mel_type_descriptors_stay_unchanged():
    descriptors=s.validate_five_reviewed_routes()
    assert len(descriptors)==5
    decoded=[w.CapabilityDescriptor.FromString(raw) for raw in descriptors]
    assert {d.capability_id for d in decoded}=={
      "cognitum.vfa.evaluate","cognitum.vfa.gradient",
      "cognitum.hdc.bind","cognitum.hdc.query","cognitum.kan.evaluate"}
    assert all(list(x.declared_effects)==[w.EFFECT_CLASS_PURE_COMPUTE]
               for x in decoded)
    assert all(x.input_type_url.startswith("type.googleapis.com/")
               and x.output_type_url.startswith("type.googleapis.com/")
               for x in decoded)
    assert s.OPERATION not in {x.capability_id for x in decoded}


def test_strict_increment_candidate_is_inert_and_bound_to_origin():
    prepared=inspect(invoke())
    assert prepared.original_operation_ref==ORIGIN.operation_ref
    assert prepared.stream_id==STREAM
    assert prepared.event_id=="event-1"
    assert prepared.kind=="increment"
    assert prepared.end_time==.5
    assert prepared.increment==(.2,)
    assert prepared.expected_revision==1
    assert prepared.prior_sha256==DIG
    assert not prepared.execution_authorized
    assert not prepared.publication_authorized
    assert len(bytes.fromhex(prepared.typed_request_sha256))==32


def test_missing_actual_increment_is_distinct_from_zero_increment():
    missing=inspect(invoke(typed_input(increment=[],missing_increment=True)))
    actual=inspect(invoke(typed_input(increment=[0.],missing_increment=False)))
    assert missing.increment is None
    assert actual.increment==(0.,)
    assert missing.typed_request_sha256!=actual.typed_request_sha256


def test_watermark_preserves_observation_count_and_cursor():
    raw=invoke(typed_input(kind=pb.ADVANCE_KIND_WATERMARK,end_time=2.))
    prepared=inspect(raw,last_observation_time=.5,last_watermark_time=1.5)
    assert prepared.kind=="watermark"
    assert prepared.increment is None
    assert prepared.end_time==2.
    assert not prepared.execution_authorized


@pytest.mark.parametrize("change",[
    {"stream_id":"foreign-stream"},
    {"event_id":"other-event"},
    {"expected_revision":2},
    {"expected_checkpoint_sha256":b"\xaa"*32},
    {"expected_checkpoint_sha256":b"\xaa"*31},
    {"approved_model_context_sha256":b"\xbb"*32},
    {"expected_source_cursor":"forged-prior-event"},
    {"kind":pb.ADVANCE_KIND_UNSPECIFIED},
    {"end_time":float("nan")},
    {"end_time":float("inf")},
    {"end_time":-1.},
    {"end_time":1e12},
    {"increment":[]},
    {"increment":[1.,2.]},
    {"increment":[float("nan")]},
    {"increment":[float("inf")]},
    {"increment":[1e9]},
    {"missing_increment":True},
    {"missing_increment":True,"increment":[.2]},
])
def test_forged_or_noncausal_domain_data_refused(change):
    with pytest.raises(ValueError,match="SSM IPC refused"):
        inspect(invoke(typed_input(**change)))


@pytest.mark.parametrize("variant",[
    "other_capability","wrong_version","wrong_type_url","wrong_origin",
    "no_deadline","ref_object","no_body","noncanonical_unknown",
])
def test_untrusted_lu_envelope_refused(variant):
    inp=typed_input()
    wire=w.CapabilityInvoke(
        origin=ORIGIN,capability_id=s.OPERATION,capability_version=1,
        deadline_unix_ms=42,input=w.TypedValue(
            type_url=s.INPUT_URL,
            encoded_message=inp.SerializeToString(deterministic=True)))
    if variant=="other_capability":
        wire.capability_id="cognitum.vfa.evaluate"
    elif variant=="wrong_version":wire.capability_version=2
    elif variant=="wrong_type_url":wire.input.type_url="type.googleapis.com/google.protobuf.Any"
    elif variant=="wrong_origin":wire.origin.user_turn_ref="other-turn"
    elif variant=="no_deadline":wire.deadline_unix_ms=0
    elif variant=="ref_object":
        wire.input_refs.add(owner_module_id="cognitum.mel",
            object_ref="not-trusted",sha256=b"a"*32,
            size_bytes=1,expiry_unix_ms=1)
    elif variant=="no_body":wire.ClearField("input")
    raw=wire.SerializeToString(deterministic=True)
    if variant=="noncanonical_unknown":
        raw+=b"\x80\x06\x01"  # unknown field 96
    with pytest.raises(ValueError,match="SSM IPC refused"):
        inspect(raw)


@pytest.mark.parametrize("trusted",[
    {"anchor_revision":2},
    {"anchor_digest":b"\xbb"*32},
    {"approved_stream_id":"foreign-stream"},
    {"approved_model_context_sha256":b"\xcc"*32},
    {"source_cursor":"different-host-cursor"},
    {"sensor_dimension":2},
    {"last_observation_time":.5},
    {"last_watermark_time":.5},
])
def test_trusted_host_anchor_or_clock_mismatch_refused(trusted):
    with pytest.raises(ValueError,match="SSM IPC refused"):
        inspect(invoke(),**trusted)


@pytest.mark.parametrize("kind,changes,clock",[
    (pb.ADVANCE_KIND_INCREMENT,{"end_time":0.},{}),
    (pb.ADVANCE_KIND_INCREMENT,{"end_time":1e7},{}),
    (pb.ADVANCE_KIND_WATERMARK,{"end_time":0.2},{"last_watermark_time":.3}),
    (pb.ADVANCE_KIND_WATERMARK,{"missing_increment":True},{}),
    (pb.ADVANCE_KIND_WATERMARK,{"increment":[.2]},{}),
])
def test_noncausal_or_fabricated_increment_refused(kind,changes,clock):
    with pytest.raises(ValueError,match="SSM IPC refused"):
        inspect(invoke(typed_input(kind=kind,**changes)),**clock)


def _result(prepared, status=pb.ADVANCE_DISPOSITION_COMMITTED, **changes):
    result=pb.SsmAdvanceResult(stream_id=prepared.stream_id,
         event_id=prepared.event_id,disposition=status,
         observed_revision=prepared.expected_revision+1,
         observed_checkpoint_sha256=b"\x13"*32,
         request_sha256=bytes.fromhex(prepared.typed_request_sha256),
         pending_release_count=1)
    for k,v in changes.items():setattr(result,k,v)
    return result.SerializeToString(deterministic=True)


def test_unpublishable_host_result_candidate_never_claims_grant():
    prepared=inspect(invoke())
    output=s.inspect_result(_result(prepared),prepared=prepared)
    assert output["status"]=="committed"
    assert not output["publication_authorized"]
    assert not output["original_grant_issued"]
    assert not output["installed_core_peer_qualified"]
    assert output["host_journal_reconciliation_required"]


@pytest.mark.parametrize("changes",[
    {"event_id":"foreign"},
    {"stream_id":"foreign"},
    {"observed_revision":1},
    {"observed_revision":3},
    {"observed_checkpoint_sha256":b"x"*31},
    {"request_sha256":b"\xff"*32},
    {"pending_release_count":257},
    {"reason_code":"unexpected-success-reason"},
    {"disposition":pb.ADVANCE_DISPOSITION_UNSPECIFIED},
])
def test_forged_committed_receipt_refused(changes):
    prepared=inspect(invoke())
    with pytest.raises(ValueError,match="SSM IPC refused"):
        s.inspect_result(_result(prepared,**changes),prepared=prepared)


@pytest.mark.parametrize("status",[
    pb.ADVANCE_DISPOSITION_REFUSED,pb.ADVANCE_DISPOSITION_FAILED,
    pb.ADVANCE_DISPOSITION_CANCELLED,pb.ADVANCE_DISPOSITION_UNCERTAIN
])
def test_refused_cancelled_failed_uncertain_are_not_publication(status):
    prepared=inspect(invoke())
    bad=_result(prepared,status,reason_code="refused")
    with pytest.raises(ValueError,match="SSM IPC refused"):
        s.inspect_result(bad,prepared=prepared)
    result=_result(prepared,status,observed_revision=0,
                   observed_checkpoint_sha256=b"",pending_release_count=0,
                   reason_code="host_refused")
    observed=s.inspect_result(result,prepared=prepared)
    assert observed["status"]=="not_committed"
    assert not observed["publication_authorized"]


def test_duplicate_is_not_new_output():
    prepared=inspect(invoke())
    result=_result(prepared,pb.ADVANCE_DISPOSITION_DUPLICATE,
                   observed_revision=1,pending_release_count=0)
    answer=s.inspect_result(result,prepared=prepared)
    assert answer["status"]=="duplicate"
    assert not answer["publication_authorized"]


def test_unknown_field_in_result_refused():
    prepared=inspect(invoke())
    raw=_result(prepared)+b"\x80\x06\x01"
    with pytest.raises(ValueError,match="noncanonical"):
        s.inspect_result(raw,prepared=prepared)


def test_api_has_no_runner_registration_model_grant_or_publish():
    assert not hasattr(s,"register")
    assert not hasattr(s,"dispatch")
    assert not hasattr(s,"execute")
    assert not hasattr(s,"invoke_model")
    assert not hasattr(s,"issue_grant")
    assert not hasattr(s,"publish")
