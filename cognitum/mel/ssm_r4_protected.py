"""R4 fixed SSM pure math behind native Windows Job / Linux delegated cgroup.

This is the existing R6 SSMComputeFactory, NOT a new tool/runtime/issuer.
One preapproved local MEL event at a time. Worker starts blocked on a
private one-use Pipe; host verifies actual kernel containment before sending
the unkeyed numerical state. A durable write-once host HMAC prelaunch claim
binds original Lu OriginRefs, MEL Scope, stream and event. Restart with an
unfinished claim is UNCERTAIN: never blindly re-execute or release a result.

These OS mechanics do not establish a signed Cognitum installer, Core grant,
OS sandbox, independent rollback-resistant stop attestation, production
publisher credentials or delivered output. Do not promote to PASS_INSTALLED.
"""
from __future__ import annotations

import ctypes
import hashlib
import hmac
import json
import multiprocessing as mp
import os
from pathlib import Path
import secrets
import stat
import sys
import time

from . import admission as mel
from . import lu_ssm_contract as typed
from .ssm_os_credentials import OSCredentialBroker
from .ssm_supervisor import SSMComputeFactory, OP, MAX_WIRE, MAX_OUTPUT

SCHEMA = "cognitum.mel.ssm_r4.native_operation_custody.v1"
DOMAIN = b"Cognitum.MEL.SSM.R4.OS_BOUND_LAUNCH.v1\x00"
FRAME_LIMIT = MAX_WIRE + 1024
MAX_RECORD = 4096


class NativeSSMCustodyRefused(ValueError):
    """No protected SSM computation or original result may be published."""


def _need(ok, why):
    if not ok:
        raise NativeSSMCustodyRefused("Cognitum protected SSM refused: " + why)


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _private_dir(path):
    p = Path(path)
    _need(p.is_absolute() and not p.is_symlink() and p.is_dir(),
          "pre-created absolute trusted launch directory")
    info = os.stat(p)
    if os.name == "posix":
        _need(info.st_uid == os.geteuid() and info.st_mode & 0o077 == 0,
              "private owner-only durable launch directory")
    return p


def _write_once(root, name, record):
    data = _canonical(record) + b"\n"
    _need(len(data) <= MAX_RECORD, "bounded immutable worker record")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(root / name, flags, 0o600)
    except FileExistsError as exc:
        raise NativeSSMCustodyRefused(
            "Cognitum protected SSM refused: duplicate or uncertain launch") from exc
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if os.name == "posix":
            directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    except BaseException:
        # NEVER unlink a partially written prelaunch record. On restart
        # recovery sees it and holds the operation as uncertain.
        raise


def _read_record(path):
    _need(not path.is_symlink(), "symlinked worker receipt")
    raw = path.read_bytes()
    _need(0 < len(raw) <= MAX_RECORD, "record size")
    def unique(pairs):
        d = {}
        for key, value in pairs:
            _need(key not in d, "duplicate durable record field")
            d[key] = value
        return d
    result = json.loads(raw, object_pairs_hook=unique,
                        parse_constant=lambda _: _need(False, "nonfinite record"))
    _need(type(result) is dict, "record shape")
    return result


def _fixed_child(channel):
    """Spawned trusted fixed target; never executes before OS attachment."""
    try:
        raw = channel.recv_bytes(FRAME_LIMIT)
        request = json.loads(raw)
        if (type(request) is not dict or set(request) != {"operation", "payload"}
                or request["operation"] != OP or type(request["payload"]) is not dict):
            raise ValueError("closed SSM worker command")
        reply = SSMComputeFactory().handle(OP, request["payload"])
        response = _canonical({"status": "ok", "reply": reply})
        if len(response) > MAX_OUTPUT + 1024:
            raise ValueError("bounded SSM worker reply")
        channel.send_bytes(response)
    except BaseException:
        try:
            channel.send_bytes(b'{"status":"error","reply":null}')
        except (OSError, EOFError, BrokenPipeError):
            pass
    finally:
        channel.close()


