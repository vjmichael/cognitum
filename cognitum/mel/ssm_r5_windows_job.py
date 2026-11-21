"""R5 Windows CREATE_SUSPENDED + Job-before-resume fixed SSM calculation.

This is a Cognitum *native-source* host adapter. It is NOT an SCM service,
signed Windows installer, private-publisher verifier, AppContainer, or a Core
grant/receipt source. Only separately installed SCM ownership can qualify the
production service. The fixed Python entrypoint and interpreter need host
provided, separately trusted SHA256 pins; deriving those pins from an
untrusted IPC message or program stdout is forbidden.

Host creates sealed input before child birth and verifies untrusted numerical
reply only after kernel Job termination, wait, and empty accounting. A failure
never falls back to an uncontained multiprocessing worker.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from .lu_ipc_windows_job_probe import (
    _win_api, _image_sha, JOB_OBJECT_LIMIT_ACTIVE_PROCESS,
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, CREATE_SUSPENDED, CREATE_NO_WINDOW,
    WAIT_OBJECT_0, WAIT_TIMEOUT,
)
from .ssm_r4_protected import (
    NativeSSMCustodyRefused, _canonical, _need, _private_dir,
    MAX_OUTPUT, FRAME_LIMIT,
)

SCHEMA = "cognitum.mel.ssm_r5.windows_suspended_fixed_job.v1"
MAX_FRAME_FILE = max(FRAME_LIMIT, MAX_OUTPUT + 1024)


def _sha(value, label):
    _need(type(value) is str and len(value) == 64 and
          all(x in "0123456789abcdef" for x in value) and value != "0" * 64,
          label)
    return value


class WindowsSuspendedFixedSSMJob:
    """Run only the pinned Cognitum fixed-child script under a true native Job.

    Does not advertise installed SCM custody or externally signed stop proof.
    The owner must separately validate package signature, service account,
    installer ACLs and source immutability before accepting these host pins.
    """

    def __init__(self, *, installed_python_executable,
                 trusted_python_sha256, trusted_child_sha256,
                 host_private_directory):
        _need(sys.platform == "win32", "native Windows SSM Job only")
        self.exe = Path(installed_python_executable)
        self.script = Path(__file__).with_name("ssm_r5_fixed_child.py")
        self.exe_pin = _sha(trusted_python_sha256, "independent Python image pin")
        self.script_pin = _sha(trusted_child_sha256, "independent SSM child pin")
        self.root = _private_dir(host_private_directory)
        self.last_evidence = None
        self._pinned_images()

    def _pinned_images(self):
        _need(self.exe.is_absolute() and self.exe.name.lower() in
              ("python.exe", "pythonw.exe") and not self.exe.is_symlink(),
              "host selected bounded interpreter path")
        _need(self.script.is_file() and not self.script.is_symlink() and
              self.script.name == "ssm_r5_fixed_child.py",
              "fixed trusted child entrypoint")
        try:
            python_hash = _image_sha(str(self.exe))
            child_hash = hashlib.sha256(self.script.read_bytes()).hexdigest()
        except OSError as exc:
            raise NativeSSMCustodyRefused(
                "Cognitum native SSM R5 refused: pinned images inaccessible") from exc
        _need(python_hash == self.exe_pin and child_hash == self.script_pin,
              "independently pinned interpreter or SSM child mismatch")

    def run(self, request, timeout_ms):
        _need(sys.platform == "win32", "Windows kernel job required")
        _need(type(timeout_ms) is int and 100 <= timeout_ms <= 10000,
              "bounded fixed SSM deadline")
        _need(type(request) is bytes and 0 < len(request) <= FRAME_LIMIT,
              "fixed SSM frame budget")
        self._pinned_images()
        k, w, STARTUP, PROCESS, LIMIT, ACCOUNTING = _win_api()
        job = k.CreateJobObjectW(None, None)
        _need(bool(job), "native private Job unavailable")
        run_dir = None
        pi = PROCESS()
        process_created = False
        pid = 0
        started_in_job = False
        stopped = False
        succeeded = False
        answer = ("error", None)
        failure = None
        try:
            limits = LIMIT()
            limits.BasicLimitInformation.LimitFlags = (
                JOB_OBJECT_LIMIT_ACTIVE_PROCESS |
                JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)
            limits.BasicLimitInformation.ActiveProcessLimit = 1
            _need(bool(k.SetInformationJobObject(
                job, 9, ctypes.byref(limits), ctypes.sizeof(limits))),
                "kernel Job kill-on-close configuration")
            run_dir = Path(tempfile.mkdtemp(prefix="r5-ssm-", dir=self.root))
            input_path = run_dir / "input.frame"
            output_path = run_dir / "output.frame"
            fd = os.open(input_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as out:
                out.write(request)
                out.flush()
                os.fsync(out.fileno())
            args = [str(self.exe), "-I", "-B", str(self.script),
                    str(input_path), str(output_path)]
            si = STARTUP()
            si.cb = ctypes.sizeof(si)
            command = ctypes.create_unicode_buffer(subprocess.list2cmdline(args))
            _need(bool(k.CreateProcessW(
                str(self.exe), command, None, None, False,
                CREATE_SUSPENDED | CREATE_NO_WINDOW, None, str(self.root),
                ctypes.byref(si), ctypes.byref(pi))),
                "CREATE_SUSPENDED fixed worker refused")
            process_created = True
            pid = int(pi.dwProcessId)
            _need(pid > 0 and bool(k.AssignProcessToJobObject(job, pi.hProcess)),
                  "Job ownership before first instruction")
            membership = w.BOOL()
            _need(bool(k.IsProcessInJob(
                pi.hProcess, job, ctypes.byref(membership))) and
                membership.value, "kernel Job membership before first instruction")
            started_in_job = True
            _need(k.ResumeThread(pi.hThread) != 0xFFFFFFFF,
                  "Windows fixed worker release refused")
            wait = k.WaitForSingleObject(pi.hProcess, timeout_ms)
            if wait == WAIT_TIMEOUT:
                answer = ("timed_out", None)
            else:
                _need(wait == WAIT_OBJECT_0, "kernel wait result")
                code = w.DWORD()
                _need(bool(k.GetExitCodeProcess(pi.hProcess, ctypes.byref(code))) and
                      code.value == 0, "fixed worker nonzero exit")
                _need(output_path.is_file() and not output_path.is_symlink(),
                      "fixed child output unavailable")
                raw = output_path.read_bytes()
                _need(0 < len(raw) <= MAX_FRAME_FILE, "bounded child output bytes")
                def unique(pairs):
                    out = {}
                    for name, val in pairs:
                        _need(name not in out, "duplicate child output field")
                        out[name] = val
                    return out
                item = json.loads(
                    raw, object_pairs_hook=unique,
                    parse_constant=lambda _: (_ for _ in ()).throw(
                        ValueError("nonfinite child output")))
                _need(type(item) is dict and
                      set(item) == {"status", "reply"} and
                      item["status"] == "ok" and type(item["reply"]) is dict,
                      "fixed child response schema")
                answer = ("ok", item["reply"])
                succeeded = True
        except BaseException as exc:
            failure = exc
        finally:
            # Kernel Job cleanup precedes admitting ANY numerical candidate.
            if job:
                k.TerminateJobObject(job, 0xEE)
            if process_created:
                waited = k.WaitForSingleObject(pi.hProcess, 5000)
                if waited == WAIT_OBJECT_0 and job:
                    until = time.monotonic() + 2
                    while time.monotonic() < until:
                        accounting = ACCOUNTING()
                        if (k.QueryInformationJobObject(
                                job, 1, ctypes.byref(accounting),
                                ctypes.sizeof(accounting), None) and
                                accounting.ActiveProcesses == 0):
                            stopped = True
                            break
                        time.sleep(.02)
                if pi.hThread:
                    k.CloseHandle(pi.hThread)
                if pi.hProcess:
                    k.CloseHandle(pi.hProcess)
            if job:
                k.CloseHandle(job)
            if run_dir is not None:
                # A forced power loss before this step leaves the R4 durable
                # original operation UNCERTAIN and requires host cleanup.
                shutil.rmtree(run_dir, ignore_errors=True)
        _need(stopped or not process_created,
              "independent kernel termination remains uncertain")
        if failure is not None:
            if isinstance(failure, NativeSSMCustodyRefused):
                raise failure
            raise NativeSSMCustodyRefused(
                "Cognitum native SSM R5 refused: fixed worker exception") from failure
        _need(started_in_job and stopped,
              "complete assigned-before-resume Job ownership")
        self.last_evidence = {
            "schema": SCHEMA,
            "native_suspended_before_job_assignment": True,
            "kernel_job_assigned_before_resume": True,
            "worker_pid": pid,
            "kernel_job_empty_after_termination": stopped,
            "numeric_child_response_valid": succeeded,
            "installed_scm_service_verified": False,
            "external_signed_stop_receipt_verified": False,
            "core_grant_authorized": False,
            "outbox_delivery_authorized": False,
        }
        return (*answer, pid, stopped)
