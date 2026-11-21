"""01E-R1: genuine Cognitum HostSSMJournal pending outbox + unprivileged 01D replay.

The R6 journal uses its own HMAC/SQLite machinery and MEL Admission.
Test brokers/revision pins are synthetic; these are not installed Lu Core
receipts, signed credentials, trusted external revision authority or worker
cancellation results. No output is published or acknowledged by this module.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import shutil
import sqlite3

import pytest

from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.mel import admission as mel
from cognitum.mel import ssm_recovery as r6
from cognitum.mel import lu_ipc_outbox as bridge
from cognitum.mel import lu_ipc_lifecycle as life
from cognitum.mel import lu_ssm_contract as ssm
from cognitum.mel.vendor.lu.workspace.v0 import workspace_pb2 as lu
from cognitum.mel.vendor.cognitum.ssm.v1 import ssm_pb2
from research_tests.mel_ssm_r6int01.test_journal import (
    S,CTX,KeyBroker,RevisionAnchor,_engine,
)
from research_tests.mel_lu_ipc01d.test_durable_lifecycle import (
    TestIndependentRevisionAnchor,
)

REQUEST="r6-registered-source-only-request"
SESSION="original-core-session-locked"
EPOCH="original-core-epoch-locked"
STREAM="ssm-session-01"
EVENT="event-002"


class OriginalOperationKeyBroker:
    """Explicit separate domain test key for event-002, not 01D event-1."""

    def __init__(self):
        self.enabled=True

    def borrow_key(self, scope, operation_ref):
        assert scope[-1] == operation_ref == EVENT
        return bytes(range(1,33)) if self.enabled else None


@pytest.fixture
def combined(tmp_path):
    # Native real R6 journal; fake upstream policy/custody intentionally
    # unsuitable for an installed signed Lu Core security acceptance.
    admission=mel.Admission(Runtime(Registry()),S.session)
    key_provider=KeyBroker()
    revision=RevisionAnchor()
    allowed={"active":True}
    def allow(scope,operation):
        return scope==S and allowed["active"]
    journal=r6.HostSSMJournal(
        admission,S,stream_id=STREAM,approved_model_context=CTX,
        credential_broker=key_provider,revision_anchor=revision,
        allow=allow,sqlite_path=tmp_path/"source-r6.sqlite",
        initial_engine=_engine())
    assert journal.process("event-001",kind="increment",
                           end_time=.3,increment=[.2])["revision"]==2
    prior=journal.status()
    origin=lu.OriginRefs(
        workspace_ref=S.workspace,conversation_ref="conversation-r6",
        user_turn_ref=S.turn,task_ref="task-r6",operation_ref=EVENT)
    context=hashlib.sha256(
        r6._scope_context(S,CTX)).digest()
    input=ssm_pb2.SsmAdvanceRequest(
        stream_id=STREAM,event_id=EVENT,expected_revision=2,
        expected_checkpoint_sha256=bytes.fromhex(prior["checkpoint_sha256"]),
        approved_model_context_sha256=context,
        expected_source_cursor="event-001",
        kind=ssm_pb2.ADVANCE_KIND_INCREMENT,end_time=1.0,increment=[.1])
    invoke=lu.CapabilityInvoke(
        origin=origin,capability_id=ssm.OPERATION,capability_version=1,
        deadline_unix_ms=123456789,
        input=lu.TypedValue(type_url=ssm.INPUT_URL,
           encoded_message=input.SerializeToString(deterministic=True)))
    wire=invoke.SerializeToString(deterministic=True)
    prepared=ssm.inspect_invoke(
        wire,trusted_origin=origin,
        approved_stream_id=STREAM,
        approved_model_context_sha256=context,
        anchor_revision=2,
        anchor_digest=bytes.fromhex(prior["checkpoint_sha256"]),
        source_cursor="event-001",last_observation_time=.3,
        last_watermark_time=.3,sensor_dimension=1)
    result=journal.process(EVENT,kind="increment",end_time=1.,increment=[.1])
    assert result["status"]=="committed" and result["emitted"]==1
    current=journal.status()
    assert current["revision"]==3 and current["pending_outputs"]==1
    typed_out=ssm_pb2.SsmAdvanceResult(
       stream_id=STREAM,event_id=EVENT,
       disposition=ssm_pb2.ADVANCE_DISPOSITION_COMMITTED,
       observed_revision=3,
       observed_checkpoint_sha256=bytes.fromhex(current["checkpoint_sha256"]),
       request_sha256=bytes.fromhex(prepared.typed_request_sha256),
       pending_release_count=1)
    terminal=lu.OperationReceipt(
       operation_ref=EVENT,state=lu.TERMINAL_STATE_APPLIED,
       durable_receipt_sha256=hashlib.sha256(b"source-only locator").digest(),
       output=lu.TypedValue(type_url=ssm.OUTPUT_URL,
           encoded_message=typed_out.SerializeToString(deterministic=True)))
    broker=OriginalOperationKeyBroker()
    anchor=TestIndependentRevisionAnchor()
    kw=dict(directory=str(tmp_path/"original-lu-log"),
      broker=broker,anchor=anchor,trusted_origin=origin,
      request_id=REQUEST,core_session_ref=SESSION,
      core_epoch_ref=EPOCH,prepared=prepared,original_invoke=wire)
    verifier=life.DurableLuOperationVerifier(
        kw["directory"],broker,anchor,
        trusted_origin=origin,request_id=REQUEST,
        core_session_ref=SESSION,core_epoch_ref=EPOCH,
        prepared=prepared,original_invoke=wire)
    obj=dict(
        journal=journal,verifier=verifier,origin=origin,
        terminal=terminal,context=context,r6_status=current,
        key_provider=key_provider,revision=revision,allowed=allowed,
        local_broker=broker,local_anchor=anchor,kwargs=kw,tmp=tmp_path)
    yield obj
    verifier.close()
    journal.close()


def raw_frame(obj,field,body,seq=0):
    frame=lu.WorkspaceFrame(protocol_major=1,protocol_minor=0,
        request_id=REQUEST,session_ref=SESSION,sequence=seq)
    getattr(frame,field).CopyFrom(body)
    return frame.SerializeToString(deterministic=True)


def reconcile_terminal(obj,*,cancel=False,uncertain=False):
    o=obj["verifier"]
    if cancel:
        o.note_cancel("operator_cancel")
        o.observe_frame(raw_frame(obj,"cancel_ack",lu.CancelAcknowledged(
            operation_ref=EVENT,signal_recorded=True)))
    o.note_credit(1,0)
    o.observe_frame(raw_frame(obj,"operation_event",lu.OperationEvent(
        operation_ref=EVENT,terminal=obj["terminal"]),seq=1))
    o.note_reconcile_request()
    if uncertain:
        observed=lu.OperationReceipt(operation_ref=EVENT,
                                    state=lu.TERMINAL_STATE_UNCERTAIN)
        available=False
    else:
        observed=obj["terminal"]
        available=True
    o.observe_frame(raw_frame(obj,"reconciled",lu.ReconciledOperation(
          observed=observed,evidence_available=available)))


def observe(obj,**changes):
    kw=dict(
        verifier=obj["verifier"],journal=obj["journal"],
        trusted_lu_origin=obj["origin"],
        trusted_core_session_ref=SESSION,
        trusted_core_epoch_ref=EPOCH,
        trusted_mel_scope=S)
    kw.update(changes)
    return bridge.reconcile_unpublished_r6_outbox(**kw)


def test_real_r6_auth_outbox_is_durably_correlated_but_never_delivered(combined):
    reconcile_terminal(combined)
    o=observe(combined)
    assert o["original_operation_ref"]==EVENT
    assert o["original_output_count"]==1
    assert o["observed_checkpoint_revision"]==3
    assert len(o["local_snapshot_sha256"])==64
    assert o["original_R6_pending_rows_verified_by_R6"]
    assert not o["installed_Lu_Core_authentication_verified"]
    assert not o["delivery_authorized"]
    assert not o["acknowledgment_authorized"]
    assert not o["publication_authorized"]
    assert combined["journal"].status()["pending_outputs"]==1
    assert combined["verifier"].status()["outbox_snapshot_recorded"]


def test_outbox_snapshot_survives_original_lu_log_restart_and_replay_refusal(combined):
    reconcile_terminal(combined)
    accepted=observe(combined)
    before=combined["verifier"].status()
    combined["verifier"].close()
    kw=combined["kwargs"]
    reopened=life.DurableLuOperationVerifier(
        kw["directory"],kw["broker"],kw["anchor"],
        trusted_origin=kw["trusted_origin"],request_id=kw["request_id"],
        core_session_ref=kw["core_session_ref"],
        core_epoch_ref=kw["core_epoch_ref"],prepared=kw["prepared"],
        original_invoke=kw["original_invoke"])
    combined["verifier"]=reopened
    assert reopened.status()==before
    assert reopened.status()["original_outbox_snapshot_sha256"]==accepted["local_snapshot_sha256"]
    with pytest.raises(ValueError,match="lifecycle refused"):
        observe(combined)


def test_repeat_snapshot_and_changed_result_cannot_start_new_delivery(combined):
    reconcile_terminal(combined)
    observe(combined)
    with pytest.raises(ValueError,match="outbox reconciliation refused"):
        observe(combined)
    with pytest.raises(ValueError,match="lifecycle refused"):
        combined["verifier"].note_outbox_snapshot(
           stream_id=STREAM,event_id=EVENT,revision=3,
           checkpoint_sha256=combined["r6_status"]["checkpoint_sha256"],
           outputs=[])


def test_no_original_reconcile_or_synthetic_terminal_alone_cannot_verify_outbox(combined):
    with pytest.raises(ValueError,match="outbox reconciliation refused"):
        observe(combined)
    combined["verifier"].note_credit(1,0)
    combined["verifier"].observe_frame(raw_frame(combined,
        "operation_event",lu.OperationEvent(
            operation_ref=EVENT,terminal=combined["terminal"]),seq=1))
    with pytest.raises(ValueError,match="outbox reconciliation refused"):
        observe(combined)


def test_unavailable_ambiguous_reconcile_never_retries_or_publishes(combined):
    reconcile_terminal(combined,uncertain=True)
    assert combined["verifier"].status()["reconciliation_status"]=="unknown"
    with pytest.raises(ValueError,match="outbox reconciliation refused"):
        observe(combined)
    assert combined["journal"].status()["pending_outputs"]==1


def test_cancel_ack_is_not_worker_termination_or_delivery_permission(combined):
    reconcile_terminal(combined,cancel=True)
    assert combined["verifier"].status()["cancellation_signal_recorded"]
    assert not combined["verifier"].status()["worker_termination_verified"]
    with pytest.raises(ValueError,match="outbox reconciliation refused"):
        observe(combined)


def test_revocation_blocks_outbox_after_matched_terminal(combined):
    reconcile_terminal(combined)
    combined["verifier"].note_revoke("host_revocation")
    with pytest.raises(ValueError,match="outbox reconciliation refused"):
        observe(combined)
    assert combined["journal"].status()["pending_outputs"]==1


def test_uncertain_delivery_hold_is_durable_one_way_and_refuses_second_hold(combined):
    reconcile_terminal(combined)
    hold=bridge.record_uncertain_delivery_hold(
        combined["verifier"],"delivery_confirmation_missing")
    assert hold["status"]=="uncertain_held_for_external_authoritative_reconciliation"
    assert not hold["retry_authorized"]
    assert not hold["acknowledgment_authorized"]
    assert combined["verifier"].status()["uncertain_hold"]
    with pytest.raises(ValueError,match="outbox reconciliation refused"):
        observe(combined)
    with pytest.raises(ValueError,match="lifecycle refused"):
        bridge.record_uncertain_delivery_hold(
            combined["verifier"],"second_recovery_attempt")


@pytest.mark.parametrize("changed",[
    {"trusted_core_session_ref":"foreign-session"},
    {"trusted_core_epoch_ref":"foreign-epoch"},
    {"trusted_mel_scope":mel.Scope("other","workspace","subject","turn")},
    {"trusted_mel_scope":mel.Scope("session","other","subject","turn")},
])
def test_cross_session_epoch_and_workspace_isolation(combined,changed):
    reconcile_terminal(combined)
    with pytest.raises(ValueError,match="outbox reconciliation refused"):
        observe(combined,**changed)


def test_lu_origin_mismatch_cannot_claim_r6_pending_output(combined):
    reconcile_terminal(combined)
    foreign=lu.OriginRefs()
    foreign.CopyFrom(combined["origin"])
    foreign.user_turn_ref="foreign-turn"
    with pytest.raises(ValueError,match="outbox reconciliation refused"):
        observe(combined,trusted_lu_origin=foreign)


def test_r6_revoked_host_policy_fails_closed_without_snapshot(combined):
    reconcile_terminal(combined)
    combined["allowed"]["active"]=False
    with pytest.raises(ValueError,match="MEL SSM journal refused"):
        observe(combined)
    assert not combined["verifier"].status()["outbox_snapshot_recorded"]


def test_authenticated_r6_outbox_tamper_refused_before_local_snapshot(combined):
    reconcile_terminal(combined)
    conn=sqlite3.connect(combined["tmp"]/"source-r6.sqlite")
    try:
        conn.execute("UPDATE output_outbox SET body=?",(b"forged",))
        conn.commit()
    finally:conn.close()
    with pytest.raises(ValueError,match="MEL SSM journal refused"):
        observe(combined)
    assert not combined["verifier"].status()["outbox_snapshot_recorded"]


def test_already_acknowledged_r6_output_cannot_be_inferred_as_published(combined):
    reconcile_terminal(combined)
    pending=combined["journal"].pending_outputs()
    combined["journal"].acknowledge(pending[0]["output_id"],pending[0]["body_sha"])
    with pytest.raises(ValueError,match="lifecycle refused"):
        observe(combined)
    assert combined["verifier"].status()["outbox_snapshot_recorded"] is False


def test_concurrently_advanced_r6_checkpoint_rejected(combined):
    reconcile_terminal(combined)
    combined["journal"].process("event-003",kind="increment",
                                end_time=1.3,increment=[.2])
    with pytest.raises(ValueError,match="outbox reconciliation refused"):
        observe(combined)


def test_external_original_lu_anchor_stale_rejected_before_outbox_snapshot(combined):
    reconcile_terminal(combined)
    rev,digest=combined["local_anchor"].record
    combined["local_anchor"].record=(rev-1,"0"*64)
    with pytest.raises(ValueError,match="lifecycle refused"):
        observe(combined)


def test_local_lu_sqlite_rollback_after_outbox_snapshot_detected(combined):
    reconcile_terminal(combined)
    path=Path(combined["kwargs"]["directory"])/"cognitum_lu_ipc01d_r1.sqlite3"
    combined["verifier"].close()
    copy=combined["tmp"]/"pre-outbox.sqlite3"
    shutil.copy2(path,copy)
    kw=combined["kwargs"]
    def reopen():
        return life.DurableLuOperationVerifier(
            kw["directory"],kw["broker"],kw["anchor"],
            trusted_origin=kw["trusted_origin"],request_id=kw["request_id"],
            core_session_ref=kw["core_session_ref"],
            core_epoch_ref=kw["core_epoch_ref"],prepared=kw["prepared"],
            original_invoke=kw["original_invoke"])
    combined["verifier"]=reopen()
    observe(combined)
    combined["verifier"].close()
    shutil.copy2(copy,path)
    with pytest.raises(ValueError,match="lifecycle refused"):
        reopen()


def test_original_lu_anchor_outage_stalls_without_implicit_recovery(combined):
    reconcile_terminal(combined)
    combined["local_anchor"].refuse=True
    with pytest.raises(ValueError,match="lifecycle refused"):
        observe(combined)
    with pytest.raises(ValueError,match="lifecycle refused"):
        combined["verifier"].status()
    assert combined["journal"].status()["pending_outputs"]==1


def test_no_automatic_ack_server_model_dispatch_or_replay_credential(combined):
    assert not hasattr(bridge,"publish")
    assert not hasattr(bridge,"acknowledge")
    assert not hasattr(bridge,"dispatch")
    assert not hasattr(bridge,"grant")
    assert not hasattr(bridge,"start_server")
    assert not hasattr(bridge,"retry_unconfirmed")
    assert combined["journal"].status()["pending_outputs"]==1
    assert not combined["verifier"].status()["result_publication_authorized"]