class DurableOriginalWorkerClaim:
    """Local HMAC write-once evidence, not an independent antirollback anchor.

    The OS key is borrowed in the parent, never passed to worker. File
    replacement/rollback by privileged attacker remains an installed blocker.
    """

    def __init__(self, directory, broker, scope, original, event_id, stream_id):
        _need(type(broker) is OSCredentialBroker, "genuine OS key provider")
        _need(type(scope) is mel.Scope, "trusted MEL scope")
        self.origin = typed._origin(original)
        _need(self.origin[0] == scope.workspace and
              self.origin[2] == scope.turn and
              scope.session and scope.session != "untrusted",
              "exact original Lu user-turn MEL identity")
        _need(type(event_id) is str and
              typed.IDENTIFIER.fullmatch(event_id) is not None and
              type(stream_id) is str and
              typed.IDENTIFIER.fullmatch(stream_id) is not None,
              "exact bounded SSM event/stream binding")
        self._root = _private_dir(directory)
        self._broker = broker
        self._scope = scope
        self._event = event_id
        self._stream = stream_id
        self._operation = self.origin[-1]
        self._tuple = [*self.origin, scope.session, scope.subject, stream_id, event_id]
        self._identity = hashlib.sha256(
            DOMAIN + _canonical(self._tuple)).hexdigest()
        self._pending = self._root / ("ssm-r4-pending-" + self._identity + ".json")
        self._stopped = self._root / ("ssm-r4-stopped-" + self._identity + ".json")

    def _key(self):
        from cognitum.research.ssm_stochastic_checkpoints import _auth_key
        return _auth_key(self._broker.borrow_key(self._scope, self._operation))

    def _signed(self, body):
        key = self._key()
        message = _canonical(body)
        return dict(body=body, hmac_sha256=hmac.new(
            key, DOMAIN + message, hashlib.sha256).hexdigest())

    def _verify(self, record):
        _need(type(record) is dict and set(record) == {"body", "hmac_sha256"},
              "complete original durable record")
        verified = self._signed(record["body"])
        _need(hmac.compare_digest(verified["hmac_sha256"],
                                  record["hmac_sha256"]),
              "durable record HMAC")
        return record["body"]

    def before_worker(self, request_sha):
        _need(type(request_sha) is str and len(request_sha) == 64 and
              all(c in "0123456789abcdef" for c in request_sha),
              "exact request SHA")
        _need(not self._pending.exists() and not self._stopped.exists(),
              "reused original operation or uncertain restart")
        body = {
            "schema": SCHEMA, "identity": self._identity,
            "original": self._tuple, "request_sha256": request_sha,
            "nonce": secrets.token_hex(16), "phase": "PRELAUNCH",
            "installed_authority": False,
        }
        _write_once(self._root, self._pending.name, self._signed(body))
        return body["nonce"]

    def after_kernel_stop(self, nonce, request_sha, *, verified, mechanism,
                          kernel_worker_pid):
        _need(verified is True and mechanism in ("windows_job", "linux_cgroup2") and
              type(kernel_worker_pid) is int and kernel_worker_pid > 0,
              "native kernel stop must be actually observed")
        pending = self._verify(_read_record(self._pending))
        _need(pending.get("identity") == self._identity and
              pending.get("request_sha256") == request_sha and
              pending.get("nonce") == nonce and
              pending.get("phase") == "PRELAUNCH",
              "original durable prelaunch binding mismatch")
        stopped = {
            "schema": SCHEMA, "identity": self._identity, "nonce": nonce,
            "request_sha256": request_sha, "phase": "KERNEL_STOP_OBSERVED",
            "mechanism": mechanism, "worker_pid": kernel_worker_pid,
            "installed_authority": False, "independent_stop_receipt": False,
        }
        _write_once(self._root, self._stopped.name, self._signed(stopped))

    def restart_assessment(self):
        if not self._pending.exists():
            _need(not self._stopped.exists(), "stop without prelaunch")
            return "NOT_STARTED"
        record = self._verify(_read_record(self._pending))
        _need(record.get("identity") == self._identity and
              record.get("original") == self._tuple and
              record.get("phase") == "PRELAUNCH",
              "foreign prelaunch record")
        if not self._stopped.exists():
            return "UNCERTAIN_REQUIRES_INDEPENDENT_STOP_RECONCILIATION"
        stop = self._verify(_read_record(self._stopped))
        _need(stop.get("identity") == self._identity and
              stop.get("request_sha256") == record.get("request_sha256") and
              stop.get("nonce") == record.get("nonce") and
              stop.get("phase") == "KERNEL_STOP_OBSERVED" and
              stop.get("installed_authority") is False and
              stop.get("independent_stop_receipt") is False,
              "contradictory local kernel-stop observation")
        # A local stop record does not authorize reexecution or output release.
        return "STOP_LOCALLY_OBSERVED_REPLAY_STILL_DENIED"


