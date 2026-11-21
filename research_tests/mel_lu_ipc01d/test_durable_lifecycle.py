"""COG-LU-IPC-01D-R1: local verifier, not installed Lu or authoritative OS evidence."""
from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import sqlite3

import pytest

from cognitum.mel import lu_ipc_lifecycle as life
from cognitum.mel import lu_ssm_contract as ssm
from cognitum.mel.vendor.lu.workspace.v0 import workspace_pb2 as lu
from cognitum.mel.vendor.cognitum.ssm.v1 import ssm_pb2 as ssm_pb
from research_tests.mel_lu_ipc01c.test_typed_ssm_contract import (
    ORIGIN, typed_input, invoke, inspect, STREAM, DIG
)

SESSION="core-session-original-1"
EPOCH="core-epoch-original-1"
REQUEST="req-original-1"
KEY=bytes(range(1,33))


class TestKeyBroker:
    def __init__(self):
        self.enabled=True
        self.key=KEY
    def borrow_key(self, scope, operation_ref):
        assert scope[-1]==operation_ref==ORIGIN.operation_ref
        return self.key if self.enabled else None


class TestIndependentRevisionAnchor:
    """In-memory independently supplied operator fixture, NOT OS authority."""
    def __init__(self):
        self.record=(0,life.ZERO)
        self.refuse=False
    def read(self,scope,operation_ref):
        assert scope[-1]==operation_ref
        return self.record
    def advance(self,scope,operation_ref,old_rev,old_sha,new_rev,new_sha):
        assert scope[-1]==operation_ref
        if self.refuse or self.record!=(old_rev,old_sha):return False
        assert new_rev==old_rev+1
        self.record=(new_rev,new_sha)
        return True


@pytest.fixture
def env(tmp_path):
    scope=dict(
        directory=str(tmp_path/"host-owned-cog-ipc"),
        broker=TestKeyBroker(),
        anchor=TestIndependentRevisionAnchor(),
        trusted_origin=ORIGIN,
        request_id=REQUEST,
        core_session_ref=SESSION,
        core_epoch_ref=EPOCH,
        prepared=inspect(invoke()),
        original_invoke=invoke(),
    )
    return scope


def open_verifier(env):
    return life.DurableLuOperationVerifier(
        env["directory"],env["broker"],env["anchor"],
        trusted_origin=env["trusted_origin"],
        request_id=env["request_id"],
        core_session_ref=env["core_session_ref"],
        core_epoch_ref=env["core_epoch_ref"],
        prepared=env["prepared"],original_invoke=env["original_invoke"])


def frame(field,body,seq=0,*,session=SESSION,request=REQUEST):
    m=lu.WorkspaceFrame(protocol_major=1,protocol_minor=0,
           request_id=request,session_ref=session,sequence=seq)
    getattr(m,field).CopyFrom(body)
    return m.SerializeToString(deterministic=True)


def progress(seq=1,stage="bounded",percent=15,*,session=SESSION,request=REQUEST):
    return frame("operation_event",lu.OperationEvent(
       operation_ref=ORIGIN.operation_ref,
       progress=lu.OperationProgress(stage_code=stage,percent=percent)),
       seq,session=session,request=request)


def completed_receipt(prepared,*, disposition=ssm_pb.ADVANCE_DISPOSITION_COMMITTED,
                      revision=2, checkpoint=b"\x11"*32, request_sha=None):
    typed=ssm_pb.SsmAdvanceResult(
        stream_id=STREAM,event_id=ORIGIN.operation_ref,
        disposition=disposition,observed_revision=revision,
        observed_checkpoint_sha256=checkpoint,
        request_sha256=(request_sha or bytes.fromhex(
            prepared.typed_request_sha256)),pending_release_count=0)
    return lu.OperationReceipt(
        operation_ref=ORIGIN.operation_ref,state=lu.TERMINAL_STATE_APPLIED,
        durable_receipt_sha256=hashlib.sha256(b"untrusted host receipt locator").digest(),
        output=lu.TypedValue(type_url=ssm.OUTPUT_URL,
            encoded_message=typed.SerializeToString(deterministic=True)))


