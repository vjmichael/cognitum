"""COG-LU-IPC-01E-R1: source-only R6 outbox / Lu operation reconciliation.

A host-typed, independently trusted MEL Scope, accepted R6 HostSSMJournal,
and accepted 01D DurableLuOperationVerifier must already exist. This code
does not create a Core session, invoke mathematical work, issue a grant,
deliver outputs, ack external results, resolve Lu ObjectRefs, or assume a
local HMAC/SQLite receipt authenticates Lu Core. It persists ONLY one complete
opaque output ID/body SHA inventory to the 01D anchored audit log.

Policy: ambiguous source, missing independent producer, absent/cancelled Lu
terminal, replayed/acked/missing R6 outbox, foreign scope, or concurrent
checkpoint changes all fail CLOSED. No implicit retry after crash/uncertainty.
"""
from __future__ import annotations

from hashlib import sha256
import hmac
from . import ssm_recovery as r6
from . import admission as mel
from . import lu_ssm_contract as typed
from . import lu_ipc_lifecycle as life
from .vendor.lu.workspace.v0 import workspace_pb2 as lu

MAX_PAGE = 256


def _need(ok, what):
    if not ok:
        raise ValueError("Cognitum Lu outbox reconciliation refused: " + what)


def reconcile_unpublished_r6_outbox(verifier, journal, *,
                                    trusted_lu_origin, trusted_core_session_ref,
                                    trusted_core_epoch_ref, trusted_mel_scope):
    """One original-authority-checked, unpublishable audit snapshot.

    R6 verifies the keyed checkpoint, event chain and each pending output MAC;
    01D verifies original authenticated-session claims against externally
    injected origin, host key and revision anchor. This *local* verification
    does not verify signed Lu Core provenance. The installed host remains
    responsible for that, and for all future delivery/ack decisions.
    """
    _need(type(verifier) is life.DurableLuOperationVerifier,
          "reviewed durable Lu operation verifier only")
    _need(type(journal) is r6.HostSSMJournal,
          "reviewed authenticated R6 host journal only")
    _need(type(trusted_mel_scope) is mel.Scope,
          "trusted MEL Scope required")
    _need(type(trusted_lu_origin) is lu.OriginRefs,
          "trusted host original Lu OriginRefs required")
    scope=typed._origin(trusted_lu_origin)
    _need(tuple(verifier._origin)==scope and
          verifier._session==trusted_core_session_ref and
          verifier._epoch==trusted_core_epoch_ref and
          verifier._op==scope[-1] and
          verifier._prepared.original_operation_ref==scope[-1] and
          journal._sid==verifier._prepared.stream_id and
          journal._scope==trusted_mel_scope and
          trusted_mel_scope.workspace==scope[0] and
          trusted_mel_scope.turn==scope[2],
          "cross-session, MEL scope or original operation identity mismatch")
    before=verifier.status()
    _need(before["reconciliation_status"]=="matched" and
          before["original_terminal_observed"] and
          not before["cancellation_requested"] and
          not before["cancellation_signal_recorded"] and
          not before["uncertain_hold"] and
          before["status"]=="reconciled_candidate" and
          not before["outbox_snapshot_recorded"] and
          not before["result_publication_authorized"],
          "missing original terminal/authoritative reconciliation or held operation")

    # The native accepted R6 journal uses MEL admission's existing host RLock.
    # Acquire that lock across both R6 reads: observe a single source revision,
    # including original pending outbox rows that have been HMAC verified.
    with journal._admission._lock:
        first=journal.status()
        count=first["pending_outputs"]
        _need(type(count) is int and 0<=count<=MAX_PAGE,
              "complete bounded outbox page required; no truncation")
        page=journal.pending_outputs(limit=MAX_PAGE)
        second=journal.status()
        _need(first["revision"]==second["revision"] and
              first["checkpoint_sha256"]==second["checkpoint_sha256"] and
              first["pending_outputs"]==second["pending_outputs"] and
              len(page)==count and
              first["revision"]==verifier._prepared.expected_revision+1,
              "atomic original checkpoint revision/pending inventory mismatch")
        output_rows=[]
        for entry in page:
            _need(type(entry) is dict and
                  set(entry)=={"output_id","body_sha","event_id","receipt",
                               "publish_authorized"},
                  "reviewed authenticated R6 pending output shape")
            result=entry["receipt"]
            _need(type(result) is dict and
                  entry["event_id"]==scope[-1] and
                  result.get("stream_id")==journal._sid and
                  result.get("event_id")==scope[-1] and
                  result.get("schema")==r6.OUTPUT_SCHEMA and
                  result.get("revision")==first["revision"] and
                  result.get("execution_authorized") is False and
                  result.get("numerical_certified") is False and
                  entry["publish_authorized"] is False,
                  "foreign, stale or privileged outbox receipt candidate")
            _need(type(entry["output_id"]) is str and
                  type(entry["body_sha"]) is str and
                  len(entry["output_id"])==64 and len(entry["body_sha"])==64,
                  "bounded original receipt identities")
            output_rows.append(dict(output_id=entry["output_id"],
                                    body_sha256=entry["body_sha"]))
        output_rows.sort(key=lambda x:x["output_id"])
        # Revalidate 01D source before durable commit; its append also
        # recomputes the complete event+anchor chain atomically under its lock.
        _need(verifier.status()==before,
              "Lu original operation changed while inspecting R6 outbox")
        verified=verifier.note_outbox_snapshot(
            stream_id=journal._sid,event_id=scope[-1],
            revision=first["revision"],
            checkpoint_sha256=first["checkpoint_sha256"],
            outputs=output_rows)
    _need(verified["outbox_snapshot_recorded"] and
          verified["original_outbox_output_count"]==len(output_rows) and
          not verified["result_publication_authorized"] and
          not verified["retry_or_acknowledgment_authorized"],
          "durable but unpublishable original inventory")
    return dict(
        schema="cognitum.lu_ipc01e_r1.observed_unpublished_outbox.v1",
        original_operation_ref=scope[-1],
        original_stream_ref=journal._sid,
        observed_checkpoint_revision=first["revision"],
        original_output_count=len(output_rows),
        local_snapshot_sha256=verified["original_outbox_snapshot_sha256"],
        lu_terminal_candidate_correlated=True,
        original_R6_pending_rows_verified_by_R6=True,
        installed_Lu_Core_authentication_verified=False,
        revision_authority_independently_installed=False,
        retry_authorized=False,
        delivery_authorized=False,
        acknowledgment_authorized=False,
        publication_authorized=False,
    )


def record_uncertain_delivery_hold(verifier, reason_code):
    """Only add an original-source durable UNCERTAIN hold; no recovery bypass."""
    _need(type(verifier) is life.DurableLuOperationVerifier,
          "reviewed Lu original source verifier only")
    state=verifier.note_uncertain_hold(reason_code)
    _need(state["uncertain_hold"] and not state["result_publication_authorized"],
          "durable uncertainty and no publication")
    return dict(
        status="uncertain_held_for_external_authoritative_reconciliation",
        durable_local_revision=state["durable_local_revision"],
        operation_ref=state["operation_ref"],
        retry_authorized=False,
        delivery_authorized=False,
        acknowledgment_authorized=False,
        publication_authorized=False,
        installed_Lu_Core_provenance_verified=False,
    )
