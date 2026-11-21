"""COG-LU-IPC-01D-R1: unprivileged, durable Lu operation verifier.

The original Lu workspace v0 Protobuf defines operation identity, bounded
stream events, cancel ACK semantics and reconciliation. This is a Cognitum-
owned *observer*, not an IPC dispatch/server, user-turn grant, signed Core
receipt verifier, installed service or mathematical worker. Every accepted
candidate remains unpublishable.

Trusted external host must supply original OriginRefs, request/session/epoch,
an independently enrolled HMAC key broker and an *independently authoritative*
monotonic anchor. Local SQLite plus HMAC by themselves are NOT anti-rollback or
protected installed custody. The test doubles are not evidence of either.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
from threading import RLock

from google.protobuf.message import DecodeError
from .vendor.lu.workspace.v0 import workspace_pb2 as lu
from . import lu_ssm_contract as ssm
from .vendor.cognitum.ssm.v1 import ssm_pb2

PROFILE = "cognitum.lu_ipc01d_r1.local_operation_verifier.v1"
DOMAIN = b"Cognitum.Lu.IPC01D.LocalObserver.HMAC.v1\x00"
ZERO = "0" * 64
MAX_RECORDS = 256
MAX_FRAME = 65536
MAX_CREDIT = 64
REFERENCE = re.compile(r"[A-Za-z0-9_.:/-]{1,128}\Z", re.ASCII)
REASON = re.compile(r"[A-Za-z0-9_.:/-]{1,96}\Z", re.ASCII)
ACTIONS = frozenset(("begin","credit","progress","terminal","cancel",
                     "cancel_ack","reconcile","reconciled","revoke",
                     "outbox_snapshot","uncertain_hold"))
TERMINAL = frozenset((lu.TERMINAL_STATE_APPLIED,
    lu.TERMINAL_STATE_REFUSED,lu.TERMINAL_STATE_FAILED,
    lu.TERMINAL_STATE_CANCELLED,lu.TERMINAL_STATE_UNCERTAIN))


def _need(ok, reason):
    if not ok:
        raise ValueError("Cognitum IPC lifecycle refused: " + reason)


def _text(value, why, pattern=REFERENCE):
    _need(type(value) is str and pattern.fullmatch(value) is not None, why)
    return value


def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),
                      ensure_ascii=True,allow_nan=False).encode("ascii")


def _strict(raw, cls):
    _need(type(raw) is bytes and 0<len(raw)<=MAX_FRAME,
          "bounded Protobuf frame")
    try:
        msg=cls.FromString(raw)
    except (DecodeError, ValueError, RecursionError) as exc:
        raise ValueError("Cognitum IPC lifecycle refused: malformed Protobuf") from exc
    msg.DiscardUnknownFields()
    _need(msg.SerializeToString(deterministic=True)==raw,
          "noncanonical/unknown Protobuf")
    return msg


def _scope(origin):
    return ssm._origin(origin)


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _key(provider, scope, op):
    _need(callable(getattr(provider,"borrow_key",None)),
          "installed host key provider required")
    key=provider.borrow_key(scope,op)
    _need(type(key) is bytes and 32<=len(key)<=128 and any(key),
          "host-owned authentication key unavailable")
    return key


def _trust_read(provider,scope,op):
    _need(callable(getattr(provider,"read",None)) and
          callable(getattr(provider,"advance",None)),
          "independent authoritative revision provider required")
    result=provider.read(scope,op)
    _need(type(result) is tuple and len(result)==2 and
          type(result[0]) is int and 0<=result[0]<=MAX_RECORDS and
          type(result[1]) is str and re.fullmatch(r"[0-9a-f]{64}",result[1]),
          "trusted anchor revision/chain shape")
    return result


def _secure_path(directory):
    _need(type(directory) is str and
          Path(directory).is_absolute(),"host-owned absolute journal directory")
    root=Path(directory)
    if not root.exists():
        root.mkdir(mode=0o700,parents=False)
    s=os.lstat(root)
    _need(stat.S_ISDIR(s.st_mode) and not stat.S_ISLNK(s.st_mode),
          "trusted directory without symlinks")
    if os.name!="nt":
        _need(s.st_uid==os.getuid() and s.st_mode & 0o077==0,
              "private current-user journal directory")
    db=root/"cognitum_lu_ipc01d_r1.sqlite3"
    if os.path.lexists(db):
        b=os.lstat(db)
        _need(stat.S_ISREG(b.st_mode) and not stat.S_ISLNK(b.st_mode),
              "refuse journal symlink/non-regular data")
        if os.name!="nt":
            _need(b.st_uid==os.getuid() and b.st_mode & 0o077==0,
                  "private journal data file")
    return db


def _initial_state():
    return dict(begin=False,credits=0,sequence=0,terminal=None,
                cancel_requested=False,cancel_ack=False,
                reconcile_requested=False,reconcile_status="not_requested",
                revoked=False,events=0,receipt_raw=None,
                original_session=None,origin=None,typed_sha=None,
                outbox_sha=None,outbox_count=0,uncertain_hold=False)


def _summarize(state):
    return dict(status=("revoked" if state["revoked"] else
             "uncertain_hold" if state["uncertain_hold"] else
             "reconciled_candidate" if state["reconcile_status"]=="matched" else
             "terminal_candidate" if state["terminal"] is not None else
             "cancel_signalled_not_terminated" if state["cancel_ack"] else
             "cancel_requested" if state["cancel_requested"] else "observing"),
         last_sequence=state["sequence"],remaining_credits=state["credits"],
         cancellation_requested=state["cancel_requested"],
         cancellation_signal_recorded=state["cancel_ack"],
         worker_termination_verified=False,
         original_terminal_observed=state["terminal"] is not None,
         reconciliation_status=state["reconcile_status"],
         outbox_snapshot_recorded=state["outbox_sha"] is not None,
         original_outbox_snapshot_sha256=state["outbox_sha"],
         original_outbox_output_count=state["outbox_count"],
         uncertain_hold=state["uncertain_hold"],
         retry_or_acknowledgment_authorized=False,
         source_verified_through_independent_lu_core=False,
         signed_core_receipt_verified=False,
         domain_execution_authorized=False,
         result_publication_authorized=False,
         new_effect_authorized=False)


class DurableLuOperationVerifier:
    """One exact original Lu operation, serialized and host-supervised.

    An operation is bound on creation to exact host-observed origin, Lu
    connection epoch, request ID and typed SSM candidate. Reopening requires
    the same identity plus an externally advanced MAC head; it never grants a
    new Core session after restart or converts UNKNOWN into APPLIED.
    """

    def __init__(self,directory,broker,anchor,*,trusted_origin,request_id,
                 core_session_ref,core_epoch_ref,prepared,original_invoke):
        self._lock=RLock()
        self._closed=False
        self._origin=_scope(trusted_origin)
        self._request_id=_text(request_id,"original request ID")
        self._session=_text(core_session_ref,"original authenticated Core session")
        self._epoch=_text(core_epoch_ref,"original Core epoch")
        _need(type(prepared) is ssm.SsmCandidate and
              not prepared.publication_authorized and
              not prepared.execution_authorized and
              prepared.original_operation_ref==self._origin[-1],
              "trusted preflighted SSM candidate required")
        self._prepared=prepared
        self._op=self._origin[-1]
        self._scope=self._origin
        wire=_strict(original_invoke,lu.CapabilityInvoke)
        _need(_scope(wire.origin)==self._origin and
              wire.capability_id==ssm.OPERATION and
              wire.capability_version==1 and wire.HasField("input") and
              wire.input.type_url==ssm.INPUT_URL and
              _digest(wire.input.encoded_message)==prepared.typed_request_sha256,
              "preflighted typed original Lu invoke identity")
        self._original=_digest(original_invoke)
        self._broker=broker
        self._anchor=anchor
        path=_secure_path(directory)
        try:
            db=sqlite3.connect(str(path),timeout=3,isolation_level=None)
            db.row_factory=sqlite3.Row
            db.execute("PRAGMA busy_timeout=3000")
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("CREATE TABLE IF NOT EXISTS journal ("
                       "seq INTEGER PRIMARY KEY, kind TEXT NOT NULL,"
                       "body BLOB NOT NULL, body_sha TEXT NOT NULL,"
                       "mac TEXT NOT NULL)")
            if os.name!="nt":
                os.chmod(path,0o600)
            self._db=db
            key=_key(broker,self._scope,self._op)
            self._db.execute("BEGIN IMMEDIATE")
            try:
                items,head=self._verified_items(key)
                trusted=_trust_read(anchor,self._scope,self._op)
                _need(trusted==(len(items),head),
                      "independent anchor disagrees with durable local chain")
                if items:
                    self._derive(items)
                    self._db.commit()
                else:
                    original=_canonical(dict(profile=PROFILE,
                        origin=list(self._origin),request_id=self._request_id,
                        core_session_ref=self._session,core_epoch_ref=self._epoch,
                        invoke_sha256=self._original,
                        typed_sha256=prepared.typed_request_sha256,
                        stream_id=prepared.stream_id,
                        prior_revision=prepared.expected_revision,
                        prior_checkpoint_sha256=prepared.prior_sha256.hex()))
                    self._commit_entry(key,"begin",original,0,ZERO)
            except BaseException:
                self._db.rollback()
                raise
        except BaseException:
            if "db" in locals():
                db.close()
            raise

    def _verified_items(self,key):
        rows=self._db.execute(
            "SELECT seq,kind,body,body_sha,mac FROM journal ORDER BY seq").fetchall()
        _need(len(rows)<=MAX_RECORDS,"bounded durable log")
        last=ZERO
        entries=[]
        for idx,row in enumerate(rows,1):
            kind=row["kind"];raw=row["body"]
            _need(row["seq"]==idx and kind in ACTIONS and
                  type(raw) is bytes and 0<len(raw)<=MAX_FRAME and
                  _digest(raw)==row["body_sha"],
                  "durable source log canonical bytes or sequence")
            expected=hmac.new(key,DOMAIN+bytes.fromhex(last)+
                              idx.to_bytes(4,"big")+kind.encode("ascii")+
                              b"\x00"+raw,hashlib.sha256).hexdigest()
            _need(hmac.compare_digest(row["mac"],expected),
                  "durable host-keyed log MAC mismatch")
            entries.append((kind,raw))
            last=expected
        return entries,last

    def _decode_frame(self,raw,body,*,stream_event=False):
        msg=_strict(raw,lu.WorkspaceFrame)
        _need(msg.protocol_major==1 and msg.protocol_minor==0 and
              msg.request_id==self._request_id and
              msg.session_ref==self._session and
              msg.WhichOneof("body")==body,
              "exact authenticated session/request/frame kind")
        _need(msg.sequence>0 if stream_event else msg.sequence==0,
              "event sequence kind")
        return msg

    def _derive(self,items):
        state=_initial_state()
        for kind,raw in items:
            _need(kind in ACTIONS,"unsupported durable action")
            if kind=="begin":
                _need(not state["begin"],"duplicated original operation")
                try:body=json.loads(raw.decode("ascii"))
                except (ValueError,UnicodeError) as exc:
                    raise ValueError("Cognitum IPC lifecycle refused: invalid begin") from exc
                _need(_canonical(body)==raw and
                      set(body)=={"profile","origin","request_id","core_session_ref",
                        "core_epoch_ref","invoke_sha256","typed_sha256","stream_id",
                        "prior_revision","prior_checkpoint_sha256"} and
                      body==dict(profile=PROFILE,origin=list(self._origin),
                        request_id=self._request_id,core_session_ref=self._session,
                        core_epoch_ref=self._epoch,invoke_sha256=self._original,
                        typed_sha256=self._prepared.typed_request_sha256,
                        stream_id=self._prepared.stream_id,
                        prior_revision=self._prepared.expected_revision,
                        prior_checkpoint_sha256=self._prepared.prior_sha256.hex()),
                      "original Lu session/typed invocation drift")
                state["begin"]=True
                continue
            _need(state["begin"],"action before begin")
            if kind=="credit":
                msg=self._decode_frame(raw,"stream_credit")
                d=msg.stream_credit
                _need(not state["revoked"] and state["terminal"] is None and
                      d.operation_ref==self._op and
                      d.acknowledged_sequence<=state["sequence"] and
                      1<=d.additional_events<=MAX_CREDIT and
                      state["credits"]+d.additional_events<=MAX_CREDIT,
                      "stream credit grant bounded by original operation")
                state["credits"]+=d.additional_events
            elif kind in ("progress","terminal"):
                msg=self._decode_frame(raw,"operation_event",stream_event=True)
                event=msg.operation_event
                _need(not state["revoked"] and state["terminal"] is None and
                      state["credits"]>0 and
                      msg.sequence==state["sequence"]+1 and
                      event.operation_ref==self._op and
                      event.WhichOneof("data")==kind,
                      "out-of-order, revoked, uncredited or mismatched event")
                state["credits"]-=1
                state["sequence"]=msg.sequence
                state["events"]+=1
                if kind=="progress":
                    _text(event.progress.stage_code,"bounded progress stage")
                    _need(not event.progress.HasField("percent") or
                          event.progress.percent<=100,
                          "progress percentage range")
                else:
                    terminal=event.terminal
                    _need(terminal.operation_ref==self._op and
                          terminal.state in TERMINAL and
                          not terminal.output_refs and
                          len(terminal.durable_receipt_sha256)==32 and
                          any(terminal.durable_receipt_sha256),
                          "reviewed terminal state and receipt locator")
                    if terminal.state==lu.TERMINAL_STATE_APPLIED:
                        _need(terminal.HasField("output") and
                              terminal.output.type_url==ssm.OUTPUT_URL and
                              not terminal.reason_code,
                              "applied SSM output type/reason")
                        candidate=ssm.inspect_result(
                             terminal.output.encoded_message,
                             prepared=self._prepared)
                        _need(candidate["status"] in ("committed","duplicate")
                              and not candidate["publication_authorized"],
                              "applied domain result did not match original")
                    else:
                        _need(not terminal.HasField("output") and
                              type(terminal.reason_code) is str and
                              REASON.fullmatch(terminal.reason_code) is not None,
                              "terminal refusal/cancel/uncertain must be output-free")
                    state["terminal"]=terminal.state
                    state["receipt_raw"]=terminal.SerializeToString(deterministic=True)
            elif kind=="cancel":
                msg=self._decode_frame(raw,"cancel")
                _need(not state["revoked"] and state["terminal"] is None and
                      not state["cancel_requested"] and
                      msg.cancel.operation_ref==self._op and
                      REASON.fullmatch(msg.cancel.reason_code) is not None,
                      "original cancel intent scope/reason")
                state["cancel_requested"]=True
            elif kind=="cancel_ack":
                msg=self._decode_frame(raw,"cancel_ack")
                _need(state["cancel_requested"] and
                      not state["cancel_ack"] and
                      msg.cancel_ack.operation_ref==self._op and
                      msg.cancel_ack.signal_recorded,
                      "cancellation signal receipt scope")
                # ACK is NOT worker termination, revocation, undo or success.
                state["cancel_ack"]=True
            elif kind=="reconcile":
                msg=self._decode_frame(raw,"reconcile")
                _need(msg.reconcile.operation_ref==self._op and
                      msg.reconcile.HasField("expected_origin") and
                      _scope(msg.reconcile.expected_origin)==self._origin and
                      not state["reconcile_requested"],
                      "original reconciliation identity or duplicate")
                state["reconcile_requested"]=True
            elif kind=="reconciled":
                msg=self._decode_frame(raw,"reconciled")
                observed=msg.reconciled.observed
                _need(state["reconcile_requested"] and
                      msg.reconciled.HasField("observed") and
                      observed.operation_ref==self._op,
                      "unrequested Core reconciliation")
                if msg.reconciled.evidence_available:
                    _need(state["terminal"] is not None and
                          observed.SerializeToString(deterministic=True)==
                          state["receipt_raw"],
                          "externally observed result differs from original terminal")
                    state["reconcile_status"]="matched"
                else:
                    _need(not observed.HasField("output") and
                          not observed.output_refs and
                          observed.state in (lu.TERMINAL_STATE_UNSPECIFIED,
                                             lu.TERMINAL_STATE_UNCERTAIN),
                          "missing evidence is not an applied event")
                    _need(state["reconcile_status"]!="matched",
                          "reconciliation must not downgrade verified candidate")
                    state["reconcile_status"]="unknown"
                state["reconcile_requested"]=False
            elif kind=="outbox_snapshot":
                try:snapshot=json.loads(raw.decode("ascii"))
                except (ValueError,UnicodeError) as exc:
                    raise ValueError("Cognitum IPC lifecycle refused: malformed outbox snapshot") from exc
                _need(type(snapshot) is dict and
                      set(snapshot)=={"schema","stream_id","event_id",
                                     "checkpoint_revision","checkpoint_sha256",
                                     "outputs"} and _canonical(snapshot)==raw and
                      snapshot["schema"]=="cognitum.lu_ipc01e_r1.original_outbox_snapshot.v1",
                      "strict source-only outbox inventory")
                _need(not state["revoked"] and not state["cancel_requested"]
                      and not state["uncertain_hold"] and
                      state["outbox_sha"] is None and
                      state["reconcile_status"]=="matched" and
                      state["terminal"]==lu.TERMINAL_STATE_APPLIED,
                      "reconciled, uncancelled, unrevoked original terminal required")
                terminal=lu.OperationReceipt.FromString(state["receipt_raw"])
                _need(terminal.HasField("output") and
                      terminal.output.type_url==ssm.OUTPUT_URL,
                      "original SSM result receipt")
                result=ssm_pb2.SsmAdvanceResult.FromString(
                    terminal.output.encoded_message)
                _need(result.disposition==ssm_pb2.ADVANCE_DISPOSITION_COMMITTED and
                      snapshot["stream_id"]==self._prepared.stream_id and
                      snapshot["event_id"]==self._op and
                      snapshot["checkpoint_revision"]==result.observed_revision and
                      snapshot["checkpoint_revision"]==self._prepared.expected_revision+1 and
                      snapshot["checkpoint_sha256"]==result.observed_checkpoint_sha256.hex() and
                      type(snapshot["outputs"]) is list and
                      len(snapshot["outputs"])==result.pending_release_count and
                      len(snapshot["outputs"])<=ssm.MAX_OUTPUTS,
                      "original committed revision and complete outbox count")
                seen=set()
                for row in snapshot["outputs"]:
                    _need(type(row) is dict and set(row)=={"output_id","body_sha256"} and
                          type(row["output_id"]) is str and
                          type(row["body_sha256"]) is str and
                          re.fullmatch(r"[0-9a-f]{64}",row["output_id"]) and
                          re.fullmatch(r"[0-9a-f]{64}",row["body_sha256"]) and
                          row["output_id"] not in seen,
                          "bounded uniquely identified outbox row")
                    seen.add(row["output_id"])
                _need(snapshot["outputs"]==sorted(snapshot["outputs"],key=lambda x:x["output_id"]),
                      "canonical sorted outbox inventory")
                state["outbox_sha"]=_digest(raw)
                state["outbox_count"]=len(snapshot["outputs"])
            elif kind=="uncertain_hold":
                try:hold=json.loads(raw.decode("ascii"))
                except (ValueError,UnicodeError) as exc:
                    raise ValueError("Cognitum IPC lifecycle refused: malformed uncertain hold") from exc
                _need(type(hold) is dict and set(hold)=={"reason"} and
                      _canonical(hold)==raw and
                      type(hold["reason"]) is str and
                      REASON.fullmatch(hold["reason"]) is not None and
                      not state["uncertain_hold"],
                      "one original uncertainty hold")
                state["uncertain_hold"]=True
            elif kind=="revoke":
                try:revoked=json.loads(raw.decode("ascii"))
                except (ValueError,UnicodeError) as exc:
                    raise ValueError("Cognitum IPC lifecycle refused: invalid revocation") from exc
                _need(_canonical(revoked)==raw and
                      type(revoked) is dict and set(revoked)=={"reason"} and
                      REASON.fullmatch(revoked["reason"]) is not None and
                      not state["revoked"],"host-side revocation intent")
                state["revoked"]=True
        _need(state["begin"],"initialized operation absent")
        return state

    def _commit_entry(self,key,kind,raw,count,last):
        _need(count<MAX_RECORDS,"bounded original operation trace")
        seq=count+1
        mac=hmac.new(key,DOMAIN+bytes.fromhex(last)+
                      seq.to_bytes(4,"big")+kind.encode("ascii")+
                      b"\x00"+raw,hashlib.sha256).hexdigest()
        self._db.execute("INSERT INTO journal VALUES (?,?,?,?,?)",
                          (seq,kind,raw,_digest(raw),mac))
        self._db.commit()
        # An OS interruption between commit and independent anchor advance
        # leaves UNCERTAIN state. No silent local self-repair / fallback.
        _need(self._anchor.advance(self._scope,self._op,count,last,seq,mac)
              is True,"independent anchor advancement unconfirmed")
        return mac

    def _append(self,kind,raw):
        _need(not self._closed,"closed operation observer")
        _need(kind in ACTIONS and kind!="begin" and
              type(raw) is bytes and 0<len(raw)<=MAX_FRAME,
              "closed bounded event/action")
        with self._lock:
            key=_key(self._broker,self._scope,self._op)
            self._db.execute("BEGIN IMMEDIATE")
            try:
                items,last=self._verified_items(key)
                _need(_trust_read(self._anchor,self._scope,self._op)==
                      (len(items),last),
                      "trusted revision floor absent/stale/replayed")
                state=self._derive(items)
                _need(not any(k==kind and b==raw for k,b in items),
                      "replayed completed signal; not an authority")
                self._derive(items+[(kind,raw)])
                return self._commit_entry(key,kind,raw,len(items),last)
            except BaseException:
                self._db.rollback()
                raise

    def _wrap(self,body,field,*,sequence=0):
        frame=lu.WorkspaceFrame(
            protocol_major=1,protocol_minor=0,
            request_id=self._request_id,
            session_ref=self._session,sequence=sequence)
        getattr(frame,field).CopyFrom(body)
        return frame.SerializeToString(deterministic=True)

    def note_credit(self, additional_events, acknowledged_sequence):
        _need(type(additional_events) is int and
              1<=additional_events<=MAX_CREDIT and
              type(acknowledged_sequence) is int and
              acknowledged_sequence>=0,"bounded host credit request")
        raw=self._wrap(lu.StreamCredit(
            operation_ref=self._op,
            additional_events=additional_events,
            acknowledged_sequence=acknowledged_sequence),"stream_credit")
        self._append("credit",raw)
        return self.status()

    def note_cancel(self, reason_code):
        _text(reason_code,"trusted cancellation reason",REASON)
        raw=self._wrap(lu.CancelOperation(
            operation_ref=self._op,reason_code=reason_code),"cancel")
        self._append("cancel",raw)
        return self.status()

    def note_reconcile_request(self):
        origin=lu.OriginRefs(
            workspace_ref=self._origin[0],
            conversation_ref=self._origin[1],
            user_turn_ref=self._origin[2],
            task_ref=self._origin[3],
            operation_ref=self._origin[4])
        raw=self._wrap(lu.ReconcileOperation(
            operation_ref=self._op,expected_origin=origin),"reconcile")
        self._append("reconcile",raw)
        return self.status()

    def note_revoke(self,reason_code):
        _text(reason_code,"independently authorized revocation reason",REASON)
        self._append("revoke",_canonical({"reason":reason_code}))
        return self.status()

    def note_outbox_snapshot(self, *, stream_id, event_id, revision,
                             checkpoint_sha256, outputs):
        """Persist one *unpublishable* originally observed R6 outbox inventory.

        A trusted host must independently call the R6 journal verifier and
        provide the resulting complete pending inventory. This method
        performs immutable source matching and one-time audit, NOT broker
        admission, user permission, actual delivery or acknowledgment.
        """
        _text(stream_id,"original outbox stream ID")
        _text(event_id,"original outbox event ID")
        _need(type(revision) is int and revision>=1,"bounded snapshot revision")
        _need(type(checkpoint_sha256) is str and
              re.fullmatch(r"[0-9a-f]{64}",checkpoint_sha256),
              "original R6 checkpoint digest")
        _need(type(outputs) is (list) and len(outputs)<=ssm.MAX_OUTPUTS,
              "bounded outbox inventory")
        rows=[]
        for item in outputs:
            _need(type(item) is dict and set(item)=={"output_id","body_sha256"},
                  "exact outbox row schema")
            rows.append(dict(item))
        rows.sort(key=lambda x:x["output_id"])
        raw=_canonical(dict(
            schema="cognitum.lu_ipc01e_r1.original_outbox_snapshot.v1",
            stream_id=stream_id,event_id=event_id,
            checkpoint_revision=revision,
            checkpoint_sha256=checkpoint_sha256,outputs=rows))
        self._append("outbox_snapshot",raw)
        return self.status()

    def note_uncertain_hold(self,reason_code):
        """Irreversibly record local uncertainty; never permit delivery."""
        _text(reason_code,"trusted uncertain outcome reason",REASON)
        self._append("uncertain_hold",_canonical({"reason":reason_code}))
        return self.status()

    def observe_frame(self,raw):
        """Record one original-session Lu event/ACK/reconciliation candidate.

        The caller must independently authenticate producer/OS peer and
        original Lu host session; this observer only verifies the byte-level
        operation trace against previously pinned trusted host data.
        """
        msg=_strict(raw,lu.WorkspaceFrame)
        field=msg.WhichOneof("body")
        if field=="operation_event":
            kind=msg.operation_event.WhichOneof("data")
            _need(kind in ("progress","terminal"),"unknown operation event")
        else:
            kind={"cancel_ack":"cancel_ack","reconciled":"reconciled"}.get(field)
        _need(kind is not None,"unsupported effect/event in observer")
        self._append(kind,raw)
        return self.status()

    def status(self):
        _need(not self._closed,"closed observer")
        with self._lock:
            key=_key(self._broker,self._scope,self._op)
            self._db.execute("BEGIN IMMEDIATE")
            try:
                entries,last=self._verified_items(key)
                _need(_trust_read(self._anchor,self._scope,self._op)==
                      (len(entries),last),"trusted anchor mismatch on read")
                state=self._derive(entries)
                result=dict(profile=PROFILE,operation_ref=self._op,
                            durable_local_revision=len(entries),
                            local_head_mac_sha256=last,**_summarize(state))
                self._db.commit()
                return result
            except BaseException:
                self._db.rollback()
                raise

    def close(self):
        with self._lock:
            if not self._closed:
                self._closed=True
                self._db.close()