def terminal(prepared,seq=2,*,receipt=None,session=SESSION,request=REQUEST):
    return frame("operation_event",lu.OperationEvent(
       operation_ref=ORIGIN.operation_ref,
       terminal=receipt or completed_receipt(prepared)),seq,
       session=session,request=request)


def reconciled(*,receipt,available=True):
    return frame("reconciled",lu.ReconciledOperation(
         observed=receipt,evidence_available=available))


def test_bootstrap_is_inert_locally_durable_and_exact_origin(env):
    o=open_verifier(env)
    try:
        s=o.status()
        assert s["durable_local_revision"]==1
        assert s["last_sequence"]==0
        assert s["remaining_credits"]==0
        assert s["status"]=="observing"
        assert s["operation_ref"]==ORIGIN.operation_ref
        assert s["local_head_mac_sha256"]==env["anchor"].record[1]
        assert not s["result_publication_authorized"]
        assert not s["domain_execution_authorized"]
        assert not s["signed_core_receipt_verified"]
    finally:o.close()


def test_credit_progress_terminal_and_external_reconcile_never_grant(env):
    o=open_verifier(env)
    try:
        o.note_credit(2,0)
        o.observe_frame(progress())
        o.observe_frame(terminal(env["prepared"]))
        s=o.status()
        assert s["original_terminal_observed"]
        assert s["last_sequence"]==2
        assert s["remaining_credits"]==0
        assert s["reconciliation_status"]=="not_requested"
        o.note_reconcile_request()
        o.observe_frame(reconciled(receipt=completed_receipt(env["prepared"])))
        s=o.status()
        assert s["reconciliation_status"]=="matched"
        assert s["status"]=="reconciled_candidate"
        assert s["worker_termination_verified"] is False
        assert s["result_publication_authorized"] is False
    finally:o.close()


def test_restart_replays_original_hmac_chain_and_preserves_receipts(env):
    o=open_verifier(env)
    o.note_credit(2,0)
    o.observe_frame(progress())
    o.observe_frame(terminal(env["prepared"]))
    before=o.status()
    o.close()
    again=open_verifier(env)
    try:
        after=again.status()
        assert after==before
        again.note_reconcile_request()
        again.observe_frame(reconciled(receipt=completed_receipt(env["prepared"])))
        assert again.status()["reconciliation_status"]=="matched"
    finally:again.close()


def test_cancel_ack_is_only_signal_not_worker_exit(env):
    o=open_verifier(env)
    try:
        o.note_cancel("operator_cancel")
        o.observe_frame(frame("cancel_ack",
            lu.CancelAcknowledged(operation_ref=ORIGIN.operation_ref,
                                  signal_recorded=True)))
        s=o.status()
        assert s["cancellation_signal_recorded"]
        assert s["status"]=="cancel_signalled_not_terminated"
        assert not s["original_terminal_observed"]
        assert not s["worker_termination_verified"]
        assert not s["result_publication_authorized"]
    finally:o.close()


@pytest.mark.parametrize("acked",[
    lu.CancelAcknowledged(operation_ref=ORIGIN.operation_ref,signal_recorded=True),
    lu.CancelAcknowledged(operation_ref="foreign",signal_recorded=True),
    lu.CancelAcknowledged(operation_ref=ORIGIN.operation_ref,signal_recorded=False),
])
def test_cancel_ack_without_prior_intent_or_signal_refused(env,acked):
    o=open_verifier(env)
    try:
        with pytest.raises(ValueError,match="lifecycle refused"):
            o.observe_frame(frame("cancel_ack",acked))
    finally:o.close()


def test_duplicate_original_cancel_and_conflicting_cancel_refused(env):
    o=open_verifier(env)
    try:
        o.note_cancel("operator_cancel")
        with pytest.raises(ValueError,match="lifecycle refused"):
            o.note_cancel("operator_cancel")
        with pytest.raises(ValueError,match="lifecycle refused"):
            o.note_cancel("different_cancel")
    finally:o.close()


@pytest.mark.parametrize("bad",[
    {"additional":0,"ack":0},
    {"additional":65,"ack":0},
    {"additional":1,"ack":1},
])
def test_credit_overflow_or_premature_ack_refused(env,bad):
    o=open_verifier(env)
    try:
        with pytest.raises(ValueError,match="lifecycle refused"):
            o.note_credit(bad["additional"],bad["ack"])
    finally:o.close()