class ProtectedFixedSSMExecutor:
    """One fixed original operation only, under real local kernel process custody.

    This intentionally does not supply a production Core grant or register a
    Lu workspace capability. It must be injected by the already trusted MEL
    host, never offered to a user/model as a runnable endpoint.
    """

    def __init__(self, *, original, mel_scope, expected_stream_id,
                 expected_event_id, credential_broker, durable_directory,
                 delegated_cgroup_root=None):
        self.claim = DurableOriginalWorkerClaim(
            durable_directory, credential_broker, mel_scope, original,
            expected_event_id, expected_stream_id)
        self._scope = mel_scope
        self._stream = expected_stream_id
        self._event = expected_event_id
        self._delegated = delegated_cgroup_root
        self._attempted = False
        self.last_evidence = None

    def execute(self, factory, operation, payload, timeout_ms, *,
                scope, stream_id, event_id):
        _need(factory is SSMComputeFactory and operation == OP,
              "fixed reviewed SSM numerical factory only")
        _need(scope is self._scope and type(scope) is mel.Scope and
              stream_id == self._stream and event_id == self._event,
              "foreign original MEL operation/stream/event identity")
        _need(not self._attempted, "one-use original event already attempted")
        _need(type(timeout_ms) is int and 100 <= timeout_ms <= 10000,
              "bounded worker timeout")
        self._attempted = True
        request = _canonical({"operation": OP, "payload": payload})
        _need(len(request) <= FRAME_LIMIT, "bounded pure numerical work")
        digest = hashlib.sha256(request).hexdigest()
        nonce = self.claim.before_worker(digest)
        status, reply = "error", None
        pid = 0
        verified = False
        if sys.platform == "win32":
            status, reply, pid, verified = self._windows(request, timeout_ms)
            mechanism = "windows_job"
        elif sys.platform.startswith("linux"):
            status, reply, pid, verified = self._linux(request, timeout_ms)
            mechanism = "linux_cgroup2"
        else:
            raise NativeSSMCustodyRefused("unsupported protected worker OS")
        _need(verified, "no independently observed native kernel stop")
        self.claim.after_kernel_stop(nonce, digest, verified=verified,
                                     mechanism=mechanism, kernel_worker_pid=pid)
        self.last_evidence = {
            "original_operation_bound": True,
            "fixed_ssm_math_under_native_kernel_custody": True,
            "native_stop_locally_observed": True,
            "installed_core_grant_verified": False,
            "independent_signed_executor_stop_receipt": False,
            "installed_production_service_verified": False,
            "output_delivery_authorized": False,
            "model_tool_execution_authorized": False,
        }
        return status, reply

    def _windows(self, request, timeout_ms):
        from .lu_ipc_windows_job_probe import (
            _win_api, JOB_OBJECT_LIMIT_ACTIVE_PROCESS,
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, WAIT_OBJECT_0,
        )
        k, w, _, _, LIMIT, ACCOUNTING = _win_api()
        job = k.CreateJobObjectW(None, None)
        _need(bool(job), "Windows CreateJobObjectW")
        ctx = mp.get_context("spawn")
        parent, child = ctx.Pipe(duplex=True)
        process = ctx.Process(target=_fixed_child, args=(child,), daemon=True)
        pid = 0
        kernel_empty = False
        result = ("error", None)
        try:
            limits = LIMIT()
            limits.BasicLimitInformation.LimitFlags = (
                JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE |
                JOB_OBJECT_LIMIT_ACTIVE_PROCESS)
            limits.BasicLimitInformation.ActiveProcessLimit = 1
            _need(bool(k.SetInformationJobObject(job, 9, ctypes.byref(limits),
                                                ctypes.sizeof(limits))),
                  "Windows Job limits")
            process.start()
            child.close()
            pid = process.pid
            # Fixed child cannot perform numerical math before parent sends
            # the only request frame. On an assignment failure, no release.
            _need(bool(k.AssignProcessToJobObject(job, process.sentinel)),
                  "Windows worker Job attach before numerical release")
            member = w.BOOL()
            _need(bool(k.IsProcessInJob(process.sentinel, job,
                                        ctypes.byref(member))) and member.value,
                  "Windows OS Job membership")
            parent.send_bytes(request)
            if parent.poll(timeout_ms / 1000):
                raw = parent.recv_bytes(MAX_OUTPUT + 1024)
                msg = json.loads(raw)
                _need(type(msg) is dict and set(msg) == {"status", "reply"} and
                      msg["status"] in ("ok", "error"),
                      "closed worker response")
                result = (msg["status"], msg["reply"])
            else:
                result = ("timed_out", None)
        except (OSError, EOFError, ValueError, RuntimeError):
            result = ("error", None)
        finally:
            # Killing the whole Job is required EVEN IF the response arrived.
            try:
                k.TerminateJobObject(job, 0xEE)
                if pid:
                    process.join(5)
                    kernel_empty = not process.is_alive()
                    if kernel_empty:
                        acc = ACCOUNTING()
                        kernel_empty = bool(k.QueryInformationJobObject(
                            job, 1, ctypes.byref(acc), ctypes.sizeof(acc),
                            None)) and acc.ActiveProcesses == 0
            finally:
                if pid and process.is_alive():
                    process.kill()
                    process.join(3)
                if pid:
                    process.close()
                parent.close()
                child.close()
                k.CloseHandle(job)
        return (*result, pid, kernel_empty)

    def _linux(self, request, timeout_ms):
        _need(type(self._delegated) is str and
              self._delegated.startswith("/"),
              "independently delegated Linux cgroup-v2 root required")
        from cognitum.cgroup2_contract import FixtureCgroupScope, ContainmentUnavailable
        from cognitum.cgroup2_fixed_runner import _birth_ticks, _require_same_attached_worker
        from cognitum.host_survivor_arm import arm_watchkeeper
        from cognitum.host_recovery import (
            record_before_worker_release, mark_closed_after_verified_cleanup,
        )
        root = _private_dir(self.claim._root)
        scope = FixtureCgroupScope(self._delegated)
        # No worker exists unless the kernel has admitted a real cgroup scope.
        scope.create()
        watcher = None
        ctx = mp.get_context("spawn")
        parent, child = ctx.Pipe(duplex=True)
        process = ctx.Process(target=_fixed_child, args=(child,), daemon=True)
        pidfd = None
        pid = 0
        kernel_empty = False
        watched = False
        status, reply = "error", None
        try:
            watcher = arm_watchkeeper(scope.path, evidence_dir=root)
            record_before_worker_release(
                root, scope.root, scope.path,
                watcher.jobid, os.getpid(), watcher.proc.pid)
            process.start()
            child.close()
            pid = process.pid
            pidfd = os.pidfd_open(pid)
            born = _birth_ticks(pid)
            scope.attach_before_release(pid)
            _require_same_attached_worker(process, pidfd, born, scope)
            _need(watcher.proc.poll() is None,
                  "Linux watchkeeper died before numerical release")
            parent.send_bytes(request)
            if parent.poll(timeout_ms / 1000):
                msg = json.loads(parent.recv_bytes(MAX_OUTPUT + 1024))
                _need(type(msg) is dict and set(msg) == {"status", "reply"} and
                      msg["status"] in ("ok", "error"),
                      "closed worker reply")
                status, reply = msg["status"], msg["reply"]
            else:
                status, reply = "timed_out", None
        except (OSError, EOFError, ValueError, RuntimeError, ContainmentUnavailable):
            status, reply = "error", None
        finally:
            if watcher is not None:
                watcher.close_lease()
                try:
                    watcher.await_cleanup(timeout=8.0)
                    watched = True
                except BaseException:
                    watched = False
            if scope.path is not None:
                if not watched:
                    try:
                        scope.kill_and_verify_empty(timeout=3)
                    except BaseException:
                        pass
                if watched:
                    try:
                        scope.remove_empty()
                        kernel_empty = scope.path is None
                    except OSError:
                        kernel_empty = False
            if pid:
                process.join(3)
                if process.is_alive():
                    process.kill()
                    process.join(3)
                kernel_empty = kernel_empty and not process.is_alive()
                process.close()
            if pidfd is not None:
                os.close(pidfd)
            parent.close()
            child.close()
            if watched and kernel_empty:
                mark_closed_after_verified_cleanup(root, watcher.jobid)
        return status, reply, pid, bool(watched and kernel_empty)