def test_uncredited_and_out_of_order_progress_refused(env):
    o=open_verifier(env)
    try:
        with pytest.raises(ValueError,match="lifecycle refused"):
            o.observe_frame(progress())
        o.note_credit(1,0)
        with pytest.raises(ValueError,match="lifecycle refused"):
            o.observe_frame(progress(seq=2))
        o.observe_frame(progress())
        with pytest.raises(ValueError,match="lifecycle refused"):
            o.observe_frame(progress())
    finally:o.close()


@pytest.mark.parametrize("kwargs",[
    {"session":"foreign-session"},
    {"request":"foreign-request"},
])
def test_foreign_core_session_or_request_refused(env,kwargs):
    o=open_verifier(env)
    try:
        o.note_credit(1,0)
        with pytest.raises(ValueError,match="session/request"):
            o.observe_frame(progress(**kwargs))
    finally:o.close()


def test_original_user_turn_and_operation_reopen_identity_refused(env):
    o=open_verifier(env);o.close()
    copy=dict(env)
    origin=lu.OriginRefs()
    origin.CopyFrom(ORIGIN)
    origin.user_turn_ref="forged-turn"
    copy["trusted_origin"]=origin
    with pytest.raises(ValueError,match="lifecycle refused"):
        open_verifier(copy)
    copy=dict(env,core_epoch_ref="forged-epoch")
    with pytest.raises(ValueError,match="lifecycle refused"):
        open_verifier(copy)


@pytest.mark.parametrize("variant",[
    "wrong_input_type","wrong_operation","malformed","wrong_prepared",
])
def test_begin_refuses_unreviewed_or_mutated_typed_invoke(env,variant):
    e=dict(env)
    if variant=="wrong_input_type":
        w=lu.CapabilityInvoke.FromString(invoke())
        w.input.type_url="type.googleapis.com/foreign"
        e["original_invoke"]=w.SerializeToString(deterministic=True)
    elif variant=="wrong_operation":
        w=lu.CapabilityInvoke.FromString(invoke())
        w.origin.operation_ref="foreign-event"
        e["original_invoke"]=w.SerializeToString(deterministic=True)
    elif variant=="malformed":
        e["original_invoke"]=invoke()+b"\x80\x06\x01"
    else:
        e["prepared"]=inspect(invoke(typed_input(increment=[0.])))
    with pytest.raises(ValueError,match="lifecycle refused"):
        open_verifier(e)


def test_reconciliation_without_terminal_evidence_is_unknown_not_applied(env):
    o=open_verifier(env)
    try:
        o.note_reconcile_request()
        report=lu.OperationReceipt(operation_ref=ORIGIN.operation_ref,
                                   state=lu.TERMINAL_STATE_UNSPECIFIED)
        o.observe_frame(reconciled(receipt=report,available=False))
        s=o.status()
        assert s["reconciliation_status"]=="unknown"
        assert not s["original_terminal_observed"]
        assert not s["result_publication_authorized"]
    finally:o.close()


@pytest.mark.parametrize("variant",["no_request","bad_terminal","fake_evidence"])
def test_reconciled_event_must_match_original_terminal_and_requested_origin(env,variant):
    o=open_verifier(env)
    try:
        o.note_credit(1,0)
        o.observe_frame(terminal(env["prepared"],seq=1))
        if variant!="no_request":
            o.note_reconcile_request()
        altered=completed_receipt(env["prepared"])
        if variant=="bad_terminal":altered.durable_receipt_sha256=b"\xaa"*32
        with pytest.raises(ValueError,match="lifecycle refused"):
            if variant=="fake_evidence":
                altered.state=lu.TERMINAL_STATE_UNCERTAIN
                o.observe_frame(reconciled(receipt=altered,available=False))
            else:
                o.observe_frame(reconciled(receipt=altered))
    finally:o.close()


@pytest.mark.parametrize("bad",[
    lu.TERMINAL_STATE_UNSPECIFIED,
    lu.TERMINAL_STATE_APPLIED,
])
def test_terminal_empty_or_forged_domain_receipt_refused(env,bad):
    o=open_verifier(env)
    try:
        o.note_credit(1,0)
        receipt=completed_receipt(env["prepared"])
        if bad==lu.TERMINAL_STATE_UNSPECIFIED:receipt.state=bad
        else:receipt.output.encoded_message=b"\x01"
        with pytest.raises(ValueError,match="refused"):
            o.observe_frame(terminal(env["prepared"],seq=1,receipt=receipt))
    finally:o.close()


@pytest.mark.parametrize("state",[
    lu.TERMINAL_STATE_REFUSED,lu.TERMINAL_STATE_FAILED,
    lu.TERMINAL_STATE_CANCELLED,lu.TERMINAL_STATE_UNCERTAIN,
])
def test_non_applied_terminal_requires_no_domain_payload(env,state):
    o=open_verifier(env)
    try:
        o.note_credit(1,0)
        receipt=lu.OperationReceipt(
            operation_ref=ORIGIN.operation_ref,state=state,
            durable_receipt_sha256=hashlib.sha256(b"original-lu-locator").digest(),
            reason_code="original_host_denial")
        o.observe_frame(terminal(env["prepared"],seq=1,receipt=receipt))
        s=o.status()
        assert s["original_terminal_observed"]
        assert not s["result_publication_authorized"]
    finally:o.close()


def test_revoke_blocks_new_progress_but_not_original_reconciliation(env):
    o=open_verifier(env)
    try:
        o.note_credit(1,0)
        o.note_revoke("host_revocation")
        assert o.status()["status"]=="revoked"
        with pytest.raises(ValueError,match="lifecycle refused"):
            o.observe_frame(progress())
        o.note_reconcile_request()
        o.observe_frame(reconciled(
             receipt=lu.OperationReceipt(operation_ref=ORIGIN.operation_ref,
                  state=lu.TERMINAL_STATE_UNCERTAIN),available=False))
        assert o.status()["reconciliation_status"]=="unknown"
        assert o.status()["status"]=="revoked"
    finally:o.close()


def test_corrupted_original_sqlite_mac_or_row_refused(env):
    o=open_verifier(env)
    o.note_credit(2,0);o.close()
    path=Path(env["directory"])/"cognitum_lu_ipc01d_r1.sqlite3"
    conn=sqlite3.connect(path)
    try:
        conn.execute("UPDATE journal SET body=? WHERE seq=2",(b"evil",))
        conn.commit()
    finally:conn.close()
    with pytest.raises(ValueError,match="lifecycle refused"):
        open_verifier(env)


def test_external_monotonic_anchor_refuses_old_database_rollback(env,tmp_path):
    o=open_verifier(env)
    path=Path(env["directory"])/"cognitum_lu_ipc01d_r1.sqlite3"
    safe=tmp_path/"original.sqlite3"
    o.close()
    shutil.copy2(path,safe)
    o=open_verifier(env)
    o.note_credit(1,0)
    o.close()
    shutil.copy2(safe,path)
    with pytest.raises(ValueError,match="independent anchor"):
        open_verifier(env)


def test_host_key_revocation_blocks_new_reads_and_writes(env):
    o=open_verifier(env)
    env["broker"].enabled=False
    try:
        with pytest.raises(ValueError,match="key unavailable"):
            o.status()
        with pytest.raises(ValueError,match="key unavailable"):
            o.note_credit(1,0)
    finally:o.close()


def test_host_anchor_failure_after_local_commit_is_uncertain_not_silent(env):
    o=open_verifier(env)
    env["anchor"].refuse=True
    try:
        with pytest.raises(ValueError,match="anchor advancement"):
            o.note_credit(1,0)
        with pytest.raises(ValueError,match="trusted anchor"):
            o.status()
    finally:o.close()
    with pytest.raises(ValueError,match="independent anchor"):
        open_verifier(env)


def test_no_execution_grant_model_registration_or_authoritative_broker(env):
    o=open_verifier(env)
    try:
        assert not hasattr(o,"dispatch")
        assert not hasattr(o,"execute")
        assert not hasattr(o,"register")
        assert not hasattr(o,"publish")
        assert not hasattr(o,"grant")
        assert not o.status()["source_verified_through_independent_lu_core"]
    finally:o.close()
